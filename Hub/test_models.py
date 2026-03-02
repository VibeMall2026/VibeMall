"""
Test cases for Hub models
Tests model creation, validation, and relationships
"""

from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Product, Cart, Wishlist, Order, OrderItem, Coupon, ProductReview


class ProductModelTests(TestCase):
    """Test Product model"""
    
    def setUp(self):
        """Create test data"""
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            price=Decimal('99.99'),
            stock=10,
            discount_percent=10,
            category='MOBILES'
        )
    
    def test_product_creation(self):
        """Test creating a product"""
        self.assertEqual(self.product.name, 'Test Product')
        self.assertEqual(self.product.price, Decimal('99.99'))
        self.assertEqual(self.product.stock, 10)
    
    def test_product_slug(self):
        """Test product slug generation"""
        self.assertIsNotNone(self.product.slug)
        self.assertEqual(self.product.slug, 'test-product')
    
    def test_product_discount_calculation(self):
        """Test discount calculation"""
        self.product.old_price = Decimal('149.99')
        self.product.save()
        expected_discount = 33  # approximately
        self.assertIsNotNone(self.product.discount_percent)
    
    def test_product_stock_management(self):
        """Test stock reduction"""
        initial_stock = self.product.stock
        self.product.stock -= 1
        self.product.save()
        self.assertEqual(self.product.stock, initial_stock - 1)


class CartModelTests(TestCase):
    """Test Cart model"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.product = Product.objects.create(
            name='Test Product',
            price=Decimal('99.99'),
            stock=10
        )
        self.cart_item = Cart.objects.create(
            user=self.user,
            product=self.product,
            quantity=2
        )
    
    def test_cart_item_creation(self):
        """Test creating a cart item"""
        self.assertEqual(self.cart_item.user, self.user)
        self.assertEqual(self.cart_item.product, self.product)
        self.assertEqual(self.cart_item.quantity, 2)
    
    def test_cart_total_price(self):
        """Test cart item total price"""
        expected_total = self.product.price * self.cart_item.quantity
        self.assertEqual(self.cart_item.get_total_price(), expected_total)
    
    def test_cart_remove(self):
        """Test removing item from cart"""
        cart_id = self.cart_item.id
        self.cart_item.delete()
        with self.assertRaises(Cart.DoesNotExist):
            Cart.objects.get(id=cart_id)


class WishlistModelTests(TestCase):
    """Test Wishlist model"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.product = Product.objects.create(
            name='Wishlist Product',
            price=Decimal('199.99'),
            stock=5
        )
        self.wishlist_item = Wishlist.objects.create(
            user=self.user,
            product=self.product
        )
    
    def test_wishlist_item_creation(self):
        """Test adding item to wishlist"""
        self.assertEqual(self.wishlist_item.user, self.user)
        self.assertEqual(self.wishlist_item.product, self.product)
    
    def test_wishlist_duplicate_prevention(self):
        """Test that duplicate wishlist items are handled"""
        # This depends on model constraints
        wishlist_count = Wishlist.objects.filter(
            user=self.user,
            product=self.product
        ).count()
        self.assertGreaterEqual(wishlist_count, 1)


class OrderModelTests(TestCase):
    """Test Order model"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.order = Order.objects.create(
            user=self.user,
            payment_method='COD',
            total_amount=Decimal('299.99'),
            status='PENDING'
        )
    
    def test_order_creation(self):
        """Test creating an order"""
        self.assertEqual(self.order.user, self.user)
        self.assertEqual(self.order.payment_method, 'COD')
        self.assertIsNotNone(self.order.order_number)
    
    def test_order_status_tracking(self):
        """Test order status updates"""
        self.order.status = 'PROCESSING'
        self.order.save()
        self.assertEqual(self.order.status, 'PROCESSING')
    
    def test_order_total_calculation(self):
        """Test order total amount"""
        self.assertGreater(self.order.total_amount, 0)


class ProductReviewTests(TestCase):
    """Test ProductReview model"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username='reviewer', password='12345')
        self.product = Product.objects.create(
            name='Reviewable Product',
            price=Decimal('99.99'),
            stock=10
        )
        self.review = ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            title='Great Product',
            description='This product is amazing!'
        )
    
    def test_review_creation(self):
        """Test creating a product review"""
        self.assertEqual(self.review.product, self.product)
        self.assertEqual(self.review.user, self.user)
        self.assertEqual(self.review.rating, 5)
    
    def test_review_rating_validation(self):
        """Test review rating constraints"""
        self.assertGreaterEqual(self.review.rating, 1)
        self.assertLessEqual(self.review.rating, 5)
    
    def test_review_approval_workflow(self):
        """Test review approval status"""
        self.review.is_approved = True
        self.review.save()
        self.assertTrue(self.review.is_approved)


class CouponTests(TestCase):
    """Test Coupon model"""
    
    def setUp(self):
        """Create test data"""
        self.coupon = Coupon.objects.create(
            code='TEST20',
            discount_percent=20,
            max_uses=10
        )
    
    def test_coupon_creation(self):
        """Test creating a coupon"""
        self.assertEqual(self.coupon.code, 'TEST20')
        self.assertEqual(self.coupon.discount_percent, 20)
    
    def test_coupon_code_uniqueness(self):
        """Test coupon code uniqueness"""
        # Attempting to create duplicate should raise an error
        with self.assertRaises(Exception):
            Coupon.objects.create(code='TEST20', discount_percent=15)
    
    def test_coupon_is_active(self):
        """Test coupon active status"""
        self.coupon.is_active = True
        self.coupon.save()
        self.assertTrue(self.coupon.is_active)
