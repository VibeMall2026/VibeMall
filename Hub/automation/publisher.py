"""
Publisher
=========

Converts an approved ``ProductDraft`` into live catalogue rows.

Everything happens in **one transaction**. If any step fails — a bad image, a
SKU collision, a variant write — nothing is committed and the draft stays
pending. That is the "no partial products" guarantee.

What gets written
-----------------

``Product``
    Core listing. ``price`` is the selling price, ``old_price`` the MRP, and
    ``discount_percent`` is computed with the project's existing
    ``calc_discount_percent`` helper so automated products discount exactly
    like manually-added ones.

``ProductImage``
    One row per staged image, carrying the role and colour the vision pass
    assigned. This is the *existing* structure the manual Add Product page
    already writes, so the storefront needs no changes.

``ProductVariant``
    One COLOR row per detected colourway and one SIZE row per size. Stock is
    divided evenly across colourways; the admin can adjust afterwards.

``ProductSEO``
    Meta title/description/keywords plus Open Graph and Twitter fields.

Attributes with no ``Product`` column (fabric, sleeve type, occasion, work
type...) are folded into the fields that do exist — a specification block
appended to ``description``, fabric and wash-care into ``care_info``, and the
distinctive values into ``tags`` — while remaining available verbatim in
``ProductDraft.parsed``.
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .ai.schema import EXTENDED_ATTRIBUTE_FIELDS
from .images import cropped_bytes

logger = logging.getLogger(__name__)


def staged_file(staged: Any) -> ContentFile:
    """
    Read a staged image, applying the admin's bottom crop if one is set.

    The crop is stored as intent on the draft rather than burned into the
    staged file, so it stays adjustable until approval. This is where it
    actually gets applied.
    """
    if staged.crop_bottom_px:
        try:
            payload = cropped_bytes(staged.image.path, staged.crop_bottom_px)
        except (ValueError, OSError):
            payload = None
        if payload:
            return ContentFile(payload)
        logger.warning(
            '[publish] Crop of %dpx could not be applied to draft image %s; using the original.',
            staged.crop_bottom_px, staged.pk,
        )

    # Read and close explicitly. On Windows an open handle blocks the file from
    # being deleted, which would break "delete draft" straight after publishing.
    try:
        staged.image.open('rb')
        return ContentFile(staged.image.read())
    finally:
        staged.image.close()


class PublishError(RuntimeError):
    """Raised when a draft cannot be turned into a product."""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError, AttributeError):
        return default
    return result if result > 0 else default


def _unique_sku(candidate: str) -> str | None:
    """
    Make a SKU unique, mirroring the manual Add Product page's behaviour.

    ``Product.sku`` is unique-but-nullable, so an empty SKU must become
    ``None`` rather than ``''`` — several blank strings would collide.
    """
    from Hub.models import Product

    cleaned = (candidate or '').strip()
    if not cleaned:
        return None

    unique = cleaned[:100]
    counter = 1
    while Product.objects.filter(sku=unique).exists():
        suffix = f'-{counter}'
        unique = f'{cleaned[:100 - len(suffix)]}{suffix}'
        counter += 1
    return unique


def _label(field: str) -> str:
    return field.replace('_', ' ').title()


def build_description(record: dict[str, Any]) -> str:
    """
    Build the product description as **plain text**.

    The storefront renders it with ``{{ product.description|linebreaks }}``,
    which escapes HTML — so markup here would be shown to shoppers as literal
    ``<p>`` and ``<li>`` tags. Plain text with blank lines is what that filter
    expects, and it matches what the manual Add Product page produces.

    The specification list is deliberately *not* repeated here: those
    attributes go into ``care_info``, which the product page already renders in
    its own panel. Duplicating them would show every spec twice.
    """
    parts: list[str] = []

    body = str(record.get('description') or '').strip()
    if body:
        parts.append(body)

    highlights = [str(h).strip() for h in (record.get('highlights') or []) if str(h).strip()]
    if highlights:
        bullets = '\n'.join(f'• {h}' for h in highlights[:8])
        parts.append(f'Key Highlights\n{bullets}')

    return '\n\n'.join(parts)


#: Order attributes are presented in on the product page. Fabrics first, then
#: construction, then care and pack details — how a shopper reads a spec sheet.
CARE_INFO_FIELD_ORDER = [
    'product_type', 'fabric', 'material',
    'top_fabric', 'bottom_fabric', 'dupatta_fabric', 'inner_fabric',
    'sleeve_type', 'neck_type', 'length', 'pattern', 'work_type',
    'style', 'fit', 'stitch_type', 'occasion',
    'wash_care', 'package_contents', 'country_of_origin',
]


def build_care_info(record: dict[str, Any]) -> str:
    """
    Every extracted attribute, as the pipe-separated spec line the product
    page already renders.

    This is where attributes with no ``Product`` column live. It carries the
    full set — including sleeve type, neck type, occasion and fit — because the
    description is plain text and no longer repeats them.
    """
    seen: list[str] = []
    parts: list[str] = []

    for field in CARE_INFO_FIELD_ORDER + EXTENDED_ATTRIBUTE_FIELDS:
        if field in seen:
            continue
        seen.append(field)
        value = str(record.get(field) or '').strip()
        if value:
            parts.append(f'{_label(field)}: {value}')

    return ' | '.join(parts)[:5000]


def build_tags(record: dict[str, Any]) -> str:
    """Comma-separated tags, capped to the column's 200 characters."""
    candidates: list[str] = []
    for tag in record.get('tags') or []:
        candidates.append(str(tag).strip())
    for field in ('product_type', 'fabric', 'occasion', 'work_type', 'pattern', 'style'):
        value = str(record.get(field) or '').strip()
        if value:
            candidates.append(value)

    seen: list[str] = []
    for tag in candidates:
        if tag and tag.lower() not in {s.lower() for s in seen}:
            seen.append(tag)

    result = ''
    for tag in seen:
        candidate = f'{result}, {tag}' if result else tag
        if len(candidate) > 200:
            break
        result = candidate
    return result


# --------------------------------------------------------------------------
# Variants
# --------------------------------------------------------------------------

#: Retail colour names -> hex, for the variant swatch. Unknown colours simply
#: get no swatch rather than a wrong one.
COLOR_HEX = {
    'red': '#E53935', 'maroon': '#800000', 'wine': '#722F37', 'rust': '#B7410E',
    'pink': '#FF69B4', 'rani pink': '#E3006D', 'baby pink': '#F4C2C2', 'magenta': '#C2185B',
    'peach': '#FFDAB9', 'orange': '#FB8C00', 'mustard': '#FFDB58', 'yellow': '#FDD835',
    'green': '#43A047', 'olive': '#808000', 'mint': '#98FF98', 'dark green': '#006400',
    'bottle green': '#006A4E', 'teal': '#008080', 'turquoise': '#40E0D0',
    'blue': '#1E88E5', 'navy blue': '#000080', 'navy': '#000080', 'sky blue': '#87CEEB',
    'royal blue': '#4169E1', 'purple': '#8E24AA', 'lavender': '#E6E6FA', 'mauve': '#E0B0FF',
    'black': '#000000', 'white': '#FFFFFF', 'off white': '#FAF9F6', 'cream': '#FFFDD0',
    'grey': '#9E9E9E', 'gray': '#9E9E9E', 'brown': '#795548', 'beige': '#F5F5DC',
    'gold': '#D4AF37', 'golden': '#D4AF37', 'silver': '#C0C0C0', 'coral': '#FF7F50',
}


def _color_hex(name: str) -> str:
    return COLOR_HEX.get((name or '').strip().lower(), '')


def create_variants(product: Any, record: dict[str, Any], images: list[Any]) -> int:
    """
    Create COLOR and SIZE variants for a published product.

    ``ProductVariant`` links by plain ``product_id`` integer rather than a
    ForeignKey, which is how the existing model is defined — respected here
    rather than changed, so nothing else in the project breaks.
    """
    from Hub.models import ProductVariant

    colors = [str(c).strip() for c in (record.get('colors') or []) if str(c).strip()]
    sizes = [str(s).strip() for s in (record.get('sizes') or []) if str(s).strip()]

    # Colours confirmed by the images take priority over colours only mentioned
    # in text, because those are the ones we actually have photos for.
    image_colors: list[str] = []
    for image in images:
        if image.color and image.color not in image_colors:
            image_colors.append(image.color)
    for color in image_colors:
        if color.lower() not in {c.lower() for c in colors}:
            colors.append(color)

    total_stock = product.stock or 0
    created = 0
    variants: list[ProductVariant] = []

    if colors:
        per_color = total_stock // len(colors)
        remainder = total_stock % len(colors)
        for index, color in enumerate(colors):
            variants.append(
                ProductVariant(
                    product_id=product.id,
                    variant_type='COLOR',
                    name=color[:100],
                    display_name=color[:100],
                    value=color[:100],
                    stock_quantity=per_color + (1 if index < remainder else 0),
                    sku_suffix=slugify(color)[:20].upper(),
                    color_hex=_color_hex(color),
                    sort_order=index,
                    is_active=True,
                )
            )

    if sizes:
        per_size = total_stock // len(sizes) if not colors else 0
        for index, size in enumerate(sizes):
            variants.append(
                ProductVariant(
                    product_id=product.id,
                    variant_type='SIZE',
                    name=size[:100],
                    display_name=size[:100],
                    value=size[:100],
                    stock_quantity=per_size,
                    sku_suffix=slugify(size)[:20].upper(),
                    sort_order=index,
                    is_active=True,
                )
            )

    if variants:
        ProductVariant.objects.bulk_create(variants)
        created = len(variants)

    return created


def create_reels(product: Any, draft: Any, user: Any) -> int:
    """
    Turn staged videos into ``Reel`` rows linked to the product.

    Uses the project's existing Reel model — the same one the manual Add
    Product page writes — so watch-and-shop, the homepage carousel and the
    reel admin all work unchanged.

    ``Reel.created_by`` is a non-nullable CASCADE FK, so a reel can only be
    created when an approving user is known; without one the videos stay on
    the draft rather than blocking the product.
    """
    from Hub.models import Reel

    videos = [v for v in draft.videos.all().order_by('order', 'id') if v.create_reel]
    if not videos:
        return 0

    if user is None:
        logger.warning(
            '[publish] Draft %s has %d video(s) but no approving user; skipping reels.',
            draft.pk, len(videos),
        )
        return 0

    created = 0
    for index, staged in enumerate(videos):
        reel = Reel(
            title=(staged.title or product.name)[:200],
            description='',
            product=product,
            duration=staged.duration or 0,
            order=index,
            is_published=staged.publish_reel,
            is_processing=False,
            created_by=user,
        )
        staged.video.open('rb')
        try:
            reel.video_file.save(
                os.path.basename(staged.video.name), ContentFile(staged.video.read()), save=False
            )
        finally:
            staged.video.close()

        if staged.thumbnail:
            staged.thumbnail.open('rb')
            try:
                reel.thumbnail.save(
                    os.path.basename(staged.thumbnail.name),
                    ContentFile(staged.thumbnail.read()),
                    save=False,
                )
            finally:
                staged.thumbnail.close()

        reel.save()
        created += 1

    return created


def create_seo(product: Any, record: dict[str, Any]) -> None:
    """Write the ``ProductSEO`` row (also linked by plain ``product_id``)."""
    from Hub.models import ProductSEO

    keywords = [str(k).strip() for k in (record.get('meta_keywords') or []) if str(k).strip()]
    meta_title = (record.get('meta_title') or product.name)[:60]
    meta_description = (record.get('meta_description') or record.get('short_description') or '')[:160]

    ProductSEO.objects.update_or_create(
        product_id=product.id,
        defaults={
            'meta_title': meta_title,
            'meta_description': meta_description,
            'meta_keywords': ', '.join(keywords)[:2000],
            'custom_slug': (product.slug or '')[:200],
            'focus_keyword': (keywords[0] if keywords else '')[:100],
            'og_title': meta_title[:100],
            'og_description': meta_description[:200],
            'twitter_title': meta_title[:70],
            'twitter_description': meta_description[:200],
            'is_indexable': True,
            'robots_meta': 'index,follow',
        },
    )


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------

@transaction.atomic
def publish(draft: Any, *, user: Any = None) -> Any:
    """
    Turn an approved draft into a live ``Product``.

    ``draft.category`` and ``draft.sub_category`` must already be set — they are
    the only two fields the admin supplies. Raises :class:`PublishError` on any
    validation failure, rolling the transaction back.
    """
    from Hub.models import Product, ProductDraft, ProductImage
    from Hub.views import calc_discount_percent

    if draft.status == ProductDraft.STATUS_PUBLISHED:
        raise PublishError('This draft has already been published.')
    if not draft.category:
        raise PublishError('Select a Category before approving.')

    record = draft.parsed or {}
    name = (record.get('name') or draft.display_name or '').strip()[:200]
    if not name:
        raise PublishError('The draft has no product name.')

    price = _decimal(record.get('price'))
    if price is None:
        raise PublishError('The draft has no valid selling price. Set one before approving.')

    old_price = _decimal(record.get('old_price'))
    if old_price is not None and old_price <= price:
        old_price = None

    try:
        stock = max(int(float(record.get('stock') or 0)), 0)
    except (TypeError, ValueError):
        stock = 0

    images = list(draft.images.all().order_by('order', 'id'))
    main_image = next((i for i in images if i.role == 'main'), None)
    description_image = next((i for i in images if i.role == 'description'), None)

    # --- Core product ------------------------------------------------------
    product = Product(
        name=name,
        price=price,
        old_price=old_price,
        margin=Decimal('0'),
        discount_percent=calc_discount_percent(price, old_price) if old_price else 0,
        stock=stock,
        sold=0,
        category=draft.category,
        sub_category=(draft.sub_category or record.get('suggested_sub_category') or '')[:100],
        sku=_unique_sku(record.get('sku') or ''),
        brand=(record.get('brand') or '')[:100],
        description=build_description(record),
        care_info=build_care_info(record),
        tags=build_tags(record),
        weight=(record.get('weight') or '')[:50],
        dimensions=(record.get('dimensions') or '')[:100],
        color=', '.join(record.get('colors') or [])[:100],
        size=', '.join(record.get('sizes') or [])[:100],
        # Return policy chosen by the admin on the review screen. Product.save()
        # drops COD automatically when a product is not returnable.
        is_returnable=bool(record.get('is_returnable', True)),
        return_days=int(record.get('return_days') or 7),
        return_policy=str(record.get('return_policy') or '')[:2000],
        is_active=True,
        is_top_deal=False,
        rating=0,
        review_count=0,
        created_by=user,
    )

    # Copy staged files onto the product rather than moving them, so a rollback
    # cannot leave the draft without its images.
    if main_image:
        product.image.save(
            os.path.basename(main_image.image.name),
            staged_file(main_image),
            save=False,
        )
    if description_image:
        product.descriptionImage.save(
            os.path.basename(description_image.image.name),
            staged_file(description_image),
            save=False,
        )

    product.save()

    # --- Gallery / variant images -----------------------------------------
    order = 0
    for staged in images:
        if staged is main_image or staged is description_image:
            continue
        order += 1
        gallery = ProductImage(
            product=product,
            color=staged.color[:100],
            image_role=staged.role,
            order=order,
            is_active=True,
        )
        gallery.image.save(
            os.path.basename(staged.image.name),
            staged_file(staged),
            save=False,
        )
        gallery.save()

    # --- Variants, SEO and reels -------------------------------------------
    variant_count = create_variants(product, record, images)
    create_seo(product, record)
    reel_count = create_reels(product, draft, user)

    # --- Close the draft ---------------------------------------------------
    draft.status = ProductDraft.STATUS_PUBLISHED
    draft.published_product = product
    draft.reviewed_at = timezone.now()
    draft.reviewed_by = user
    draft.log_event(
        'publish',
        f'Published as product #{product.pk} '
        f'({order} gallery image(s), {variant_count} variant(s), {reel_count} reel(s)).',
        save=False,
    )
    draft.save(
        update_fields=[
            'status', 'published_product', 'reviewed_at', 'reviewed_by', 'events', 'updated_at',
        ]
    )

    logger.info(
        '[publish] Draft %s -> Product %s (%s) by %s',
        draft.pk, product.pk, product.slug, getattr(user, 'username', 'system'),
    )
    return product
