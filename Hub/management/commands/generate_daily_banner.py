from django.core.management.base import BaseCommand

from Hub.automation.social_banner import generate_today_banner


class Command(BaseCommand):
    help = "Generate today's Instagram Story/Reel marketing banner from the next product in rotation."

    def handle(self, *args, **options):
        asset = generate_today_banner()
        if asset is None:
            self.stdout.write(self.style.WARNING("No active, in-stock products with an image found - nothing generated."))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Creative #{asset.id} generated for '{asset.product.name}' "
            f"(theme={asset.theme_name}, provider={asset.ai_provider or 'fallback'}) - "
            f"sent to Telegram for approval."
        ))
