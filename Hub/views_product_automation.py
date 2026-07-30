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

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from Hub.automation.publisher import PublishError, publish
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
        'category_labels': dict(Product.CATEGORY_CHOICES),
    }


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

    record = draft.parsed or {}
    suggestion = draft.ai_suggestions or {}
    images = list(draft.images.all().order_by('order', 'id'))

    context = {
        'draft': draft,
        'record': record,
        'suggestion': suggestion,
        'images': images,
        'videos': draft.videos.all().order_by('order', 'id'),
        'any_footer_detected': any(image.suggested_crop_bottom_px for image in images),
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
    for field in ('sizes', 'colors', 'tags', 'meta_keywords'):
        if field in request.POST:
            raw = request.POST.get(field) or ''
            record[field] = [part.strip() for part in raw.split(',') if part.strip()]
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
        f'Category: {dict(Product.CATEGORY_CHOICES).get(product.category, product.category)}.',
    )
    return redirect('admin_edit_product', product_id=product.pk)


@login_required(login_url='login')
@staff_member_required(login_url='login')
@require_POST
def admin_delete_product_draft(request, draft_id: int):
    """Discard a draft and its staged images entirely."""
    draft = get_object_or_404(ProductDraft, pk=draft_id)
    for image in draft.images.all():
        try:
            image.image.delete(save=False)
        except OSError as exc:
            # A locked file on Windows must not block removing the draft row;
            # the orphaned file is harmless and can be swept up later.
            logger.warning('[review] Could not delete staged file for image %s: %s', image.pk, exc)
    draft.delete()
    messages.success(request, f'Draft #{draft_id} deleted.')
    return redirect('admin_product_drafts')


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
