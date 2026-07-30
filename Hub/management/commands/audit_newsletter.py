"""
Audit — and optionally quarantine — newsletter subscribers nobody opted in.

Bots stuff scraped mailing lists into public subscribe forms. Every address is
a real person who never asked to hear from this shop, so mailing them earns
spam complaints, and enough of those get the whole domain blocked — taking
order confirmations down with the newsletter.

    python manage.py audit_newsletter                 # report only
    python manage.py audit_newsletter --deactivate    # quarantine the suspects
"""

from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand
from django.utils import timezone

from Hub.models import NewsletterSubscription

#: Networks the confirmations came from. These are hosting providers — a
#: shopper confirming a newsletter comes from a home or mobile connection, not
#: from a rack in a datacenter.
SUSPECT_PREFIXES = (
    '192.210.', '198.12.', '198.46.', '216.9.', '107.173.',   # ColoCrossing
    '51.', '54.37.', '54.38.', '5.135.', '5.196.', '178.32.', '217.182.',  # OVH
)

#: Distinct addresses one IP may sign up before it stops looking like a
#: household. This is the rule that does the real work: a hand-maintained list
#: of hosting ranges is always a step behind whoever rents the next one,
#: whereas "one connection, forty different people's email addresses" is the
#: shape of the abuse itself and needs no list to keep current.
MAX_EMAILS_PER_IP = 3


class Command(BaseCommand):
    help = 'Report or quarantine newsletter subscribers that were never genuine opt-ins.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--deactivate',
            action='store_true',
            help='Set is_active=False on the suspects. Nothing is deleted.',
        )
        parser.add_argument(
            '--before',
            default='',
            help='Only consider subscriptions made before this date (YYYY-MM-DD).',
        )

    def handle(self, *args, **options) -> None:
        rows = NewsletterSubscription.objects.all()
        if options['before']:
            rows = rows.filter(subscribed_at__date__lt=options['before'])

        total = rows.count()
        self.stdout.write(self.style.MIGRATE_HEADING(f'\n{total} subscriber(s) under review\n'))

        # How many different people each connection claims to be.
        per_ip = Counter(
            (row.ip_address or '').strip() for row in rows if (row.ip_address or '').strip()
        )

        suspects = []
        for row in rows:
            reasons = []
            ip = (row.ip_address or '').strip()

            if not ip:
                reasons.append('no IP recorded')
            elif ip.startswith(SUSPECT_PREFIXES):
                reasons.append('datacenter IP')
            elif per_ip[ip] > MAX_EMAILS_PER_IP:
                reasons.append(f'{per_ip[ip]} addresses from one IP')

            if not (row.user_agent or '').strip():
                reasons.append('no user agent')

            if reasons:
                suspects.append((row, reasons))

        self.stdout.write(f'  suspect : {len(suspects)}')
        self.stdout.write(f'  genuine : {total - len(suspects)}')

        def label(reason: str) -> str:
            return 'many addresses from one IP' if 'from one IP' in reason else reason

        counts = Counter(label(reason) for _, reasons in suspects for reason in reasons)
        self.stdout.write('\n  why:')
        for reason, n in counts.most_common():
            self.stdout.write(f'    {n:5}  {reason}')

        self.stdout.write('\n  examples:')
        for row, reasons in suspects[:8]:
            self.stdout.write(f'    {row.email[:44]:44}  {", ".join(reasons)}')

        if not options['deactivate']:
            self.stdout.write(self.style.WARNING(
                '\nReport only. Re-run with --deactivate to quarantine these.\n'
                'Nothing is deleted — is_active is set to False, so they simply\n'
                'stop receiving mail and can be reactivated if one was genuine.\n'
            ))
            return

        now = timezone.now()
        changed = 0
        for row, _ in suspects:
            if row.is_active:
                row.is_active = False
                row.unsubscribed_at = now
                row.save(update_fields=['is_active', 'unsubscribed_at'])
                changed += 1

        self.stdout.write(self.style.SUCCESS(f'\nQuarantined {changed} subscriber(s).'))
        self.stdout.write(
            f'{NewsletterSubscription.objects.filter(is_active=True).count()} remain active.\n'
        )
