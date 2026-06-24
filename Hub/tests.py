from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .email_utils import _get_admin_notification_emails, _get_customer_notification_email
from .models import SiteSettings


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
