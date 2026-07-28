from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Order, OrderItem, Product, ResellerProfile, SellerPayout
from .seller_earnings_service import confirm_seller_earnings_for_order, create_seller_earnings
from .seller_payout_service import request_payout


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


@override_settings(SECURE_SSL_REDIRECT=False)
class SellerPayoutPageTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username="pg_seller", password="pass12345")
        self.other = User.objects.create_user(username="pg_other", password="pass12345")
        self.customer = User.objects.create_user(username="pg_buyer", password="pass12345")
        self.admin = User.objects.create_user(
            username="pg_admin", password="pass12345", is_staff=True, is_superuser=True,
        )
        for user in (self.seller, self.other):
            ResellerProfile.objects.create(
                user=user, is_reseller_enabled=True,
                bank_account_name="N", bank_account_number="123", bank_ifsc_code="IFSC0001",
                upi_id=f"{user.username}@upi",
            )
        self.product = Product.objects.create(
            name="P", image=_tiny_image("p.gif"), price=Decimal("1000.00"),
            stock=50, is_active=True, created_by=self.seller,
        )
        self.request_url = reverse('admin_seller_payout')
        self.manage_url = reverse('admin_seller_payouts')
        self.report_url = reverse('admin_seller_settlements')

    def _earn(self, amount="1000.00", seller=None, product=None):
        product = product or self.product
        order = Order.objects.create(
            user=self.customer, subtotal=Decimal(amount), total_amount=Decimal(amount),
            shipping_address="a", billing_address="a", payment_method="COD",
        )
        OrderItem.objects.create(
            order=order, product=product, product_name=product.name,
            product_price=Decimal(amount), base_price=Decimal(amount),
            quantity=1, subtotal=Decimal(amount),
        )
        create_seller_earnings(order)
        confirm_seller_earnings_for_order(order)
        return order

    # ── access ───────────────────────────────────────────────────────────────

    def test_customer_cannot_reach_any_payout_page(self):
        self.client.login(username="pg_buyer", password="pass12345")
        for url in (self.request_url, self.manage_url, self.report_url):
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_admin_is_redirected_from_the_seller_request_page(self):
        """An admin has no balance of their own to withdraw."""
        self.client.login(username="pg_admin", password="pass12345")
        response = self.client.get(self.request_url)
        self.assertRedirects(response, self.manage_url)

    # ── requesting ───────────────────────────────────────────────────────────

    def test_seller_can_request_a_payout(self):
        self._earn("1000.00")
        self.client.login(username="pg_seller", password="pass12345")

        response = self.client.post(self.request_url, {
            'amount': '900.00', 'payout_method': 'UPI', 'upi_id': 'pg_seller@upi',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        payout = SellerPayout.objects.get(seller=self.seller)
        self.assertEqual(payout.amount, Decimal("900.00"))
        self.assertEqual(payout.status, 'PENDING')

    def test_invalid_amount_shows_an_error_not_a_crash(self):
        self._earn("1000.00")
        self.client.login(username="pg_seller", password="pass12345")

        response = self.client.post(self.request_url, {
            'amount': 'not-a-number', 'payout_method': 'UPI',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SellerPayout.objects.count(), 0)

    def test_over_balance_request_is_refused(self):
        self._earn("1000.00")
        self.client.login(username="pg_seller", password="pass12345")

        self.client.post(self.request_url, {
            'amount': '99999.00', 'payout_method': 'UPI',
        }, follow=True)

        self.assertEqual(SellerPayout.objects.count(), 0)

    # ── managing ─────────────────────────────────────────────────────────────

    def test_seller_sees_only_their_own_payouts(self):
        self._earn("1000.00")
        request_payout(self.seller, Decimal("900.00"), 'UPI')

        other_product = Product.objects.create(
            name="OP", image=_tiny_image("op.gif"), price=Decimal("2000.00"),
            stock=10, is_active=True, created_by=self.other,
        )
        self._earn("2000.00", product=other_product)
        request_payout(self.other, Decimal("1800.00"), 'UPI')

        self.client.login(username="pg_seller", password="pass12345")
        response = self.client.get(self.manage_url)

        self.assertEqual(response.status_code, 200)
        rows = response.context['payouts'].object_list
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].seller, self.seller)

    def test_seller_cannot_approve_their_own_payout(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')

        self.client.login(username="pg_seller", password="pass12345")
        self.client.post(self.manage_url, {'action': 'approve', 'payout_id': payout.id}, follow=True)

        payout.refresh_from_db()
        self.assertEqual(payout.status, 'PENDING')

    def test_admin_can_approve_and_complete(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')

        self.client.login(username="pg_admin", password="pass12345")
        self.client.post(self.manage_url, {'action': 'approve', 'payout_id': payout.id}, follow=True)
        payout.refresh_from_db()
        self.assertEqual(payout.status, 'APPROVED')

        self.client.post(self.manage_url, {
            'action': 'complete', 'payout_id': payout.id, 'note': 'UTR999',
        }, follow=True)
        payout.refresh_from_db()
        self.assertEqual(payout.status, 'COMPLETED')
        self.assertEqual(payout.transaction_id, 'UTR999')

    def test_admin_reject_returns_the_money(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')

        self.client.login(username="pg_admin", password="pass12345")
        self.client.post(self.manage_url, {
            'action': 'reject', 'payout_id': payout.id, 'note': 'Wrong UPI',
        }, follow=True)

        payout.refresh_from_db()
        profile = self.seller.reseller_profile
        profile.refresh_from_db()
        self.assertEqual(payout.status, 'REJECTED')
        self.assertEqual(profile.seller_available_balance, Decimal("900.00"))

    def test_unknown_action_is_rejected_cleanly(self):
        self._earn("1000.00")
        payout = request_payout(self.seller, Decimal("900.00"), 'UPI')

        self.client.login(username="pg_admin", password="pass12345")
        response = self.client.post(self.manage_url, {
            'action': 'delete_everything', 'payout_id': payout.id,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        payout.refresh_from_db()
        self.assertEqual(payout.status, 'PENDING')

    # ── settlements ──────────────────────────────────────────────────────────

    def test_settlement_report_renders_for_admin(self):
        self._earn("1000.00")
        self.client.login(username="pg_admin", password="pass12345")
        response = self.client.get(self.report_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['totals']['gross'], Decimal("1000.00"))
        self.assertEqual(response.context['totals']['commission'], Decimal("100.00"))

    def test_settlement_report_is_scoped_for_a_seller(self):
        self._earn("1000.00")
        other_product = Product.objects.create(
            name="OP2", image=_tiny_image("op2.gif"), price=Decimal("5000.00"),
            stock=10, is_active=True, created_by=self.other,
        )
        self._earn("5000.00", product=other_product)

        self.client.login(username="pg_seller", password="pass12345")
        response = self.client.get(self.report_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['rows']), 1)
        self.assertEqual(response.context['totals']['gross'], Decimal("1000.00"))

    def test_csv_export(self):
        self._earn("1000.00")
        self.client.login(username="pg_admin", password="pass12345")
        response = self.client.get(self.report_url, {'export': 'csv'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        body = response.content.decode()
        self.assertIn('Seller,Gross,Commission,TDS,Net,Paid,Outstanding', body)
        self.assertIn('TOTAL', body)
