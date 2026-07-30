"""
Product draft worker.

Claims queued drafts and runs the AI + image pipeline over them, leaving each
one ready for admin approval. Retries with exponential backoff and reclaims
drafts abandoned by a crashed worker.

Usage::

    python manage.py process_product_drafts              # run continuously
    python manage.py process_product_drafts --once       # drain and exit
    python manage.py process_product_drafts --limit 20   # cap work per run
"""

from __future__ import annotations

import logging
import signal
import time

from django.core.management.base import BaseCommand

from Hub.automation.pipeline import process_once, reclaim_stale

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process queued product drafts: AI extraction, image analysis and duplicate checks.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--once', action='store_true', help='Drain the queue and exit.')
        parser.add_argument('--limit', type=int, default=0, help='Maximum drafts to process (0 = unlimited).')
        parser.add_argument('--idle-sleep', type=float, default=5.0, help='Seconds to wait when the queue is empty.')

    def handle(self, *args, **options) -> None:
        reclaim_stale()

        running = True

        def stop(signum, frame):  # noqa: ARG001
            nonlocal running
            running = False
            self.stdout.write(self.style.WARNING('\nFinishing the current draft, then stopping…'))

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)

        limit = options['limit']
        processed = 0

        while running:
            try:
                did_work = process_once()
            except Exception:
                # process_once already applies the retry policy; this only
                # catches a failure in the queue machinery itself.
                logger.exception('[worker] Queue error')
                time.sleep(5)
                continue

            if did_work:
                processed += 1
                self.stdout.write(f'  processed {processed}')
                if limit and processed >= limit:
                    break
                continue

            if options['once']:
                break
            time.sleep(options['idle_sleep'])

        self.stdout.write(self.style.SUCCESS(f'Done. {processed} draft(s) processed.'))
