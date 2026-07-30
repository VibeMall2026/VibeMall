"""
Framing protection.

Nobody else's page may embed this store in an iframe — that is how a lookalike
site wraps a real shop and passes it off as its own.

Django's XFrameOptionsMiddleware only sees responses that travel back up
through it, so a middleware short-circuiting *above* it produces a response
with no header at all. The coming-soon redirect did exactly that.

    python manage.py test Hub.tests_clickjacking
"""

from __future__ import annotations

from django.conf import settings
from django.test import Client, TestCase


class MiddlewareOrderTests(TestCase):
    def test_frame_protection_runs_before_short_circuiting_middleware(self):
        order = list(settings.MIDDLEWARE)
        frame = order.index('django.middleware.clickjacking.XFrameOptionsMiddleware')

        for name in order:
            if name.startswith('Hub.middleware.') and 'ComingSoon' in name:
                self.assertLess(
                    frame, order.index(name),
                    f'{name} can return a response on its own; frame protection '
                    'must sit above it or that response ships bare',
                )


class FrameHeaderTests(TestCase):
    """Every response leaves with the header, redirects included."""

    def setUp(self):
        self.client = Client(SERVER_NAME='localhost')

    def assertProtected(self, response, where):
        self.assertIn(
            'X-Frame-Options', response,
            f'{where} went out without frame protection',
        )
        self.assertEqual(response['X-Frame-Options'], 'DENY')

    def test_the_home_page_response_is_protected(self):
        self.assertProtected(self.client.get('/', secure=True), 'the home page')

    def test_a_redirect_is_protected(self):
        response = self.client.get('/', secure=True)
        if response.status_code in (301, 302):
            self.assertProtected(response, 'the redirect')

    def test_a_missing_page_is_protected(self):
        self.assertProtected(
            self.client.get('/no-such-page-here/', secure=True), 'the 404 page'
        )
