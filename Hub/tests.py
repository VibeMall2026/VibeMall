from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse
from django.test import TestCase, override_settings

from .email_utils import send_order_status_update_email
from .email_utils import _get_admin_notification_emails, _get_customer_notification_email
from .models import Order, OrderCancellationRequest, SiteSettings


class EmailUtilityTests(TestCase):
    def test_customer_email_prefers_persisted_order_email(self):
        order = SimpleNamespace(
            customer_email='checkout@example.com',
            user=SimpleNamespace(email='account@example.com'),
        )

        self.assertEqual(_get_customer_notification_email(order), 'checkout@example.com')

    def test_customer_email_falls_back_to_user_email(self):
        order = SimpleNamespace(
            customer_email='',
            user=SimpleNamespace(email='account@example.com'),
        )

        self.assertEqual(_get_customer_notification_email(order), 'account@example.com')

    @override_settings(ADMIN_NOTIFICATION_EMAILS='fallback@example.com')
    def test_admin_email_resolution_uses_site_and_staff_fallbacks(self):
        site_settings = SiteSettings.get_settings()
        site_settings.contact_email = 'contact@example.com'
        site_settings.save(update_fields=['contact_email'])

        staff_user = User.objects.create_user(
            username='admin01',
            email='staff@example.com',
            password='testpass123',
        )
        staff_user.is_staff = True
        staff_user.save(update_fields=['is_staff'])

        emails = _get_admin_notification_emails()

        self.assertIn('fallback@example.com', emails)
        self.assertIn('contact@example.com', emails)
        self.assertIn('staff@example.com', emails)


class OrderTrackingLiveStateTests(TestCase):
    def test_live_state_reflects_cancellation_request(self):
        user = User.objects.create_user(
            username='buyer01',
            email='buyer@example.com',
            password='testpass123',
        )
        order = Order.objects.create(
            user=user,
            customer_email='buyer@example.com',
            subtotal='100.00',
            tax='0.00',
            shipping_cost='0.00',
            total_amount='100.00',
            shipping_address='Test Street',
            billing_address='Test Street',
            payment_method='COD',
        )
        OrderCancellationRequest.objects.create(
            order=order,
            user=user,
            status='REQUESTED',
            reason='CHANGED_MIND',
        )

        self.client.force_login(user)
        response = self.client.get(
            reverse('order_tracking_live_state', args=[order.order_number]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['cancel_request_status'], 'REQUESTED')
        self.assertTrue(payload['signature'])


class CancellationEmailTests(TestCase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_cancellation_request_email_is_sent(self):
        user = User.objects.create_user(
            username='buyer02',
            email='buyer2@example.com',
            password='testpass123',
        )
        order = Order.objects.create(
            user=user,
            customer_email='buyer2@example.com',
            subtotal='100.00',
            tax='0.00',
            shipping_cost='0.00',
            total_amount='100.00',
            shipping_address='Test Street',
            billing_address='Test Street',
            payment_method='COD',
        )

        sent = send_order_status_update_email(order, old_status='PENDING', new_status='CANCEL_REQUESTED')

        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Cancellation Request Received', mail.outbox[0].subject)
        self.assertIn('buyer2@example.com', mail.outbox[0].to)
