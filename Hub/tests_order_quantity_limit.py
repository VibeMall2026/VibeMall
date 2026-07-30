"""
Per-item order limit.

A shopper may take at most ``MAX_QUANTITY_PER_ITEM`` of any one product in a
single order. The storefront's ``max`` attribute is a convenience — every path
that can set a quantity is capped server-side, because that attribute is a
suggestion to the browser and nothing more.

    python manage.py test Hub.tests_order_quantity_limit
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from Hub.models import Cart, Product
from Hub.views import max_quantity_per_item


@override_settings(MAX_QUANTITY_PER_ITEM=2)
class MaxQuantityHelperTests(TestCase):
    def test_cap_applies_when_stock_is_plentiful(self):
        product = Product.objects.create(name='Kurti', price=899, stock=50)
        self.assertEqual(max_quantity_per_item(product), 2)

    def test_stock_wins_when_it_is_lower(self):
        product = Product.objects.create(name='Last one', price=899, stock=1)
        self.assertEqual(max_quantity_per_item(product), 1)

    def test_out_of_stock_allows_nothing(self):
        product = Product.objects.create(name='Gone', price=899, stock=0)
        self.assertEqual(max_quantity_per_item(product), 0)

    def test_the_limit_is_configurable(self):
        with override_settings(MAX_QUANTITY_PER_ITEM=5):
            product = Product.objects.create(name='Bulk', price=899, stock=50)
            self.assertEqual(max_quantity_per_item(product), 5)


@override_settings(MAX_QUANTITY_PER_ITEM=2)
class CartLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('shopper', password='pw')
        self.client = Client(SERVER_NAME='localhost')
        self.client.force_login(self.user)
        self.product = Product.objects.create(name='Sharara Set', price=899, stock=50)

    def add(self, quantity):
        return self.client.post(
            '/add-to-cart/',
            {'product_id': self.product.id, 'quantity': quantity},
            secure=True,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def quantity(self):
        item = Cart.objects.filter(user=self.user, product=self.product).first()
        return item.quantity if item else 0

    def test_a_single_oversized_add_is_capped(self):
        self.add(10)
        self.assertEqual(self.quantity(), 2)

    def test_repeated_adds_cannot_climb_past_the_limit(self):
        for _ in range(5):
            self.add(1)
        self.assertEqual(self.quantity(), 2, 'adding one at a time is still capped')

    def test_the_shopper_is_told_why(self):
        response = self.add(10)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertIn('Limit 2', payload['message'])
        self.assertEqual(payload['max_quantity'], 2)

    def test_an_ordinary_add_is_not_nagged(self):
        payload = self.add(1).json()
        self.assertNotIn('Limit', payload['message'])

    def test_updating_the_cart_is_capped_too(self):
        self.add(1)
        item = Cart.objects.get(user=self.user, product=self.product)
        self.client.post(f'/update-cart-quantity/{item.id}/', {'quantity': 9}, secure=True)
        self.assertEqual(self.quantity(), 2)

    def test_stock_below_the_limit_still_wins(self):
        self.product.stock = 1
        self.product.save(update_fields=['stock'])
        self.add(5)
        self.assertEqual(self.quantity(), 1)


@override_settings(MAX_QUANTITY_PER_ITEM=2)
class BuyNowLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('buyer', password='pw')
        self.client = Client(SERVER_NAME='localhost')
        self.client.force_login(self.user)
        self.product = Product.objects.create(name='Lehenga', price=2499, stock=50)

    def test_buy_now_refuses_more_than_the_limit(self):
        response = self.client.post(
            f'/buy-now/{self.product.id}/', {'quantity': 4}, secure=True,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload['success'])
        self.assertIn('up to 2', payload['message'])
        self.assertNotIn('buy_now_item', self.client.session)

    def test_buy_now_allows_the_limit(self):
        response = self.client.post(
            f'/buy-now/{self.product.id}/', {'quantity': 2}, secure=True,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(self.client.session['buy_now_item']['quantity'], 2)
