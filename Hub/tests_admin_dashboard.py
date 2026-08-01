import ast
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

TEMPLATE = Path(settings.BASE_DIR, 'Hub', 'templates', 'admin_panel', 'dashboard.html')


@override_settings(SECURE_SSL_REDIRECT=False)
class DashboardRendersTests(TestCase):
    """The redesigned dashboard has to keep working, not just look different."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='dash_admin', password='pass12345', is_staff=True, is_superuser=True)
        self.client.login(username='dash_admin', password='pass12345')

    def _page(self):
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_it_loads_on_an_empty_shop(self):
        """No orders, no products, no customers - it must still render."""
        self._page()

    def test_every_chart_has_a_mount_point(self):
        html = self._page()
        for chart in ('vmYearChart', 'vmOrdersRadial', 'vmVisitorsChart',
                      'vmActivityChart', 'vmPerformanceChart', 'vmFinanceChart',
                      'vmDailySalesChart'):
            self.assertIn(f'id="{chart}"', html, f'{chart} has no container')

    def test_every_chart_is_actually_rendered(self):
        """A container with no matching render() call is a blank box."""
        html = self._page()
        mounts = set(re.findall(r'id="(vm[A-Za-z]+)"', html))
        rendered = set(re.findall(r"render\('#(vm[A-Za-z]+)'", html))
        self.assertEqual(mounts - rendered, set(),
                         'these containers are never rendered into')

    def test_the_five_bands_are_present(self):
        html = self._page()
        for marker in ('Total Revenue', 'Income, Expense', 'Order Pipeline',
                       'Conversion Funnel', 'New Visitors', 'Returns &amp; Refunds',
                       'Recent Orders'):
            self.assertIn(marker, html, f'missing section: {marker}')

    def test_no_template_comment_leaks_into_the_page(self):
        """
        Django's {% comment %} must not reach the browser. JavaScript comments
        inside <script> legitimately do, so only the template-side markers are
        checked here.
        """
        html = self._page()
        for leak in ('BAND 1', 'BAND 5', 'endcomment',
                     'the four figures that answer'):
            self.assertNotIn(leak, html)

    def test_recent_orders_shows_product_thumbnails(self):
        html = self._page()
        self.assertIn('<th>Items</th>', html)
        self.assertIn('vm-stack', html)
        self.assertIn('.vm-stack__more', html, 'the "+N" badge has no styling')

    def test_the_orders_table_uses_the_prefetched_queryset(self):
        """
        The thumbnails read order.items. Only recent_order_items prefetches
        them; looping recent_orders instead would fire one extra query per row.
        """
        template = TEMPLATE.read_text(encoding='utf-8')
        table = template.split('<th>Items</th>', 1)[1].split('</table>', 1)[0]
        self.assertIn('for order in recent_order_items', table)
        self.assertNotIn('for order in recent_orders', table)

    def test_a_product_without_an_image_still_renders(self):
        """A missing image must show an initial, not a broken tile."""
        template = TEMPLATE.read_text(encoding='utf-8')
        self.assertIn('vm-stack__fallback', template)

    def test_charts_survive_a_missing_library(self):
        """ApexCharts is guarded, so the page is readable without it."""
        html = self._page()
        self.assertIn("typeof ApexCharts === 'undefined'", html)
        self.assertIn('Chart unavailable', html)


class DashboardKeepsEveryMetricTests(SimpleTestCase):
    """
    The redesign changed the layout, not the data. The first pass silently
    dropped 21 metrics - a whole Finance card, Top Products, the visitor
    comparison series - because a new layout is written from scratch and it is
    easy to forget what was on the old one. This compares the template against
    the view rather than against memory.
    """

    def _context_keys(self):
        source = Path(settings.BASE_DIR, 'Hub', 'views.py').read_text(encoding='utf-8-sig')
        keys = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.FunctionDef) and node.name == 'admin_dashboard':
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Dict):
                        for key in sub.keys:
                            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                keys.add(key.value)
        return keys

    def test_the_view_still_supplies_a_full_context(self):
        """Guards the guard: if this drops to nothing, the check below is empty."""
        self.assertGreater(len(self._context_keys()), 50)

    def test_no_metric_is_dropped_by_the_template(self):
        template = TEMPLATE.read_text(encoding='utf-8')
        missing = sorted(k for k in self._context_keys() if k not in template)
        self.assertEqual(
            missing, [],
            'admin_dashboard computes these but the dashboard never shows them: '
            + ', '.join(missing),
        )

    def test_the_legacy_dashboard_is_kept(self):
        """Somewhere to look if a figure seems wrong after the redesign."""
        legacy = Path(settings.BASE_DIR, 'Hub', 'templates', 'admin_panel',
                      'dashboard_legacy.html')
        self.assertTrue(legacy.exists(), 'the previous dashboard was not preserved')

    def test_the_design_tokens_are_used(self):
        """Hex values should come from the design system, not be invented."""
        template = TEMPLATE.read_text(encoding='utf-8')
        for token in ('#fbf9f4', '#171818', '#6f5c37', '#dcc397', '#e6e2da'):
            self.assertIn(token, template, f'{token} from DESIGN.md is unused')
