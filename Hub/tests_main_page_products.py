"""
Main page management: the product dropdowns must offer every product.

They were sliced to 50, 200 and 500. The ordering is by units sold, so the
products cut off were the newest ones with no sales yet — exactly the products
an admin opens this page to feature.

    python manage.py test Hub.tests_main_page_products
"""

from __future__ import annotations

import re

from django.contrib.auth.models import User
from django.test import Client, TestCase

from Hub.models import Product


class ProductDropdownTests(TestCase):
    #: Comfortably past every cap that used to be in the view.
    PRODUCTS = 120

    def setUp(self):
        self.client = Client(SERVER_NAME='localhost')
        self.client.force_login(
            User.objects.create_user('mp_admin', is_staff=True, is_superuser=True)
        )
        for index in range(self.PRODUCTS):
            Product.objects.create(
                name=f'Product {index:03}', price=100 + index,
                stock=5, sold=0, is_active=True,
            )
        # One best-seller, to prove ordering is not what hides the rest.
        Product.objects.create(name='Bestseller', price=999, stock=5, sold=500, is_active=True)

    def options(self, body: str, position: int = 0) -> list[str]:
        block = body.split('name="product_id"')[position + 1].split('</select>')[0]
        return [value for value in re.findall(r'<option value="(\d*)"', block) if value]

    def page(self, section: str) -> str:
        response = self.client.get(
            f'/admin-panel/main-page-products/?section={section}', secure=True
        )
        self.assertEqual(response.status_code, 200)
        return response.content.decode('utf-8', 'replace')

    def test_every_active_product_is_offered(self):
        options = self.options(self.page('categories'))
        self.assertEqual(
            len(options), self.PRODUCTS + 1,
            'the dropdown must not be truncated',
        )

    def test_a_product_with_no_sales_is_still_offered(self):
        """Ordering by -sold put new products last, and the slice cut them."""
        body = self.page('categories')
        newest = Product.objects.get(name='Product 119')
        self.assertIn(f'<option value="{newest.id}"', body)

    def test_inactive_products_stay_out(self):
        hidden = Product.objects.create(name='Retired', price=10, stock=0, is_active=False)
        body = self.page('categories')
        self.assertNotIn(f'<option value="{hidden.id}"', body)

    def test_the_ready_ship_dropdown_is_complete_too(self):
        options = self.options(self.page('ready_ship'))
        self.assertEqual(len(options), self.PRODUCTS + 1)

    def test_the_dropdowns_are_filterable(self):
        body = self.page('categories')
        self.assertIn('data-filters="mainPageProductSelect"', body)
        self.assertIn('id="mainPageProductSelect"', body)

    def test_the_count_shown_matches_what_is_offered(self):
        body = self.page('categories')
        self.assertIn(f'Showing all {self.PRODUCTS + 1} active products', body)
