from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (Order, OrderItem, Product, ProductReview, ReviewPromptLog,
                     UserProfile)


def _tiny_image(name="rp.gif"):
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
class ReviewPromptTests(TestCase):
    """
    The prompt was rate-limited by a counter in the cache, and the cache backend
    is LocMemCache: per-process, wiped on restart, not shared between workers.
    The counter read back as zero, so the popup returned on every login. It is
    now gated by a database row: one prompt per delivered product, ever.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="rp_buyer", password="pass12345")
        UserProfile.objects.get_or_create(user=self.user, defaults={'mobile_number': '9876543210'})
        self.product = Product.objects.create(
            name="Delivered Thing", image=_tiny_image(), price=Decimal("500.00"),
            stock=5, is_active=True,
        )
        self.order = Order.objects.create(
            user=self.user, subtotal=Decimal('500.00'), total_amount=Decimal('500.00'),
            payment_method='RAZORPAY', payment_status='PAID',
            order_status='DELIVERED', delivery_date=timezone.now(),
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, product_name=self.product.name,
            product_price=Decimal('500.00'), quantity=1, subtotal=Decimal('500.00'),
        )

    def _visit(self):
        """A page load as the shopper. Returns whether the prompt was rendered."""
        response = self.client.get(reverse('shop'))
        self.assertEqual(response.status_code, 200)
        return response.context.get('mobile_review_prompt') is not None

    def _fresh_session(self):
        """A new login, as if the shopper came back tomorrow."""
        self.client.logout()
        self.client.login(username="rp_buyer", password="pass12345")

    # ── the reported problem ─────────────────────────────────────────────────

    def test_prompt_appears_once_then_never_again(self):
        self.client.login(username="rp_buyer", password="pass12345")
        self.assertTrue(self._visit(), 'the first visit after delivery should prompt')

        # same session
        self.assertFalse(self._visit())

        # and after logging out and back in, repeatedly
        for attempt in range(3):
            self._fresh_session()
            self.assertFalse(
                self._visit(),
                f'the prompt came back on login #{attempt + 2}',
            )

    def test_showing_it_writes_exactly_one_row(self):
        self.client.login(username="rp_buyer", password="pass12345")
        self._visit()
        self._fresh_session()
        self._visit()
        self.assertEqual(
            ReviewPromptLog.objects.filter(user=self.user, product=self.product).count(), 1)

    def test_clearing_the_cache_does_not_bring_it_back(self):
        """The old guard lived in the cache, which is wiped on every restart."""
        from django.core.cache import cache

        self.client.login(username="rp_buyer", password="pass12345")
        self.assertTrue(self._visit())
        cache.clear()
        self._fresh_session()
        self.assertFalse(self._visit())

    # ── it still does its job ────────────────────────────────────────────────

    def test_a_second_delivered_product_gets_its_own_prompt(self):
        self.client.login(username="rp_buyer", password="pass12345")
        self.assertTrue(self._visit())

        other = Product.objects.create(
            name="Another Thing", image=_tiny_image("rp2.gif"),
            price=Decimal("300.00"), stock=5, is_active=True,
        )
        OrderItem.objects.create(
            order=self.order, product=other, product_name=other.name,
            product_price=Decimal('300.00'), quantity=1, subtotal=Decimal('300.00'),
        )
        self._fresh_session()
        self.assertTrue(self._visit(), 'a newly delivered product should prompt once')
        self.assertEqual(ReviewPromptLog.objects.filter(user=self.user).count(), 2)

    def test_no_prompt_before_delivery(self):
        self.order.order_status = 'SHIPPED'
        self.order.save()
        self.client.login(username="rp_buyer", password="pass12345")
        self.assertFalse(self._visit())
        self.assertEqual(ReviewPromptLog.objects.count(), 0)

    def test_no_prompt_for_an_already_reviewed_product(self):
        ProductReview.objects.create(product=self.product, user=self.user, rating=5,
                                     comment='Great')
        self.client.login(username="rp_buyer", password="pass12345")
        self.assertFalse(self._visit())

    def test_no_prompt_for_anonymous_visitors(self):
        self.assertFalse(self._visit())
        self.assertEqual(ReviewPromptLog.objects.count(), 0)

    # ── dismissing ───────────────────────────────────────────────────────────

    def test_dismiss_marks_the_row_answered(self):
        self.client.login(username="rp_buyer", password="pass12345")
        self._visit()
        response = self.client.post(reverse('mobile_review_prompt_dismiss'),
                                    {'product_id': self.product.id})
        self.assertEqual(response.status_code, 200)
        log = ReviewPromptLog.objects.get(user=self.user, product=self.product)
        self.assertTrue(log.responded)

    def test_dismiss_without_a_product_id_still_succeeds(self):
        self.client.login(username="rp_buyer", password="pass12345")
        self._visit()
        response = self.client.post(reverse('mobile_review_prompt_dismiss'))
        self.assertEqual(response.status_code, 200)

    def test_one_row_per_user_and_product(self):
        from django.db import IntegrityError, transaction

        ReviewPromptLog.objects.create(user=self.user, product=self.product)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ReviewPromptLog.objects.create(user=self.user, product=self.product)
