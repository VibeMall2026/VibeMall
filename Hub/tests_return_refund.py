from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import views
from .models import Order, OrderItem, Product, Refund, ReturnRequest, UserProfile


def _tiny_image(name="r.gif"):
    return SimpleUploadedFile(
        name,
        (
            b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00"
            b"\x01\x00\x00\x02\x02D\x01\x00;"
        ),
        content_type="image/gif",
    )


@override_settings(SECURE_SSL_REDIRECT=False,
                   RAZORPAY_KEY_ID='rzp_test_key', RAZORPAY_KEY_SECRET='secret')
class PrepaidReturnRefundTests(TestCase):
    """
    A prepaid return has to be able to go back down the rail it came in on.
    The customer form only offered wallet/bank/UPI, so the money could never
    return to the card unless an admin remembered to change the dropdown.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="buyer", password="pass12345")
        UserProfile.objects.get_or_create(user=self.user, defaults={'mobile_number': '9876543210'})
        self.product = Product.objects.create(
            name="Returnable", image=_tiny_image(), price=Decimal("1000.00"),
            stock=5, is_active=True,
        )
        self.client.login(username="buyer", password="pass12345")

    def _order(self, method='RAZORPAY', status='PAID', payment_id='pay_ABC123'):
        order = Order.objects.create(
            user=self.user, subtotal=Decimal('1000.00'), total_amount=Decimal('1000.00'),
            payment_method=method, payment_status=status,
            razorpay_payment_id=payment_id, order_status='DELIVERED',
            delivery_date=timezone.now(),
        )
        OrderItem.objects.create(
            order=order, product=self.product, product_name=self.product.name,
            product_price=Decimal('1000.00'), quantity=1, subtotal=Decimal('1000.00'),
        )
        return order

    # ── which options a shopper is offered ───────────────────────────────────

    def test_prepaid_order_can_refund_to_source(self):
        self.assertTrue(views._can_refund_to_source(self._order()))

    def test_cod_order_cannot_refund_to_source(self):
        order = self._order(method='COD', status='PENDING', payment_id='')
        self.assertFalse(views._can_refund_to_source(order))

    def test_unpaid_razorpay_order_cannot_refund_to_source(self):
        self.assertFalse(views._can_refund_to_source(self._order(status='PENDING')))

    def test_razorpay_order_without_payment_id_cannot_refund_to_source(self):
        self.assertFalse(views._can_refund_to_source(self._order(payment_id='')))

    def test_lowercase_payment_method_still_counts_as_prepaid(self):
        """payment_method is written from several places; don't trust its case."""
        self.assertTrue(views._can_refund_to_source(self._order(method='razorpay')))

    # ── the SDK import that broke every refund ───────────────────────────────

    def test_refund_helper_reaches_the_gateway(self):
        """
        razorpay 1.4.1 has no NoDataError, so importing it threw ImportError and
        every refund fell into the "SDK not installed" branch - a real gateway
        call was never made. Any message about installing the SDK means the
        import is broken again.
        """
        with patch('razorpay.Client') as client_cls:
            client = client_cls.return_value
            client.payment.fetch.return_value = {'amount': 100000, 'amount_refunded': 0}
            client.payment.refund.return_value = {'id': 'rfnd_1', 'status': 'processed'}
            ok, err = views._create_razorpay_refund('pay_ABC123', Decimal('10.00'), notes={})
        self.assertTrue(ok, err)
        self.assertTrue(client.payment.refund.called, "the gateway was never called")

    def test_sdk_missing_message_is_not_produced_when_it_is_installed(self):
        with patch('razorpay.Client') as client_cls:
            client_cls.return_value.payment.fetch.side_effect = Exception('boom')
            _, err = views._create_razorpay_refund('pay_ABC123', Decimal('10.00'), notes={})
        self.assertNotIn('pip install razorpay', err)

    # ── the audit row ────────────────────────────────────────────────────────

    def test_successful_refund_is_recorded(self):
        order = self._order()
        with patch('razorpay.Client') as client_cls:
            client = client_cls.return_value
            client.payment.fetch.return_value = {'amount': 100000, 'amount_refunded': 0}
            client.payment.refund.return_value = {'id': 'rfnd_XYZ', 'status': 'processed'}
            ok, err = views._create_razorpay_refund(
                'pay_ABC123', Decimal('980.00'),
                notes={'reason': 'Return #1'}, order=order,
            )
        self.assertTrue(ok, err)
        refund = Refund.objects.get(order=order)
        self.assertEqual(refund.razorpay_refund_id, 'rfnd_XYZ')
        self.assertEqual(refund.refund_amount, Decimal('980.00'))
        self.assertEqual(refund.status, 'SUCCESS')

    def test_refund_capped_to_remaining_is_recorded_at_the_capped_amount(self):
        """Razorpay caps the refund; the row must show what actually moved."""
        order = self._order()
        with patch('razorpay.Client') as client_cls:
            client = client_cls.return_value
            client.payment.fetch.return_value = {'amount': 100000, 'amount_refunded': 60000}
            client.payment.refund.return_value = {'id': 'rfnd_CAP', 'status': 'processed'}
            ok, _ = views._create_razorpay_refund(
                'pay_ABC123', Decimal('1000.00'), notes={}, order=order,
            )
        self.assertTrue(ok)
        self.assertEqual(Refund.objects.get(order=order).refund_amount, Decimal('400.00'))

    def test_failed_refund_writes_no_row(self):
        order = self._order()
        with patch('razorpay.Client') as client_cls:
            client = client_cls.return_value
            client.payment.fetch.return_value = {'amount': 100000, 'amount_refunded': 0}
            client.payment.refund.side_effect = Exception('gateway down')
            ok, err = views._create_razorpay_refund(
                'pay_ABC123', Decimal('980.00'), notes={}, order=order,
            )
        self.assertFalse(ok)
        self.assertIn('gateway down', err)
        self.assertFalse(Refund.objects.filter(order=order).exists())

    def test_recording_twice_does_not_duplicate(self):
        order = self._order()
        for _ in range(2):
            views._record_refund(order, 'pay_ABC123', 'rfnd_SAME', Decimal('100.00'), 'x')
        self.assertEqual(Refund.objects.filter(order=order).count(), 1)

    def test_bookkeeping_failure_does_not_break_a_completed_refund(self):
        """The money has already moved; a DB problem must not report failure."""
        order = self._order()
        with patch('razorpay.Client') as client_cls, \
             patch('Hub.models.Refund.objects.get_or_create', side_effect=Exception('db gone')):
            client = client_cls.return_value
            client.payment.fetch.return_value = {'amount': 100000, 'amount_refunded': 0}
            client.payment.refund.return_value = {'id': 'rfnd_OK', 'status': 'processed'}
            ok, err = views._create_razorpay_refund(
                'pay_ABC123', Decimal('980.00'), notes={}, order=order,
            )
        self.assertTrue(ok, err)

    # ── showing where the money will land ────────────────────────────────────

    def test_summary_reads_a_upi_payment(self):
        order = self._order()
        with patch('razorpay.Client') as client_cls:
            client_cls.return_value.payment.fetch.return_value = {
                'id': 'pay_ABC123', 'method': 'upi', 'vpa': 'shopper@okhdfc',
                'amount': 100000, 'amount_refunded': 20000, 'contact': '+919876543210',
            }
            summary = views._razorpay_payment_summary(order)
        self.assertEqual(summary['method'], 'UPI')
        self.assertEqual(summary['instrument'], 'shopper@okhdfc')
        self.assertEqual(summary['captured'], Decimal('1000.00'))
        self.assertEqual(summary['refunded'], Decimal('200.00'))
        self.assertEqual(summary['refundable'], Decimal('800.00'))

    def test_summary_reads_a_card_payment(self):
        order = self._order()
        with patch('razorpay.Client') as client_cls:
            client_cls.return_value.payment.fetch.return_value = {
                'id': 'pay_ABC123', 'method': 'card', 'amount': 100000,
                'amount_refunded': 0,
                'card': {'last4': '1234', 'network': 'Visa', 'issuer': 'HDFC'},
            }
            summary = views._razorpay_payment_summary(order)
        self.assertEqual(summary['method'], 'CARD')
        self.assertIn('****1234', summary['instrument'])
        self.assertIn('Visa', summary['instrument'])

    def test_summary_reads_a_netbanking_payment(self):
        order = self._order()
        with patch('razorpay.Client') as client_cls:
            client_cls.return_value.payment.fetch.return_value = {
                'id': 'pay_ABC123', 'method': 'netbanking', 'bank': 'SBIN',
                'amount': 100000, 'amount_refunded': 0,
            }
            summary = views._razorpay_payment_summary(order)
        self.assertEqual(summary['instrument'], 'SBIN')

    def test_summary_is_none_for_cod(self):
        order = self._order(method='COD', status='PENDING', payment_id='')
        self.assertIsNone(views._razorpay_payment_summary(order))

    def test_summary_survives_a_gateway_outage(self):
        """A dead API must not take the return page down with it."""
        order = self._order()
        with patch('razorpay.Client') as client_cls:
            client_cls.return_value.payment.fetch.side_effect = Exception('timeout')
            self.assertIsNone(views._razorpay_payment_summary(order))

    def test_fully_refunded_payment_shows_nothing_left(self):
        order = self._order()
        with patch('razorpay.Client') as client_cls:
            client_cls.return_value.payment.fetch.return_value = {
                'id': 'pay_ABC123', 'method': 'upi', 'vpa': 'a@b',
                'amount': 100000, 'amount_refunded': 100000,
            }
            summary = views._razorpay_payment_summary(order)
        self.assertEqual(summary['refundable'], Decimal('0.00'))

    # ── end to end through the return refund helper ──────────────────────────

    def test_process_refund_sends_a_prepaid_return_back_to_razorpay(self):
        order = self._order()
        rr = ReturnRequest.objects.create(order=order, user=self.user,
                                          refund_method='RAZORPAY')
        with patch('razorpay.Client') as client_cls:
            client = client_cls.return_value
            client.payment.fetch.return_value = {'amount': 100000, 'amount_refunded': 0}
            client.payment.refund.return_value = {'id': 'rfnd_RET', 'status': 'processed'}
            ok, notes = views._process_refund(rr, Decimal('1000.00'))
        self.assertTrue(ok, notes)
        # _process_refund mutates the return request and leaves persisting it to
        # admin_return_detail, which saves once at the end of the POST. Only the
        # order is saved by the helper itself, so that one is re-read.
        order.refresh_from_db()
        # ₹20 collection fee comes off before the gateway call
        self.assertEqual(rr.refund_amount_net, Decimal('980.00'))
        self.assertEqual(rr.refund_method, 'RAZORPAY')
        self.assertEqual(order.payment_status, 'REFUNDED')
        self.assertEqual(Refund.objects.get(order=order).razorpay_refund_id, 'rfnd_RET')

    def test_wallet_choice_still_credits_the_wallet(self):
        order = self._order()
        rr = ReturnRequest.objects.create(order=order, user=self.user,
                                          refund_method='WALLET')
        ok, _ = views._process_refund(rr, Decimal('1000.00'))
        self.assertTrue(ok)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.wallet_balance, Decimal('980.00'))
        self.assertFalse(Refund.objects.filter(order=order).exists())

    def test_missing_payment_id_is_reported_not_silently_passed(self):
        order = self._order(payment_id='')
        rr = ReturnRequest.objects.create(order=order, user=self.user,
                                          refund_method='RAZORPAY')
        ok, notes = views._process_refund(rr, Decimal('1000.00'))
        self.assertFalse(ok)
        self.assertIn('payment id missing', notes.lower())
