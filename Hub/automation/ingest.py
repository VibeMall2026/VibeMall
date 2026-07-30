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

from .parsing.rules import first_price, looks_like_price_message
from .sources.base import IncomingProduct

logger = logging.getLogger(__name__)


def max_images_per_draft() -> int:
    """Ceiling on staged images, so a runaway album cannot fill the disk."""
    return int(getattr(settings, 'AUTOMATION_MAX_IMAGES_PER_DRAFT', 40))


def max_videos_per_draft() -> int:
    """Reels are heavy; a product rarely needs more than a handful."""
    return int(getattr(settings, 'AUTOMATION_MAX_VIDEOS_PER_DRAFT', 5))


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


def _find_open_draft(incoming: IncomingProduct) -> ProductDraft | None:
    """
    Find the in-progress draft this message belongs to.

    Telegram only sets ``media_group_id`` when photos are posted as a single
    album. Suppliers routinely send fifteen photos one at a time, and a
    forwarded catalogue arrives as photo(s) plus a separate description
    message — none of which carry a group id. Treating each message as its own
    product turns one item into fifteen, and multiplies the AI cost by fifteen
    with it.

    So messages from the same chat are grouped by time instead, following the
    order suppliers actually send in — **photos, then the description, then the
    next product**:

    * photos join whatever draft is still open;
    * the description joins the draft those photos are in, and *closes* it;
    * anything after that — another photo or another description — belongs to
      the next product and starts a new draft.

    The description ends the *photos*, but not always the product: Meesho
    resellers send the rate as a third message. So a draft holding photos and a
    description stays open a little longer, and only a message that is nothing
    but a price may join it. Anything else — another photo, another caption —
    is the next product, and closes this one on its way past.

    ``intake_closed`` records that, because the order matters and cannot be
    re-derived later: a supplier who sends the description *first* is still
    mid-product, and their photos must keep joining.

    Only the most recent open draft is considered, which is what makes it work.
    """
    if incoming.group_id:
        return None

    now = timezone.now()
    has_text = bool(incoming.text.strip())

    candidate = (
        ProductDraft.objects.filter(
            source=incoming.source,
            source_chat_id=str(incoming.chat_id or ''),
            status__in=ProductDraft.CLAIMABLE_STATUSES,
            intake_closed=False,
            last_message_at__gte=now - timedelta(seconds=group_window_seconds()),
        )
        .order_by('-last_message_at')
        .first()
    )
    if candidate is None:
        return None

    candidate_has_text = bool((candidate.raw_text or '').strip())

    # The description has landed on top of its photos: only the rate may still
    # arrive. A draft whose description came *first* is not in this state —
    # there the photos are still on their way.
    if candidate.awaiting_rate:
        if has_text and looks_like_price_message(incoming.text):
            return candidate
        _close(candidate, 'The next product started.')
        return None

    # Two descriptions in a row mean two products.
    if has_text and candidate_has_text:
        return None

    # Description first, photos after — the reverse order. Still one product
    # while the photos keep coming, but only for as long as they keep coming.
    if not has_text and candidate_has_text:
        if (now - candidate.last_message_at).total_seconds() > burst_seconds():
            return None

    return candidate


def _close(draft: ProductDraft, reason: str) -> None:
    """Mark a draft final so nothing else can land on it."""
    if draft.intake_closed:
        return
    draft.intake_closed = True
    draft.log_event('ingest', f'Closed for new messages. {reason}', save=False)
    draft.save(update_fields=['intake_closed', 'events', 'updated_at'])


def _attach_videos(draft: ProductDraft, incoming: IncomingProduct) -> int:
    """Save inbound videos as staged reels. Returns how many were stored."""
    stored = 0
    existing = draft.videos.count()

    for media in incoming.media:
        if not media.is_video:
            continue
        if existing + stored >= max_videos_per_draft():
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
        if existing + stored >= max_images_per_draft():
            draft.log_event(
                'ingest',
                f'Image limit ({max_images_per_draft()}) reached; ignoring further files.',
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

        # Remaining album parts still merge on ``source_group_id``; this only
        # governs which *other* messages may land here once the caption exists.
        draft.awaiting_rate = bool(draft.raw_text.strip()) and draft.images.exists()

        draft.log_event(
            'ingest', f'Album part merged (+{stored} image(s), +{clips} video(s)).', save=False
        )
        draft.save(
            update_fields=['raw_text', 'last_message_at', 'awaiting_rate', 'events', 'updated_at']
        )
        logger.info('[automation] Merged album part into draft %s (+%d images)', draft.pk, stored)
        return draft

    # --- Consecutive messages for one product: join them -------------------
    partner = _find_open_draft(incoming)
    if partner is not None:
        text = incoming.text.strip()

        # The rate, sent as its own message. It is the last thing that arrives,
        # and it is kept apart from the catalogue text because it means
        # something different — see ``follow_up_price``.
        is_price = bool(text) and partner.raw_text.strip() and looks_like_price_message(text)

        if is_price:
            partner.follow_up_price = (first_price(text) or '')[:20]
            partner.raw_text = f'{partner.raw_text}\n{text}'.strip()
            partner.intake_closed = True
            partner.awaiting_rate = False
            note = f'Rate received separately: {partner.follow_up_price or text}. Product complete.'
        else:
            # A description landing on staged photos leaves only the rate
            # outstanding; anything else after this belongs to the next product.
            if text and partner.images.exists():
                partner.awaiting_rate = True

            if text and not partner.raw_text.strip():
                partner.raw_text = incoming.text
            images = _attach_media(partner, incoming)
            clips = _attach_videos(partner, incoming)
            note = (
                f'Grouped with the previous message (+{images} image(s), '
                f'+{clips} video(s)'
                f'{", description added" if text else ""}).'
            )

        partner.last_message_at = timezone.now()
        partner.log_event('ingest', note, save=False)
        partner.save(
            update_fields=[
                'raw_text', 'follow_up_price', 'last_message_at',
                'intake_closed', 'awaiting_rate', 'events', 'updated_at',
            ]
        )
        logger.info('[automation] Grouped message into draft %s', partner.pk)
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

    # A photo captioned with its description is a whole product in one message,
    # but the rate may still follow — so it waits for one rather than closing.
    draft.awaiting_rate = bool(incoming.text.strip()) and stored > 0 and not incoming.group_id

    draft.log_event(
        'ingest',
        f'Received from {incoming.source} with {stored} image(s) and {clips} video(s).',
        save=False,
    )
    draft.save(update_fields=['awaiting_rate', 'events', 'updated_at'])

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


def group_window_seconds() -> int:
    """How long a new message may still join the draft in progress."""
    return int(getattr(settings, 'AUTOMATION_GROUP_WINDOW_SECONDS', 180))


def burst_seconds() -> int:
    """
    Gap below which consecutive messages are still one burst.

    Used to decide whether media arriving after a description belongs to the
    same product ("text first, then photos") or starts the next one.
    """
    return int(getattr(settings, 'AUTOMATION_BURST_SECONDS', 30))


def price_window_seconds() -> int:
    """
    How long a photos-plus-description draft waits for a separate rate message.

    Meesho resellers send image -> description -> price, seconds apart. Waiting
    briefly costs nothing; publishing first would drop the one number the admin
    cannot recover from the catalogue text.
    """
    return int(getattr(settings, 'AUTOMATION_PRICE_WINDOW_SECONDS', 45))


def group_quiet_seconds() -> int:
    """
    How long a chat draft must be idle before the worker may process it.

    Sending fifteen photos by hand takes a while, and processing after the
    first one would strand the rest in a second draft. This is the pause that
    means "they have finished sending", so it is much longer than the
    album settle window — an album arrives in one burst, a human does not.
    """
    return int(getattr(settings, 'AUTOMATION_GROUP_QUIET_SECONDS', 45))
