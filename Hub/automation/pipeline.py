"""
Processing pipeline & queue
===========================

Drives a draft from "raw message received" to "ready for admin approval", and
provides the claim/retry logic the worker command uses.

Why the draft table *is* the queue
----------------------------------
This project runs on SQLite with no broker installed. Adding Celery + Redis
would mean new infrastructure to deploy and supervise on a Windows host for a
workload measured in hundreds of jobs a day. Instead ``status`` +
``next_attempt_at`` + ``attempts`` on the draft give us at-least-once delivery,
exponential backoff, crash recovery (stale claims are reclaimed) and full
visibility in the admin — with zero new services.

If throughput ever outgrows this, ``process_draft`` is a plain function: point
a Celery task at it and nothing else changes.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from .ai import AIUnavailable, active_provider, get_client, is_configured
from .ai.extraction import extract, suggested_slug
from .ai.vision import analyse_images, apply_to_images
from .duplicates import find_duplicate
from .images import process_draft_images
from .ingest import pair_window_seconds, settle_seconds

logger = logging.getLogger(__name__)

#: Retry schedule, in minutes, indexed by attempt number.
BACKOFF_MINUTES = [1, 5, 15, 60]

#: A claim older than this is assumed to belong to a crashed worker.
STALE_CLAIM_MINUTES = 30


def max_attempts() -> int:
    return int(getattr(settings, 'AUTOMATION_MAX_ATTEMPTS', 4))


# --------------------------------------------------------------------------
# Queue
# --------------------------------------------------------------------------

def reclaim_stale() -> int:
    """Return drafts abandoned by a crashed worker to the queue."""
    from Hub.models import ProductDraft

    cutoff = timezone.now() - timedelta(minutes=STALE_CLAIM_MINUTES)
    stale = ProductDraft.objects.filter(status=ProductDraft.STATUS_PROCESSING, claimed_at__lt=cutoff)
    count = stale.count()
    if count:
        stale.update(status=ProductDraft.STATUS_QUEUED, claimed_at=None)
        logger.warning('[pipeline] Reclaimed %d stale draft(s) from a previous worker.', count)
    return count


def claim_next() -> Any | None:
    """
    Claim the next draft that is due, safely under concurrent workers.

    Uses a conditional UPDATE rather than ``select_for_update(skip_locked=True)``
    — SQLite raises ``NotSupportedError`` for row-level lock options, and this
    approach is race-free on every backend: only one worker's UPDATE can match
    the still-claimable row, and the loser simply tries the next draft.

    Drafts whose album is still arriving are skipped, so a six-photo Telegram
    post is not parsed after the first photo lands and left missing the rest.
    """
    from django.db.models import F

    from Hub.models import ProductDraft

    now = timezone.now()
    settled_before = now - timedelta(seconds=settle_seconds())

    pair_deadline = now - timedelta(seconds=pair_window_seconds())

    candidates = (
        ProductDraft.objects.filter(
            status__in=ProductDraft.CLAIMABLE_STATUSES,
            last_message_at__lte=settled_before,
        )
        .filter(_due(now))
        .order_by('created_at')[:20]
    )

    for draft in candidates:
        # A draft missing either half is probably one of a photo/description
        # pair that has not fully arrived. Hold it for the pairing window so
        # ingest can join them, rather than publishing two half-products.
        if draft.last_message_at > pair_deadline and _is_half_complete(draft):
            continue

        claimed = ProductDraft.objects.filter(
            pk=draft.pk, status__in=ProductDraft.CLAIMABLE_STATUSES
        ).update(
            status=ProductDraft.STATUS_PROCESSING,
            claimed_at=now,
            attempts=F('attempts') + 1,
            updated_at=now,
        )
        if claimed:
            return ProductDraft.objects.get(pk=draft.pk)

    return None


def _is_half_complete(draft: Any) -> bool:
    """True when a draft has text but no media, or media but no text."""
    has_text = bool((draft.raw_text or '').strip())
    has_files = draft.images.exists() or draft.videos.exists()
    return has_text != has_files


def _due(now: Any) -> Any:
    """``next_attempt_at`` is null (never tried) or already in the past."""
    from django.db.models import Q

    return Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)


def reschedule(draft: Any, error: str) -> None:
    """Back off and requeue, or mark permanently failed once retries run out."""
    from Hub.models import ProductDraft

    if draft.attempts >= max_attempts():
        draft.status = ProductDraft.STATUS_FAILED
        draft.next_attempt_at = None
        draft.last_error = error[:2000]
        draft.log_event('worker', f'Giving up after {draft.attempts} attempts: {error}', level='error', save=False)
        logger.error('[pipeline] Draft %s failed permanently: %s', draft.pk, error)
    else:
        delay = BACKOFF_MINUTES[min(draft.attempts - 1, len(BACKOFF_MINUTES) - 1)]
        draft.status = ProductDraft.STATUS_QUEUED
        draft.next_attempt_at = timezone.now() + timedelta(minutes=delay)
        draft.last_error = error[:2000]
        draft.log_event('worker', f'Attempt {draft.attempts} failed, retrying in {delay}m: {error}',
                        level='warning', save=False)
        logger.warning('[pipeline] Draft %s retrying in %dm: %s', draft.pk, delay, error)

    draft.claimed_at = None
    draft.save(update_fields=['status', 'next_attempt_at', 'last_error', 'claimed_at', 'events', 'updated_at'])


# --------------------------------------------------------------------------
# Processing
# --------------------------------------------------------------------------

def process_draft(draft: Any) -> Any:
    """
    Run the full AI + image pipeline over one claimed draft.

    Leaves the draft in ``PENDING`` (ready for approval) or ``DUPLICATE``.
    Raises on failure so the caller can apply the retry policy — the draft is
    never left half-processed in a terminal state.
    """
    from Hub.models import ProductDraft

    draft.log_event('pipeline', 'Processing started.', save=False)

    # --- 1. AI client (optional) -------------------------------------------
    client = None
    if is_configured():
        try:
            client = get_client()
            draft.log_event('pipeline', f'Using AI provider: {active_provider()}.', save=False)
        except AIUnavailable as exc:
            draft.log_event('pipeline', f'AI disabled: {exc}', level='warning', save=False)
    else:
        draft.log_event(
            'pipeline',
            'No AI key configured (GEMINI_API_KEY or ANTHROPIC_API_KEY) — '
            'using rule-based extraction only.',
            level='warning',
            save=False,
        )

    images = list(draft.images.all().order_by('order', 'id'))

    # --- 2. Vision ----------------------------------------------------------
    findings: dict = {}
    if images and client is not None:
        findings = analyse_images(client, images, context=draft.raw_text)
        draft.log_event(
            'vision',
            f'Analysed {findings.get("_analysed_count", 0)}/{len(images)} image(s).'
            if findings else 'Image analysis unavailable; using positional fallback.',
            save=False,
        )
    apply_to_images(images, findings)

    # --- 3. Extraction ------------------------------------------------------
    record, used_ai = extract(
        raw_text=draft.raw_text,
        client=client,
        image_findings=findings or None,
        source_label=draft.get_source_display(),
    )
    draft.parsed = record
    draft.log_event('extraction', f'Extracted via {"AI" if used_ai else "rules"}: "{record.get("name")}".', save=False)

    if client is not None:
        draft.ai_model = client.model
        draft.ai_tokens_used = (draft.ai_tokens_used or 0) + client.total_tokens

    # --- 4. Category suggestion --------------------------------------------
    draft.ai_suggestions = {
        'category': record.get('suggested_category', ''),
        'sub_category': record.get('suggested_sub_category', ''),
        'confidence': record.get('category_confidence', 'low'),
        'reasoning': record.get('category_reasoning', ''),
    }
    # Pre-select the suggestion so approval is usually a single click, while
    # leaving the admin free to change it.
    if not draft.category and record.get('suggested_category'):
        draft.category = record['suggested_category']
    if not draft.sub_category and record.get('suggested_sub_category'):
        draft.sub_category = record['suggested_sub_category'][:100]

    # --- 5. Image post-processing ------------------------------------------
    if images:
        stats = process_draft_images(draft, slug=suggested_slug(record))
        draft.log_event(
            'images',
            f'Kept {stats.get("kept", 0)}/{stats.get("total", 0)}; '
            f'removed {stats.get("duplicates_removed", 0)} duplicate(s); '
            f'compressed {stats.get("compressed", 0)}.',
            save=False,
        )

    # --- 6. Duplicate guard -------------------------------------------------
    draft.refresh_from_db(fields=['id'])
    match = find_duplicate(draft, record)
    if match is not None:
        draft.status = ProductDraft.STATUS_DUPLICATE
        draft.duplicate_of = match.product
        draft.duplicate_reasons = match.reasons
        draft.log_event(
            'duplicates',
            f'Possible duplicate of product #{match.product.pk} (score {match.score}).',
            level='warning',
            save=False,
        )
    else:
        draft.status = ProductDraft.STATUS_PENDING
        draft.duplicate_of = None
        draft.duplicate_reasons = []

    draft.last_error = ''
    draft.next_attempt_at = None
    draft.claimed_at = None
    draft.log_event('pipeline', f'Ready for review ({draft.get_status_display()}).', save=False)
    draft.save()

    return draft


def process_once() -> bool:
    """
    Claim and process a single draft.

    Returns ``True`` if work was done, ``False`` when the queue was empty.
    """
    draft = claim_next()
    if draft is None:
        return False

    try:
        process_draft(draft)
    except Exception as exc:  # noqa: BLE001 - the retry policy handles everything
        logger.exception('[pipeline] Draft %s raised during processing', draft.pk)
        reschedule(draft, f'{type(exc).__name__}: {exc}')
    return True
