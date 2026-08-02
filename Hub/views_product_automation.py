"""
Admin approval screens for automated product drafts.

Kept in its own module rather than appended to the 15k-line ``views.py``, and
wired through ``Hub/urls.py`` alongside the existing admin-panel routes.

The review screen is deliberately narrow in scope: everything except
**Category** and **Sub Category** arrives pre-filled by the pipeline. The admin
can override any field, but the intended flow is glance → confirm the category
→ Approve.
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from Hub.automation.publisher import (
    PublishError,
    default_stock,
    next_sku,
    publish,
    sku_prefix,
)
from Hub.models import CategoryIcon, Product, ProductDraft, SubCategory

logger = logging.getLogger(__name__)

#: Statuses shown as tabs on the list screen, in display order.
LIST_TABS = [
    (ProductDraft.STATUS_PENDING, 'Pending Approval'),
    (ProductDraft.STATUS_DUPLICATE, 'Possible Duplicates'),
    (ProductDraft.STATUS_RECEIVED, 'Processing'),
    (ProductDraft.STATUS_FAILED, 'Failed'),
    (ProductDraft.STATUS_PUBLISHED, 'Published'),
    (ProductDraft.STATUS_REJECTED, 'Rejected'),
]


def _category_context() -> dict:
    """Category and sub-category options for the two admin-supplied fields."""
    categories = CategoryIcon.objects.filter(is_active=True).order_by('order', 'id')
    sub_categories = list(
        SubCategory.objects.filter(is_active=True)
        .order_by('category_key', 'order', 'name')
        .values('category_key', 'name')
    )
    return {
        'categories': categories,
        'sub_categories': sub_categories,
        'sub_categories_json': json.dumps(sub_categories),
        'category_labels': _category_labels(),
    }


def _category_labels() -> dict:
    """
    Key -> display name for every category, this store's first.

    ``Product.CATEGORY_CHOICES`` is a stale template list, so it is only a
    fallback for keys on older products that predate the CategoryIcon rows.
    """
    labels = dict(Product.CATEGORY_CHOICES)
    labels.update({
        (icon.category_key or '').strip(): (icon.name or '').strip()
        for icon in CategoryIcon.objects.filter(is_active=True)
        if (icon.category_key or '').strip()
    })
    return labels


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_product_drafts(request):
    """Queue overview: everything Telegram has sent, grouped by status."""
    status = request.GET.get('status') or ProductDraft.STATUS_PENDING
    search = (request.GET.get('q') or '').strip()

    drafts = ProductDraft.objects.select_related('published_product', 'duplicate_of')

    if status != 'all':
        # "Processing" covers everything not yet reviewable.
        if status == ProductDraft.STATUS_RECEIVED:
            drafts = drafts.filter(
                status__in=[
                    ProductDraft.STATUS_RECEIVED,
                    ProductDraft.STATUS_QUEUED,
                    ProductDraft.STATUS_PROCESSING,
                ]
            )
        else:
            drafts = drafts.filter(status=status)

    if search:
        # Key transform rather than a whole-document icontains — the latter is
        # not a supported JSONField lookup on every backend.
        drafts = drafts.filter(Q(raw_text__icontains=search) | Q(parsed__name__icontains=search))

    drafts = drafts.annotate(image_count=Count('images')).order_by('-created_at')

    counts = {
        row['status']: row['n']
        for row in ProductDraft.objects.values('status').annotate(n=Count('id'))
    }
    counts[ProductDraft.STATUS_RECEIVED] = (
        counts.get(ProductDraft.STATUS_RECEIVED, 0)
        + counts.get(ProductDraft.STATUS_QUEUED, 0)
        + counts.get(ProductDraft.STATUS_PROCESSING, 0)
    )

    page = Paginator(drafts, 25).get_page(request.GET.get('page'))

    return render(
        request,
        'admin_panel/product_drafts.html',
        {
            'page_obj': page,
            'drafts': page.object_list,
            'tabs': [(key, label, counts.get(key, 0)) for key, label in LIST_TABS],
            'active_status': status,
            'search': search,
        },
    )


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_review_product_draft(request, draft_id: int):
    """Review one draft, pick its category, and approve or reject it."""
    draft = get_object_or_404(
        ProductDraft.objects.select_related('published_product', 'duplicate_of'), pk=draft_id
    )

    if request.method == 'POST':
        return _handle_review_post(request, draft)

    record = dict(draft.parsed or {})
    suggestion = draft.ai_suggestions or {}
    images = list(draft.images.all().order_by('order', 'id'))

    # The supplier's price is the MRP, so the cost and margin boxes start empty
    # for the admin to fill. Once either has been set they are shown back.
    record.setdefault('base_price', '')
    record.setdefault('margin', '')

    # Show the stock the product would publish with, rather than a blank box
    # that silently becomes 50 on approval.
    if not str(record.get('stock') or '').strip():
        record['stock'] = str(default_stock())

    context = {
        'draft': draft,
        'record': record,
        'suggestion': suggestion,
        'images': images,
        'videos': draft.videos.all().order_by('order', 'id'),
        'any_footer_detected': any(image.suggested_crop_bottom_px for image in images),
        # Derived from the crops themselves rather than stored, so the toggle
        # can never disagree with what will actually be published.
        'crop_mode': 'meesho' if any(image.crop_bottom_px for image in images) else 'market',
        'meesho_crop_px': meesho_crop_px(),
        'suggested_sku': next_sku(draft.sub_category or record.get('suggested_sub_category') or ''),
        'events': list(reversed(draft.events or []))[:25],
        # Attributes with no Product column — shown so the admin can see what
        # was extracted before it is folded into description/care_info/tags.
        'extended_attributes': _extended_attribute_rows(record),
        'colorways': _colorways(draft),
    }
    context.update(_category_context())
    return render(request, 'admin_panel/review_product_draft.html', context)


def _extended_attribute_rows(record: dict) -> list[tuple[str, str]]:
    from Hub.automation.ai.schema import EXTENDED_ATTRIBUTE_FIELDS

    rows = []
    for field in EXTENDED_ATTRIBUTE_FIELDS:
        value = str(record.get(field) or '').strip()
        if value:
            rows.append((field.replace('_', ' ').title(), value))
    return rows


def _colorways(draft: ProductDraft) -> list[dict]:
    """Group staged images by detected colour, for the variant preview."""
    grouped: dict[str, list] = {}
    for image in draft.images.all().order_by('order', 'id'):
        grouped.setdefault(image.color or 'Default', []).append(image)
    return [{'color': color, 'images': images} for color, images in grouped.items()]


def meesho_crop_px() -> int:
    """
    Fallback strip height for the Meesho toggle.

    Detection fills each image's own suggestion; this is what the toggle uses
    when a photo was cropped tightly enough that no band was found, so one
    missed detection cannot leave a code visible on a single image.
    """
    from django.conf import settings

    return max(int(getattr(settings, 'AUTOMATION_MEESHO_CROP_PX', 28)), 0)


def _money(raw, default: Decimal | None = None) -> Decimal | None:
    """Parse a rupee amount from a form field, tolerating ``1,299`` and ``₹``."""
    text = re.sub(r'[^\d.\-]', '', str(raw or ''))
    if not text:
        return default
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return default
    return value if value >= 0 else default


def _apply_pricing(request, record: dict) -> None:
    """
    Resolve the four price boxes into what the catalogue stores.

    The review screen asks for cost, margin and MRP the way the manual Add
    Product page does, because that is how the shop reasons about a product::

        original price (what the supplier charges)
      + margin         (the profit on this item)
      = selling price  (what the customer pays)         -> Product.price
        MRP            (the struck-through comparison)  -> Product.old_price

    The browser computes the selling price live, but it is recomputed here as
    well: a posted total must never be trusted over the two numbers it claims
    to be the sum of, or a stale field silently books the wrong profit.
    """
    base = _money(request.POST.get('base_price'))
    margin = _money(request.POST.get('margin'), Decimal('0')) or Decimal('0')

    if base is not None:
        record['base_price'] = str(base)
        record['margin'] = str(margin)
        record['price'] = str(base + margin)
        return

    # No cost given — keep whatever selling price was typed and treat the whole
    # of it as unattributed, rather than inventing a profit figure.
    record['margin'] = str(margin)
    price = _money(record.get('price'))
    if price is not None:
        record['base_price'] = str(max(price - margin, Decimal('0')))


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_next_sku(request):
    """Suggest a SKU for the sub-category the admin just picked."""
    sub_category = (request.GET.get('sub_category') or '').strip()
    return JsonResponse({'sku': next_sku(sub_category), 'prefix': sku_prefix(sub_category)})


def _save_crops(request, draft: ProductDraft) -> int:
    """
    Persist per-image bottom crops posted from the review screen.

    Values are stored as intent — the file is untouched until publish — so an
    admin can adjust or clear a crop as many times as they like.
    """
    updated = 0
    for image in draft.images.all():
        field = f'crop_{image.pk}'
        if field not in request.POST:
            continue
        try:
            value = max(int(request.POST.get(field) or 0), 0)
        except (TypeError, ValueError):
            continue
        if value != image.crop_bottom_px:
            image.crop_bottom_px = value
            image.save(update_fields=['crop_bottom_px'])
            updated += 1
    return updated


def _save_image_roles(request, draft: ProductDraft) -> None:
    """
    Apply the admin's per-image role choices.

    The vision pass only ever marks an image as ``description`` when it looks
    informational (a size chart or fabric card). When a supplier sends none,
    this is how an admin nominates one by hand.

    Exactly one main and one description image are used on publish, so extra
    selections are demoted to gallery rather than silently ignored — the
    reloaded page then shows what will actually happen.
    """
    from Hub.models import ProductDraftImage

    valid = {
        ProductDraftImage.ROLE_MAIN,
        ProductDraftImage.ROLE_GALLERY,
        ProductDraftImage.ROLE_DESCRIPTION,
    }
    seen_main = False
    seen_description = False

    for image in draft.images.all().order_by('order', 'id'):
        posted = (request.POST.get(f'role_{image.pk}') or '').strip()
        if posted not in valid:
            continue

        role = posted
        if role == ProductDraftImage.ROLE_MAIN:
            if seen_main:
                role = ProductDraftImage.ROLE_GALLERY
            else:
                seen_main = True
        elif role == ProductDraftImage.ROLE_DESCRIPTION:
            if seen_description:
                role = ProductDraftImage.ROLE_GALLERY
            else:
                seen_description = True

        if role != image.role:
            image.role = role
            image.save(update_fields=['role'])


def _save_reel_settings(request, draft: ProductDraft) -> None:
    """Persist per-video reel title and publish choices from the review screen."""
    for video in draft.videos.all():
        video.title = (request.POST.get(f'reel_title_{video.pk}') or '').strip()[:200]
        video.create_reel = bool(request.POST.get(f'reel_create_{video.pk}'))
        video.publish_reel = bool(request.POST.get(f'reel_publish_{video.pk}'))
        video.save(update_fields=['title', 'create_reel', 'publish_reel'])


def _handle_review_post(request, draft: ProductDraft):
    action = request.POST.get('action')

    if action == 'save_crops':
        count = _save_crops(request, draft)
        _save_image_roles(request, draft)
        _save_reel_settings(request, draft)
        messages.success(request, f'Crop updated on {count} image{"" if count == 1 else "s"}.')
        return redirect('admin_review_product_draft', draft_id=draft.pk)

    if action == 'reject':
        draft.status = ProductDraft.STATUS_REJECTED
        draft.reviewed_at = timezone.now()
        draft.reviewed_by = request.user
        draft.log_event('review', f'Rejected by {request.user.username}.', save=False)
        draft.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'events', 'updated_at'])
        messages.info(request, f'Draft #{draft.pk} rejected.')
        return redirect('admin_product_drafts')

    if action == 'requeue':
        draft.status = ProductDraft.STATUS_QUEUED
        draft.attempts = 0
        draft.next_attempt_at = None
        draft.last_error = ''
        draft.log_event('review', f'Requeued by {request.user.username}.', save=False)
        draft.save(update_fields=['status', 'attempts', 'next_attempt_at', 'last_error', 'events', 'updated_at'])
        messages.success(request, f'Draft #{draft.pk} queued for reprocessing.')
        return redirect('admin_review_product_draft', draft_id=draft.pk)

    if action != 'approve':
        messages.error(request, 'Unknown action.')
        return redirect('admin_review_product_draft', draft_id=draft.pk)

    # --- Approve -----------------------------------------------------------
    # Crops are applied to the live images by the publisher, so they must be
    # saved before publish() reads them.
    _save_crops(request, draft)
    _save_image_roles(request, draft)
    _save_reel_settings(request, draft)

    draft.category = (request.POST.get('category') or '').strip()
    draft.sub_category = (request.POST.get('sub_category') or '').strip()[:100]

    if not draft.category:
        messages.error(request, 'Please select a Category before approving.')
        draft.save(update_fields=['category', 'sub_category', 'updated_at'])
        return redirect('admin_review_product_draft', draft_id=draft.pk)

    # Let the admin correct any AI-generated field at approval time.
    record = dict(draft.parsed or {})
    for field in ('name', 'price', 'old_price', 'stock', 'sku', 'brand',
                  'short_description', 'description', 'meta_title', 'meta_description'):
        if field in request.POST:
            record[field] = (request.POST.get(field) or '').strip()

    _apply_pricing(request, record)

    # A blank SKU is filled from the sub-category, so every product carries a
    # traceable code even when the admin never touched the field.
    if not (record.get('sku') or '').strip():
        record['sku'] = next_sku(draft.sub_category or record.get('suggested_sub_category') or '')
    for field in ('sizes', 'colors', 'tags', 'meta_keywords'):
        if field in request.POST:
            raw = request.POST.get(field) or ''
            record[field] = [part.strip() for part in raw.split(',') if part.strip()]

    # Return policy — an unchecked switch posts nothing, so absence means "off".
    record['is_returnable'] = bool(request.POST.get('is_returnable'))
    try:
        record['return_days'] = max(min(int(request.POST.get('return_days') or 7), 90), 0)
    except (TypeError, ValueError):
        record['return_days'] = 7
    record['return_policy'] = (request.POST.get('return_policy') or '').strip()[:2000]

    draft.parsed = record
    draft.save(update_fields=['category', 'sub_category', 'parsed', 'updated_at'])

    try:
        product = publish(draft, user=request.user)
    except PublishError as exc:
        messages.error(request, f'Could not publish: {exc}')
        return redirect('admin_review_product_draft', draft_id=draft.pk)
    except Exception as exc:  # noqa: BLE001
        logger.exception('[review] Publishing draft %s failed', draft.pk)
        messages.error(request, f'Unexpected error while publishing: {exc}')
        return redirect('admin_review_product_draft', draft_id=draft.pk)

    messages.success(
        request,
        f'"{product.name}" is now live. '
        f'Category: {_category_labels().get(product.category, product.category)}.',
    )
    return redirect('admin_edit_product', product_id=product.pk)


@login_required(login_url='login')
@staff_member_required(login_url='login')
@require_POST
def admin_delete_product_draft(request, draft_id: int):
    """Discard a draft and its staged images entirely."""
    draft = get_object_or_404(ProductDraft, pk=draft_id)
    # PROCESSING means a worker currently holds this row (pipeline.py sets
    # claimed_at and works through vision/extraction/publish). Deleting it
    # out from under that in-flight request used to crash the worker with a
    # confusing DatabaseError and silently lose the product - a stuck claim
    # already self-heals in 30 minutes via pipeline.reclaim_stale(), so there
    # is never a reason to force it from here.
    if draft.status == ProductDraft.STATUS_PROCESSING:
        messages.error(
            request,
            f'Draft #{draft_id} is being processed right now — try again in a moment.',
        )
        return redirect('admin_product_drafts')
    # A locked file on Windows must not block removing the draft row; an
    # orphaned file is harmless and can be swept up later.
    _delete_draft_files(draft)
    draft.delete()
    messages.success(request, f'Draft #{draft_id} deleted.')
    return redirect('admin_product_drafts')


@login_required(login_url='login')
@staff_member_required(login_url='login')
@require_POST
def admin_bulk_delete_product_drafts(request):
    """
    Discard every draft in one status tab.

    A supplier sending photos one at a time used to create a draft per photo,
    so clearing up meant dozens of individual deletes. Published drafts are
    never touched — deleting those would orphan the audit trail of a live
    product. PROCESSING drafts are never touched either, for the same reason
    as the single-delete view above: that status means a worker currently
    holds the row, and deleting it out from under that request used to crash
    the worker and silently lose the product. A stuck claim self-heals in 30
    minutes via pipeline.reclaim_stale().
    """
    status = (request.POST.get('status') or '').strip()

    drafts = ProductDraft.objects.exclude(
        status__in=[ProductDraft.STATUS_PUBLISHED, ProductDraft.STATUS_PROCESSING]
    )
    if status == ProductDraft.STATUS_RECEIVED:
        drafts = drafts.filter(status__in=[ProductDraft.STATUS_RECEIVED, ProductDraft.STATUS_QUEUED])
    elif status and status != 'all':
        drafts = drafts.filter(status=status)

    skipped_processing = ProductDraft.objects.filter(status=ProductDraft.STATUS_PROCESSING).count()

    count = 0
    for draft in drafts:
        _delete_draft_files(draft)
        draft.delete()
        count += 1

    if skipped_processing:
        messages.info(
            request,
            f'{skipped_processing} draft{"" if skipped_processing == 1 else "s"} '
            f'being processed right now — left alone, try again shortly if they still need clearing.',
        )

    messages.success(request, f'Deleted {count} draft{"" if count == 1 else "s"}.')
    return redirect('admin_product_drafts')


def _delete_draft_files(draft: ProductDraft) -> None:
    """Remove staged media, tolerating files locked or already gone."""
    for image in draft.images.all():
        try:
            image.image.delete(save=False)
        except OSError as exc:
            logger.warning('[review] Could not delete staged image %s: %s', image.pk, exc)
    for video in draft.videos.all():
        try:
            video.video.delete(save=False)
        except OSError as exc:
            logger.warning('[review] Could not delete staged video %s: %s', video.pk, exc)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_product_drafts_status(request):
    """Small JSON endpoint so the list page can show live queue counts."""
    counts = {
        row['status']: row['n']
        for row in ProductDraft.objects.values('status').annotate(n=Count('id'))
    }
    return JsonResponse(
        {
            'pending': counts.get(ProductDraft.STATUS_PENDING, 0),
            'duplicates': counts.get(ProductDraft.STATUS_DUPLICATE, 0),
            'processing': (
                counts.get(ProductDraft.STATUS_RECEIVED, 0)
                + counts.get(ProductDraft.STATUS_QUEUED, 0)
                + counts.get(ProductDraft.STATUS_PROCESSING, 0)
            ),
            'failed': counts.get(ProductDraft.STATUS_FAILED, 0),
        }
    )


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_latest_processing_draft(request):
    """
    Polled from every admin page (base_admin.html) so a product that starts
    processing anywhere pulls the admin to the queue automatically, rather
    than them finding out only if they happen to be on that page already.

    Returns the newest draft that has ever entered PROCESSING, not "currently
    processing" — a draft that finished a second after it started would
    otherwise vanish from a naive "status=PROCESSING right now" query before
    the poller's next tick ever saw it. The frontend tracks which id it has
    already redirected for, so this being "sticky" doesn't mean a repeat
    redirect once it reaches PENDING.
    """
    latest = (
        ProductDraft.objects
        .exclude(claimed_at__isnull=True)
        .order_by('-claimed_at')
        .values('id', 'status', 'claimed_at')
        .first()
    )
    if not latest:
        return JsonResponse({'id': None})
    return JsonResponse({
        'id': latest['id'],
        'status': latest['status'],
        'claimed_at': latest['claimed_at'].isoformat(),
    })


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_ai_usage(request):
    """AI usage widget data: active model, today/month spend, and the daily
    ceiling for whichever model is actually answering right now."""
    from Hub.automation.ai import PROVIDER_CLAUDE, PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_OLLAMA
    from Hub.automation.ai.usage import usage_summary

    data = usage_summary()
    data['available_providers'] = [PROVIDER_GROQ, PROVIDER_GEMINI, PROVIDER_CLAUDE, PROVIDER_OLLAMA]
    # Everything that still needs *someone's* attention - the AI's (still in
    # the queue) or the admin's (AI is done, waiting on a review click).
    # Originally only counted the first group, which reads as "0 pending"
    # the instant a draft clears the AI step even though it is now sitting
    # in the Pending Approval tab asking for a decision.
    data['pending_count'] = ProductDraft.objects.filter(
        status__in=[
            ProductDraft.STATUS_RECEIVED,
            ProductDraft.STATUS_QUEUED,
            ProductDraft.STATUS_PROCESSING,
            ProductDraft.STATUS_PENDING,
            ProductDraft.STATUS_DUPLICATE,
        ],
    ).count()
    return JsonResponse(data)


@login_required(login_url='login')
@staff_member_required(login_url='login')
@require_POST
def admin_ai_usage_switch(request):
    """
    Switch the AI provider without a deploy.

    Writes to SiteSettings.ai_provider_override, which Hub.automation.ai
    checks ahead of AUTOMATION_AI_PROVIDER on every call - so a quota running
    out mid-day can be worked around from here instead of waiting on an SSH
    session. 'auto' clears the override and returns to the .env default.
    """
    from Hub.automation.ai import PROVIDER_CLAUDE, PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_OLLAMA
    from Hub.automation.ai.usage import usage_summary
    from Hub.models import SiteSettings

    provider = (request.POST.get('provider') or '').strip().lower()
    valid = {PROVIDER_GROQ, PROVIDER_GEMINI, PROVIDER_CLAUDE, PROVIDER_OLLAMA, 'auto'}
    if provider not in valid:
        return JsonResponse({'success': False, 'error': f'Unknown provider {provider!r}.'}, status=400)

    site_settings = SiteSettings.get_settings()
    site_settings.ai_provider_override = '' if provider == 'auto' else provider
    site_settings.save(update_fields=['ai_provider_override'])

    return JsonResponse({'success': True, **usage_summary()})
