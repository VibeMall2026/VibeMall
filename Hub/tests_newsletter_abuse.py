"""
Newsletter signup abuse.

The form had a honeypot and double opt-in and was still stuffed with 2000+
scraped addresses. The gap: confirmation activated on a bare GET, and mail
filters fetch every link in an incoming email to scan it. So the bot never had
to read the victim's inbox — the victim's own mail provider confirmed for it.

    python manage.py test Hub.tests_newsletter_abuse
"""

from __future__ import annotations

from django.core import mail, signing
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from Hub.models import NewsletterSubscription
from Hub.views import NEWSLETTER_CONFIRMATION_SALT


def token_for(email: str, ip: str = '203.0.113.9') -> str:
    return signing.dumps(
        {'email': email, 'source_page': 'footer', 'client_ip': ip, 'user_agent': 'test'},
        salt=NEWSLETTER_CONFIRMATION_SALT,
    )


class ConfirmationRequiresAClickTests(TestCase):
    """A link scanner issues GETs; only a person presses the button."""

    def setUp(self):
        self.client = Client(SERVER_NAME='localhost')
        cache.clear()

    def url(self, email: str) -> str:
        return reverse('confirm_newsletter_subscription', args=[token_for(email)])

    def test_a_bare_get_does_not_subscribe_anyone(self):
        response = self.client.get(self.url('victim@example.com'), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            NewsletterSubscription.objects.filter(email='victim@example.com').exists(),
            'fetching the link is what mail scanners do automatically',
        )

    def test_the_get_shows_a_confirm_button(self):
        body = self.client.get(self.url('victim@example.com'), secure=True).content.decode()
        self.assertIn('Yes, subscribe me', body)
        self.assertIn('victim@example.com', body)

    def test_posting_the_form_subscribes(self):
        self.client.post(self.url('real@example.com'), {}, secure=True)
        subscriber = NewsletterSubscription.objects.filter(email='real@example.com').first()
        self.assertIsNotNone(subscriber, 'a real click must still work')
        self.assertTrue(subscriber.is_active)

    def test_a_tampered_token_is_refused(self):
        url = reverse('confirm_newsletter_subscription', args=['not-a-real-token'])
        self.client.post(url, {}, secure=True)
        self.assertEqual(NewsletterSubscription.objects.count(), 0)


class MailBombingTests(TestCase):
    """The form must not become a way to email a stranger repeatedly."""

    def setUp(self):
        self.client = Client(SERVER_NAME='localhost')
        cache.clear()
        mail.outbox = []

    def subscribe(self, email: str, ip: str = '198.51.100.7'):
        return self.client.post(
            reverse('subscribe_newsletter'),
            {'email': email, 'source_page': 'footer'},
            secure=True,
            REMOTE_ADDR=ip,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_the_first_request_sends_one_confirmation(self):
        self.subscribe('someone@example.com')
        self.assertEqual(len(mail.outbox), 1)

    def test_repeats_for_the_same_address_are_suppressed(self):
        for index in range(5):
            self.subscribe('someone@example.com', ip=f'198.51.100.{index + 1}')
        self.assertEqual(
            len(mail.outbox), 1,
            'rotating IPs must not let a bot mail the same victim over and over',
        )

    def test_a_suppressed_repeat_still_looks_successful(self):
        self.subscribe('someone@example.com')
        response = self.subscribe('someone@example.com', ip='198.51.100.99')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'], 'never confirm to a bot what was blocked')

    def test_the_honeypot_sends_nothing(self):
        self.client.post(
            reverse('subscribe_newsletter'),
            {'email': 'bot@example.com', 'website': 'http://spam.example'},
            secure=True,
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(NewsletterSubscription.objects.filter(email='bot@example.com').exists())


class AuditCommandTests(TestCase):
    def test_many_addresses_from_one_ip_are_flagged(self):
        from io import StringIO

        from django.core.management import call_command

        # A residential IP, but claiming to be six different people.
        for index in range(6):
            NewsletterSubscription.objects.create(
                email=f'person{index}@example.com', ip_address='49.36.99.1',
                user_agent='Mozilla', is_active=True,
            )
        # A household: two people sharing one connection.
        for index in range(2):
            NewsletterSubscription.objects.create(
                email=f'family{index}@example.com', ip_address='49.36.99.2',
                user_agent='Mozilla', is_active=True,
            )

        call_command('audit_newsletter', '--deactivate', stdout=StringIO())

        self.assertEqual(
            NewsletterSubscription.objects.filter(ip_address='49.36.99.1', is_active=True).count(),
            0, 'six people behind one IP is a list being stuffed, not a household',
        )
        self.assertEqual(
            NewsletterSubscription.objects.filter(ip_address='49.36.99.2', is_active=True).count(),
            2, 'a shared connection must not be punished',
        )

    def test_it_reports_without_changing_anything(self):
        from io import StringIO

        from django.core.management import call_command

        NewsletterSubscription.objects.create(
            email='bot@example.com', ip_address='192.210.150.199', user_agent='x', is_active=True,
        )
        NewsletterSubscription.objects.create(
            email='real@example.com', ip_address='49.36.1.2', user_agent='Mozilla', is_active=True,
        )

        out = StringIO()
        call_command('audit_newsletter', stdout=out)
        self.assertIn('suspect : 1', out.getvalue())
        self.assertEqual(NewsletterSubscription.objects.filter(is_active=True).count(), 2)

    def test_deactivate_quarantines_only_the_suspects(self):
        from io import StringIO

        from django.core.management import call_command

        NewsletterSubscription.objects.create(
            email='bot@example.com', ip_address='192.210.150.199', user_agent='x', is_active=True,
        )
        NewsletterSubscription.objects.create(
            email='nodata@example.com', ip_address=None, user_agent='', is_active=True,
        )
        NewsletterSubscription.objects.create(
            email='real@example.com', ip_address='49.36.1.2', user_agent='Mozilla', is_active=True,
        )

        call_command('audit_newsletter', '--deactivate', stdout=StringIO())

        self.assertFalse(NewsletterSubscription.objects.get(email='bot@example.com').is_active)
        self.assertFalse(NewsletterSubscription.objects.get(email='nodata@example.com').is_active)
        self.assertTrue(
            NewsletterSubscription.objects.get(email='real@example.com').is_active,
            'a genuine subscriber must survive the cleanup',
        )
        self.assertEqual(
            NewsletterSubscription.objects.count(), 3, 'nothing is deleted, only deactivated',
        )
