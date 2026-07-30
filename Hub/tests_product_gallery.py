"""
Product page image gallery.

Two rules the page must keep:

* it opens on the product's own main image, never on a gallery photo;
* the main thumbnail is not filtered away by the colour filter.

Both broke in ways that only showed on products the automation published,
because those are the ones whose gallery images carry colour tags.

    python manage.py test Hub.tests_product_gallery
"""

from __future__ import annotations

import io
import re
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from Hub.models import Product, ProductImage

MEDIA = tempfile.mkdtemp(prefix='vm-gallery-tests-')

TEMPLATE = Path(settings.BASE_DIR) / 'Hub' / 'templates' / 'product-details.html'


def photo(shade: int) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGB', (400, 500), (shade, 40, 90)).save(buffer, format='JPEG')
    return buffer.getvalue()


@override_settings(MEDIA_ROOT=MEDIA)
class GalleryRenderTests(TestCase):
    """What the server hands the browser to start from."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = Client(SERVER_NAME='localhost')
        # The storefront gates anonymous visitors, so browse as a real user.
        self.client.force_login(User.objects.create_user('browser', password='pw'))

        self.product = Product.objects.create(
            name='Ikat Print Saree', price=899, old_price=1599,
            stock=10, color='Navy Blue', category='Women Wear',
            sub_category='Sarees', is_active=True,
        )
        self.product.image.save('hero.jpg', ContentFile(photo(30)), save=True)

        for index, shade in enumerate((90, 150, 210), start=1):
            row = ProductImage(
                product=self.product, color='Navy Blue',
                image_role='gallery', order=index, is_active=True,
            )
            row.image.save(f'g{index}.jpg', ContentFile(photo(shade)), save=True)
            row.save()

    def body(self) -> str:
        response = self.client.get(f'/product/{self.product.slug}/', secure=True, follow=True)
        self.assertEqual(response.status_code, 200)
        return response.content.decode('utf-8', 'replace')

    def test_the_stage_starts_on_the_main_image(self):
        stage = re.search(r'id="pddxMainImage"[^>]*src="([^"]+)"', self.body())
        self.assertIsNotNone(stage, 'the desktop stage image is missing')
        self.assertEqual(stage.group(1), self.product.image.url)

    def test_the_main_thumbnail_is_the_active_one(self):
        thumbs = re.findall(r'<button[^>]*class="pddx-thumb[^"]*"[^>]*>', self.body())
        self.assertGreaterEqual(len(thumbs), 4, 'hero plus three gallery images')
        self.assertIn('is-active', thumbs[0], 'the hero thumbnail starts selected')
        for other in thumbs[1:]:
            self.assertNotIn('is-active', other, 'only one thumbnail is selected')

    def test_the_main_thumbnail_carries_the_colour(self):
        """Without this the colour filter hides the hero on load."""
        thumbs = re.findall(r'<button[^>]*class="pddx-thumb[^"]*"[^>]*>', self.body())
        colour = re.search(r'data-image-color="([^"]*)"', thumbs[0])
        self.assertIsNotNone(colour)
        self.assertEqual(colour.group(1), 'Navy Blue')


class GalleryScriptTests(TestCase):
    """
    Guard the page-load contract in the script itself.

    The swap happens in the browser, so a rendered response cannot prove it.
    These assert the shape that keeps the hero on screen: both initial
    ``applyColorSelection`` calls must pass the keep-current-image flag.
    """

    def setUp(self):
        self.source = TEMPLATE.read_text(encoding='utf-8')

    def test_page_load_calls_keep_the_current_image(self):
        initial = re.findall(
            r"applyColorSelection\(\s*(?:initiallySelectedColor|firstSwatch)"
            r"\.getAttribute\('data-value'\) \|\| '',\s*null,\s*true\s*\)",
            self.source,
        )
        self.assertEqual(
            len(initial), 2,
            'both page-load colour calls must keep the main image on the stage',
        )

    def test_the_keep_flag_returns_before_touching_the_stage(self):
        body = self.source.split('function applyColorSelection(')[1]
        guard = body.index('keepCurrentImage')
        swap = body.index('pddxMainImage')
        self.assertLess(
            guard, swap,
            'the keep-current-image guard must come before the image swap',
        )

    def test_clicking_a_thumbnail_still_swaps(self):
        self.assertIn(
            "window._vmApplyColorSelection(thumbColor, src)", self.source,
            'thumbnail clicks pass no keep flag, so they still change the image',
        )
