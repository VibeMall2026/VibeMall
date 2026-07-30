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
import re
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


def _ordered_colors(record: dict[str, Any], main_image: Any) -> list[str]:
    """
    The product's colours, with the hero image's colour first.

    The storefront preselects the first colour and tags the main thumbnail with
    it. If the hero were not that colour, the colour filter would hide the main
    photo the moment the page loaded — so the order is not cosmetic.
    """
    colors = [str(c).strip() for c in (record.get('colors') or []) if str(c).strip()]
    hero = str(getattr(main_image, 'color', '') or '').strip()

    if not hero:
        return colors

    rest = [c for c in colors if c.lower() != hero.lower()]
    return [hero] + rest


def sku_prefix(sub_category: str) -> str:
    """
    Turn a sub-category into the letters that start its SKUs.

    ``Top_Pallazo set`` -> ``TOPPALLAZO``, ``lehenga choli`` -> ``LEHENGACHO``.
    Capped at ten characters so the serial stays readable beside it.
    """
    letters = re.sub(r'[^A-Za-z0-9]', '', sub_category or '').upper()
    return letters[:10] or 'PROD'


def next_sku(sub_category: str) -> str:
    """
    The next free SKU for a sub-category, as ``PREFIX-0001``.

    Numbered from the highest serial already issued rather than from how many
    products exist, so deleting one never re-issues its code. A collision is
    still impossible either way: ``_unique_sku`` suffixes anything that slips
    through, including a code an admin typed by hand.
    """
    from Hub.models import Product

    prefix = sku_prefix(sub_category)
    pattern = re.compile(rf'^{re.escape(prefix)}-(\d+)$')

    highest = 0
    for sku in Product.objects.filter(sku__startswith=f'{prefix}-').values_list('sku', flat=True):
        match = pattern.match((sku or '').strip().upper())
        if match:
            highest = max(highest, int(match.group(1)))

    return f'{prefix}-{highest + 1:04d}'


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

    # Styling and construction attributes live here rather than in care_info,
    # which the page renders as "Care Guide". Fabric is excluded too: it is the
    # first line of the Care Guide, and repeating it here — once per component,
    # all of them usually the same fabric — is what made the block unreadable.
    excluded = set(CARE_INFO_FIELDS) | set(FABRIC_FIELDS)
    known = [f for f in SPECIFICATION_FIELDS if f not in excluded]

    # Any attribute added to the schema later still gets shown, but ahead of
    # ``occasion`` so it stays the closing line of the block.
    extras = [
        f for f in EXTENDED_ATTRIBUTE_FIELDS
        if f not in excluded and f not in SPECIFICATION_FIELDS
    ]
    order = [f for f in known if f != 'occasion'] + extras + ['occasion']

    specs: list[str] = []
    for field in order:
        value = str(record.get(field) or '').strip()
        if value:
            specs.append(f'{_label(field)}: {value}')
    if specs:
        parts.append('Product Details\n' + '\n'.join(specs))

    return '\n\n'.join(parts)


#: Fields consumed when writing the Care Guide. They are *inputs* to it, not
#: lines of it — listing them raw is what produced "Fabric: Georgette |
#: Material: Georgette | Top Fabric: Georgette | Bottom Fabric: Georgette |
#: Dupatta Fabric: Georgette", which is a spec dump, not care advice.
CARE_INFO_FIELDS = ['wash_care', 'package_contents']

#: The fabric of each component. Suppliers repeat the same fabric across all of
#: them, so these are collapsed before being shown.
FABRIC_FIELDS = ['fabric', 'material', 'top_fabric', 'bottom_fabric', 'dupatta_fabric', 'inner_fabric']

#: Construction and styling attributes, in the order they read best.
#: ``occasion`` is deliberately last: it is the natural closing line of the
#: specification block, and nothing should follow it.
SPECIFICATION_FIELDS = [
    'product_type', 'sleeve_type', 'neck_type', 'length', 'pattern',
    'work_type', 'style', 'fit', 'stitch_type', 'country_of_origin', 'occasion',
]

#: Fabrics that a washing machine ruins. Indian womenswear is dominated by
#: these, so an unrecognised fabric is treated as delicate too — advising a
#: gentle wash for a sturdy fabric costs nothing, the reverse ruins a garment.
DELICATE_FABRICS = {
    'silk', 'georgette', 'chiffon', 'organza', 'net', 'tissue', 'velvet', 'satin',
    'banarasi', 'chanderi', 'brasso', 'taffeta', 'tafeta', 'jacquard', 'brocade',
    'tussar', 'kanjivaram', 'paithani', 'chinnon', 'chinon', 'vichitra', 'sequin',
    'zari', 'shimmer', 'lace', 'raw silk', 'art silk',
}

#: Fabrics that take an ordinary gentle machine cycle.
WASHABLE_FABRICS = {
    'cotton', 'linen', 'khadi', 'denim', 'rayon', 'viscose', 'modal', 'crepe',
    'lycra', 'polyester', 'poly', 'nylon', 'jersey', 'knit', 'terry', 'fleece',
    'muslin', 'cambric', 'poplin', 'dobby',
}

#: Surface work that must never meet a hot iron directly.
EMBELLISHMENT_HINTS = {
    'embroider', 'zari', 'sequin', 'sequence', 'mirror', 'stone', 'bead',
    'thread work', 'hand work', 'zardosi', 'gota', 'applique', 'foil', 'print',
}


def _fabric_values(record: dict[str, Any]) -> list[str]:
    """Every distinct fabric named on the product, in declaration order."""
    seen: list[str] = []
    for field in FABRIC_FIELDS:
        value = str(record.get(field) or '').strip()
        if value and value.lower() not in {s.lower() for s in seen}:
            seen.append(value)
    return seen


def _is_delicate(record: dict[str, Any]) -> bool:
    """True unless every named fabric is one that survives a machine."""
    fabrics = ' '.join(_fabric_values(record)).lower()
    if not fabrics:
        return True
    if any(word in fabrics for word in DELICATE_FABRICS):
        return True
    return not any(word in fabrics for word in WASHABLE_FABRICS)


def _is_embellished(record: dict[str, Any]) -> bool:
    haystack = ' '.join(
        str(record.get(field) or '') for field in ('work_type', 'pattern', 'style', 'name')
    ).lower()
    return any(hint in haystack for hint in EMBELLISHMENT_HINTS)


def build_care_info(record: dict[str, Any]) -> str:
    """
    Write a real care guide for the garment.

    The product page renders this under "Care Guide", so it has to read as
    instructions a customer can follow — not as a list of the fabric fields
    with their labels, which is what it used to be.

    The advice is derived deterministically from the fabric rather than asked
    of the model: care is the one section where a confident wrong answer
    ("machine washable" for georgette) actually destroys the customer's
    purchase, and the fabric alone is enough to get it right.
    """
    delicate = _is_delicate(record)
    supplier_wash = str(record.get('wash_care') or '').strip()

    wash: list[str] = []
    if supplier_wash and supplier_wash.lower() not in {'na', 'n/a', '-'}:
        wash.append(supplier_wash.rstrip('.') + '.')
    elif delicate:
        wash.append(
            'Dry clean recommended. If washing at home, hand wash separately in cold '
            'water with a mild detergent.'
        )
    else:
        wash.append('Machine wash cold on a gentle cycle with similar colours.')

    wash.append('Do not bleach. Do not soak or wring the garment.')
    wash.append('Wash dark shades separately for the first few washes.')

    drying = ['Dry in shade, inside out — direct sunlight fades the colour.']
    if delicate:
        drying.append('Iron on low heat.')
    else:
        drying.append('Iron on medium heat.')
    if _is_embellished(record):
        drying.append(
            'Press embroidered and embellished areas from the reverse, or with a thin '
            'cloth over the work.'
        )

    storage = ['Fold and store in a dry place, away from direct sunlight.']
    if delicate:
        storage.append('Keep in a cotton or muslin bag rather than plastic, so the fabric can breathe.')

    sections = [
        ('Wash Care', wash),
        ('Drying & Ironing', drying),
        ('Storage', storage),
    ]

    fabrics = _fabric_values(record)
    if fabrics:
        sections.insert(0, ('Fabric', [', '.join(fabrics)]))

    contents = str(record.get('package_contents') or '').strip()
    if contents:
        sections.append(('Package Contents', [contents]))

    blocks = [
        heading + '\n' + '\n'.join(f'• {line}' for line in lines)
        for heading, lines in sections
    ]
    return '\n\n'.join(blocks)[:5000]


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

    # Profit carried inside the selling price, so the reports that read
    # Product.margin attribute this product correctly. Never more than the
    # price itself: a margin above it would report a negative cost.
    margin = _decimal(record.get('margin'), Decimal('0')) or Decimal('0')
    margin = min(margin, price)

    try:
        stock = max(int(float(record.get('stock') or 0)), 0)
    except (TypeError, ValueError):
        stock = 0

    images = list(draft.images.all().order_by('order', 'id'))
    main_image = next((i for i in images if i.role == 'main'), None)
    description_image = next((i for i in images if i.role == 'description'), None)

    colors = _ordered_colors(record, main_image)

    # --- Core product ------------------------------------------------------
    product = Product(
        name=name,
        price=price,
        old_price=old_price,
        margin=margin,
        discount_percent=calc_discount_percent(price, old_price) if old_price else 0,
        stock=stock,
        sold=0,
        category=draft.category,
        sub_category=(draft.sub_category or record.get('suggested_sub_category') or '')[:100],
        # Falls back to a serial derived from the sub-category, so every
        # product carries a traceable code even if nobody typed one.
        sku=_unique_sku(
            (record.get('sku') or '').strip()
            or next_sku(draft.sub_category or record.get('suggested_sub_category') or '')
        ),
        brand=(record.get('brand') or '')[:100],
        description=build_description(record),
        care_info=build_care_info(record),
        tags=build_tags(record),
        weight=(record.get('weight') or '')[:50],
        dimensions=(record.get('dimensions') or '')[:100],
        color=', '.join(colors)[:100],
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
