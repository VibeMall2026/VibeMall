"""
Product Automation — staging models
===================================

Holds inbound product submissions (Telegram today; WhatsApp/CSV/Shopify later)
between ingestion and admin approval.

Nothing here writes to the live catalogue. A ``ProductDraft`` is converted into
a real ``Product`` (plus ``ProductImage`` / ``ProductVariant`` / ``ProductSEO``
rows) only when an admin approves it, inside a single transaction — see
``Hub.automation.publisher``.

Design notes
------------
* The draft *is* the job queue. ``status`` + ``next_attempt_at`` + ``attempts``
  let the worker (``manage.py process_product_drafts``) claim, retry and
  back off without any extra broker. This suits the project's SQLite database
  and Windows host, where Celery/Redis would be new infrastructure.
* ``source`` + ``source_message_id`` is unique, so re-delivering the same
  Telegram update can never create a second draft.
* Telegram albums arrive as several separate updates sharing a
  ``media_group_id``. Images are appended to the existing draft and
  ``last_message_at`` is bumped; the worker waits for the group to settle
  before parsing. See ``AUTOMATION_ALBUM_SETTLE_SECONDS``.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def draft_image_upload_to(instance: "ProductDraftImage", filename: str) -> str:
    """Store staged images away from the live ``products/`` media tree."""
    return f"product_drafts/{instance.draft.reference}/{filename}"


def draft_video_upload_to(instance: "ProductDraftVideo", filename: str) -> str:
    """Store staged videos away from the live ``reels/`` media tree."""
    return f"product_drafts/{instance.draft.reference}/videos/{filename}"


def draft_thumbnail_upload_to(instance: "ProductDraftVideo", filename: str) -> str:
    return f"product_drafts/{instance.draft.reference}/videos/thumbs/{filename}"


class ProductDraft(models.Model):
    """An inbound product awaiting AI processing and admin approval."""

    # --- Sources -----------------------------------------------------------
    SOURCE_TELEGRAM = 'telegram'
    SOURCE_WHATSAPP = 'whatsapp'
    SOURCE_CSV = 'csv'
    SOURCE_EXCEL = 'excel'
    SOURCE_API = 'api'
    SOURCE_CHOICES = [
        (SOURCE_TELEGRAM, 'Telegram'),
        (SOURCE_WHATSAPP, 'WhatsApp'),
        (SOURCE_CSV, 'CSV Import'),
        (SOURCE_EXCEL, 'Excel Import'),
        (SOURCE_API, 'Supplier API'),
    ]

    # --- Lifecycle ---------------------------------------------------------
    STATUS_RECEIVED = 'RECEIVED'        # raw message stored, album may still be arriving
    STATUS_QUEUED = 'QUEUED'            # ready for the worker to pick up
    STATUS_PROCESSING = 'PROCESSING'    # claimed by a worker
    STATUS_PENDING = 'PENDING'          # AI done — waiting for admin approval
    STATUS_DUPLICATE = 'DUPLICATE'      # matches an existing product
    STATUS_PUBLISHED = 'PUBLISHED'      # approved; live Product created
    STATUS_REJECTED = 'REJECTED'        # admin discarded it
    STATUS_FAILED = 'FAILED'            # retries exhausted
    STATUS_CHOICES = [
        (STATUS_RECEIVED, 'Received'),
        (STATUS_QUEUED, 'Queued'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_DUPLICATE, 'Possible Duplicate'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_FAILED, 'Failed'),
    ]

    #: Statuses the worker is allowed to claim.
    CLAIMABLE_STATUSES = (STATUS_RECEIVED, STATUS_QUEUED)

    reference = models.CharField(
        max_length=36,
        unique=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Stable identifier used for media paths and log correlation",
    )

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_TELEGRAM)
    source_chat_id = models.CharField(max_length=100, blank=True, default='')
    source_message_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Provider message id — makes re-delivery idempotent",
    )
    source_group_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_index=True,
        help_text="Telegram media_group_id: album parts share one draft",
    )
    source_author = models.CharField(max_length=150, blank=True, default='')

    raw_text = models.TextField(blank=True, default='', help_text="Supplier message exactly as received")
    raw_payload = models.JSONField(default=dict, blank=True, help_text="Full provider payload for replay/debugging")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RECEIVED, db_index=True)

    # --- AI output ---------------------------------------------------------
    parsed = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured attributes extracted from the message (see automation.ai.schema)",
    )
    ai_suggestions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Suggested category/sub-category with confidence and reasoning",
    )
    ai_model = models.CharField(max_length=80, blank=True, default='')
    ai_tokens_used = models.PositiveIntegerField(default=0)

    # --- Admin-supplied on approval ---------------------------------------
    category = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Chosen by the admin at approval time",
    )
    sub_category = models.CharField(max_length=100, blank=True, default='')

    # --- Results -----------------------------------------------------------
    published_product = models.ForeignKey(
        'Hub.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_drafts',
    )
    duplicate_of = models.ForeignKey(
        'Hub.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicate_drafts',
        help_text="Existing product this draft appears to duplicate",
    )
    duplicate_reasons = models.JSONField(default=list, blank=True)

    # --- Queue bookkeeping -------------------------------------------------
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    events = models.JSONField(default=list, blank=True, help_text="Append-only processing audit trail")

    last_message_at = models.DateTimeField(
        default=timezone.now,
        help_text="Bumped as album parts arrive; parsing waits for this to settle",
    )
    intake_closed = models.BooleanField(
        default=False,
        help_text=(
            "Set once the description has arrived for photos already staged. "
            "Suppliers send photos, then the description, then the next "
            "product — so a closed draft is a finished item and the next "
            "message starts a new one."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_product_drafts'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Product Draft'
        verbose_name_plural = 'Product Drafts'
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'source_message_id'],
                condition=~models.Q(source_message_id=''),
                name='uniq_draft_per_source_message',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'next_attempt_at']),
            models.Index(fields=['source', 'source_group_id']),
        ]

    def __str__(self) -> str:
        return f"{self.get_source_display()} draft #{self.pk} — {self.display_name}"

    # -- Convenience --------------------------------------------------------

    @property
    def display_name(self) -> str:
        """Best available product name, falling back to a snippet of raw text."""
        name = (self.parsed or {}).get('name')
        if name:
            return str(name)
        snippet = (self.raw_text or '').strip().splitlines()
        return snippet[0][:80] if snippet else '(no text)'

    @property
    def is_editable(self) -> bool:
        """Can an admin still act on this draft?"""
        return self.status in (self.STATUS_PENDING, self.STATUS_DUPLICATE, self.STATUS_FAILED)

    def attr(self, key: str, default: Any = '') -> Any:
        """Read a single extracted attribute."""
        return (self.parsed or {}).get(key, default)

    def log_event(self, stage: str, message: str, *, level: str = 'info', save: bool = True) -> None:
        """Append to the audit trail. Kept bounded so a retry loop can't bloat the row."""
        entry = {
            'at': timezone.now().isoformat(),
            'stage': stage,
            'level': level,
            'message': str(message)[:1000],
        }
        events = list(self.events or [])
        events.append(entry)
        self.events = events[-100:]
        if save:
            self.save(update_fields=['events', 'updated_at'])


class ProductDraftImage(models.Model):
    """A staged image belonging to a draft, already classified by role and colour."""

    ROLE_MAIN = 'main'
    ROLE_GALLERY = 'gallery'
    ROLE_DESCRIPTION = 'description'
    ROLE_CHOICES = [
        (ROLE_MAIN, 'Main Product Image'),
        (ROLE_GALLERY, 'Gallery Image'),
        (ROLE_DESCRIPTION, 'Description Image'),
    ]

    draft = models.ForeignKey(ProductDraft, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=draft_image_upload_to)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_GALLERY)
    color = models.CharField(max_length=100, blank=True, default='', help_text="Detected colour variant")
    alt_text = models.CharField(max_length=255, blank=True, default='')
    order = models.PositiveIntegerField(default=0)

    phash = models.CharField(
        max_length=64,
        blank=True,
        default='',
        db_index=True,
        help_text="Perceptual hash — used for near-duplicate detection",
    )

    # Suppliers (Meesho and similar) burn a catalogue code into a strip along
    # the bottom of every photo. Cropping is stored as intent rather than
    # applied to the file, so the admin can adjust or undo it right up until
    # approval; the publisher bakes it in when the product goes live.
    crop_bottom_px = models.PositiveIntegerField(
        default=0,
        help_text="Pixels trimmed from the bottom when published (0 = no crop)",
    )
    suggested_crop_bottom_px = models.PositiveIntegerField(
        default=0,
        help_text="Auto-detected height of the supplier code strip",
    )
    source_file_id = models.CharField(max_length=200, blank=True, default='')
    analysis = models.JSONField(default=dict, blank=True, help_text="Raw vision output for this image")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Product Draft Image'
        verbose_name_plural = 'Product Draft Images'
        indexes = [models.Index(fields=['draft', 'role'])]

    def __str__(self) -> str:
        label = self.color or 'default'
        return f"Draft {self.draft_id} — {self.get_role_display()} ({label})"


class ProductDraftVideo(models.Model):
    """
    A staged video that becomes a ``Reel`` when the product is approved.

    Suppliers send product videos alongside photos. Rather than a separate
    upload step in the admin, a video sent to the bot is staged here and, on
    approval, written to the existing ``Reel`` model already linked to
    ``Product`` for watch-and-shop.
    """

    draft = models.ForeignKey(ProductDraft, on_delete=models.CASCADE, related_name='videos')
    video = models.FileField(upload_to=draft_video_upload_to)
    thumbnail = models.ImageField(upload_to=draft_thumbnail_upload_to, blank=True, null=True)

    title = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Reel title; falls back to the product name on approval",
    )
    duration = models.PositiveIntegerField(default=0, help_text="Seconds, as reported by Telegram")
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    size_bytes = models.PositiveBigIntegerField(default=0)

    create_reel = models.BooleanField(
        default=True,
        help_text="Create a Reel for this video when the product is approved",
    )
    publish_reel = models.BooleanField(
        default=False,
        help_text="Publish the Reel immediately (otherwise it is created unpublished)",
    )

    source_file_id = models.CharField(max_length=200, blank=True, default='')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Product Draft Video'
        verbose_name_plural = 'Product Draft Videos'

    def __str__(self) -> str:
        return f"Draft {self.draft_id} — video {self.order}"

    @property
    def size_mb(self) -> float:
        return round((self.size_bytes or 0) / (1024 * 1024), 1)
