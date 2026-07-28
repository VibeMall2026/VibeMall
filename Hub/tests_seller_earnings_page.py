from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Order, OrderItem, Product, ResellerProfile
from .seller_earnings_service import create_seller_earnings


def _tiny_image(name="test.gif"):
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
class SellerEarningsPageTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username="page_seller", password="pass12345")
        self.other_seller = User.objects.create_user(username="page_other", password="pass12345")
        self.customer = User.objects.create_user(username="page_buyer", password="pass12345")
        self.admin = User.objects.create_user(
            username="page_admin", password="pass12345", is_staff=True, is_superuser=True,
        )

        ResellerProfile.objects.create(user=self.seller, is_reseller_enabled=True)
        ResellerProfile.objects.create(user=self.other_seller, is_reseller_enabled=True)

        self.my_product = Product.objects.create(
            name="Mine", image=_tiny_image("m.gif"), price=Decimal("100.00"),
            stock=10, is_active=True, created_by=self.seller,
        )
        self.their_product = Product.objects.create(
            name="Theirs", image=_tiny_image("t.gif"), price=Decimal("500.00"),
            stock=10, is_active=True, created_by=self.other_seller,
        )

        # One order containing both sellers' products
        order = Order.objects.create(
            user=self.customer, subtotal=Decimal("600.00"), total_amount=Decimal("600.00"),
            shipping_address="a", billing_address="a", payment_method="COD",
        )
        for product, price in ((self.my_product, "100.00"), (self.their_product, "500.00")):
            OrderItem.objects.create(
                order=order, product=product, product_name=product.name,
                product_price=Decimal(price), base_price=Decimal(price),
                quantity=1, subtotal=Decimal(price),
            )
        create_seller_earnings(order)
        self.url = reverse('admin_seller_earnings')

    def test_anonymous_is_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_plain_customer_cannot_open_page(self):
        self.client.login(username="page_buyer", password="pass12345")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_seller_sees_only_their_own_earnings(self):
        self.client.login(username="page_seller", password="pass12345")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['seller_mode'])
        rows = response.context['earnings'].object_list
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].seller, self.seller)
        # 100 gross - 10% = 90 net; the other seller's 500 must not leak
        self.assertEqual(rows[0].net_amount, Decimal("90.00"))
        self.assertNotContains(response, "450.00")

    def test_admin_sees_every_seller(self):
        self.client.login(username="page_admin", password="pass12345")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['seller_mode'])
        self.assertEqual(len(response.context['earnings'].object_list), 2)
        # No single balance makes sense for an admin
        self.assertIsNone(response.context['summary'])

    def test_status_filter_applies(self):
        self.client.login(username="page_admin", password="pass12345")
        response = self.client.get(self.url, {'status': 'CONFIRMED'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['earnings'].object_list), 0)

    def test_bad_status_falls_back_to_all(self):
        self.client.login(username="page_admin", password="pass12345")
        response = self.client.get(self.url, {'status': 'DROP TABLE'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['status_filter'], 'ALL')
        self.assertEqual(len(response.context['earnings'].object_list), 2)

    def test_search_by_order_number(self):
        self.client.login(username="page_seller", password="pass12345")
        response = self.client.get(self.url, {'search': 'NOSUCHORDER'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['earnings'].object_list), 0)
