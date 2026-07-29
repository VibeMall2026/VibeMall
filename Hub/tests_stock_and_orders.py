from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from . import views
from .email_utils import notify_back_in_stock
from .models import (Order, OrderItem, Product, ProductStockNotification,
                     Refund, ReturnRequest, UserProfile)


def _tiny_image(name="st.gif"):
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
class StockReservationTests(TestCase):
    """
    Nothing reduced stock when an order was placed. Only cancellations and
    returns touched it, and only upwards - so a product could be sold any number
    of times, never went out of stock, and every return inflated its stock by a
    quantity that had never been taken out.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="st_buyer", password="pass12345")
        UserProfile.objects.get_or_create(user=self.user, defaults={'mobile_number': '9876543210'})
        self.product = Product.objects.create(
            name="Limited Item", image=_tiny_image(), price=Decimal("500.00"),
            stock=3, sold=0, is_active=True,
        )

    def _order(self, quantity=1):
        order = Order.objects.create(
            user=self.user, subtotal=Decimal('500.00'), total_amount=Decimal('500.00'),
            payment_method='COD', payment_status='PENDING', order_status='PENDING',
        )
        OrderItem.objects.create(
            order=order, product=self.product, product_name=self.product.name,
            product_price=Decimal('500.00'), quantity=quantity,
            subtotal=Decimal('500.00') * quantity,
        )
        return order

    def test_reserving_reduces_stock_and_records_the_sale(self):
        ok, message = views._reserve_stock_for_order(self._order(2))
        self.assertTrue(ok, message)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(self.product.sold, 2)

    def test_cannot_order_more_than_is_in_stock(self):
        ok, message = views._reserve_stock_for_order(self._order(5))
        self.assertFalse(ok)
        self.assertIn('only 3 left', message)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3, 'a rejected order must not touch stock')
        self.assertEqual(self.product.sold, 0)

    def test_the_last_unit_cannot_be_sold_twice(self):
        self.product.stock = 1
        self.product.save()
        first_ok, _ = views._reserve_stock_for_order(self._order(1))
        second_ok, message = views._reserve_stock_for_order(self._order(1))
        self.assertTrue(first_ok)
        self.assertFalse(second_ok, 'the second order took stock that was gone')
        self.assertIn('only 0 left', message)

    def test_nothing_is_reserved_if_any_line_fails(self):
        """A part-filled order would be worse than a rejected one."""
        other = Product.objects.create(
            name="Plenty", image=_tiny_image("st2.gif"), price=Decimal("100.00"),
            stock=50, sold=0, is_active=True,
        )
        order = self._order(99)          # more than the 3 in stock
        OrderItem.objects.create(
            order=order, product=other, product_name=other.name,
            product_price=Decimal('100.00'), quantity=1, subtotal=Decimal('100.00'),
        )
        ok, _ = views._reserve_stock_for_order(order)
        self.assertFalse(ok)
        other.refresh_from_db()
        self.assertEqual(other.stock, 50, 'the healthy line was reserved anyway')

    def test_releasing_puts_stock_back_and_undoes_the_sale(self):
        order = self._order(2)
        views._reserve_stock_for_order(order)
        views._release_stock_for_order(order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(self.product.sold, 0)

    def test_release_never_drives_sold_negative(self):
        """Orders placed before reservation existed were never counted as sold."""
        order = self._order(2)           # not reserved
        views._release_stock_for_order(order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.sold, 0)
        self.assertEqual(self.product.stock, 5, 'stock still returns')


@override_settings(SECURE_SSL_REDIRECT=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BackInStockTests(TestCase):
    """
    The waiting list was always collected, but only two admin screens sent
    anything - and stock coming back through a cancellation or return, the
    commonest way an item reappears, notified nobody.
    """

    def setUp(self):
        self.product = Product.objects.create(
            name="Sold Out Thing", image=_tiny_image("bs.gif"), price=Decimal("900.00"),
            stock=0, is_active=True,
        )
        ProductStockNotification.objects.create(
            product=self.product, email='waiting@example.com')

    def test_notifies_when_stock_returns_from_zero(self):
        self.product.stock = 4
        self.product.save()
        self.assertEqual(notify_back_in_stock(self.product, previous_stock=0), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Back in stock', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['waiting@example.com'])

    def test_email_carries_the_product_and_a_link(self):
        self.product.stock = 4
        self.product.save()
        notify_back_in_stock(self.product, previous_stock=0)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Sold Out Thing', html)
        self.assertIn('900', html)
        self.assertIn(f'/product-details/{self.product.id}/', html)

    def test_each_person_is_told_only_once(self):
        self.product.stock = 4
        self.product.save()
        notify_back_in_stock(self.product, previous_stock=0)
        mail.outbox.clear()
        notify_back_in_stock(self.product, previous_stock=0)
        self.assertEqual(len(mail.outbox), 0)

    def test_topping_up_existing_stock_is_not_news(self):
        self.product.stock = 10
        self.product.save()
        self.assertEqual(notify_back_in_stock(self.product, previous_stock=5), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_a_cancellation_notifies_the_waiting_list(self):
        """This is the path that used to send nothing at all."""
        buyer = User.objects.create_user(username="bs_buyer", password="pass12345")
        order = Order.objects.create(
            user=buyer, subtotal=Decimal('900.00'), total_amount=Decimal('900.00'),
            payment_method='COD', payment_status='PENDING', order_status='PENDING',
        )
        OrderItem.objects.create(
            order=order, product=self.product, product_name=self.product.name,
            product_price=Decimal('900.00'), quantity=1, subtotal=Decimal('900.00'),
        )
        views._release_stock_for_order(order)
        self.assertEqual(len(mail.outbox), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)


@override_settings(SECURE_SSL_REDIRECT=False)
class RefundProgressTests(TestCase):
    """'Where is my money' answered on the return page."""

    def setUp(self):
        self.user = User.objects.create_user(username="rf_buyer", password="pass12345")
        self.order = Order.objects.create(
            user=self.user, subtotal=Decimal('1000.00'), total_amount=Decimal('1000.00'),
            payment_method='RAZORPAY', payment_status='PAID',
            razorpay_payment_id='pay_ABC', order_status='DELIVERED',
        )
        self.rr = ReturnRequest.objects.create(
            order=self.order, user=self.user, status='REQUESTED',
            refund_method='RAZORPAY',
        )

    def test_before_qc_it_says_the_refund_has_not_started(self):
        progress = views._refund_progress(self.rr)
        self.assertEqual(progress['stage'], 'waiting')
        self.assertIn('quality check', progress['detail'])

    def test_after_qc_it_says_processing(self):
        self.rr.status = 'REFUND_PENDING'
        progress = views._refund_progress(self.rr)
        self.assertEqual(progress['stage'], 'processing')

    def test_once_refunded_it_states_route_and_timing(self):
        self.rr.status = 'REFUNDED'
        self.rr.refund_amount = Decimal('1000.00')
        self.rr.refund_fee = Decimal('20.00')
        self.rr.refund_amount_net = Decimal('980.00')
        self.rr.refund_date = timezone.now()
        progress = views._refund_progress(self.rr)
        self.assertEqual(progress['stage'], 'done')
        self.assertEqual(progress['net'], Decimal('980.00'))
        self.assertIn('5-7', progress['eta'])
        self.assertIn('original payment method', progress['method_label'].lower())

    def test_a_rejected_return_says_no_refund_is_due(self):
        self.rr.status = 'REJECTED'
        self.assertEqual(views._refund_progress(self.rr)['stage'], 'none')

    def test_the_gateway_reference_is_shown_once_it_exists(self):
        self.rr.status = 'REFUNDED'
        Refund.objects.create(
            order=self.order, razorpay_payment_id='pay_ABC',
            razorpay_refund_id='rfnd_XYZ', refund_amount=Decimal('980.00'),
            status='SUCCESS', reason='Return',
        )
        self.assertEqual(views._refund_progress(self.rr)['gateway_reference'], 'rfnd_XYZ')

    def test_wallet_refunds_are_described_as_instant(self):
        self.rr.status = 'REFUNDED'
        self.rr.refund_method = 'WALLET'
        progress = views._refund_progress(self.rr)
        self.assertIn('instant', progress['eta'])

    def test_the_page_renders_the_panel(self):
        from django.urls import reverse

        self.client.login(username="rf_buyer", password="pass12345")
        response = self.client.get(reverse('return_status', args=[self.rr.id]))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('vm-refund-progress', body)
        self.assertIn('Refund not started yet', body)

    def test_a_refunded_return_shows_the_amount_on_the_page(self):
        from django.urls import reverse

        self.rr.status = 'REFUNDED'
        self.rr.refund_amount = Decimal('1000.00')
        self.rr.refund_fee = Decimal('20.00')
        self.rr.refund_amount_net = Decimal('980.00')
        self.rr.refund_date = timezone.now()
        self.rr.save()

        self.client.login(username="rf_buyer", password="pass12345")
        body = self.client.get(reverse('return_status', args=[self.rr.id])).content.decode()
        self.assertIn('Refund issued', body)
        self.assertIn('980.00', body)
        self.assertIn('vm-refund-progress--done', body)
