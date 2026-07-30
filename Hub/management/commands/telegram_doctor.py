"""
Diagnose the Telegram product automation setup.

Answers "why is nothing arriving?" by checking every link in the chain and
printing the exact fix for whatever is broken.

Usage::

    python manage.py telegram_doctor
    python manage.py telegram_doctor --peek     # also show pending messages
"""

from __future__ import annotations

import json

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

API_ROOT = 'https://api.telegram.org'


class Command(BaseCommand):
    help = 'Check the Telegram bot + AI product automation configuration end to end.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--peek',
            action='store_true',
            help='Show messages waiting on the Telegram queue (does not consume them).',
        )

    # -- output helpers -----------------------------------------------------

    def ok(self, message: str) -> None:
        self.stdout.write(self.style.SUCCESS(f'  [OK]   {message}'))

    def bad(self, message: str, fix: str = '') -> None:
        self.stdout.write(self.style.ERROR(f'  [FAIL] {message}'))
        if fix:
            for line in fix.splitlines():
                self.stdout.write(f'         {line}')

    def warn(self, message: str, fix: str = '') -> None:
        self.stdout.write(self.style.WARNING(f'  [WARN] {message}'))
        if fix:
            for line in fix.splitlines():
                self.stdout.write(f'         {line}')

    def section(self, title: str) -> None:
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(title))

    # -- main ---------------------------------------------------------------

    def handle(self, *args, **options) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING('\nTelegram Product Automation — diagnostics'))
        failures = 0

        # --- 1. Token ------------------------------------------------------
        self.section('1. Bot token')
        token = (getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or '').strip()

        if not token:
            failures += 1
            self.bad(
                'TELEGRAM_BOT_TOKEN is not set.',
                'Nothing can work until this is fixed.\n'
                'Open the .env file in the project root and add a line:\n'
                '    TELEGRAM_BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n'
                'Get the token from @BotFather in Telegram (/mybots -> API Token,\n'
                'or /revoke to issue a fresh one). Then run this command again.',
            )
            self.finish(failures)
            return

        if ':' not in token:
            failures += 1
            self.bad(
                'TELEGRAM_BOT_TOKEN looks malformed (no ":" in it).',
                'A real token looks like 123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            )
            self.finish(failures)
            return

        self.ok(f'Token present ({token[:10]}...{token[-4:]})')

        # --- 2. Token works ------------------------------------------------
        self.section('2. Telegram connectivity')
        me = self._call(token, 'getMe')
        if me is None:
            failures += 1
            self.bad(
                'Could not reach Telegram or the token was rejected.',
                'Check your internet connection, then confirm the token with\n'
                '@BotFather. A revoked token keeps failing until you paste the new one.',
            )
            self.finish(failures)
            return

        self.ok(f"Authenticated as @{me.get('username')} ({me.get('first_name')})")

        # --- 3. Webhook conflict -------------------------------------------
        self.section('3. Delivery mode')
        hook = self._call(token, 'getWebhookInfo') or {}
        if hook.get('url'):
            failures += 1
            self.bad(
                f"A webhook is set ({hook['url']}).",
                'A webhook and getUpdates are mutually exclusive — while a webhook\n'
                'exists, this bot receives nothing. Remove it with:\n'
                f'    curl "{API_ROOT}/bot<YOUR_TOKEN>/deleteWebhook"',
            )
        else:
            self.ok('Using getUpdates (long polling) — correct for this setup')

        pending = hook.get('pending_update_count', 0)
        if pending:
            self.ok(f'{pending} message(s) waiting to be collected')
        else:
            self.warn(
                'No messages waiting.',
                'Either everything has already been collected, or nothing has been\n'
                'sent yet. Note the bot NEVER replies in chat — that is by design.\n'
                'Send a product photo with the description as its CAPTION, then\n'
                'run this command again.',
            )

        # --- 4. Peek -------------------------------------------------------
        if options['peek']:
            self.section('4. Pending messages')
            updates = self._call(token, 'getUpdates', timeout=1, limit=10) or []
            if not updates:
                self.warn('Queue is empty (or the bot process already consumed them).')
            for update in updates:
                message = (
                    update.get('message')
                    or update.get('channel_post')
                    or update.get('edited_message')
                    or update.get('edited_channel_post')
                )
                if not message:
                    continue
                chat = message.get('chat') or {}
                text = (message.get('text') or message.get('caption') or '').replace('\n', ' ')
                self.stdout.write(
                    f"  chat_id={chat.get('id')} ({chat.get('type')}) "
                    f"photo={'yes' if message.get('photo') else 'no'} "
                    f"album={message.get('media_group_id') or '-'}"
                )
                self.stdout.write(f'    text: {self._safe(text[:90]) or "(none)"}')

        # --- 5. Chat allow-list --------------------------------------------
        self.section('5. Chat allow-list')
        allowed = getattr(settings, 'TELEGRAM_ALLOWED_CHAT_IDS', []) or []
        if allowed:
            self.ok(f'Restricted to: {", ".join(allowed)}')
            self.warn(
                'Messages from any other chat are silently ignored.',
                'If products are not appearing, run with --peek and confirm the\n'
                'chat_id shown there is in this list.',
            )
        else:
            self.ok('Accepting every chat (fine for testing)')
            self.warn(
                'Set TELEGRAM_ALLOWED_CHAT_IDS in .env before real use.',
                'Otherwise anyone who finds your bot can push products to your queue.',
            )

        # --- 6. AI ---------------------------------------------------------
        self.section('6. AI enrichment')
        try:
            import anthropic  # noqa: F401
            self.ok('anthropic package installed')
            package_ok = True
        except ImportError:
            package_ok = False
            self.warn('anthropic package not installed.', 'Fix:  pip install anthropic')

        if (getattr(settings, 'ANTHROPIC_API_KEY', '') or '').strip():
            self.ok(f"ANTHROPIC_API_KEY set (model: {getattr(settings, 'AUTOMATION_AI_MODEL', '')})")
        else:
            self.warn(
                'ANTHROPIC_API_KEY not set.',
                'The pipeline still runs using rule-based extraction only — you lose\n'
                'generated descriptions, SEO copy, category suggestions and image\n'
                'role/colour detection. Add the key to .env to enable them.',
            )
            package_ok = package_ok  # keep flake happy; not a failure

        # --- 7. Queue state ------------------------------------------------
        self.section('7. Draft queue')
        from django.db.models import Count

        from Hub.models import ProductDraft

        counts = {
            row['status']: row['n']
            for row in ProductDraft.objects.values('status').annotate(n=Count('id'))
        }
        total = sum(counts.values())
        if total == 0:
            self.warn('No drafts yet - nothing has reached the database.')
        else:
            for status, label in ProductDraft.STATUS_CHOICES:
                if counts.get(status):
                    self.stdout.write(f'  {label:22} {counts[status]}')

        waiting = counts.get(ProductDraft.STATUS_RECEIVED, 0) + counts.get(ProductDraft.STATUS_QUEUED, 0)
        if waiting:
            self.warn(
                f'{waiting} draft(s) waiting to be processed.',
                'Is the worker running?  python manage.py process_product_drafts',
            )

        self.finish(failures)

    # -- utilities ----------------------------------------------------------

    def finish(self, failures: int) -> None:
        self.stdout.write('')
        if failures:
            self.stdout.write(self.style.ERROR(f'{failures} blocking problem(s) found - fix the [FAIL] items above.'))
        else:
            self.stdout.write(self.style.SUCCESS('No blocking problems found.'))
            self.stdout.write('Run these two processes to go live:')
            self.stdout.write('    python manage.py telegram_product_bot')
            self.stdout.write('    python manage.py process_product_drafts')
        self.stdout.write('')

    @staticmethod
    def _safe(text: str) -> str:
        import sys

        encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
        return str(text).encode(encoding, errors='replace').decode(encoding, errors='replace')

    def _call(self, token: str, method: str, **params):
        """Call a Bot API method, returning the result or None on failure."""
        try:
            response = requests.get(f'{API_ROOT}/bot{token}/{method}', params=params, timeout=20)
            payload = response.json()
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'         {method} request failed: {exc}'))
            return None

        if not payload.get('ok'):
            self.stdout.write(
                self.style.ERROR(f"         {method} error {payload.get('error_code')}: {payload.get('description')}")
            )
            return None
        return payload.get('result')
