"""
Creative Library
================

One row per generated marketing banner. This is the audit trail for the
daily-banner pipeline: what was generated, what copy went with it, whether
it was approved/rejected/regenerated via Telegram, and (once campaign
tracking exists) how it performed. Deliberately separate from
``models_product_automation`` — a creative is marketing output, not a
product-intake draft, even though both flow through Telegram.
"""
from __future__ import annotations

from django.db import models


class CreativeAsset(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    product = models.ForeignKey('Hub.Product', on_delete=models.CASCADE, related_name='creative_assets')

    #: Path relative to MEDIA_ROOT, e.g. "social_banners/2026-08-07_54_xyz.png".
    image_path = models.CharField(max_length=500)
    theme_name = models.CharField(max_length=50, blank=True)

    headline = models.CharField(max_length=200, blank=True)
    caption = models.TextField(blank=True)
    hashtags = models.CharField(max_length=500, blank=True, help_text='Comma-separated, without #')
    cta_text = models.CharField(max_length=100, blank=True)
    ai_provider = models.CharField(max_length=30, blank=True, help_text='Which AI provider wrote the copy, if any')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    regenerated_from = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='regenerations'
    )

    telegram_chat_id = models.CharField(max_length=64, blank=True)
    telegram_message_id = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.product.name} — {self.get_status_display()}'

    @property
    def hashtag_list(self) -> list[str]:
        return [h.strip() for h in self.hashtags.split(',') if h.strip()]
