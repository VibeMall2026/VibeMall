from django.core.management.base import BaseCommand

from Hub.models import Product, ProductImage


class Command(BaseCommand):
    help = "Reprocess existing product and gallery images into 4:5 high-res frame (960x1200) without crop."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            choices=["all", "product", "gallery"],
            default="all",
            help="Choose what to reprocess: all, product (main image only), gallery (additional images only).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Optional limit for quick batch testing.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show counts only; do not modify images.",
        )

    def handle(self, *args, **options):
        only = options["only"]
        limit = max(0, int(options["limit"] or 0))
        dry_run = bool(options["dry_run"])

        product_qs = Product.objects.exclude(image="").exclude(image__isnull=True).order_by("id")
        gallery_qs = ProductImage.objects.exclude(image="").exclude(image__isnull=True).order_by("id")

        if limit:
            product_qs = product_qs[:limit]
            gallery_qs = gallery_qs[:limit]

        product_count = product_qs.count()
        gallery_count = gallery_qs.count()

        self.stdout.write(self.style.SUCCESS(f"Product images: {product_count}"))
        self.stdout.write(self.style.SUCCESS(f"Gallery images: {gallery_count}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete. No files changed."))
            return

        updated_product = 0
        updated_gallery = 0
        failed_product = 0
        failed_gallery = 0

        if only in ("all", "product"):
            self.stdout.write("Reprocessing main product images...")
            for obj in product_qs.iterator():
                try:
                    # Triggers Product.save -> frame fit + compression pipeline
                    obj.save(update_fields=["image"])
                    updated_product += 1
                    if updated_product % 50 == 0:
                        self.stdout.write(f"  processed product images: {updated_product}")
                except Exception as exc:
                    failed_product += 1
                    self.stdout.write(self.style.ERROR(f"  product {obj.id} failed: {exc}"))

        if only in ("all", "gallery"):
            self.stdout.write("Reprocessing gallery images...")
            for obj in gallery_qs.iterator():
                try:
                    # Triggers ProductImage.save -> frame fit + compression pipeline
                    obj.save(update_fields=["image"])
                    updated_gallery += 1
                    if updated_gallery % 50 == 0:
                        self.stdout.write(f"  processed gallery images: {updated_gallery}")
                except Exception as exc:
                    failed_gallery += 1
                    self.stdout.write(self.style.ERROR(f"  gallery {obj.id} failed: {exc}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Reprocess completed."))
        self.stdout.write(
            f"Main product images: updated={updated_product}, failed={failed_product}"
        )
        self.stdout.write(
            f"Gallery images: updated={updated_gallery}, failed={failed_gallery}"
        )
