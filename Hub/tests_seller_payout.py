from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import Order, OrderItem, Product, ResellerProfile, SellerEarning, SellerPayout
from .seller_earnings_service import (
    calculate_tds,
    cancel_seller_earnings_for_order,
    confirm_seller_earnings_for_order,
    create_seller_earnings,
    financial_year_start,
)
from .seller_payout_service import (
    approve_payout,
    complete_payout,
    fail_payout,
    get_settleable_total,
    reject_payout,
    request_payout,
    seller_settlement_report,
    send_via_gateway,
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


class SellerPayoutBase(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username="po_seller", password="pass12345")
        self.customer = User.objects.create_user(username="po_buyer", password="pass12345")
        self.admin = User.objects.create_user(
            username="po_admin", password="pass12345", is_staff=True, is_superuser=True,
        )
        self.profile = ResellerProfile.objects.create(
            user=self.seller, is_reseller_enabled=True,
            bank_account_name="Seller Name",
            bank_account_number="1234567890",
            bank_ifsc_code="HDFC0001234",
            upi_id="seller@upi",
        )
        self.product = Product.objects.create(
            name="P", image=_tiny_image("p.gif"), price=Decimal("1000.00"),
            stock=100, is_active=True, created_by=self.seller,
        )

    def _earn(self, amount="1000.00", confirm=True):
        """Create one order worth `amount` gross; returns (order, earning)."""
        order = Order.objects.create(
            user=self.customer, subtotal=Decimal(amount), total_amount=Decimal(amount),
            shipping_address="a", billing_address="a", payment_method="COD",
        )
        OrderItem.objects.create(
            order=order, product=self.product, product_name="P",
            product_price=Decimal(amount), base_price=Decimal(amount),
            quantity=1, subtotal=Decimal(amount),
        )
        earning = create_seller_earnings(order)[0]
        if confirm:
            confirm_seller_earnings_for_order(order)
            earning.refresh_from_db()
        return order, earning

    def _balance(self):
        self.profile.refresh_from_db()
        return self.profile.seller_available_balance


class SellerPayoutRequestTests(SellerPayoutBase):
    def test_request_debits_balance_immediately(self):
        self._earn("1000.00")                       # net 900
        self.assertEqual(self._balance(), Decimal("900.00"))

        payout = request_payout(self.seller, Decimal("900.00"), 'BANK_TRANSFER')

        self.assertEqual(payout.status, 'PENDING')
        self.assertEqual(payout.amount, Decimal("900.00"))
        # Money is claimed the moment it is requested, not at approval, so it
        # cannot be requested a second time while pending.
        self.assertEqual(self._balance(), Decimal("0.00"))

    def test_cannot_request_twice_for_same_money(self):
        self._earn("1000.00")
        request_payout(self.seller, Decimal("900.00"), 'UPI')
        with self.assertRaises(ValidationError):
            request_payout(self.seller, Decimal("900.00"), 'UPI')

    def test_rejects_amount_above_balance(self):
        self._earn("1000.00")
        with self.assertRaises(ValidationError):
            request_payout(self.seller, Decimal("5000.00"), 'UPI')

    def test_rejects_below_minimum(self):
        self._earn("1000.00")
        with self.assertRaises(ValidationError):
            request_payout(self.seller, Decimal("100.00"), 'UPI')

    @override_settings(SELLER_MIN_PAYOUT='100.00')
    def test_minimum_is_configurable(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        self.assertEqual(payout.amount, Decimal("900.00"))

    def test_settles_whole_earnings_only(self):
        """Requesting less than the oldest earning settles nothing, and says so."""
        self._earn("1000.00")                       # single 900 earning
        with self.assertRaises(ValidationError) as ctx:
            request_payout(self.seller, Decimal("600.00"), 'UPI')
        self.assertIn("900", str(ctx.exception))

    def test_picks_oldest_earnings_that_fit(self):
        self._earn("1000.00")   # net 900  (oldest)
        self._earn("2000.00")   # net 1800
        self.assertEqual(self._balance(), Decimal("2700.00"))

        payout = request_payout(self.seller, Decimal("1000.00"), 'UPI')

        # Only the 900 fits inside 1000; the payout is worth exactly that
        self.assertEqual(payout.amount, Decimal("900.00"))
        self.assertEqual(self._balance(), Decimal("1800.00"))
        self.assertEqual(SellerEarning.objects.filter(payout=payout).count(), 1)

    def test_payout_amount_always_equals_sum_of_its_earnings(self):
        self._earn("1000.00")
        self._earn("2000.00")
        payout = request_payout(self.seller, Decimal("2700.00"), 'UPI')

        linked = SellerEarning.objects.filter(payout=payout)
        self.assertEqual(
            payout.amount, sum(e.net_amount for e in linked)
        )

    def test_disabled_account_cannot_request(self):
        self._earn("1000.00")
        self.profile.is_reseller_enabled = False
        self.profile.save()
        with self.assertRaises(ValidationError):
            request_payout(self.seller, Decimal("900.00"), 'UPI')

    def test_destination_is_snapshotted(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'BANK_TRANSFER')

        self.profile.bank_account_number = "9999999999"
        self.profile.save()

        payout.refresh_from_db()
        # Editing the profile must not redirect an in-flight payout
        self.assertEqual(payout.bank_account_number, "1234567890")


class SellerPayoutLifecycleTests(SellerPayoutBase):
    def test_approve_then_complete_marks_earnings_paid(self):
        _, earning = self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')

        approve_payout(payout.id, self.admin)
        complete_payout(payout.id, transaction_id="TXN123", admin_user=self.admin)

        payout.refresh_from_db()
        earning.refresh_from_db()
        self.assertEqual(payout.status, 'COMPLETED')
        self.assertEqual(payout.transaction_id, "TXN123")
        self.assertEqual(earning.status, 'PAID')
        self.assertIsNotNone(earning.paid_at)
        self.assertEqual(self._balance(), Decimal("0.00"))

    def test_reject_refunds_and_releases_earnings(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        self.assertEqual(self._balance(), Decimal("0.00"))

        reject_payout(payout.id, self.admin, reason="Bank details invalid")

        payout.refresh_from_db()
        self.assertEqual(payout.status, 'REJECTED')
        self.assertEqual(self._balance(), Decimal("900.00"))
        self.assertEqual(get_settleable_total(self.seller), Decimal("900.00"))

    def test_reject_requires_reason(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        with self.assertRaises(ValidationError):
            reject_payout(payout.id, self.admin, reason="   ")

    def test_fail_refunds_so_it_can_be_retried(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        approve_payout(payout.id, self.admin)

        fail_payout(payout.id, reason="NEFT bounced", admin_user=self.admin)

        payout.refresh_from_db()
        self.assertEqual(payout.status, 'FAILED')
        self.assertEqual(self._balance(), Decimal("900.00"))

    def test_completed_payout_cannot_be_failed(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        approve_payout(payout.id, self.admin)
        complete_payout(payout.id, "TXN")
        with self.assertRaises(ValidationError):
            fail_payout(payout.id, reason="too late")

    def test_cannot_approve_twice(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        approve_payout(payout.id, self.admin)
        with self.assertRaises(ValidationError):
            approve_payout(payout.id, self.admin)

    def test_cannot_complete_a_pending_payout(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        with self.assertRaises(ValidationError):
            complete_payout(payout.id, "TXN")


class SellerPayoutRefundRaceTests(SellerPayoutBase):
    """
    The dangerous case: a customer is refunded after the seller has already
    locked that earning into a payout request.
    """

    def test_cancelling_locked_earning_does_not_debit_twice(self):
        order, earning = self._earn("1000.00")
        request_payout(self.seller, Decimal("900.00"), 'UPI')
        self.assertEqual(self._balance(), Decimal("0.00"))

        cancel_seller_earnings_for_order(order, reason="Customer refunded")

        # The money was already held by the payout. Debiting again would take
        # 900 off a seller who only ever earned 900.
        self.assertEqual(self._balance(), Decimal("0.00"))

    def test_payout_is_flagged_for_the_admin(self):
        order, _ = self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        cancel_seller_earnings_for_order(order, reason="Customer refunded")

        payout.refresh_from_db()
        self.assertIn("[ALERT]", payout.admin_notes)

    def test_approval_is_blocked_when_an_earning_was_cancelled(self):
        order, _ = self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        cancel_seller_earnings_for_order(order, reason="Customer refunded")

        with self.assertRaises(ValidationError) as ctx:
            approve_payout(payout.id, self.admin)
        self.assertIn("cancelled", str(ctx.exception).lower())

    def test_rejecting_does_not_refund_cancelled_money(self):
        order, _ = self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        cancel_seller_earnings_for_order(order, reason="Customer refunded")

        reject_payout(payout.id, self.admin, reason="Order was refunded")

        # The customer got their money back, so the seller must not also get it
        self.assertEqual(self._balance(), Decimal("0.00"))

    def test_partial_cancellation_refunds_only_the_live_part(self):
        order_a, _ = self._earn("1000.00")   # net 900 -> will be cancelled
        self._earn("2000.00")                # net 1800 -> stays live

        payout = request_payout(self.seller, Decimal("2700.00"), 'UPI')
        self.assertEqual(payout.amount, Decimal("2700.00"))
        self.assertEqual(self._balance(), Decimal("0.00"))

        cancel_seller_earnings_for_order(order_a, reason="Refunded")
        reject_payout(payout.id, self.admin, reason="Contains a refunded order")

        # 2700 held, 900 died with the refund -> 1800 comes back
        self.assertEqual(self._balance(), Decimal("1800.00"))


@override_settings(SELLER_TDS_ENABLED=True)
class SellerTdsTests(SellerPayoutBase):
    def test_tds_is_off_by_default(self):
        with override_settings(SELLER_TDS_ENABLED=False):
            self.assertEqual(calculate_tds(self.seller, Decimal("100000.00")), Decimal("0.00"))

    def test_below_threshold_with_pan_is_exempt(self):
        self.profile.pan_number = "ABCDE1234F"
        self.profile.save()
        self.assertEqual(calculate_tds(self.seller, Decimal("1000.00")), Decimal("0.00"))

    def test_above_threshold_with_pan_uses_standard_rate(self):
        self.profile.pan_number = "ABCDE1234F"
        self.profile.save()
        # 600000 clears the 500000 threshold -> 1%
        self.assertEqual(calculate_tds(self.seller, Decimal("600000.00")), Decimal("6000.00"))

    def test_no_pan_is_taxed_from_the_first_rupee(self):
        self.profile.pan_number = ""
        self.profile.save()
        # 5% higher rate, no small-seller exemption
        self.assertEqual(calculate_tds(self.seller, Decimal("1000.00")), Decimal("50.00"))

    def test_threshold_is_cumulative_across_the_year(self):
        """Splitting sales must not keep a seller under the threshold forever."""
        self.profile.pan_number = "ABCDE1234F"
        self.profile.save()

        # Bank 490000 of gross first
        self._earn("490000.00", confirm=False)
        self.assertEqual(calculate_tds(self.seller, Decimal("5000.00")), Decimal("0.00"))

        self._earn("20000.00", confirm=False)   # now 510000 YTD
        self.assertEqual(calculate_tds(self.seller, Decimal("1000.00")), Decimal("10.00"))

    def test_tds_is_deducted_from_net(self):
        self.profile.pan_number = ""
        self.profile.save()
        _, earning = self._earn("1000.00", confirm=False)
        # gross 1000, commission 10% = 100, tds 5% = 50 -> net 850
        self.assertEqual(earning.commission_amount, Decimal("100.00"))
        self.assertEqual(earning.tds_amount, Decimal("50.00"))
        self.assertEqual(earning.net_amount, Decimal("850.00"))

    def test_financial_year_starts_in_april(self):
        from datetime import date
        self.assertEqual(financial_year_start(date(2026, 3, 31)), date(2025, 4, 1))
        self.assertEqual(financial_year_start(date(2026, 4, 1)), date(2026, 4, 1))


class SellerGatewayTests(SellerPayoutBase):
    def test_gateway_is_disabled_by_default(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        approve_payout(payout.id, self.admin)

        with self.assertRaises(ValidationError) as ctx:
            send_via_gateway(payout.id, self.admin)
        self.assertIn("disabled", str(ctx.exception).lower())

    @override_settings(SELLER_PAYOUT_GATEWAY_ENABLED=True, RAZORPAY_KEY_ID='', RAZORPAY_KEY_SECRET='')
    def test_gateway_refuses_without_credentials(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        approve_payout(payout.id, self.admin)

        with self.assertRaises(ValidationError) as ctx:
            send_via_gateway(payout.id, self.admin)
        self.assertIn("not configured", str(ctx.exception).lower())

    @override_settings(SELLER_PAYOUT_GATEWAY_ENABLED=True)
    def test_gateway_refuses_unapproved_payout(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        with self.assertRaises(ValidationError):
            send_via_gateway(payout.id, self.admin)


class SellerSettlementReportTests(SellerPayoutBase):
    def test_report_totals(self):
        self._earn("1000.00")   # net 900
        self._earn("2000.00")   # net 1800
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')
        approve_payout(payout.id, self.admin)
        complete_payout(payout.id, "TXN")

        rows = seller_settlement_report(seller=self.seller)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['gross'], Decimal("3000.00"))
        self.assertEqual(row['commission'], Decimal("300.00"))
        self.assertEqual(row['net'], Decimal("2700.00"))
        self.assertEqual(row['paid'], Decimal("900.00"))
        self.assertEqual(row['outstanding'], Decimal("1800.00"))

    def test_cancelled_earnings_are_excluded(self):
        order, _ = self._earn("1000.00")
        cancel_seller_earnings_for_order(order, reason="refund")
        rows = seller_settlement_report(seller=self.seller)
        self.assertEqual(rows, [])
