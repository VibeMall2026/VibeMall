"""
Create (or retire) the ₹40 product used to rehearse a real Razorpay
payment-then-refund on a live site.

Run on the server that serves the site - the product has to exist in the
database that site talks to, not in a developer's local copy.

    python manage.py create_test_refund_product          # create / refresh
    python manage.py create_test_refund_product --off    # hide it again
    python manage.py create_test_refund_product --delete # remove it entirely
"""
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from Hub.models import Coupon, Product

NAME = "TEST Refund Product"
SLUG = slugify(NAME)
CODE = "FREESHIPTEST"
PRICE = Decimal("40.00")

# 1x1 transparent GIF, so no real image file has to be shipped for this.
TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


class Command(BaseCommand):
    help = "Create or retire the Rs.40 Razorpay refund test product."

    def add_arguments(self, parser):
        parser.add_argument(
            "--off", action="store_true",
            help="Deactivate the product and coupon instead of creating them.",
        )
        parser.add_argument(
            "--delete", action="store_true",
            help="Delete the product and coupon outright.",
        )

    def handle(self, *args, **options):
        if options["delete"]:
            return self._delete()
        if options["off"]:
            return self._deactivate()
        self._create()

    # ── teardown ─────────────────────────────────────────────────────────────

    def _deactivate(self):
        count = Product.objects.filter(slug=SLUG).update(is_active=False)
        Coupon.objects.filter(code=CODE).update(is_active=False)
        if count:
            self.stdout.write(self.style.SUCCESS(f"Hidden: {NAME} is no longer active."))
        else:
            self.stdout.write(self.style.WARNING("Nothing to hide - product not found."))

    def _delete(self):
        deleted, _ = Product.objects.filter(slug=SLUG).delete()
        Coupon.objects.filter(code=CODE).delete()
        self.stdout.write(self.style.SUCCESS(
            f"Deleted {deleted} row(s)." if deleted else "Nothing to delete."
        ))

    # ── setup ────────────────────────────────────────────────────────────────

    def _create(self):
        product = Product.objects.filter(slug=SLUG).first()
        if product:
            product.price = PRICE
            product.stock = max(product.stock, 10)
            product.is_active = True
            product.is_returnable = True
            product.return_days = 7
            # COD would skip the gateway entirely and defeat the exercise.
            product.payment_methods = "ONLINE,UPI,CARD"
            product.save()
            self.stdout.write(f"Refreshed existing product id={product.id}")
        else:
            product = Product(
                name=NAME,
                slug=SLUG,
                sku="TEST-REFUND-40",
                description=(
                    "Temporary listing used to verify the Razorpay refund flow. "
                    "Not a real product."
                ),
                price=PRICE,
                stock=10,
                is_active=True,
                is_returnable=True,
                return_days=7,
                payment_methods="ONLINE,UPI,CARD",
                shipping_info="Test item - apply FREESHIPTEST to waive delivery.",
            )
            product.image.save("test_refund_40.gif", ContentFile(TINY_GIF), save=False)
            product.save()
            self.stdout.write(f"Created product id={product.id}")

        now = timezone.now()
        # Delivery is a flat Rs.50 under Rs.500 and is not a per-product setting,
        # so the only way to reach a shipping-free Rs.40 order is this coupon.
        coupon, made = Coupon.objects.update_or_create(
            code=CODE,
            defaults=dict(
                description="Free shipping for the Rs.40 refund test",
                discount_type="FREE_SHIPPING",
                coupon_type="FREE_SHIPPING",
                discount_value=Decimal("0.00"),
                min_purchase_amount=Decimal("1.00"),
                is_active=True,
                valid_from=now - timezone.timedelta(days=1),
                valid_to=now + timezone.timedelta(days=30),
            ),
        )
        self.stdout.write(f"{'Created' if made else 'Updated'} coupon {coupon.code}")

        tax = (PRICE * Decimal("0.05")).quantize(Decimal("0.01"))
        shipping = Decimal("0.00") if PRICE > 500 else Decimal("50.00")
        waived = coupon.get_discount_amount(PRICE, shipping)
        payable = PRICE + tax + shipping - waived

        self.stdout.write("")
        self.stdout.write(f"  URL       /product/{SLUG}/")
        self.stdout.write(f"  Coupon    {CODE}")
        self.stdout.write("")
        self.stdout.write(f"  subtotal  Rs.{PRICE}")
        self.stdout.write(f"  tax 5%    Rs.{tax}")
        self.stdout.write(f"  shipping  Rs.{shipping}")
        self.stdout.write(f"  waived   -Rs.{waived}")
        self.stdout.write(self.style.SUCCESS(f"  payable   Rs.{payable}"))
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "This listing is visible to every shopper. Run with --off when done."
        ))
