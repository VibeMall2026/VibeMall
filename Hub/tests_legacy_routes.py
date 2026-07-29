import ast
import collections
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class LegacyRouteTests(TestCase):
    """
    Three public URLs answered every request with a 500:

      /product/        rendered product.html, which does not exist
      /shop-details/   rendered shop-details.html, which does not exist
      /order-tracking/ called order_tracking() without the order_number it takes

    Nothing links to them, but they are addressable, so they now forward to the
    working page rather than erroring.
    """

    def test_legacy_product_url_forwards_to_the_catalogue(self):
        response = self.client.get('/product/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('shop'))

    def test_legacy_shop_details_url_forwards_to_the_catalogue(self):
        response = self.client.get('/shop-details/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('shop'))

    def test_legacy_order_tracking_url_forwards_to_the_lookup_page(self):
        response = self.client.get('/order-tracking/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('track_order'))

    def test_none_of_them_error_when_followed(self):
        for path in ('/product/', '/shop-details/', '/order-tracking/'):
            with self.subTest(path=path):
                response = self.client.get(path, follow=True)
                self.assertEqual(response.status_code, 200)

    def test_the_real_pages_still_answer(self):
        for name in ('shop', 'track_order'):
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)


class NoDuplicateViewTests(SimpleTestCase):
    """
    views.py carried six functions defined twice. Python keeps only the later
    definition, so the earlier one was dead - and editing it changed nothing,
    which is an expensive way to lose an afternoon. It also meant a reordering
    could silently swap which implementation ran.
    """

    def _source(self):
        return Path(settings.BASE_DIR, 'Hub', 'views.py').read_text(
            encoding='utf-8-sig')

    def test_no_view_is_defined_twice(self):
        names = [node.name for node in ast.parse(self._source()).body
                 if isinstance(node, ast.FunctionDef)]
        duplicates = {n: c for n, c in collections.Counter(names).items() if c > 1}
        self.assertEqual(
            duplicates, {},
            'These functions are defined more than once in views.py; only the '
            f'last definition ever runs: {sorted(duplicates)}',
        )

    def test_reachable_views_render_templates_that_exist(self):
        """
        A routed view rendering a template that was never added is a guaranteed
        500 for whoever opens that URL - which is how /product/, /shop-details/
        and /order-tracking/ behaved.

        Scoped to routed views on purpose. Hub/views_advanced_analytics.py has
        four views (traffic_analytics, conversion_funnel, scheduled_reports,
        add_scheduled_report) whose templates were never written, but they are
        not wired into any URL, so nobody can reach them. They are unfinished
        work to either complete or delete, not a live fault.
        """
        from django.template import TemplateDoesNotExist
        from django.template.loader import get_template
        from django.urls import get_resolver

        routed = set()

        def walk(patterns):
            for pattern in patterns:
                if hasattr(pattern, 'url_patterns'):
                    walk(pattern.url_patterns)
                elif getattr(pattern, 'callback', None) is not None:
                    routed.add(getattr(pattern.callback, '__name__', ''))

        walk(get_resolver().url_patterns)

        missing = []
        for py in Path(settings.BASE_DIR, 'Hub').rglob('*.py'):
            if py.name.startswith('tests'):
                continue
            try:
                tree = ast.parse(py.read_text(encoding='utf-8-sig', errors='replace'))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef) or node.name not in routed:
                    continue
                for call in ast.walk(node):
                    if not (isinstance(call, ast.Call)
                            and getattr(call.func, 'id', '') == 'render'
                            and len(call.args) >= 2
                            and isinstance(call.args[1], ast.Constant)
                            and isinstance(call.args[1].value, str)):
                        continue
                    name = call.args[1].value
                    try:
                        get_template(name)
                    except TemplateDoesNotExist:
                        missing.append(f'{py.name}:{node.name} -> {name}')

        self.assertEqual(
            missing, [],
            f'Routed views rendering templates that do not exist: {missing}',
        )
