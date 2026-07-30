"""
Ingestion
=========

Converts an :class:`~Hub.automation.sources.base.IncomingProduct` into a
``ProductDraft`` row plus its staged images.

Two properties matter here:

* **Idempotency** — the same provider message can arrive twice (Telegram
  redelivers un-acked updates after a crash). ``(source, source_message_id)``
  is unique, so a repeat is a no-op.
* **Album grouping** — a Telegram post with six photos arrives as six separate
  updates sharing one ``media_group_id``. They must become *one* product, not
  six. We merge into the existing draft and push ``last_message_at`` forward;
  the worker will not start parsing until the group has been quiet for
  ``AUTOMATION_ALBUM_SETTLE_SECONDS``.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from Hub.models import ProductDraft, ProductDraftImage, ProductDraftVideo

from .sources.base import IncomingProduct

logger = logging.getLogger(__name__)

#: Hard ceiling on staged images per draft, so a runaway album cannot fill the disk.
MAX_IMAGES_PER_DRAFT = 40

#: Reels are heavy; a product rarely needs more than a handful.
MAX_VIDEOS_PER_DRAFT = 5


def _find_group_draft(incoming: IncomingProduct) -> ProductDraft | None:
    """Return the open draft this message belongs to, if it is part of an album."""
    if not incoming.group_id:
        return None
    return (
        ProductDraft.objects.filter(
            source=incoming.source,
            source_group_id=incoming.group_id,
            status__in=ProductDraft.CLAIMABLE_STATUSES,
        )
        .order_by('created_at')
        .first()
    )


def _find_pairable_draft(incoming: IncomingProduct) -> ProductDraft | None:
    """
    Find a recent draft from the same chat that this message completes.

    Suppliers forward a catalogue as *two* messages: the photo, then the
    description (often a forward from someone else). Neither carries a
    ``media_group_id``, so album grouping cannot join them, and the naive
    result is two useless half-products — one with an image and no text, one
    with text and no image.

    This pairs them: a text-only message merges into a recent image-only
    draft, and vice versa. The complementary requirement is deliberate — two
    photos, or two descriptions, are two different products and must not be
    merged.
    """
    if incoming.group_id:
        return None

    has_text = bool(incoming.text.strip())
    has_media = bool(incoming.media)
    # Only a message supplying exactly one half can complete another draft.
    if has_text == has_media:
        return None

    cutoff = timezone.now() - timedelta(seconds=pair_window_seconds())
    candidates = ProductDraft.objects.filter(
        source=incoming.source,
        source_chat_id=str(incoming.chat_id or ''),
        status__in=ProductDraft.CLAIMABLE_STATUSES,
        last_message_at__gte=cutoff,
    ).order_by('-last_message_at')[:5]

    for draft in candidates:
        draft_has_text = bool((draft.raw_text or '').strip())
        draft_has_files = draft.images.exists() or draft.videos.exists()
        if has_text and draft_has_files and not draft_has_text:
            return draft
        if has_media and draft_has_text and not draft_has_files:
            return draft

    return None


def _attach_videos(draft: ProductDraft, incoming: IncomingProduct) -> int:
    """Save inbound videos as staged reels. Returns how many were stored."""
    stored = 0
    existing = draft.videos.count()

    for media in incoming.media:
        if not media.is_video:
            continue
        if existing + stored >= MAX_VIDEOS_PER_DRAFT:
            break
        if media.source_file_id and draft.videos.filter(source_file_id=media.source_file_id).exists():
            continue

        video = ProductDraftVideo(
            draft=draft,
            source_file_id=media.source_file_id,
            duration=media.duration,
            width=media.width,
            height=media.height,
            size_bytes=len(media.data),
            order=existing + stored,
        )
        video.video.save(media.filename, ContentFile(media.data), save=False)
        video.save()
        stored += 1

    return stored


def _attach_media(draft: ProductDraft, incoming: IncomingProduct) -> int:
    """Save inbound images as staged photos. Returns how many were stored."""
    existing = draft.images.count()
    stored = 0

    for media in incoming.media:
        if media.is_video:
            continue
        if existing + stored >= MAX_IMAGES_PER_DRAFT:
            draft.log_event(
                'ingest',
                f'Image limit ({MAX_IMAGES_PER_DRAFT}) reached; ignoring further files.',
                level='warning',
                save=False,
            )
            break

        # Same provider file id already staged — a redelivery, not a new photo.
        if media.source_file_id and draft.images.filter(source_file_id=media.source_file_id).exists():
            continue

        image = ProductDraftImage(
            draft=draft,
            source_file_id=media.source_file_id,
            order=existing + stored,
        )
        image.image.save(media.filename, ContentFile(media.data), save=False)
        image.save()
        stored += 1

    return stored


@transaction.atomic
def ingest(incoming: IncomingProduct) -> ProductDraft | None:
    """
    Store an inbound product submission.

    Returns the draft it landed in, or ``None`` when the message carried nothing
    usable or was a duplicate delivery.
    """
    if not incoming.has_content:
        return None

    # --- Album continuation: merge into the draft already in flight ---------
    draft = _find_group_draft(incoming)
    if draft is not None:
        # Telegram puts the caption on whichever part of the album carries it —
        # usually the first, but do not rely on that.
        if incoming.text.strip() and not draft.raw_text.strip():
            draft.raw_text = incoming.text

        stored = _attach_media(draft, incoming)
        clips = _attach_videos(draft, incoming)
        draft.last_message_at = timezone.now()
        draft.log_event(
            'ingest', f'Album part merged (+{stored} image(s), +{clips} video(s)).', save=False
        )
        draft.save(update_fields=['raw_text', 'last_message_at', 'events', 'updated_at'])
        logger.info('[automation] Merged album part into draft %s (+%d images)', draft.pk, stored)
        return draft

    # --- Separate photo / description messages: join them ------------------
    partner = _find_pairable_draft(incoming)
    if partner is not None:
        if incoming.text.strip() and not partner.raw_text.strip():
            partner.raw_text = incoming.text
        stored = _attach_media(partner, incoming)
        stored += _attach_videos(partner, incoming)
        partner.last_message_at = timezone.now()
        partner.log_event(
            'ingest',
            f'Paired with a separate message (+{stored} image(s), '
            f'{"text added" if incoming.text.strip() else "images added"}).',
            save=False,
        )
        partner.save(update_fields=['raw_text', 'last_message_at', 'events', 'updated_at'])
        logger.info('[automation] Paired message into draft %s', partner.pk)
        return partner

    # --- New draft ---------------------------------------------------------
    try:
        with transaction.atomic():
            draft = ProductDraft.objects.create(
                source=incoming.source,
                source_chat_id=str(incoming.chat_id or ''),
                source_message_id=str(incoming.message_id or ''),
                source_group_id=str(incoming.group_id or ''),
                source_author=incoming.author or '',
                raw_text=incoming.text or '',
                raw_payload=incoming.raw or {},
                status=ProductDraft.STATUS_RECEIVED,
                last_message_at=timezone.now(),
            )
    except IntegrityError:
        # Unique (source, source_message_id) tripped — we already have this message.
        logger.info(
            '[automation] Ignoring duplicate delivery of %s message %s',
            incoming.source,
            incoming.message_id,
        )
        return None

    stored = _attach_media(draft, incoming)
    clips = _attach_videos(draft, incoming)
    draft.log_event(
        'ingest',
        f'Received from {incoming.source} with {stored} image(s) and {clips} video(s).',
        save=False,
    )
    draft.save(update_fields=['events', 'updated_at'])

    logger.info('[automation] Created draft %s from %s (%d images)', draft.pk, incoming.source, stored)
    return draft


def settle_seconds() -> int:
    """How long an album must be quiet before the worker treats it as complete."""
    return int(getattr(settings, 'AUTOMATION_ALBUM_SETTLE_SECONDS', 10))


def pair_window_seconds() -> int:
    """
    How long to keep accepting a partner message for a half-complete draft.

    Generous by design: forwarding a catalogue description after the photo
    takes a supplier a little while, and a product split in two is far more
    annoying than a draft that waits an extra minute.
    """
    return int(getattr(settings, 'AUTOMATION_PAIR_WINDOW_SECONDS', 180))
