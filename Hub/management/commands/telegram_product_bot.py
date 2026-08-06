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

from Hub.automation.creative_delivery import handle_callback as handle_creative_callback
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

        self.stdout.write('Waiting for products. Send one to the bot with the description as its caption.')
        self.stdout.write('(The bot never replies in chat - watch this window and the admin queue.)')
        self.stdout.flush()

        total = 0
        #: Consecutive failures on the same batch. A message that fails every
        #: time must not wedge every product behind it forever.
        failures = 0
        MAX_BATCH_FAILURES = 5

        while running:
            try:
                for incoming in source.poll():
                    draft = ingest(incoming)
                    if draft is not None:
                        total += 1
                        self.stdout.write(
                            console_safe(f'  -> draft #{draft.pk}  {draft.display_name[:60]}')
                        )
                    else:
                        self.stdout.write(
                            console_safe(f'  .. ignored duplicate delivery of {incoming.message_id}')
                        )

                # Approve/Reject/Regenerate presses on creative banners ride
                # the same poll (Telegram allows only one active getUpdates
                # connection per bot token).
                for callback_query in source.callback_queries:
                    try:
                        handle_creative_callback(callback_query)
                        self.stdout.write(
                            console_safe(f"  -> handled button: {callback_query.get('data', '')}")
                        )
                    except Exception:
                        logger.exception('[telegram] Failed to handle callback_query %s', callback_query.get('id'))

                # Explain anything the source dropped, so a silent queue is
                # never a mystery.
                for reason in source.skipped:
                    self.stdout.write(self.style.WARNING(console_safe(f'  .. skipped: {reason}')))

                # Everything in this batch is stored, so it is now safe to tell
                # Telegram not to send it again.
                source.commit()
                failures = 0
                self.stdout.flush()
            except Exception:
                failures += 1
                logger.exception(
                    '[telegram] Poll cycle failed (%d/%d); the batch will be retried',
                    failures, MAX_BATCH_FAILURES,
                )
                self.stdout.write(self.style.ERROR(
                    f'  !! poll failed ({failures}/{MAX_BATCH_FAILURES}); '
                    'messages kept for retry (see logs)'
                ))

                if failures >= MAX_BATCH_FAILURES:
                    logger.error(
                        '[telegram] Giving up on this batch after %d attempts and '
                        'skipping past it. Those messages are lost — resend them.',
                        failures,
                    )
                    self.stdout.write(self.style.ERROR(
                        '  !! skipping the stuck batch; resend those products'
                    ))
                    source.skip_batch()
                    failures = 0
                self.stdout.flush()
                time.sleep(5)

            if options['once']:
                break

        self.stdout.write(self.style.SUCCESS(f'Done. {total} message(s) staged.'))
