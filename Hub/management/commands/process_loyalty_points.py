from django.core.management.base import BaseCommand

from Hub.loyalty_manager import LoyaltyPointsManager


class Command(BaseCommand):
    help = "Process pending loyalty points for delivered orders after return window closure"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500, help="Max orders to scan in one run")

    def handle(self, *args, **options):
        limit = max(int(options.get("limit") or 500), 1)
        result = LoyaltyPointsManager.process_pending_delivery_points(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                "Loyalty points processed | "
                f"processed={result['processed']} awarded={result['awarded']} "
                f"skipped={result['skipped']} errors={result['errors']}"
            )
        )
