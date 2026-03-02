"""
Management command to process earning confirmations and send payout reminders.

Run daily:
  python manage.py process_resell_payouts
"""

import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from Hub.models import ResellerEarning, PayoutTransaction
from Hub.resell_payout_service import (
    PayoutEligibilityManager,
    PayoutEmailService,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process resell payout eligibility and send admin reminder emails"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--confirm-earnings',
            action='store_true',
            default=True,
            help='Auto-confirm earnings after 7-day hold (default: True)',
        )
        parser.add_argument(
            '--send-reminders',
            action='store_true',
            default=True,
            help='Send admin reminder emails (default: True)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        do_confirm = options['confirm_earnings']
        do_remind = options['send_reminders']

        self.stdout.write(self.style.SUCCESS('=== Resell Payout Processing ==='))
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN MODE]'))

        # Step 1: Auto-confirm earnings
        if do_confirm:
            self.stdout.write('\n📋 Auto-confirming eligible earnings...')
            if dry_run:
                eligible = self._get_eligible_to_confirm()
                self.stdout.write(f"  Would confirm {eligible.count()} earnings")
            else:
                confirmed = PayoutEligibilityManager.check_and_confirm_earnings()
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Confirmed {confirmed} earnings')
                )

        # Step 2: Send reminder emails
        if do_remind:
            self.stdout.write('\n📧 Sending payout reminder emails...')
            reminded = self._send_payout_reminders(dry_run)
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Sent reminders for {reminded} payouts')
            )

        self.stdout.write(self.style.SUCCESS('\n✓ Processing complete!'))

    def _get_eligible_to_confirm(self):
        """Get earnings eligible for confirmation (for dry-run preview)"""
        cutoff_time = timezone.now() - timedelta(days=7)
        return ResellerEarning.objects.filter(
            status='PENDING',
            order__order_status='DELIVERED',
            order__delivery_date__lte=cutoff_time
        )

    def _send_payout_reminders(self, dry_run=False):
        """Send admin reminder emails for confirmed earnings pending payout"""
        seven_days_ago = timezone.now() - timedelta(days=7)

        # Find confirmed earnings that have a corresponding payout NOT yet initiated
        confirmed_pending = ResellerEarning.objects.filter(
            status='CONFIRMED',
            payout_transaction__isnull=True,
            order__delivery_date__lte=seven_days_ago,
            order__order_status='DELIVERED'
        ).exclude(
            # Exclude if payout reminder already sent today
            reseller__payout_reminder_sent_at__date=timezone.now().date()
        ).select_related('order', 'reseller')

        sent_count = 0
        for earning in confirmed_pending:
            if dry_run:
                self.stdout.write(
                    f"  Would remind: {earning.reseller.username} - "
                    f"₹{earning.margin_amount} (Order #{earning.order.order_number})"
                )
            else:
                if PayoutEmailService.send_admin_payout_reminder(earning):
                    sent_count += 1
                    # Update reminder sent timestamp (add to ResellProfile if needed)

        return sent_count
