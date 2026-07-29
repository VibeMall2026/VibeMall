from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Order, OrderItem, Product


def _tiny_image(name="bo.gif"):
    return SimpleUploadedFile(
        name,
        (
            b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00"
            b"\x01\x00\x00\x02\x02D\x01\x00;"
        ),
        content_type="image/gif",
    )


@override_settings(SECURE_SSL_REDIRECT=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdminBulkOrderActionTests(TestCase):
    """
    Every bulk action on the orders screen returned a 500. order_scope was read
    inside the POST branch but only assigned further down the view, after that
    branch - so Python raised UnboundLocalError before anything was deleted or
    updated. Both the delete and the status actions were affected.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            username="bo_admin", password="pass12345", is_staff=True, is_superuser=True)
        self.buyer = User.objects.create_user(
            username="bo_buyer", password="pass12345", email="bo@example.com")
        self.product = Product.objects.create(
            name="Bulk Item", image=_tiny_image(), price=Decimal("500.00"),
            stock=50, is_active=True,
        )
        self.client.login(username="bo_admin", password="pass12345")

    def _orders(self, count=3):
        made = []
        for _ in range(count):
            order = Order.objects.create(
                user=self.buyer, subtotal=Decimal('500.00'), total_amount=Decimal('500.00'),
                payment_method='COD', payment_status='PENDING', order_status='PENDING',
            )
            OrderItem.objects.create(
                order=order, product=self.product, product_name=self.product.name,
                product_price=Decimal('500.00'), quantity=1, subtotal=Decimal('500.00'),
            )
            made.append(order)
        return made

    def _post(self, action, orders):
        return self.client.post(reverse('admin_orders'), {
            'action': action,
            'selected_orders': [str(o.id) for o in orders],
        })

    # ── the reported failure ─────────────────────────────────────────────────

    def test_bulk_delete_does_not_error(self):
        orders = self._orders(3)
        response = self._post('delete', orders)
        self.assertEqual(response.status_code, 302, 'bulk delete returned an error page')

    def test_bulk_delete_removes_the_orders(self):
        orders = self._orders(3)
        self._post('delete', orders)
        self.assertEqual(Order.objects.filter(id__in=[o.id for o in orders]).count(), 0)

    def test_bulk_delete_removes_the_order_items_too(self):
        orders = self._orders(2)
        self._post('delete', orders)
        self.assertEqual(OrderItem.objects.filter(order__in=orders).count(), 0)

    def test_deleting_every_order_at_once(self):
        """The exact case reported: select all, delete."""
        orders = self._orders(8)
        response = self._post('delete', orders)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

    # ── the other bulk action, broken by the same line ───────────────────────

    def test_bulk_status_update_does_not_error(self):
        orders = self._orders(2)
        response = self._post('SHIPPED', orders)
        self.assertEqual(response.status_code, 302)

    def test_bulk_status_update_applies(self):
        orders = self._orders(2)
        self._post('SHIPPED', orders)
        for order in orders:
            order.refresh_from_db()
            self.assertEqual(order.order_status, 'SHIPPED')

    # ── guard rails ──────────────────────────────────────────────────────────

    def test_an_action_with_no_selection_is_harmless(self):
        self._orders(2)
        response = self.client.post(reverse('admin_orders'), {'action': 'delete'})
        self.assertIn(response.status_code, (200, 302))
        self.assertEqual(Order.objects.count(), 2, 'orders were deleted with nothing selected')

    def test_rubbish_ids_are_rejected_without_erroring(self):
        self._orders(2)
        response = self.client.post(reverse('admin_orders'), {
            'action': 'delete',
            'selected_orders': ['', 'abc', 'null'],
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 2)

    def test_a_seller_cannot_delete_another_sellers_orders(self):
        """order_scope is what keeps sellers to their own rows."""
        from Hub.views_comprehensive_features import _prepare_seller_account

        seller = User.objects.create_user(username="bo_seller", password="pass12345")
        _prepare_seller_account(seller, created_by=self.admin, business_name="Theirs")

        orders = self._orders(2)          # belong to nobody's seller scope
        self.client.logout()
        self.client.login(username="bo_seller", password="pass12345")
        self._post('delete', orders)
        self.assertEqual(
            Order.objects.filter(id__in=[o.id for o in orders]).count(), 2,
            'a seller deleted orders outside their own scope',
        )
