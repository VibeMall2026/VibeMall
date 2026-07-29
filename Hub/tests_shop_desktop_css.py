from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Product


def _tiny_image(name="sd.gif"):
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
class ShopDesktopStyleTests(TestCase):
    """
    Both fixes are asserted against the served page, not the stylesheet on disk.
    shop-desktop-alt.css only reaches a browser after collectstatic runs on the
    serving box, so a file-level check can pass while shoppers still see the old
    layout - which is exactly what happened here.
    """

    def setUp(self):
        Product.objects.create(
            name="Shop Style Item", image=_tiny_image(), price=Decimal("500.00"),
            stock=3, is_active=True,
        )

    def _page(self):
        response = self.client.get(reverse('shop'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _rule(self, html, selector):
        self.assertIn(selector, html, f'{selector} is not served with the page')
        return html.split(selector, 1)[1].split('}', 1)[0]

    # ── the doubled dropdown arrow ───────────────────────────────────────────

    def test_sort_select_suppresses_the_native_arrow(self):
        """
        appearance:none on its own left the browser's arrow drawn beside the
        ::after chevron, so the control showed two.
        """
        rule = self._rule(self._page(), '.vm-shop-d-sort-wrap select {')
        for prop in ('-webkit-appearance: none', '-moz-appearance: none', 'appearance: none'):
            self.assertIn(prop, rule, f'sort select is missing {prop}')

    # ── the empty white slab under list rows ─────────────────────────────────

    def test_list_view_thumbnail_is_capped_not_pinned(self):
        rule = self._rule(self._page(), '.vm-shop-d-grid.list-view .vm-shop-d-thumb {')
        self.assertIn('max-height: 240px', rule)
        # Without this the base rule's 340px min-height still wins and the row
        # stays exactly as tall as before.
        self.assertIn('min-height: 0', rule)
        self.assertNotIn('min-height: 340px', rule)

    def test_list_view_card_centres_its_columns(self):
        rule = self._rule(self._page(), '.vm-shop-d-grid.list-view .vm-shop-d-card {')
        self.assertIn('align-items: center', rule)

    # ── grid view keeps its taller thumbnail ─────────────────────────────────

    def test_the_override_is_scoped_to_list_view(self):
        html = self._page()
        thumb_rule = self._rule(html, '.vm-shop-d-grid.list-view .vm-shop-d-thumb {')
        self.assertIn('list-view', '.vm-shop-d-grid.list-view .vm-shop-d-thumb {')
        # the cap must not be written as a bare .vm-shop-d-thumb rule, which
        # would shrink the grid thumbnails too
        for block in html.split('<style>')[1:]:
            self.assertNotIn('\n  .vm-shop-d-thumb {', block)
        self.assertIn('max-height: 240px', thumb_rule)
