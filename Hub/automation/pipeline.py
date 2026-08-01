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

from .ai import AIUnavailable, active_provider, get_client, get_vision_client, is_configured
from .ai.extraction import extract, suggested_slug
from .ai.vision import analyse_images, apply_to_images
from .duplicates import find_duplicate
from .images import process_draft_images
from .ingest import (
    group_quiet_seconds,
    pair_window_seconds,
    price_window_seconds,
    settle_seconds,
)

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
    quiet_deadline = now - timedelta(seconds=group_quiet_seconds())
    price_deadline = now - timedelta(seconds=price_window_seconds())

    candidates = (
        ProductDraft.objects.filter(
            status__in=ProductDraft.CLAIMABLE_STATUSES,
            last_message_at__lte=settled_before,
        )
        .filter(_due(now))
        .order_by('created_at')[:20]
    )

    for draft in candidates:
        # A closed draft is finished — the rate arrived, or the next product
        # started. Nothing more can join, so there is nothing to wait for, and
        # claiming it now takes it out of the claimable window as well.
        if not draft.intake_closed:
            # Photos and a description, but no rate yet. Suppliers who price
            # separately send it moments later; publishing before it lands
            # would cost the admin the one number they cannot look up.
            if draft.awaiting_rate and draft.last_message_at > price_deadline:
                continue

            # Messages sent one at a time need a longer pause than an album,
            # which arrives in a single burst. Processing a chat draft the
            # moment a photo lands would strand the ones still being sent.
            if not draft.source_group_id and draft.last_message_at > quiet_deadline:
                continue

            # Still missing a half — probably one of a photo/description pair
            # that has not fully arrived. Hold it for the pairing window so
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


def separate_price_is_cost() -> bool:
    """
    Whether a separately-sent rate is what this shop *pays*, not what it charges.

    Defaults to True. A supplier who sends the catalogue text and then the rate
    is quoting their own price, which is this shop's cost — the number the
    margin calculation starts from. Set ``AUTOMATION_SEPARATE_PRICE_IS_COST``
    to false to treat it as the selling price instead.
    """
    return bool(getattr(settings, 'AUTOMATION_SEPARATE_PRICE_IS_COST', True))


def _apply_follow_up_price(draft: Any, record: dict) -> None:
    """
    Place a rate that arrived as its own message.

    It is deliberately not merged with the prices found inside the catalogue
    text: those are the supplier's MRP, this one is the deal. Recorded loudly
    in the warnings so the admin sees which box it filled rather than
    discovering it in a profit report later.
    """
    price = (getattr(draft, 'follow_up_price', '') or '').strip()
    if not price:
        return

    if separate_price_is_cost():
        record['base_price'] = price
        record.setdefault('warnings', []).append(
            f'Rate Rs.{price} was sent separately and recorded as your COST. '
            'Add your margin to set the selling price.'
        )
    else:
        record['price'] = price
        record.setdefault('warnings', []).append(
            f'Rate Rs.{price} was sent separately and recorded as the SELLING price.'
        )


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
    # A separate acquisition from the extraction client below: they do not
    # have to be the same provider. Groq is fast and free for text but has no
    # vision model on the free tier, so a Groq-primary setup still gets a
    # real vision pass from whichever configured provider can see images
    # (Gemini today) — see ai.get_vision_client.
    findings: dict = {}
    if images and client is not None:
        vision_client = get_vision_client()
        if getattr(vision_client, 'supports_vision', True):
            findings = analyse_images(vision_client, images, context=draft.raw_text)
            draft.log_event(
                'vision',
                f'Analysed {findings.get("_analysed_count", 0)}/{len(images)} image(s) '
                f'via {vision_client.model}.'
                if findings else 'Image analysis unavailable; using positional fallback.',
                save=False,
            )
        else:
            # No configured provider can read images; sending them would waste
            # a request and return nothing useful.
            draft.log_event(
                'vision',
                f'{client.model} is text-only and no vision-capable provider is '
                'configured — image roles and colours use the positional fallback.',
                level='warning',
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
    _apply_follow_up_price(draft, record)

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
    from django.db import DatabaseError, transaction

    from Hub.models import ProductDraft

    draft = claim_next()
    if draft is None:
        return False

    try:
        process_draft(draft)
    except ProductDraft.DoesNotExist:
        # The row was deleted out from under a claimed draft - an admin
        # clearing the queue mid-process, most likely (bulk-delete now
        # refuses PROCESSING rows, but an already-in-flight request from
        # before that guard, or a direct DB edit, can still hit this).
        # Nothing to save; log and move on rather than falling into the
        # generic handler below, which would try to reschedule a row that
        # no longer exists.
        logger.warning('[pipeline] Draft %s was deleted while being processed; skipping.', draft.pk)
    except Exception as exc:  # noqa: BLE001 - the retry policy handles everything
        logger.exception('[pipeline] Draft %s raised during processing', draft.pk)
        try:
            # A savepoint, not a bare call: save(update_fields=...) on a row
            # that no longer exists raises DatabaseError("Save with
            # update_fields did not affect any rows"), and a failed query
            # leaves the connection refusing every further query until
            # something rolls it back to a known point - the caller's loop
            # over the next draft would fail too, not just this one.
            with transaction.atomic():
                reschedule(draft, f'{type(exc).__name__}: {exc}')
        except DatabaseError:
            # Django only refuses the silent INSERT fallback here, it does
            # not re-check existence first - so this is the same "deleted
            # mid-process" cause as the DoesNotExist branch above, just
            # surfacing one step later. This used to bury that cause behind
            # a confusing second traceback instead of resolving cleanly.
            logger.warning('[pipeline] Draft %s was deleted while being processed; skipping.', draft.pk)
    return True
