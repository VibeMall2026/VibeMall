"""
Telegram delivery + approval for generated creatives.

Sends each ``CreativeAsset`` to Telegram with Approve / Reject / Regenerate
buttons, and processes the button press when it comes back.

Delivered via ``sendMessage`` with the image URL as the message text,
relying on Telegram's automatic link-preview to render the banner - NOT
``sendPhoto`` or ``sendDocument``. Confirmed by direct testing: every
media-transfer endpoint (sendPhoto with a file upload, sendPhoto with a
URL, sendDocument with a URL) hangs or connect-times-out from this
network, regardless of payload shape, while plain text endpoints
(sendMessage, answerCallbackQuery, editMessageText, getMe) all return in
under a second. That points at network-level filtering of Telegram's
media-fetch traffic specifically, which sendMessage's link preview
sidesteps entirely - it is still a plain text POST.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

API_ROOT = 'https://api.telegram.org'


def _token() -> str:
    return getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or ''


def _site_url() -> str:
    return getattr(settings, 'SITE_URL', 'https://vibemall.in').rstrip('/')


def _api(method: str, **payload: Any) -> dict[str, Any] | None:
    token = _token()
    if not token:
        return None
    try:
        resp = requests.post(f'{API_ROOT}/bot{token}/{method}', data=payload, timeout=20)
        data = resp.json()
        if not data.get('ok'):
            logger.warning('[creative_delivery] %s failed: %s', method, data.get('description'))
            return None
        return data.get('result')
    except Exception as exc:
        logger.warning('[creative_delivery] %s errored: %s', method, exc)
        return None


def _build_message_text(asset) -> str:
    """Image URL first so Telegram's link-preview attaches to it, then the
    copy. Telegram's text message limit is 4096 characters - comfortable
    headroom, unlike the 1024-char photo-caption limit we'd otherwise hit."""
    photo_url = f'{_site_url()}/media/{asset.image_path}'
    hashtag_text = ' '.join(f'#{h}' for h in asset.hashtag_list)
    parts = [photo_url, '', asset.headline, '', asset.caption, '', hashtag_text, '', f'CTA: {asset.cta_text}']
    text = '\n'.join(p for p in parts if p is not None)
    status_suffix = {
        'approved': '\n\n✅ APPROVED',
        'rejected': '\n\n❌ REJECTED',
    }.get(asset.status, '')
    text += status_suffix
    return text[:4096]


def _approval_keyboard(asset_id: int) -> dict[str, Any]:
    return {
        'inline_keyboard': [[
            {'text': '✅ Approve', 'callback_data': f'banner:{asset_id}:approve'},
            {'text': '❌ Reject', 'callback_data': f'banner:{asset_id}:reject'},
            {'text': '🔄 Regenerate', 'callback_data': f'banner:{asset_id}:regenerate'},
        ]]
    }


def send_for_approval(asset) -> bool:
    """Send (or resend) `asset` to Telegram with approval buttons."""
    chat_id = getattr(settings, 'DAILY_BANNER_CHAT_ID', '')
    if not chat_id:
        return False

    result = _api(
        'sendMessage',
        chat_id=chat_id,
        text=_build_message_text(asset),
        reply_markup=json.dumps(_approval_keyboard(asset.id)),
    )
    if not result:
        return False

    asset.telegram_chat_id = str((result.get('chat') or {}).get('id', chat_id))
    asset.telegram_message_id = str(result.get('message_id', ''))
    asset.save(update_fields=['telegram_chat_id', 'telegram_message_id'])
    return True


def _finalize(asset, status: str) -> None:
    asset.status = status
    asset.decided_at = timezone.now()
    asset.save(update_fields=['status', 'decided_at'])
    if asset.telegram_chat_id and asset.telegram_message_id:
        _api(
            'editMessageText',
            chat_id=asset.telegram_chat_id,
            message_id=asset.telegram_message_id,
            text=_build_message_text(asset),
        )
        _api(
            'editMessageReplyMarkup',
            chat_id=asset.telegram_chat_id,
            message_id=asset.telegram_message_id,
            reply_markup=json.dumps({'inline_keyboard': []}),
        )


def _regenerate(asset) -> None:
    from datetime import date
    from pathlib import Path

    from Hub.automation.marketing_copy import generate_copy
    from Hub.automation.social_banner import OUTPUT_DIR, compose_banner
    from Hub.models_creative import CreativeAsset

    if asset.telegram_chat_id and asset.telegram_message_id:
        _api(
            'editMessageReplyMarkup',
            chat_id=asset.telegram_chat_id,
            message_id=asset.telegram_message_id,
            reply_markup=json.dumps({'inline_keyboard': []}),
        )

    product = asset.product
    # Copy first: the CTA text it writes goes into the button on the banner
    # image itself, not just the caption.
    copy = generate_copy(product)

    filename = f'{date.today().isoformat()}_{product.id}_{product.slug or product.id}_r{asset.id}.png'
    output_path = OUTPUT_DIR / filename
    compose_banner(product, output_path, cta_text=copy['cta'])

    new_asset = CreativeAsset.objects.create(
        product=product,
        image_path=f'social_banners/{filename}',
        headline=copy['headline'],
        caption=copy['caption'],
        hashtags=','.join(copy['hashtags']),
        cta_text=copy['cta'],
        ai_provider=copy.get('provider', ''),
        regenerated_from=asset,
    )
    send_for_approval(new_asset)


def handle_callback(callback_query: dict[str, Any]) -> None:
    """Process one Approve/Reject/Regenerate button press."""
    from Hub.models_creative import CreativeAsset

    cq_id = callback_query.get('id', '')
    data = str(callback_query.get('data', ''))
    parts = data.split(':')
    if len(parts) != 3 or parts[0] != 'banner':
        _api('answerCallbackQuery', callback_query_id=cq_id)
        return

    _, asset_id_raw, action = parts
    try:
        asset = CreativeAsset.objects.select_related('product').get(id=int(asset_id_raw))
    except (CreativeAsset.DoesNotExist, ValueError):
        _api('answerCallbackQuery', callback_query_id=cq_id, text='This creative no longer exists.')
        return

    if asset.status != CreativeAsset.STATUS_PENDING:
        _api('answerCallbackQuery', callback_query_id=cq_id, text=f'Already {asset.status}.')
        return

    message = callback_query.get('message') or {}
    if not asset.telegram_chat_id:
        asset.telegram_chat_id = str((message.get('chat') or {}).get('id', ''))
    if not asset.telegram_message_id:
        asset.telegram_message_id = str(message.get('message_id', ''))

    if action == 'approve':
        _finalize(asset, CreativeAsset.STATUS_APPROVED)
        _api('answerCallbackQuery', callback_query_id=cq_id, text='Approved!')
    elif action == 'reject':
        _finalize(asset, CreativeAsset.STATUS_REJECTED)
        _api('answerCallbackQuery', callback_query_id=cq_id, text='Rejected.')
    elif action == 'regenerate':
        _api('answerCallbackQuery', callback_query_id=cq_id, text='Regenerating...')
        _regenerate(asset)
    else:
        _api('answerCallbackQuery', callback_query_id=cq_id)
