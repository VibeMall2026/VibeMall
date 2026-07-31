"""
Telegram Bot API source
=======================

Long-polls ``getUpdates`` and yields one :class:`IncomingProduct` per message.

Album handling
--------------
The Bot API has no "album" update. A post with six photos is six separate
updates that share a ``media_group_id``, and only one of them carries the
caption. We do *not* buffer them in memory — each update is yielded
immediately with its ``group_id`` set, and :mod:`Hub.automation.ingest` merges
them into a single draft. That keeps album assembly durable across restarts.

Photo sizes
-----------
Telegram sends several rescaled versions of each photo. We take the last entry
in ``message.photo`` (largest) but skip anything over
``AUTOMATION_MAX_IMAGE_BYTES`` so a rogue upload cannot exhaust memory.

Offset persistence
------------------
``getUpdates`` acknowledges by offset. The offset is written to a small file so
a restart does not reprocess the last batch — and even if it does,
``ingest()`` is idempotent on ``(source, message_id)``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterable

import requests
from django.conf import settings

from Hub.models import ProductDraft

from .base import IncomingMedia, IncomingProduct, ProductSource

logger = logging.getLogger(__name__)

API_ROOT = 'https://api.telegram.org'

#: Documents with these MIME types are treated as product images.
IMAGE_MIME_PREFIXES = ('image/',)

#: Documents with these MIME types become Reels on approval.
VIDEO_MIME_PREFIXES = ('video/',)

#: A bare bot command such as ``/start`` or ``/help@VibeMallBot``. Users press
#: Start before their first message, and that must not become a draft.
BOT_COMMAND = re.compile(r'^/[A-Za-z0-9_]{1,32}(@[A-Za-z0-9_]+)?\s*$')


class TelegramConfigError(RuntimeError):
    """Raised when the bot token is missing or obviously malformed."""


class TelegramBotSource(ProductSource):
    """Reads product posts from Telegram via the Bot API."""

    name = ProductDraft.SOURCE_TELEGRAM

    def __init__(
        self,
        token: str | None = None,
        *,
        allowed_chats: Iterable[str] | None = None,
        long_poll_seconds: int = 25,
        offset_path: Path | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.token = (token or getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or '').strip()
        if not self.token or ':' not in self.token:
            raise TelegramConfigError(
                'TELEGRAM_BOT_TOKEN is missing or malformed. Set it in .env — '
                'never hardcode it.'
            )

        configured = allowed_chats if allowed_chats is not None else getattr(
            settings, 'TELEGRAM_ALLOWED_CHAT_IDS', []
        )
        #: Empty set means "accept every chat the bot can see".
        self.allowed_chats = {str(c).strip() for c in configured if str(c).strip()}

        self.long_poll_seconds = long_poll_seconds
        self.max_image_bytes = int(getattr(settings, 'AUTOMATION_MAX_IMAGE_BYTES', 12 * 1024 * 1024))
        # Telegram's Bot API refuses getFile above 20 MB, so there is no point
        # allowing a larger ceiling here.
        self.max_video_bytes = int(getattr(settings, 'AUTOMATION_MAX_VIDEO_BYTES', 20 * 1024 * 1024))
        self.offset_path = offset_path or Path(
            getattr(settings, 'TELEGRAM_OFFSET_FILE', settings.BASE_DIR / 'logs' / 'telegram_offset.json')
        )
        self.session = session or requests.Session()
        self._offset = self._load_offset()
        #: Where the offset moves to once the caller confirms the batch landed.
        self._pending_offset = self._offset
        #: Reasons updates were discarded during the last poll. Surfaced by the
        #: management command so "nothing arrived" is never a silent outcome.
        self.skipped: list[str] = []

    # -- Offset persistence -------------------------------------------------

    def _load_offset(self) -> int:
        try:
            return int(json.loads(self.offset_path.read_text(encoding='utf-8'))['offset'])
        except Exception:
            return 0

    def _save_offset(self, offset: int) -> None:
        try:
            self.offset_path.parent.mkdir(parents=True, exist_ok=True)
            self.offset_path.write_text(json.dumps({'offset': offset}), encoding='utf-8')
        except OSError as exc:
            # Losing the offset only costs us idempotent reprocessing.
            logger.warning('[telegram] Could not persist update offset: %s', exc)

    # -- HTTP helpers -------------------------------------------------------

    def _api(self, method: str, **params: Any) -> Any:
        url = f'{API_ROOT}/bot{self.token}/{method}'
        response = self.session.get(url, params=params, timeout=self.long_poll_seconds + 15)
        response.raise_for_status()
        payload = response.json()
        if not payload.get('ok'):
            raise RuntimeError(f"Telegram {method} failed: {payload.get('description')}")
        return payload.get('result')

    def _download(
        self, file_id: str, *, limit: int | None = None, label: str = 'image'
    ) -> tuple[bytes, str] | None:
        """Resolve a ``file_id`` to its bytes. Returns ``None`` if unusable."""
        limit = limit if limit is not None else self.max_image_bytes
        try:
            meta = self._api('getFile', file_id=file_id)
        except Exception as exc:
            # The Bot API refuses getFile above 20 MB, which is the usual reason
            # a supplier's video does not arrive. Say so plainly.
            message = str(exc)
            if 'too big' in message.lower() or 'file is too big' in message.lower():
                self.skipped.append(
                    f'{label} is larger than Telegram\'s 20 MB bot limit - '
                    'compress it or send a shorter clip'
                )
            else:
                self.skipped.append(f'{label} could not be fetched from Telegram ({message[:80]})')
            logger.warning('[telegram] getFile failed for %s: %s', file_id, exc)
            return None

        size = int(meta.get('file_size') or 0)
        if size and size > limit:
            self.skipped.append(
                f'{label} is {size // (1024 * 1024)} MB, over the configured '
                f'{limit // (1024 * 1024)} MB limit'
            )
            logger.warning('[telegram] Skipping %s: %d bytes exceeds limit', file_id, size)
            return None

        path = meta.get('file_path') or ''
        url = f'{API_ROOT}/file/bot{self.token}/{path}'
        try:
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()
            data = response.content
        except Exception as exc:
            logger.warning('[telegram] Download failed for %s: %s', file_id, exc)
            return None

        if len(data) > limit:
            logger.warning('[telegram] Skipping %s: downloaded %d bytes exceeds limit', file_id, len(data))
            return None

        filename = Path(path).name or f'{file_id}.jpg'
        return data, filename

    # -- Message parsing ----------------------------------------------------

    def _collect_media(self, message: dict[str, Any]) -> list[IncomingMedia]:
        """Pull the largest photo, or an image document, out of a message."""
        media: list[IncomingMedia] = []

        photos = message.get('photo') or []
        if photos:
            # Telegram orders photo sizes smallest -> largest.
            largest = photos[-1]
            downloaded = self._download(largest.get('file_id', ''))
            if downloaded:
                data, filename = downloaded
                media.append(
                    IncomingMedia(
                        data=data,
                        filename=filename,
                        source_file_id=largest.get('file_unique_id') or largest.get('file_id', ''),
                    )
                )

        # Videos: `video` for normal uploads, `animation` for GIF-style clips.
        for key in ('video', 'animation'):
            clip = message.get(key) or {}
            if not clip:
                continue
            downloaded = self._download(
                clip.get('file_id', ''), limit=self.max_video_bytes, label='video'
            )
            if not downloaded:
                continue
            data, filename = downloaded
            media.append(
                IncomingMedia(
                    data=data,
                    filename=clip.get('file_name') or filename,
                    source_file_id=clip.get('file_unique_id') or clip.get('file_id', ''),
                    kind=IncomingMedia.KIND_VIDEO,
                    duration=int(clip.get('duration') or 0),
                    width=int(clip.get('width') or 0),
                    height=int(clip.get('height') or 0),
                )
            )

        document = message.get('document') or {}
        mime = (document.get('mime_type') or '').lower()
        if document and (mime.startswith(IMAGE_MIME_PREFIXES) or mime.startswith(VIDEO_MIME_PREFIXES)):
            is_video = mime.startswith(VIDEO_MIME_PREFIXES)
            downloaded = self._download(
                document.get('file_id', ''),
                limit=self.max_video_bytes if is_video else self.max_image_bytes,
                label='video' if is_video else 'image',
            )
            if downloaded:
                data, filename = downloaded
                media.append(
                    IncomingMedia(
                        data=data,
                        filename=document.get('file_name') or filename,
                        source_file_id=document.get('file_unique_id') or document.get('file_id', ''),
                        kind=IncomingMedia.KIND_VIDEO if is_video else IncomingMedia.KIND_IMAGE,
                    )
                )

        return media

    @staticmethod
    def _author(message: dict[str, Any]) -> str:
        sender = message.get('from') or {}
        username = sender.get('username')
        if username:
            return f'@{username}'
        name = ' '.join(filter(None, [sender.get('first_name'), sender.get('last_name')]))
        return name or (message.get('sender_chat') or {}).get('title', '') or ''

    def _to_incoming(self, update: dict[str, Any]) -> IncomingProduct | None:
        message = (
            update.get('message')
            or update.get('channel_post')
            or update.get('edited_message')
            or update.get('edited_channel_post')
        )
        if not message:
            return None

        chat_id = str((message.get('chat') or {}).get('id', ''))
        if self.allowed_chats and chat_id not in self.allowed_chats:
            self.skipped.append(
                f'chat {chat_id} is not in TELEGRAM_ALLOWED_CHAT_IDS - add it to .env to accept it'
            )
            return None

        text = message.get('text') or message.get('caption') or ''
        media = self._collect_media(message)

        # "/start", "/help" and friends are chat plumbing, not products.
        if not media and BOT_COMMAND.match(text.strip()):
            self.skipped.append(f'bot command {text.strip()!r} (not a product)')
            return None

        if not text.strip() and not media:
            had_file = bool(
                message.get('photo') or message.get('document')
                or message.get('video') or message.get('animation')
            )
            # _download already recorded a specific reason for a failed fetch.
            if not had_file:
                self.skipped.append('message had no text, image or video')
            return None

        incoming = IncomingProduct(
            source=self.name,
            message_id=f"{chat_id}:{message.get('message_id')}",
            text=text,
            media=media,
            chat_id=chat_id,
            group_id=str(message.get('media_group_id') or ''),
            author=self._author(message),
            raw={
                'update_id': update.get('update_id'),
                'message_id': message.get('message_id'),
                'chat': message.get('chat'),
                'date': message.get('date'),
                'has_photo': bool(message.get('photo')),
            },
        )
        return incoming if incoming.has_content else None

    # -- ProductSource ------------------------------------------------------

    def poll(self) -> Iterable[IncomingProduct]:
        """One long-poll cycle. Never raises on transient failure."""
        self.skipped = []
        try:
            updates = self._api(
                'getUpdates',
                offset=self._offset,
                timeout=self.long_poll_seconds,
                allowed_updates=json.dumps(
                    ['message', 'channel_post', 'edited_message', 'edited_channel_post']
                ),
            ) or []
        except requests.Timeout:
            return []
        except Exception as exc:
            logger.warning('[telegram] getUpdates failed: %s', exc)
            return []

        results: list[IncomingProduct] = []
        highest = self._offset
        for update in updates:
            highest = max(highest, int(update.get('update_id', 0)) + 1)
            try:
                incoming = self._to_incoming(update)
            except Exception:
                logger.exception('[telegram] Failed to parse update %s', update.get('update_id'))
                continue
            if incoming:
                results.append(incoming)

        # Held, not saved. Acknowledging here would tell Telegram the batch was
        # handled before the caller has stored a single draft — and a failure
        # after that point loses the product for good, with the sender seeing
        # nothing wrong. The caller calls commit() once the batch is safe.
        self._pending_offset = highest
        return results

    def commit(self) -> None:
        """
        Acknowledge the batch returned by the last :meth:`poll`.

        Until this is called the offset stays where it was, so a crashed or
        failed cycle re-fetches the same updates on the next poll. Re-ingesting
        is harmless: ``(source, source_message_id)`` is unique, so a repeat is
        a no-op.
        """
        if self._pending_offset > self._offset:
            self._offset = self._pending_offset
            self._save_offset(self._offset)

    def skip_batch(self) -> None:
        """
        Give up on the current batch and move past it.

        Only for an update that fails every time — one poisonous message must
        not wedge the queue behind it forever.
        """
        self.commit()

    def describe(self) -> str:
        """Human-readable summary for the management command banner."""
        scope = ', '.join(sorted(self.allowed_chats)) if self.allowed_chats else 'all chats'
        return f'Telegram bot listening on {scope}'
