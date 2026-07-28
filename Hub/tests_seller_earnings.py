from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import Order, OrderItem, Product, ResellerProfile, SellerEarning
from .seller_earnings_service import (
    cancel_seller_earnings_for_order,
    confirm_seller_earnings_for_order,
    create_seller_earnings,
    get_seller_earnings_summary,
)


def _tiny_image(name="test.gif"):
    return SimpleUploadedFile(
        name,
        (
            b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00"
            b"\x01\x00\x00\x02\x02D\x01\x00;"
        ),
        content_type="image/gif",
    )


class SellerEarningsTests(TestCase):
    def setUp(self):
        self.seller_a = User.objects.create_user(username="seller_a", password="pass12345")
        self.seller_b = User.objects.create_user(username="seller_b", password="pass12345")
        self.customer = User.objects.create_user(username="buyer", password="pass12345")

        # 10% default commission
        ResellerProfile.objects.create(user=self.seller_a, is_reseller_enabled=True)
        ResellerProfile.objects.create(user=self.seller_b, is_reseller_enabled=True)

        self.prod_a1 = Product.objects.create(
            name="A1", image=_tiny_image("a1.gif"), price=Decimal("100.00"),
            stock=50, is_active=True, created_by=self.seller_a,
        )
        self.prod_a2 = Product.objects.create(
            name="A2", image=_tiny_image("a2.gif"), price=Decimal("50.00"),
            stock=50, is_active=True, created_by=self.seller_a,
        )
        self.prod_b1 = Product.objects.create(
            name="B1", image=_tiny_image("b1.gif"), price=Decimal("200.00"),
            stock=50, is_active=True, created_by=self.seller_b,
        )
        # Platform-owned: nobody to pay
        self.prod_platform = Product.objects.create(
            name="P1", image=_tiny_image("p1.gif"), price=Decimal("300.00"),
            stock=50, is_active=True, created_by=None,
        )

    def _make_order(self, items, **kwargs):
        """items: list of (product, qty, base_price)"""
        defaults = dict(
            user=self.customer,
            subtotal=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            shipping_address="addr",
            billing_address="addr",
            payment_method="COD",
        )
        defaults.update(kwargs)
        order = Order.objects.create(**defaults)
        for product, qty, base in items:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                product_price=base,
                base_price=base,
                quantity=qty,
                subtotal=base * qty,
            )
        return order

    # ── splitting ────────────────────────────────────────────────────────────

    def test_multi_seller_order_creates_one_earning_per_seller(self):
        order = self._make_order([
            (self.prod_a1, 2, Decimal("100.00")),   # seller_a: 200
            (self.prod_b1, 1, Decimal("200.00")),   # seller_b: 200
            (self.prod_a2, 1, Decimal("50.00")),    # seller_a: +50 -> 250
        ])
        created = create_seller_earnings(order)

        self.assertEqual(len(created), 2)
        a = SellerEarning.objects.get(order=order, seller=self.seller_a)
        b = SellerEarning.objects.get(order=order, seller=self.seller_b)

        # seller_a's two products are combined into a single row
        self.assertEqual(a.gross_amount, Decimal("250.00"))
        self.assertEqual(a.item_count, 3)
        self.assertEqual(b.gross_amount, Decimal("200.00"))
        self.assertEqual(b.item_count, 1)

    def test_platform_owned_product_produces_no_earning(self):
        order = self._make_order([(self.prod_platform, 2, Decimal("300.00"))])
        created = create_seller_earnings(order)
        self.assertEqual(created, [])
        self.assertEqual(SellerEarning.objects.filter(order=order).count(), 0)

    # ── commission maths ─────────────────────────────────────────────────────

    def test_commission_is_deducted_from_gross(self):
        order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        earning = create_seller_earnings(order)[0]

        self.assertEqual(earning.gross_amount, Decimal("100.00"))
        self.assertEqual(earning.commission_percent, Decimal("10.00"))
        self.assertEqual(earning.commission_amount, Decimal("10.00"))
        self.assertEqual(earning.net_amount, Decimal("90.00"))

    def test_per_seller_commission_rate_is_used(self):
        profile = self.seller_a.reseller_profile
        profile.seller_commission_percent = Decimal("25.00")
        profile.save()

        order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        earning = create_seller_earnings(order)[0]
        self.assertEqual(earning.commission_amount, Decimal("25.00"))
        self.assertEqual(earning.net_amount, Decimal("75.00"))

    def test_rate_change_does_not_rewrite_past_earnings(self):
        order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        earning = create_seller_earnings(order)[0]
        self.assertEqual(earning.net_amount, Decimal("90.00"))

        profile = self.seller_a.reseller_profile
        profile.seller_commission_percent = Decimal("50.00")
        profile.save()

        earning.refresh_from_db()
        self.assertEqual(earning.commission_percent, Decimal("10.00"))
        self.assertEqual(earning.net_amount, Decimal("90.00"))

    def test_falls_back_to_product_price_when_base_price_missing(self):
        order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        OrderItem.objects.filter(order=order).update(base_price=Decimal("0.00"))
        earning = create_seller_earnings(order)[0]
        self.assertEqual(earning.gross_amount, Decimal("100.00"))

    # ── idempotency ──────────────────────────────────────────────────────────

    def test_creating_twice_does_not_duplicate(self):
        order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        create_seller_earnings(order)
        create_seller_earnings(order)
        create_seller_earnings(order)
        self.assertEqual(SellerEarning.objects.filter(order=order).count(), 1)

    def test_confirming_twice_credits_balance_only_once(self):
        order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        create_seller_earnings(order)

        confirm_seller_earnings_for_order(order)
        confirm_seller_earnings_for_order(order)
        confirm_seller_earnings_for_order(order)

        profile = self.seller_a.reseller_profile
        profile.refresh_from_db()
        self.assertEqual(profile.seller_available_balance, Decimal("90.00"))
        self.assertEqual(profile.seller_total_earnings, Decimal("90.00"))
        self.assertEqual(profile.seller_total_orders, 1)

    # ── lifecycle ────────────────────────────────────────────────────────────

    def test_confirm_credits_each_seller_separately(self):
        order = self._make_order([
            (self.prod_a1, 2, Decimal("100.00")),   # a: 200 -> 180
            (self.prod_b1, 1, Decimal("200.00")),   # b: 200 -> 180
        ])
        create_seller_earnings(order)
        confirm_seller_earnings_for_order(order)

        pa = self.seller_a.reseller_profile
        pb = self.seller_b.reseller_profile
        pa.refresh_from_db()
        pb.refresh_from_db()
        self.assertEqual(pa.seller_available_balance, Decimal("180.00"))
        self.assertEqual(pb.seller_available_balance, Decimal("180.00"))

    def test_cancel_after_confirm_reverses_balance(self):
        order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        create_seller_earnings(order)
        confirm_seller_earnings_for_order(order)

        profile = self.seller_a.reseller_profile
        profile.refresh_from_db()
        self.assertEqual(profile.seller_available_balance, Decimal("90.00"))

        cancel_seller_earnings_for_order(order, reason="Order cancelled")

        profile.refresh_from_db()
        self.assertEqual(profile.seller_available_balance, Decimal("0.00"))
        self.assertEqual(profile.seller_total_orders, 0)
        self.assertEqual(
            SellerEarning.objects.get(order=order).status, 'CANCELLED'
        )

    def test_cancel_before_confirm_leaves_balance_untouched(self):
        order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        create_seller_earnings(order)
        cancel_seller_earnings_for_order(order, reason="Cancelled early")

        profile = self.seller_a.reseller_profile
        profile.refresh_from_db()
        self.assertEqual(profile.seller_available_balance, Decimal("0.00"))

    def test_paid_earning_is_not_cancelled(self):
        """Money already sent out is a manual finance decision, not automatic."""
        order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        earning = create_seller_earnings(order)[0]
        earning.status = 'PAID'
        earning.save()

        cancel_seller_earnings_for_order(order, reason="too late")
        earning.refresh_from_db()
        self.assertEqual(earning.status, 'PAID')

    def test_balance_never_goes_negative_on_reversal(self):
        order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        create_seller_earnings(order)
        confirm_seller_earnings_for_order(order)

        # Simulate the balance already having been drawn down by a payout
        profile = self.seller_a.reseller_profile
        profile.seller_available_balance = Decimal("0.00")
        profile.save()

        cancel_seller_earnings_for_order(order, reason="return")
        profile.refresh_from_db()
        self.assertEqual(profile.seller_available_balance, Decimal("0.00"))

    # ── summary ──────────────────────────────────────────────────────────────

    def test_summary_reports_each_bucket(self):
        paid_order = self._make_order([(self.prod_a1, 1, Decimal("100.00"))])
        create_seller_earnings(paid_order)
        confirm_seller_earnings_for_order(paid_order)

        pending_order = self._make_order([(self.prod_a2, 2, Decimal("50.00"))])
        create_seller_earnings(pending_order)

        summary = get_seller_earnings_summary(self.seller_a)
        self.assertEqual(summary['available_balance'], Decimal("90.00"))
        self.assertEqual(summary['confirmed_amount'], Decimal("90.00"))
        self.assertEqual(summary['pending_amount'], Decimal("90.00"))   # 100 - 10%
        self.assertEqual(summary['total_orders'], 2)
        self.assertEqual(summary['commission_paid'], Decimal("20.00"))


class SellerEarningsSignalTests(TestCase):
    """The order lifecycle must drive earnings without any explicit calls."""

    def setUp(self):
        self.seller = User.objects.create_user(username="sig_seller", password="pass12345")
        self.customer = User.objects.create_user(username="sig_buyer", password="pass12345")
        ResellerProfile.objects.create(user=self.seller, is_reseller_enabled=True)
        self.product = Product.objects.create(
            name="SigProd", image=_tiny_image("sig.gif"), price=Decimal("100.00"),
            stock=50, is_active=True, created_by=self.seller,
        )

    def _order_with_item(self):
        order = Order.objects.create(
            user=self.customer,
            subtotal=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            shipping_address="addr",
            billing_address="addr",
            payment_method="COD",
        )
        OrderItem.objects.create(
            order=order, product=self.product, product_name=self.product.name,
            product_price=Decimal("100.00"), base_price=Decimal("100.00"),
            quantity=1, subtotal=Decimal("100.00"),
        )
        return order

    def test_paid_then_delivered_credits_seller(self):
        order = self._order_with_item()

        order.payment_status = 'PAID'
        order.save()
        self.assertEqual(
            SellerEarning.objects.get(order=order, seller=self.seller).status, 'PENDING'
        )

        order.order_status = 'DELIVERED'
        order.save()
        self.assertEqual(
            SellerEarning.objects.get(order=order, seller=self.seller).status, 'CONFIRMED'
        )

        profile = self.seller.reseller_profile
        profile.refresh_from_db()
        self.assertEqual(profile.seller_available_balance, Decimal("90.00"))

    def test_cancelling_paid_order_reverses(self):
        order = self._order_with_item()
        order.payment_status = 'PAID'
        order.save()
        order.order_status = 'DELIVERED'
        order.save()

        order.order_status = 'CANCELLED'
        order.save()

        profile = self.seller.reseller_profile
        profile.refresh_from_db()
        self.assertEqual(profile.seller_available_balance, Decimal("0.00"))
        self.assertEqual(
            SellerEarning.objects.get(order=order, seller=self.seller).status, 'CANCELLED'
        )

    def test_refund_reverses(self):
        order = self._order_with_item()
        order.payment_status = 'PAID'
        order.save()
        order.order_status = 'DELIVERED'
        order.save()

        order.payment_status = 'REFUNDED'
        order.save()

        profile = self.seller.reseller_profile
        profile.refresh_from_db()
        self.assertEqual(profile.seller_available_balance, Decimal("0.00"))

    def test_unpaid_order_creates_nothing(self):
        order = self._order_with_item()
        order.order_status = 'PROCESSING'
        order.save()
        self.assertEqual(SellerEarning.objects.filter(order=order).count(), 0)

    def test_repeated_saves_do_not_double_credit(self):
        order = self._order_with_item()
        order.payment_status = 'PAID'
        order.order_status = 'DELIVERED'
        for _ in range(4):
            order.save()

        self.assertEqual(SellerEarning.objects.filter(order=order).count(), 1)
        profile = self.seller.reseller_profile
        profile.refresh_from_db()
        self.assertEqual(profile.seller_available_balance, Decimal("90.00"))
