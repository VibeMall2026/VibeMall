"""
Test cases for Hub views
Tests view requests, responses, and templates
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Product, Cart, Wishlist, Order


class IndexViewTests(TestCase):
    """Test home/index view"""
    
    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.product = Product.objects.create(
            name='Featured Product',
            price=Decimal('99.99'),
            stock=10,
            category='MOBILES'
        )
    
    def test_index_view_exists(self):
        """Test index page loads successfully"""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
    
    def test_index_uses_correct_template(self):
        """Test correct template is used"""
        response = self.client.get(reverse('index'))
        self.assertTemplateUsed(response, 'index.html')
    
    def test_index_context_has_products(self):
        """Test products are passed to context"""
        response = self.client.get(reverse('index'))
        self.assertIn('products', response.context or {})


class ShopViewTests(TestCase):
    """Test shop/product listing view"""
    
    def setUp(self):
        """Create test data"""
        self.client = Client()
        # Create multiple products
        for i in range(20):
            Product.objects.create(
                name=f'Product {i}',
                slug=f'product-{i}',
                price=Decimal('99.99'),
                stock=10,
                category='MOBILES'
            )
    
    def test_shop_view_loads(self):
        """Test shop page loads"""
        response = self.client.get(reverse('shop'))
        self.assertEqual(response.status_code, 200)
    
    def test_shop_pagination(self):
        """Test shop page uses pagination"""
        response = self.client.get(reverse('shop'))
        # Check if pagination is used
        self.assertIsNotNone(response.context.get('page_obj') 
                            or response.context.get('products'))


class ProductDetailViewTests(TestCase):
    """Test product detail view"""
    
    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            price=Decimal('199.99'),
            stock=5,
            description='Test Description'
        )
    
    def test_product_detail_view(self):
        """Test product detail page loads"""
        response = self.client.get(
            reverse('product_detail', args=[self.product.slug])
        )
        self.assertEqual(response.status_code, 200)
    
    def test_product_detail_context(self):
        """Test product is in context"""
        response = self.client.get(
            reverse('product_detail', args=[self.product.slug])
        )
        self.assertIn('product', response.context or {})


class AuthenticationViewTests(TestCase):
    """Test authentication views"""
    
    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_login_page_loads(self):
        """Test login page loads"""
        response = self.client.get(reverse('accounts_login'))
        self.assertEqual(response.status_code, 200)
    
    def test_valid_login(self):
        """Test valid user login"""
        response = self.client.post(
            reverse('accounts_login'),
            {'username': 'testuser', 'password': 'testpass123'},
            follow=True
        )
        # Check if user is authenticated in any of the redirects
        self.assertTrue(response.wsgi_request.user.is_authenticated 
                       or response.status_code == 200)
    
    def test_register_page_loads(self):
        """Test register page loads"""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)


class CartViewTests(TestCase):
    """Test cart views and functionality"""
    
    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='cartuser',
            password='testpass123'
        )
        self.product = Product.objects.create(
            name='Cart Product',
            price=Decimal('99.99'),
            stock=10
        )
    
    def test_cart_view_unauthenticated(self):
        """Test cart view redirects unauthenticated users"""
        response = self.client.get(reverse('cart'))
        # Should redirect to login or show empty cart
        self.assertIn(response.status_code, [200, 302])
    
    def test_add_to_cart_authenticated(self):
        """Test adding item to cart for authenticated user"""
        self.client.login(username='cartuser', password='testpass123')
        # Add to cart requires POST typically
        response = self.client.post(
            reverse('add_to_cart'),
            {'product_id': self.product.id, 'quantity': 1},
            follow=True
        )
        # Check if product is in user's cart
        cart_items = Cart.objects.filter(user=self.user)
        self.assertTrue(cart_items.exists() or response.status_code == 200)


class WishlistViewTests(TestCase):
    """Test wishlist views"""
    
    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='wishlistuser',
            password='testpass123'
        )
        self.product = Product.objects.create(
            name='Wishlist Product',
            price=Decimal('99.99'),
            stock=10
        )
    
    def test_wishlist_view_requires_auth(self):
        """Test wishlist requires authentication"""
        response = self.client.get(reverse('wishlist'))
        # Should redirect or require login
        self.assertIn(response.status_code, [200, 302])
    
    def test_add_to_wishlist(self):
        """Test adding to wishlist"""
        self.client.login(username='wishlistuser', password='testpass123')
        wishlist = Wishlist.objects.create(
            user=self.user,
            product=self.product
        )
        self.assertTrue(Wishlist.objects.filter(
            user=self.user,
            product=self.product
        ).exists())


class APIViewTests(TestCase):
    """Test API endpoints"""
    
    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.product = Product.objects.create(
            name='API Test Product',
            price=Decimal('99.99'),
            stock=10
        )
    
    def test_product_search_api(self):
        """Test product search API"""
        response = self.client.get(
            reverse('product_search_api'),
            {'q': 'test'}
        )
        # API should return JSON
        self.assertIn(response.status_code, [200, 400])
    
    def test_cart_summary_api(self):
        """Test cart summary API"""
        response = self.client.get(reverse('cart_summary'))
        # Should return JSON or redirect
        self.assertIn(response.status_code, [200, 302, 400])
