from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Coupon


@override_settings(SECURE_SSL_REDIRECT=False)
class FreeShippingCouponTests(TestCase):
    """
    A free-shipping coupon waives the delivery charge, which is its own line on
    the order. It used to be capped by the cart total, so a cart cheaper than
    delivery had only part of the charge waived and the shopper still paid the
    difference on an offer that said "free shipping".
    """

    def _coupon(self, discount_type='FREE_SHIPPING', coupon_type='FREE_SHIPPING'):
        now = timezone.now()
        return Coupon.objects.create(
            code=f'FS{discount_type}{coupon_type}'[:20],
            description='Free shipping',
            discount_type=discount_type,
            coupon_type=coupon_type,
            discount_value=Decimal('0.00'),
            min_purchase_amount=Decimal('1.00'),
            is_active=True,
            valid_from=now - timezone.timedelta(days=1),
            valid_to=now + timezone.timedelta(days=30),
        )

    def test_waives_full_shipping_on_a_cart_cheaper_than_delivery(self):
        coupon = self._coupon()
        # Rs.40 of goods against a Rs.50 delivery charge
        self.assertEqual(coupon.get_discount_amount(Decimal('40'), Decimal('50')),
                         Decimal('50'))

    def test_waives_full_shipping_on_a_normal_cart(self):
        coupon = self._coupon()
        self.assertEqual(coupon.get_discount_amount(Decimal('900'), Decimal('50')),
                         Decimal('50'))

    def test_no_shipping_charge_means_no_discount(self):
        coupon = self._coupon()
        self.assertEqual(coupon.get_discount_amount(Decimal('900'), Decimal('0')),
                         Decimal('0'))

    def test_free_shipping_by_coupon_type_alone_behaves_the_same(self):
        coupon = self._coupon(discount_type='FIXED', coupon_type='FREE_SHIPPING')
        self.assertEqual(coupon.get_discount_amount(Decimal('40'), Decimal('50')),
                         Decimal('50'))

    def test_order_total_stays_positive(self):
        """subtotal + tax + shipping - waiver can never go below the goods."""
        coupon = self._coupon()
        subtotal, shipping = Decimal('40'), Decimal('50')
        tax = subtotal * Decimal('0.05')
        total = subtotal + tax + shipping - coupon.get_discount_amount(subtotal, shipping)
        self.assertEqual(total, Decimal('42.00'))
        self.assertGreater(total, 0)

    # ── a normal discount is still capped by the goods ───────────────────────

    def test_percentage_discount_still_capped_by_cart_total(self):
        coupon = self._coupon(discount_type='PERCENTAGE', coupon_type='MANUAL')
        coupon.discount_value = Decimal('50.00')
        coupon.save()
        self.assertEqual(coupon.get_discount_amount(Decimal('100'), Decimal('50')),
                         Decimal('50.00'))

    def test_fixed_discount_cannot_exceed_the_goods(self):
        coupon = self._coupon(discount_type='FIXED', coupon_type='MANUAL')
        coupon.discount_value = Decimal('500.00')
        coupon.save()
        self.assertEqual(coupon.get_discount_amount(Decimal('100'), Decimal('50')),
                         Decimal('100'))
