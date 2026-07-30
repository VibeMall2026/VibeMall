"""
Telegram product listener.

Long-polls the Bot API and stores every product post as a ``ProductDraft``.
It does no AI work — ``process_product_drafts`` does that — so a slow model
call can never stall message intake.

Usage::

    python manage.py telegram_product_bot
    python manage.py telegram_product_bot --once      # single poll, for cron
"""

from __future__ import annotations

import logging
import signal
import time

from django.core.management.base import BaseCommand, CommandError

from Hub.automation.ingest import ingest
from Hub.automation.sources.telegram_bot import TelegramBotSource, TelegramConfigError

logger = logging.getLogger(__name__)


def console_safe(text: str) -> str:
    """
    Make text printable on a legacy Windows console.

    Supplier messages routinely contain Devanagari, Gujarati or the ₹ sign. On
    a cp1252 console ``self.stdout.write`` raises ``UnicodeEncodeError``, which
    would kill the listener loop over nothing more than a product name.
    """
    import sys

    encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
    return str(text).encode(encoding, errors='replace').decode(encoding, errors='replace')


class Command(BaseCommand):
    help = 'Listen to Telegram and stage incoming products as drafts awaiting approval.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--once', action='store_true', help='Poll once and exit (for cron/Task Scheduler).')
        parser.add_argument('--timeout', type=int, default=25, help='Long-poll seconds per request (default: 25).')

    def handle(self, *args, **options) -> None:
        try:
            source = TelegramBotSource(long_poll_seconds=options['timeout'])
        except TelegramConfigError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(console_safe(source.describe())))

        running = True

        def stop(signum, frame):  # noqa: ARG001
            nonlocal running
            running = False
            self.stdout.write(self.style.WARNING('\nShutting down after the current poll…'))

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)

        total = 0
        while running:
            try:
                for incoming in source.poll():
                    draft = ingest(incoming)
                    if draft is not None:
                        total += 1
                        self.stdout.write(
                            console_safe(f'  -> draft #{draft.pk}  {draft.display_name[:60]}')
                        )
            except Exception:
                logger.exception('[telegram] Poll cycle failed; continuing')
                time.sleep(5)

            if options['once']:
                break

        self.stdout.write(self.style.SUCCESS(f'Done. {total} message(s) staged.'))
