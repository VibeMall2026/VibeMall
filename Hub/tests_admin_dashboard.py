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
        """
        A container with no matching render() call is a blank box.

        Scoped to the dashboard's own naming convention (every real ApexCharts
        mount ends in "Chart" or "Radial") rather than every id="vm*" on the
        page - base_admin.html's AI usage widget also uses vm-prefixed ids for
        plain DOM elements it fills with textContent, not ApexCharts mounts,
        and a broader pattern would false-positive on those.
        """
        html = self._page()
        mounts = set(re.findall(r'id="(vm[A-Za-z]+(?:Chart|Radial))"', html))
        rendered = set(re.findall(r"render\('#(vm[A-Za-z]+(?:Chart|Radial))'", html))
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

    def test_trend_direction_is_not_carried_by_colour_alone(self):
        """
        Green/red chips are indistinguishable to a red-green colour blind
        reader. A triangle in ::before states the direction a second way.
        """
        template = TEMPLATE.read_text(encoding='utf-8')
        self.assertIn('.vm-chip--up::before', template)
        self.assertIn('.vm-chip--down::before', template)

    def test_the_hero_keeps_its_supporting_detail(self):
        """
        Moving the percentage up beside the label must not throw away what it
        is a percentage of - "12%" on its own says nothing.
        """
        html = self._page()
        for note in ('vs last period', 'product views', 'products active'):
            self.assertIn(note, html, f'the hero lost its "{note}" caption')

    def test_recent_orders_spans_the_full_width(self):
        """
        The table used to share a 12-column grid with the Performance and
        Top Selling cards below it, in an 8-column slot - that squeezed
        Amount and Date together. It now gets its own row at c12.
        """
        template = TEMPLATE.read_text(encoding='utf-8')
        head = template.split('<p class="vm-label">Recent Orders</p>', 1)[0]
        wrapper = head.rsplit('<div class="c', 1)[1]
        self.assertTrue(wrapper.startswith('12"'), 'Recent Orders is no longer full width')

    def test_each_order_row_has_a_details_button(self):
        html = self._page()
        self.assertIn('<th class="num">Details</th>', html)
        # setUp has no orders, so the {% empty %} branch renders on the live
        # page - the button markup is checked against the template source.
        template = TEMPLATE.read_text(encoding='utf-8')
        self.assertIn('vm-btn', template)
        self.assertIn('Show Details', template)
        self.assertIn('colspan="8"', template)

    def test_rows_below_recent_orders_are_grouped_in_even_pairs(self):
        """
        The old layout was two unequal stacks (4 cards left, 6 right), which
        left a blank gap on the left once it ran out before the right column
        did. Cards are grouped into rows now, each inside its own
        <div class="vm-grid">, so every row ends level: three equal charts,
        a full-width Top Selling banner, four equal lists, then Transactions
        on its own.
        """
        template = TEMPLATE.read_text(encoding='utf-8')
        rows = template.split('Bands 6 to 9', 1)[1].split('<div class="vm-grid">')[1:]
        labels = [re.search(r'vm-label">([^<]+)<', row).group(1) for row in rows[:4]]
        self.assertEqual(labels, ['Performance', 'Top Selling', 'Top Products', 'Transactions'])

    def test_transactions_is_a_full_width_table_with_a_date_column(self):
        """
        Transactions used to be a label/method list with no date and no
        per-row identifier - promoted to a table (like Recent Orders) so a
        transaction can actually be found again.
        """
        html = self._page()
        self.assertIn('<th>Transaction</th>', html)
        self.assertIn('<th class="num">Date</th>', html)

    def test_top_selling_is_a_full_width_banner(self):
        template = TEMPLATE.read_text(encoding='utf-8')
        head = template.split('<p class="vm-label">Top Selling</p>', 1)[0]
        wrapper = head.rsplit('<div class="c', 1)[1]
        self.assertTrue(wrapper.startswith('12"'), 'Top Selling is no longer full width')

    def test_top_products_and_low_stock_show_a_photo(self):
        """
        A product used to be identified only by rank number or bare name.
        A photo lets it be recognised the same way Recent Orders already
        shows thumbnails.
        """
        template = TEMPLATE.read_text(encoding='utf-8')
        top_block = template.split('Top Products</p>', 1)[1].split('</div>\n        </div>', 1)[0]
        low_block = template.split('Low Stock</p>', 1)[1].split('</div>\n        </div>', 1)[0]
        self.assertIn('vm-thumb', top_block)
        self.assertIn('vm-thumb', low_block)

    def test_recent_reviews_names_the_reviewer_and_shows_the_comment(self):
        """
        The card used to show only a product name and a star rating - no
        way to tell who said it or what they actually wrote.
        """
        template = TEMPLATE.read_text(encoding='utf-8')
        block = template.split('Recent Reviews</p>', 1)[1].split('Recent Customers</p>', 1)[0]
        self.assertIn('review.name', block)
        self.assertIn('review.comment', block)
        self.assertIn('review.created_at', block)
        self.assertIn('review.product.name', block, 'lost which product the review is about')

    def test_recent_customers_shows_an_email(self):
        html = self._page()
        template = TEMPLATE.read_text(encoding='utf-8')
        self.assertIn('customer.email', template)

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
