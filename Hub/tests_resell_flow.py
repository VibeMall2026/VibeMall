from decimal import Decimal
from unittest.mock import patch

from django.test import Client
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Cart, Order, Product, ResellLink, ResellerEarning, ResellerProfile
from .resell_services import ResellOrderProcessor, ResellerPaymentManager, cancel_resell_order


def _tiny_image(name="test.gif"):
    # 1x1 transparent GIF
    return SimpleUploadedFile(
        name,
        (
            b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00"
            b"\x01\x00\x00\x02\x02D\x01\x00;"
        ),
        content_type="image/gif",
    )


class ResellOrderProcessorTests(TestCase):
    def setUp(self):
        self.reseller = User.objects.create_user(username="reseller", password="pass12345")
        self.customer = User.objects.create_user(username="customer", password="pass12345")

        self.linked_product = Product.objects.create(
            name="Linked Product",
            image=_tiny_image("linked.gif"),
            price=Decimal("100.00"),
            stock=20,
            is_active=True,
        )
        self.other_product = Product.objects.create(
            name="Other Product",
            image=_tiny_image("other.gif"),
            price=Decimal("200.00"),
            stock=20,
            is_active=True,
        )

        self.resell_link = ResellLink.objects.create(
            reseller=self.reseller,
            product=self.linked_product,
            resell_code="RSLTEST1",
            margin_amount=Decimal("20.00"),
            margin_percentage=Decimal("20.00"),
            is_active=True,
        )

    def test_create_resell_order_applies_margin_only_to_linked_product_and_points_discount(self):
        linked_item = Cart.objects.create(user=self.customer, product=self.linked_product, quantity=2)
        other_item = Cart.objects.create(user=self.customer, product=self.other_product, quantity=1)

        order = ResellOrderProcessor.create_resell_order(
            cart_items=[linked_item, other_item],
            resell_link=self.resell_link,
            customer=self.customer,
            shipping_address="Customer\nAddress",
            billing_address="Customer\nAddress",
            payment_method="COD",
            tax=Decimal("10.00"),
            shipping_cost=Decimal("0.00"),
            coupon_discount=Decimal("5.00"),
            points_discount=Decimal("3.00"),
            payment_status="PENDING",
        )

        self.assertEqual(order.base_amount, Decimal("400.00"))  # 100*2 + 200*1
        self.assertEqual(order.total_margin, Decimal("40.00"))  # margin only on linked product qty=2
        self.assertEqual(order.subtotal, Decimal("440.00"))
        self.assertEqual(order.total_amount, Decimal("442.00"))  # 440 + 10 - 5 - 3

        linked_order_item = order.items.get(product=self.linked_product)
        other_order_item = order.items.get(product=self.other_product)
        self.assertEqual(linked_order_item.margin_amount, Decimal("20.00"))
        self.assertEqual(linked_order_item.product_price, Decimal("120.00"))
        self.assertEqual(other_order_item.margin_amount, Decimal("0.00"))
        self.assertEqual(other_order_item.product_price, Decimal("200.00"))

        earning = ResellerEarning.objects.get(order=order)
        self.assertEqual(earning.margin_amount, Decimal("40.00"))

    def test_create_resell_order_requires_linked_product_in_items(self):
        other_item = Cart.objects.create(user=self.customer, product=self.other_product, quantity=1)

        with self.assertRaises(ValidationError):
            ResellOrderProcessor.create_resell_order(
                cart_items=[other_item],
                resell_link=self.resell_link,
                customer=self.customer,
                shipping_address="Customer\nAddress",
                billing_address="Customer\nAddress",
                payment_method="COD",
            )


class ManualResellCancellationTests(TestCase):
    def setUp(self):
        self.reseller = User.objects.create_user(username="manual-reseller", password="pass12345")
        self.customer = User.objects.create_user(username="manual-customer", password="pass12345")

    def test_cancel_manual_resell_order_without_resell_link(self):
        order = Order.objects.create(
            user=self.customer,
            subtotal=Decimal("120.00"),
            tax=Decimal("6.00"),
            shipping_cost=Decimal("0.00"),
            total_amount=Decimal("126.00"),
            shipping_address="Customer\nAddress",
            billing_address="Customer\nAddress",
            payment_method="COD",
            is_resell=True,
            reseller=self.reseller,
            base_amount=Decimal("100.00"),
            total_margin=Decimal("20.00"),
            resell_from_name="Manual Reseller",
            resell_from_phone="9999999999",
        )
        earning = ResellerEarning.objects.create(
            reseller=self.reseller,
            order=order,
            resell_link=None,
            margin_amount=Decimal("20.00"),
            status="PENDING",
        )

        cancel_resell_order(order)
        earning.refresh_from_db()
        self.assertEqual(earning.status, "CANCELLED")


class ResellerPayoutVerificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="payout-user", password="pass12345")
        self.profile = ResellerProfile.objects.create(
            user=self.user,
            is_reseller_enabled=True,
            available_balance=Decimal("500.00"),
        )
        self.client.login(username="payout-user", password="pass12345")

    @patch("Hub.views_resell._verify_upi_with_razorpay", return_value=(False, "", "UPI ID not found."))
    def test_reseller_profile_rejects_unverified_upi(self, _mock_upi_verify):
        response = self.client.post(
            reverse("reseller_profile"),
            {
                "business_name": "Test Shop",
                "upi_id": "wrong@upi",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.upi_id, "")

    @patch("Hub.views_resell._lookup_ifsc_details", return_value=(True, "State Bank of India", "Main Branch", ""))
    @patch("Hub.views_resell._verify_upi_with_razorpay", return_value=(True, "Payout User", ""))
    def test_reseller_profile_saves_normalized_verified_details(self, _mock_upi_verify, _mock_ifsc_lookup):
        response = self.client.post(
            reverse("reseller_profile"),
            {
                "business_name": "Test Shop",
                "bank_account_name": "Payout User",
                "bank_account_number": "1234 5678 9012",
                "bank_ifsc_code": "sbin0001234",
                "upi_id": "Payout.User@YBL",
                "pan_number": "abcde1234f",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bank_account_number, "123456789012")
        self.assertEqual(self.profile.bank_ifsc_code, "SBIN0001234")
        self.assertEqual(self.profile.upi_id, "payout.user@ybl")
        self.assertEqual(self.profile.pan_number, "ABCDE1234F")

    def test_process_payout_rejects_invalid_bank_account_number(self):
        with self.assertRaises(ValidationError):
            ResellerPaymentManager.process_payout(
                user_id=self.user.id,
                amount=Decimal("500.00"),
                payout_method="BANK_TRANSFER",
                payment_details={
                    "bank_account_number": "1234",
                    "bank_ifsc_code": "SBIN0001234",
                },
            )
