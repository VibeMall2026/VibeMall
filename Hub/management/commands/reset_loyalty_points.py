"""
Zero every loyalty balance, because the rates changed.

Points used to be earned at Rs.100 = 1 point and spent at 1 point = Rs.10 - a
10% return. They are now earned at Rs.100 = 10 points and spent at 10 points =
Rs.1, a 1% return. An old balance carried into the new scheme would be worth a
hundredth of what its holder expected, and an old balance left at its old size
would still redeem for real money at the wrong rate. Clearing is the honest
option.

    python manage.py reset_loyalty_points --dry-run   # see what would change
    python manage.py reset_loyalty_points             # do it

Balances are set to zero and an ADJUSTED transaction records what was removed,
so the history stays auditable. Nothing is deleted.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from Hub.models import LoyaltyPoints, PointsTransaction


class Command(BaseCommand):
    help = "Reset all loyalty point balances to zero after a rate change."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing anything.',
        )
        parser.add_argument(
            '--keep-history', action='store_true',
            help='Skip the ADJUSTED audit rows (balances are still zeroed).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        write_history = not options['keep_history']

        accounts = LoyaltyPoints.objects.exclude(
            total_points=0, points_used=0, points_available=0)
        totals = accounts.aggregate(
            available=Sum('points_available'), earned=Sum('total_points'))
        available = totals['available'] or 0
        earned = totals['earned'] or 0
        count = accounts.count()

        self.stdout.write(f"accounts with a balance : {count}")
        self.stdout.write(f"points outstanding      : {available}")
        self.stdout.write(f"points ever earned      : {earned}")

        if not count:
            self.stdout.write(self.style.SUCCESS("Nothing to reset."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "Dry run - nothing was written. Re-run without --dry-run to apply."))
            return

        reset_count = 0
        with transaction.atomic():
            # Iterated rather than bulk-updated so each account gets its own
            # audit row carrying the balance it actually lost.
            for account in accounts.select_related('user').iterator():
                lost = account.points_available
                if write_history and lost:
                    PointsTransaction.objects.create(
                        user=account.user,
                        points=lost,
                        transaction_type='ADJUSTED',
                        description=(
                            'Balance reset to zero when the loyalty rates changed '
                            'to Rs.100 = 10 points and 10 points = Rs.1.'
                        ),
                    )
                account.total_points = 0
                account.points_used = 0
                account.points_available = 0
                account.save(update_fields=[
                    'total_points', 'points_used', 'points_available', 'updated_at'])
                reset_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Reset {reset_count} account(s); {available} outstanding point(s) cleared."))
        if write_history:
            self.stdout.write("An ADJUSTED transaction was recorded for each one.")
