from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .loyalty_manager import LoyaltyPointsManager
from .models import LoyaltyPoints, Order, OrderItem, PointsTransaction, Product


def _tiny_image(name="la.gif"):
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
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LoyaltyAwardTests(TestCase):
    """
    Points were being awarded from two places at once. The status-update email
    used a rate of its own - Rs.1 = 33 points - with no return-window wait and
    no duplicate guard, so a Rs.1,260 order handed out 41,580 points and one
    live account reached 476,665. Only the delivery signal may award now.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="la_buyer", password="pass12345", email="la@example.com")
        self.product = Product.objects.create(
            name="Points Item", image=_tiny_image(), price=Decimal("1260.00"),
            stock=5, is_active=True, is_returnable=True, return_days=7,
        )
        self.order = Order.objects.create(
            user=self.user, subtotal=Decimal('1260.00'), total_amount=Decimal('1260.00'),
            payment_method='RAZORPAY', payment_status='PAID',
            order_status='SHIPPED', customer_email='la@example.com',
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, product_name=self.product.name,
            product_price=Decimal('1260.00'), quantity=1, subtotal=Decimal('1260.00'),
        )

    def _points(self):
        account = LoyaltyPoints.objects.filter(user=self.user).first()
        return account.points_available if account else 0

    # ── the runaway award ────────────────────────────────────────────────────

    def test_the_status_email_awards_nothing(self):
        from .email_utils import send_order_status_update_email

        send_order_status_update_email(self.order, 'SHIPPED', 'DELIVERED')
        self.assertEqual(
            self._points(), 0,
            'sending an email must not move money',
        )
        self.assertEqual(PointsTransaction.objects.count(), 0)

    def test_a_delivered_order_does_not_award_33x_the_amount(self):
        """Rs.1,260 at the old email rate was 41,580 points."""
        self.order.order_status = 'DELIVERED'
        self.order.delivery_date = timezone.now()
        self.order.save()
        self.assertLess(self._points(), 1000)

    # ── the correct path still works ─────────────────────────────────────────

    def test_no_points_while_the_return_window_is_open(self):
        self.order.order_status = 'DELIVERED'
        self.order.delivery_date = timezone.now()
        self.order.save()
        self.assertEqual(self._points(), 0)

    def test_points_land_once_the_return_window_has_passed(self):
        self.order.order_status = 'DELIVERED'
        self.order.delivery_date = timezone.now() - timedelta(days=8)
        self.order.save()
        # Rs.1,260 at Rs.100 = 10 points
        self.assertEqual(self._points(), 126)

    def test_an_order_is_never_awarded_twice(self):
        self.order.order_status = 'DELIVERED'
        self.order.delivery_date = timezone.now() - timedelta(days=8)
        self.order.save()
        first = self._points()
        self.order.save()
        self.order.save()
        self.assertEqual(self._points(), first, 're-saving awarded the order again')

    def test_the_award_matches_the_published_rate(self):
        self.order.order_status = 'DELIVERED'
        self.order.delivery_date = timezone.now() - timedelta(days=8)
        self.order.save()
        expected = LoyaltyPointsManager.calculate_points_earned(self.order.total_amount)
        self.assertEqual(self._points(), expected)
        # and those points are worth 1% of the order
        self.assertEqual(LoyaltyPointsManager.calculate_rupee_value(expected),
                         Decimal('12.60'))
