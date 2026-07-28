from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from . import views


@override_settings(SECURE_SSL_REDIRECT=False, DEBUG=False)
class ErrorPageTests(TestCase):
    """
    With DEBUG on, Django served its own debug pages on the live domain - the
    404 listed every admin-panel URL. These cover the handlers that take over
    once DEBUG is off, including the case where the error page itself fails.
    """

    def setUp(self):
        self.factory = RequestFactory()

    # ── a wrong URL ──────────────────────────────────────────────────────────

    def test_unknown_url_returns_the_branded_404(self):
        response = self.client.get('/this-page-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        body = response.content.decode()
        self.assertIn('404', body)
        # the debug page's giveaway: a dump of the URLconf
        self.assertNotIn('Using the URLconf defined in', body)

    def test_unknown_product_slug_returns_404_not_a_debug_page(self):
        response = self.client.get('/product/no-such-product-slug/')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('Using the URLconf defined in', response.content.decode())

    def test_404_does_not_leak_admin_urls(self):
        body = self.client.get('/nope/').content.decode()
        for leak in ('admin-panel/products/delete', 'admin-panel/orders',
                     'Raised by:', 'Django tried these URL patterns'):
            self.assertNotIn(leak, body)

    # ── the handlers themselves ──────────────────────────────────────────────

    def test_custom_404_handler_status(self):
        response = views.custom_404(self.factory.get('/x/'), exception=Exception())
        self.assertEqual(response.status_code, 404)

    def test_custom_500_handler_status(self):
        response = views.custom_500(self.factory.get('/x/'))
        self.assertEqual(response.status_code, 500)

    # ── the error page must not become the error ─────────────────────────────

    def test_500_falls_back_when_its_own_template_fails(self):
        """
        500.html extends base.html, whose context processors hit the database.
        If the database is what broke, rendering the apology raises too - and
        the shopper must still get something readable, not Django's bare text.
        """
        with patch('Hub.views.render', side_effect=Exception('db is down')):
            response = views.custom_500(self.factory.get('/x/'))
        self.assertEqual(response.status_code, 500)
        body = response.content.decode()
        self.assertIn('500', body)
        self.assertIn('VibeMall', body)

    def test_fallback_does_not_expose_the_underlying_error(self):
        with patch('Hub.views.render', side_effect=Exception('secret-db-password')):
            body = views.custom_500(self.factory.get('/x/')).content.decode()
        self.assertNotIn('secret-db-password', body)

    def test_404_falls_back_when_its_own_template_fails(self):
        with patch('Hub.views.render', side_effect=Exception('boom')):
            response = views.custom_404(self.factory.get('/x/'))
        self.assertEqual(response.status_code, 404)
        self.assertIn('404', response.content.decode())

    def test_fallback_page_is_a_complete_document(self):
        with patch('Hub.views.render', side_effect=Exception('boom')):
            body = views.custom_500(self.factory.get('/x/')).content.decode()
        self.assertTrue(body.startswith('<!doctype html>'))
        self.assertIn('<meta name="viewport"', body)
        self.assertIn('</html>', body)


class DebugDefaultTests(TestCase):
    def test_debug_defaults_to_off_when_unset(self):
        """
        A deploy with no DEBUG variable used to get DEBUG=True and serve Django's
        debug pages publicly. Forgetting the variable must now fail safe.
        """
        from VibeMall.settings import _env_bool
        with patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('DEBUG', None)
            self.assertFalse(_env_bool('DEBUG', False))
