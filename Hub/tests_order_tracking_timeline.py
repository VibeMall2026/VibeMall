from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Order, OrderItem, Product, UserProfile


def _tiny_image(name="ot.gif"):
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
class OrderTrackingTimelineTests(TestCase):
    """
    The tracking timeline had no notion of a cancelled order, so a cancelled
    order still showed Processing/In Transit/Delivered as "Pending" - it read as
    though the parcel were still on its way. The steps were also emitted out of
    order: In Transit above Order Received.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ot_buyer", password="pass12345")
        UserProfile.objects.get_or_create(user=self.user, defaults={'mobile_number': '9876543210'})
        self.product = Product.objects.create(
            name="Tracked Item", image=_tiny_image(), price=Decimal("500.00"),
            stock=5, is_active=True,
        )
        self.order = Order.objects.create(
            user=self.user, subtotal=Decimal('500.00'), total_amount=Decimal('500.00'),
            payment_method='RAZORPAY', payment_status='PAID',
            order_status='PENDING', shipping_address='46 Sangam Soc, Surat',
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, product_name=self.product.name,
            product_price=Decimal('500.00'), quantity=1, subtotal=Decimal('500.00'),
        )
        self.client.login(username="ot_buyer", password="pass12345")

    def _page(self):
        response = self.client.get(reverse('order_tracking',
                                           args=[self.order.order_number]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _positions(self, html):
        return {label: html.find(f'<h4>{label}</h4>')
                for label in ('Order Received', 'Processing', 'In Transit', 'Delivered')}

    def _track(self, html=None):
        """
        Just the timeline markup. The page's <style> block defines the state
        classes, so searching the whole document for them always matches.
        """
        html = html if html is not None else self._page()
        return html.split('<div class="vm-tod-track">', 1)[1].split('vm-tod-address', 1)[0]

    # ── the sequence ─────────────────────────────────────────────────────────

    def test_steps_run_oldest_to_newest(self):
        pos = self._positions(self._page())
        for label, index in pos.items():
            self.assertNotEqual(index, -1, f'{label} step is missing')
        self.assertLess(pos['Order Received'], pos['Processing'])
        self.assertLess(pos['Processing'], pos['In Transit'])
        self.assertLess(pos['In Transit'], pos['Delivered'])

    # ── a cancelled order ────────────────────────────────────────────────────

    def test_cancelled_order_shows_a_cancelled_step(self):
        self.order.order_status = 'CANCELLED'
        self.order.save()
        html = self._page()
        self.assertIn('<h4>Cancelled</h4>', html)
        self.assertIn('This order was cancelled.', html)

    def test_cancelled_order_stops_saying_pending(self):
        self.order.order_status = 'CANCELLED'
        self.order.save()
        track = self._track()
        self.assertNotIn('>Pending<', track)
        self.assertIn('Not applicable', track)

    def test_cancelled_order_voids_the_later_steps(self):
        self.order.order_status = 'CANCELLED'
        self.order.save()
        # Processing, In Transit and Delivered are all struck through
        self.assertEqual(self._track().count('vm-tod-event--void'), 3)

    def test_cancelled_order_hides_the_tracking_number(self):
        self.order.order_status = 'CANCELLED'
        self.order.tracking_number = 'TRK123456'
        self.order.save()
        self.assertNotIn('TRK123456', self._page())

    def test_refunded_cancellation_says_so(self):
        self.order.order_status = 'CANCELLED'
        self.order.payment_status = 'REFUNDED'
        self.order.save()
        self.assertIn('has been refunded', self._page())

    def test_paid_cancellation_promises_a_refund(self):
        self.order.order_status = 'CANCELLED'
        self.order.payment_status = 'PAID'
        self.order.save()
        self.assertIn('will be refunded', self._page())

    # ── a live order is untouched ────────────────────────────────────────────

    def test_pending_order_still_shows_pending_steps(self):
        track = self._track()
        self.assertNotIn('<h4>Cancelled</h4>', track)
        self.assertNotIn('vm-tod-event--void', track)
        self.assertIn('Pending', track)

    def test_shipped_order_marks_transit_active_and_keeps_tracking_number(self):
        self.order.order_status = 'SHIPPED'
        self.order.tracking_number = 'TRK999'
        self.order.save()
        track = self._track()
        self.assertIn('TRK999', track)
        self.assertIn('handed to courier', track)
        self.assertNotIn('vm-tod-event--void', track)

    def test_delivered_order_completes_the_timeline(self):
        self.order.order_status = 'DELIVERED'
        self.order.save()
        track = self._track()
        self.assertIn('delivered successfully', track)
        self.assertNotIn('vm-tod-event--void', track)
