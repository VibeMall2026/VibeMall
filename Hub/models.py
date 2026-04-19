from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List
import uuid

# Import comprehensive feature models
from .models_customer_insights import *
from .models_financial_management import *
from .models_product_enhancements import *
from .models_security_access import *
from .models_content_management import *
from .models_performance_optimization import *
from .models_ai_ml_features import *
from .models_activation_tracking import *

class PasswordResetLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('requested', 'Requested'), ('success', 'Success'), ('failed', 'Failed')])
    reason = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.email} ({self.status}) at {self.timestamp}"


class NewsletterSubscription(models.Model):
    """Email subscribers for marketing/newsletter updates."""
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    source_page = models.CharField(max_length=120, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-subscribed_at']

    def __str__(self):
        state = "active" if self.is_active else "inactive"
        return f"{self.email} ({state})"
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone

class CategoryIcon(models.Model):
    """Category icons for Shop By Department section"""
    name = models.CharField(max_length=100, help_text="Category name (e.g., Mobiles, Food & Health)")
    icon_class = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="FontAwesome icon class (e.g., 'fas fa-mobile-alt') - DEPRECATED: Use icon_image instead"
    )
    icon_image = models.ImageField(
        upload_to='category_icons/',
        blank=True,
        null=True,
        help_text="Upload category icon image (PNG with transparent background recommended)"
    )
    card_image = models.ImageField(
        upload_to='category_cards/',
        blank=True,
        null=True,
        help_text="Homepage All Categories card image (recommended: 800x1000 or 4:5 ratio)"
    )
    category_key = models.CharField(
        max_length=50,
        unique=True,
        help_text="Category key matching Product.CATEGORY_CHOICES (e.g., 'MOBILES')"
    )
    background_gradient = models.CharField(
        max_length=200,
        default="linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)",
        help_text="CSS gradient for icon background"
    )
    icon_color = models.CharField(
        max_length=20,
        default="#0288d1",
        help_text="Icon color (hex code) - Only used for FontAwesome icons"
    )
    icon_size = models.PositiveIntegerField(
        default=48,
        help_text="Icon size in pixels (used for image width/height or FontAwesome size)"
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order (lower numbers appear first)")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Category Icon"
        verbose_name_plural = "Category Icons"

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    category_key = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    icon_class = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="FontAwesome icon class (e.g., 'fas fa-tshirt')"
    )
    icon_image = models.ImageField(
        upload_to='subcategory_icons/',
        blank=True,
        null=True,
        help_text="Upload sub-category icon image (PNG recommended)"
    )
    background_gradient = models.CharField(
        max_length=200,
        default="linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)",
        help_text="CSS gradient for icon background"
    )
    icon_color = models.CharField(
        max_length=20,
        default="#0288d1",
        help_text="Icon color (hex code) - Only used for FontAwesome icons"
    )
    icon_size = models.PositiveIntegerField(
        default=48,
        help_text="Icon size in pixels (used for image width/height or FontAwesome size)"
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ('category_key', 'name')

    def __str__(self):
        return f"{self.category_key} - {self.name}"

class Slider(models.Model):
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='sliders/')
    top_button_text = models.CharField(max_length=50, default="HOT DEALS")
    top_button_url = models.CharField(max_length=100)
    order = models.IntegerField(default=0, help_text="Display order (lower numbers appear first)")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', '-id']

    def __str__(self):
        return self.title




class Feature(models.Model):
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=200)
    icon_class = models.CharField(
        max_length=50,
        help_text="FontAwesome class e.g. 'fal fa-truck'"
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class Banner(models.Model):
    BANNER_TYPE_CHOICES = [
        ('SMALL', 'Small Banner'),
        ('MEDIUM', 'Medium Banner'),
        ('LARGE', 'Large Banner'),
    ]
    
    PAGE_CHOICES = [
        ('HOME', 'Home Page'),
        ('SHOP', 'Shop Page'),
        ('BOTH', 'Both Home & Shop'),
    ]
    
    BUTTON_STYLE_CHOICES = [
        ('st-btn', 'Yellow Button (HOT DEALS)'),
        ('st-btn-3 b-radius', 'White Button (Shop Deals)'),
        ('none', 'No Button'),
    ]
    
    title = models.CharField(max_length=200, help_text="Main title/heading of the banner")
    subtitle = models.CharField(max_length=200, blank=True, help_text="Subtitle or description (optional)")
    badge_text = models.CharField(max_length=50, blank=True, help_text="Badge text like 'HOT DEALS' (optional)")
    
    image = models.ImageField(upload_to='banners/', help_text="Banner background image")
    
    link_url = models.CharField(
        max_length=200,
        default="#",
        blank=True,
        help_text="URL to redirect when banner is clicked"
    )
    
    button_text = models.CharField(max_length=50, blank=True, help_text="Button text like 'Shop Deals' (optional)")
    button_style = models.CharField(
        max_length=20,
        choices=BUTTON_STYLE_CHOICES,
        default='none',
        help_text="Select button style"
    )
    
    banner_type = models.CharField(
        max_length=10,
        choices=BANNER_TYPE_CHOICES,
        default='LARGE',
        help_text="Banner size type"
    )
    
    page_type = models.CharField(
        max_length=10,
        choices=PAGE_CHOICES,
        default='HOME',
        help_text="Which page to display this banner on"
    )
    
    background_color = models.CharField(
        max_length=20,
        blank=True,
        help_text="Optional background color overlay (e.g., rgba(255,0,0,0.1))"
    )
    
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order (lower number = shown first)")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.title} ({self.get_banner_type_display()}) - {self.get_page_type_display()}"


CATEGORY_CHOICES = [
    ('TOP_DEALS', 'Top Deals Of The Day'),
    ('TOP_SELLING', 'Top Selling Products'),
    ('TOP_FEATURED', 'Top Featured Products'),
    ('RECOMMENDED', 'Recommended For You'),
    ('MOBILES', 'Mobiles'),
    ('FOOD_HEALTH', 'Food & Health'),
    ('HOME_KITCHEN', 'Home & Kitchen'),
    ('AUTO_ACC', 'Auto Acc'),
    ('FURNITURE', 'Furniture'),
    ('SPORTS', 'Sports'),
    ('GENZ_TRENDS', 'GenZ Trends'),
    ('NEXT_GEN', 'Next Gen'),
]


class Product(models.Model):
    # Category choices - also available as class attribute for templates
    CATEGORY_CHOICES = [
        ('TOP_DEALS', 'Top Deals Of The Day'),
        ('TOP_SELLING', 'Top Selling Products'),
        ('TOP_FEATURED', 'Top Featured Products'),
        ('RECOMMENDED', 'Recommended For You'),
        ('MOBILES', 'Mobiles'),
        ('FOOD_HEALTH', 'Food & Health'),
        ('HOME_KITCHEN', 'Home & Kitchen'),
        ('AUTO_ACC', 'Auto Acc'),
        ('FURNITURE', 'Furniture'),
        ('SPORTS', 'Sports'),
        ('GENZ_TRENDS', 'GenZ Trends'),
        ('NEXT_GEN', 'Next Gen'),
    ]
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, null=True, blank=True)
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True, help_text="Stock Keeping Unit")
    image = models.ImageField(upload_to='products/')
    description = models.TextField(blank=True, help_text="Full product description")
    descriptionImage = models.ImageField(upload_to='products/descriptions/', blank=True, null=True, help_text="Large description image displayed below product description")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    margin = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    old_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        blank=True,
        null=True
    )

    sub_category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional sub-category label"
    )

    discount_percent = models.PositiveIntegerField(default=0)

    sold = models.PositiveIntegerField(default=0)
    stock = models.PositiveIntegerField(default=0)
    
    # Product Details
    weight = models.CharField(max_length=50, blank=True, help_text="e.g., 2 lbs")
    dimensions = models.CharField(max_length=100, blank=True, help_text="e.g., 12 × 16 × 19 in")
    color = models.CharField(max_length=100, blank=True, help_text="Available colors")
    size = models.CharField(max_length=100, blank=True, help_text="Available sizes")
    brand = models.CharField(max_length=100, blank=True)
    shipping_info = models.CharField(max_length=200, blank=True, help_text="e.g., Standard shipping: $5.95")
    care_info = models.TextField(blank=True, help_text="Care instructions")
    tags = models.CharField(max_length=200, blank=True, help_text="Comma-separated tags")
    
    # External Product Link (for admin reference only)
    product_link = models.URLField(max_length=500, blank=True, help_text="External product link (e.g., Meesho URL) - for admin reference only")
    
    # Return & Payment Policy
    is_returnable = models.BooleanField(default=True, help_text="Can this product be returned?")
    return_days = models.PositiveIntegerField(default=7, help_text="Return period in days")
    return_policy = models.TextField(blank=True, help_text="Return policy details")
    
    # Payment Methods (stored as comma-separated values)
    payment_methods = models.CharField(
        max_length=200, 
        default='COD,ONLINE,UPI,CARD',
        help_text="Comma-separated: COD,ONLINE,UPI,CARD"
    )
    
    is_top_deal = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    rating = models.FloatField(default=0)
    review_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-id']

    def save(self, *args, **kwargs):
        # Sanitize user-input fields to prevent XSS attacks
        from Hub.sanitizer import sanitize_text, sanitize_html
        
        self.description = sanitize_html(self.description)  # Allow safe HTML tags in description
        self.return_policy = sanitize_text(self.return_policy)  # Remove HTML from return policy
        
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            
            # Make slug unique by appending counter if needed
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def discount_percent_display(self):
        try:
            if self.old_price and self.price and self.old_price > self.price:
                old_value = Decimal(str(self.old_price))
                price_value = Decimal(str(self.price))
                if old_value > 0:
                    return int(((old_value - price_value) / old_value) * Decimal('100'))
        except Exception:
            pass

        return int(self.discount_percent or 0)

    def progress_percent(self):
        if self.stock == 0:
            return 0
        return int((self.sold / self.stock) * 100)

    def get_tags_list(self):
        """Return tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []
    
    def get_payment_methods_list(self):
        """Return available payment methods as list"""
        if self.payment_methods:
            return [method.strip() for method in self.payment_methods.split(',')]
        return ['COD', 'ONLINE', 'UPI', 'CARD']
    
    def is_cod_available(self):
        """Check if COD is available for this product"""
        return 'COD' in self.get_payment_methods_list()
    
    def get_return_policy_display(self):
        """Get formatted return policy"""
        if self.is_returnable:
            return f"{self.return_days} Days Return Available"
        return "No Return Available"

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    """Additional images for product gallery"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='additional_images')
    image = models.ImageField(upload_to='products/gallery/')
    color = models.CharField(max_length=100, blank=True, help_text='Color variant for this image')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name} - Image {self.order}"


class ProductStockNotification(models.Model):
    """Record of users requesting restock notifications"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_notifications')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_notifications')
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    is_sent = models.BooleanField(default=False)

    class Meta:
        unique_together = ('product', 'email')
        ordering = ['-created_at']

    def mark_sent(self):
        self.is_sent = True
        self.notified_at = timezone.now()
        self.save(update_fields=['is_sent', 'notified_at'])

    def __str__(self):
        return f"Notify {self.email} about {self.product.name}"


class DealCountdown(models.Model):
    title = models.CharField(max_length=100, default="Top Deals Of The Day")
    end_time = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title




class UserProfile(models.Model):
    CUSTOMER_SEGMENT_CHOICES = [
        ('NEW', 'New Customer'),
        ('REGULAR', 'Regular Customer'),
        ('VIP', 'VIP Customer'),
        ('ADMIN', 'Admin User'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', default='profile_images/default.png', blank=True)
    country_code = models.CharField(max_length=5, blank=True)
    mobile_number = models.CharField(max_length=15, blank=True)
    is_blocked = models.BooleanField(default=False, help_text="Block user from accessing the site")
    customer_segment = models.CharField(max_length=15, choices=CUSTOMER_SEGMENT_CHOICES, default='NEW')
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username
    
    def get_orders_count(self):
        """Get total number of orders (placeholder - needs Order model)"""
        return 0
    
    def get_wishlist_count(self):
        """Get wishlist items count"""
        return self.user.wishlist_items.count()
    
    def get_cart_count(self):
        """Get cart items count"""
        return self.user.cart_items.count()


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'product')
        verbose_name_plural = 'Cart Items'

    def get_total_price(self) -> Decimal:
        """Calculate total price for cart item (price * quantity)"""
        return self.product.price * self.quantity

    def __str__(self) -> str:
        return f"{self.user.username} - {self.product.name} x{self.quantity}"


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        verbose_name_plural = 'Wishlist Items'

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class ProductReview(models.Model):
    """Product reviews with admin approval workflow and enhanced features"""
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    name = models.CharField(max_length=100, help_text="Reviewer name")
    email = models.EmailField()
    comment = models.TextField()
    is_approved = models.BooleanField(default=False, help_text="Admin must approve before review is publicly visible")
    is_verified_purchase = models.BooleanField(default=False, help_text="User purchased this product")
    is_auto_generated = models.BooleanField(default=False, help_text="Auto-generated review by system")
    helpful_count = models.PositiveIntegerField(default=0, help_text="Number of helpful votes")
    not_helpful_count = models.PositiveIntegerField(default=0, help_text="Number of not helpful votes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Product Review'
        verbose_name_plural = 'Product Reviews'

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating} stars) - {'Approved' if self.is_approved else 'Pending'}"
    
    def get_helpfulness_percentage(self):
        """Calculate helpfulness percentage"""
        total_votes = self.helpful_count + self.not_helpful_count
        if total_votes == 0:
            return 0
        return int((self.helpful_count / total_votes) * 100)
    
    def save(self, *args, **kwargs):
        """Override save to auto-update product rating and review count and sanitize inputs"""
        # Sanitize user inputs to prevent XSS attacks
        from Hub.sanitizer import sanitize_text, sanitize_email
        
        self.name = sanitize_text(self.name)  # Remove HTML from reviewer name
        self.comment = sanitize_text(self.comment)  # Remove HTML from comment
        self.email = sanitize_email(self.email) or self.email  # Validate and normalize email
        
        super().save(*args, **kwargs)
        
        # Update product review count and rating
        from django.db.models import Avg
        
        product = self.product
        approved_reviews = ProductReview.objects.filter(product=product, is_approved=True)
        
        if approved_reviews.exists():
            # Update review count
            product.review_count = approved_reviews.count()
            
            # Update average rating
            avg_rating = approved_reviews.aggregate(Avg('rating'))['rating__avg']
            product.rating = round(avg_rating, 1) if avg_rating else 0
        else:
            product.review_count = 0
            product.rating = 0
        
        product.save(update_fields=['review_count', 'rating'])


class ReviewImage(models.Model):
    """Images uploaded with product reviews"""
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='reviews/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"Image for {self.review.product.name} review by {self.review.user.username}"


class ReviewVote(models.Model):
    """Track user votes on review helpfulness"""
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_helpful = models.BooleanField(help_text="True for helpful, False for not helpful")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('review', 'user')
        verbose_name = 'Review Vote'
        verbose_name_plural = 'Review Votes'
    
    def __str__(self):
        vote_type = "helpful" if self.is_helpful else "not helpful"
        return f"{self.user.username} voted {vote_type} on review #{self.review.id}"


class ProductQuestion(models.Model):
    """Q&A section for products"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='questions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.TextField(help_text="Customer question")
    answer = models.TextField(blank=True, help_text="Admin answer")
    answered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='answered_questions')
    is_answered = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False, help_text="Show on product page only after admin approval and answer")
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Product Question'
        verbose_name_plural = 'Product Questions'
    
    def __str__(self):
        status = "Answered" if self.is_answered else "Pending"
        return f"Q&A for {self.product.name} - {status}"
    
    def save(self, *args, **kwargs):
        """Sanitize user inputs to prevent XSS attacks"""
        from Hub.sanitizer import sanitize_text
        
        self.question = sanitize_text(self.question)  # Remove HTML from question
        if self.answer:
            self.answer = sanitize_text(self.answer)  # Remove HTML from answer
        
        super().save(*args, **kwargs)


# ==================== ORDER MANAGEMENT MODELS ====================

class Address(models.Model):
    """Customer shipping and billing addresses"""
    ADDRESS_TYPE_CHOICES = [
        ('HOME', 'Home'),
        ('OFFICE', 'Office'),
        ('OTHER', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=100)
    mobile_number = models.CharField(max_length=15)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='India')
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES, default='HOME')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        return f"{self.full_name} - {self.city}, {self.state}"
    
    def save(self, *args, **kwargs):
        # If this is set as default, unset other defaults for this user
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class Order(models.Model):
    """Customer orders"""
    ORDER_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('ONLINE', 'Online Payment'),
        ('UPI', 'UPI'),
        ('CARD', 'Credit/Debit Card'),
    ]
    
    # Order identification
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    
    # Order amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, help_text="Applied coupon")
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Discount from coupon")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Order status
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='PENDING')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='COD')
    
    # Dates
    order_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateTimeField(null=True, blank=True)
    
    # Addresses (stored as text to preserve at time of order)
    shipping_address = models.TextField()
    billing_address = models.TextField()
    
    # Additional info
    customer_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True, help_text="Internal notes for admins")
    tracking_number = models.CharField(max_length=100, blank=True)
    courier_name = models.CharField(max_length=100, blank=True, help_text="Courier/Shipping company name")
    invoice_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    
    # Loyalty Points System
    delivery_points_awarded = models.BooleanField(default=False, help_text="Whether delivery bonus loyalty points were awarded")
    
    # Payment related fields
    razorpay_order_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Order ID")
    razorpay_payment_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Payment ID")
    razorpay_signature = models.CharField(max_length=200, blank=True, help_text="Razorpay Payment Signature")
    
    # Resell functionality (Enhanced)
    is_resell = models.BooleanField(default=False, help_text="Is this a resell order?")
    reseller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resold_orders', help_text="Reseller user for resell orders")
    resell_link = models.ForeignKey('ResellLink', on_delete=models.SET_NULL, null=True, blank=True, help_text="Resell link used for this order")
    total_margin = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Total margin amount for reseller")
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Base amount before margin")
    
    # Deprecated fields (kept for backward compatibility)
    resell_from_name = models.CharField(max_length=200, blank=True, help_text="[DEPRECATED] Use reseller field instead")
    resell_from_phone = models.CharField(max_length=20, blank=True, help_text="[DEPRECATED] Use reseller.phone instead")
    
    # Order Approval System
    APPROVAL_STATUS_CHOICES = [
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'R-Approved'),
        ('REJECTED', 'Rejected'),
        ('AUTO_APPROVED', 'Auto Approved'),
    ]
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='PENDING_APPROVAL')
    approval_notes = models.TextField(blank=True, help_text="Admin notes for approval/rejection")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_orders')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Fraud Detection Flags
    is_suspicious = models.BooleanField(default=False, help_text="Flagged as potentially fraudulent")
    suspicious_reason = models.TextField(blank=True, help_text="Reason for flagging as suspicious")
    risk_score = models.IntegerField(default=0, help_text="Fraud risk score (0-100)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order #{self.order_number} - {self.user.username}"
    
    def clean(self):
        """Validate order data"""
        from django.core.exceptions import ValidationError
        
        # If is_resell is True, reseller must be set.
        # resell_link can be null for manual (Meesho-style) resell orders.
        if self.is_resell:
            if not self.reseller:
                raise ValidationError({'reseller': 'Reseller must be set for resell orders.'})
            if self.resell_link and self.resell_link.reseller_id != self.reseller_id:
                raise ValidationError({'resell_link': 'Selected resell link does not belong to this reseller.'})
            if not self.resell_link and not (self.resell_from_name or self.resell_from_phone):
                raise ValidationError({
                    'resell_from_name': 'Provide reseller FROM details when resell link is not used.'
                })

        if self.total_margin is not None and self.total_margin < 0:
            raise ValidationError({'total_margin': 'Total margin cannot be negative.'})
        if self.base_amount is not None and self.base_amount < 0:
            raise ValidationError({'base_amount': 'Base amount cannot be negative.'})
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate unique order number: ORD20260129001
            import datetime
            date_str = datetime.datetime.now().strftime('%Y%m%d')
            last_order = Order.objects.filter(order_number__startswith=f'ORD{date_str}').order_by('-order_number').first()
            if last_order:
                last_number = int(last_order.order_number[-3:])
                new_number = last_number + 1
            else:
                new_number = 1
            self.order_number = f'ORD{date_str}{new_number:03d}'
        super().save(*args, **kwargs)
    
    def get_status_color(self):
        """Return color class for order status"""
        status_colors = {
            'PENDING': 'warning',
            'PROCESSING': 'info',
            'SHIPPED': 'primary',
            'DELIVERED': 'success',
            'CANCELLED': 'danger',
        }
        return status_colors.get(self.order_status, 'secondary')
    
    def get_payment_status_color(self):
        """Return color class for payment status"""
        payment_colors = {
            'PENDING': 'warning',
            'PAID': 'success',
            'FAILED': 'danger',
            'REFUNDED': 'info',
        }
        return payment_colors.get(self.payment_status, 'secondary')
    
    def calculate_risk_score(self) -> int:
        """Calculate fraud risk score for this order"""
        risk = 0
        
        # High value order (>10000)
        if self.total_amount > 10000:
            risk += 30
        
        # Very high value (>50000)
        if self.total_amount > 50000:
            risk += 40
        
        # First time customer
        user_orders_count = Order.objects.filter(user=self.user).count()
        if user_orders_count <= 1:
            risk += 20
        
        # Multiple orders same day
        from django.utils import timezone
        today_orders = Order.objects.filter(
            user=self.user,
            created_at__date=timezone.now().date()
        ).count()
        if today_orders > 3:
            risk += 25
        
        # COD for high value
        if self.payment_method == 'COD' and self.total_amount > 5000:
            risk += 15
        
        return min(risk, 100)  # Cap at 100
    
    def check_auto_approval_eligibility(self) -> bool:
        """Check if order should be auto-approved"""
        # Trusted customer (>5 successful orders)
        successful_orders = Order.objects.filter(
            user=self.user,
            order_status='DELIVERED',
            payment_status='PAID'
        ).count()
        
        if successful_orders >= 5 and self.total_amount < 15000:
            return True
        
        # Low value, paid orders
        if self.payment_status == 'PAID' and self.total_amount < 5000:
            return True
        
        return False
    
    def auto_process_approval(self) -> None:
        """Automatically approve/flag order based on rules"""
        self.risk_score = self.calculate_risk_score()
        
        # Flag suspicious orders
        if self.risk_score >= 70:
            self.is_suspicious = True
            reasons = []
            if self.total_amount > 50000:
                reasons.append("Very high order value")
            if Order.objects.filter(user=self.user).count() <= 1:
                reasons.append("First time customer")
            if self.payment_method == 'COD' and self.total_amount > 5000:
                reasons.append("High value COD order")
            self.suspicious_reason = ", ".join(reasons)
            self.approval_status = 'PENDING_APPROVAL'
        
        # Auto-approve trusted customers
        elif self.check_auto_approval_eligibility():
            self.approval_status = 'AUTO_APPROVED'
            self.approved_at = timezone.now()
            self.order_status = 'PROCESSING'
        
        else:
            self.approval_status = 'PENDING_APPROVAL'
        
        self.save()
    
    def get_subtotal(self):
        """Calculate subtotal from order items"""
        return sum(item.subtotal for item in self.items.all())


class OrderItem(models.Model):
    """Items in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    
    # Product details at time of order (preserved even if product changes)
    product_name = models.CharField(max_length=255)
    product_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price shown to customer (includes margin for resell orders)")
    product_image = models.CharField(max_length=500, blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Original product price before margin")
    margin_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Reseller margin per unit")
    
    # Order details
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=10, blank=True)
    color = models.CharField(max_length=50, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.product_name} x {self.quantity} - Order #{self.order.order_number}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate subtotal
        self.subtotal = self.product_price * self.quantity
        super().save(*args, **kwargs)

    @property
    def display_image_url(self):
        """Return safest available image URL for admin/front display."""
        if self.product and self.product.image:
            try:
                return self.product.image.url
            except Exception:
                pass

        raw_url = (self.product_image or '').strip()
        if not raw_url:
            return ''

        local_hosts = (
            'http://127.0.0.1', 'https://127.0.0.1',
            'http://localhost', 'https://localhost'
        )

        if raw_url.startswith(local_hosts):
            try:
                from urllib.parse import urlparse
                parsed = urlparse(raw_url)
                return parsed.path if parsed.path.startswith('/media/') else ''
            except Exception:
                return ''

        if raw_url.startswith('/media/'):
            return raw_url

        if raw_url.startswith('media/'):
            return f"/{raw_url}"

        if raw_url.startswith(('http://', 'https://')):
            return raw_url

        return raw_url


class OrderStatusHistory(models.Model):
    """Track order status changes over time"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Order Status Histories"
    
    def __str__(self):
        return f"Order #{self.order.order_number} - {self.old_status} → {self.new_status}"


class OrderCancellationRequest(models.Model):
    """Customer requested cancellation for an order"""
    STATUS_CHOICES = [
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    REFUND_METHOD_CHOICES = [
        ('WALLET', 'VibeMall Wallet'),
        ('BANK', 'Direct Bank Transfer'),
        ('RAZORPAY', 'RazorPay'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='cancellation_request')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cancellation_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REQUESTED')
    reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    refund_method = models.CharField(max_length=20, choices=REFUND_METHOD_CHOICES, blank=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    bank_account_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=34, blank=True)
    bank_ifsc = models.CharField(max_length=20, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    upi_id = models.CharField(max_length=200, blank=True)
    upi_name = models.CharField(max_length=200, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_cancellations')

    class Meta:
        ordering = ['-requested_at']
        verbose_name = 'Order Cancellation Request'
        verbose_name_plural = 'Order Cancellation Requests'

    def __str__(self):
        return f"Cancel #{self.order.order_number} - {self.get_status_display()}"


class ReturnRequest(models.Model):
    """Customer return requests for delivered orders"""
    STATUS_CHOICES = [
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('PICKUP_SCHEDULED', 'Pickup Scheduled'),
        ('RECEIVED', 'Received'),
        ('UNABLE_TO_REACH', 'Unable to Reach'),
        ('RESCHEDULED', 'Rescheduled'),
        ('QC_PENDING', 'Waiting for Product Review'),
        ('REFUND_PENDING', 'Waiting for Refunded'),
        ('WRONG_RETURN', 'Wrong Return'),
        ('REFUNDED', 'Refunded'),
        ('REPLACED', 'Replaced'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('QC_PASSED', 'QC Passed'),
        ('QC_FAILED', 'QC Failed'),
    ]

    RETURN_REASON_CHOICES = [
        ('DEFECTIVE', 'Defective / Damaged'),
        ('WRONG_ITEM', 'Wrong Item Delivered'),
        ('NOT_AS_DESCRIBED', 'Not as described'),
        ('SIZE_FIT', 'Size / Fit Issue'),
        ('CHANGED_MIND', 'Changed Mind'),
        ('OTHER', 'Other'),
    ]

    return_number = models.CharField(max_length=20, unique=True, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='return_requests')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='return_requests', null=True, blank=True)

    reason = models.CharField(max_length=30, choices=RETURN_REASON_CHOICES, default='OTHER')
    reason_notes = models.TextField(blank=True)
    description = models.TextField(blank=True, help_text="Detailed description of the issue")
    images = models.ImageField(upload_to='returns/', blank=True, null=True, help_text="Upload product images")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REQUESTED')

    requested_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    pickup_scheduled_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    qc_checked_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    refund_amount_net = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_method = models.CharField(max_length=50, blank=True)
    bank_account_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=34, blank=True)
    bank_ifsc = models.CharField(max_length=20, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    upi_id = models.CharField(max_length=200, blank=True)
    upi_name = models.CharField(max_length=200, blank=True)
    admin_notes = models.TextField(blank=True)

    request_ip = models.GenericIPAddressField(null=True, blank=True)
    request_user_agent = models.CharField(max_length=255, blank=True)

    pickup_date = models.DateTimeField(null=True, blank=True)
    refund_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']
        verbose_name = "Return Request"
        verbose_name_plural = "Return Requests"

    def __str__(self):
        display_number = self.return_number or f"{self.id}"
        return f"Return #{display_number} - Order #{self.order.order_number}"

    def save(self, *args, **kwargs):
        if not self.return_number:
            date_str = timezone.now().strftime('%Y%m%d')
            last_return = ReturnRequest.objects.filter(
                return_number__startswith=f'RET-{date_str}'
            ).order_by('-return_number').first()

            if last_return:
                last_num = int(last_return.return_number.split('-')[-1])
                new_num = str(last_num + 1).zfill(5)
            else:
                new_num = '00001'

            self.return_number = f'RET-{date_str}-{new_num}'

        super().save(*args, **kwargs)


class ReturnItem(models.Model):
    """Line items for a return request"""
    CONDITION_CHOICES = [
        ('NEW', 'New / Unused'),
        ('OPENED', 'Opened / Tried'),
        ('DAMAGED', 'Damaged'),
    ]

    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='items')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='return_items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='OPENED')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"ReturnItem {self.order_item.product_name} x {self.quantity}"


class ReturnHistory(models.Model):
    """Track return request status changes"""
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='history')
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Return Histories"

    def __str__(self):
        return f"Return #{self.return_request.id} - {self.old_status} → {self.new_status}"


class ReturnAttachment(models.Model):
    """Evidence images for returns"""
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='returns/')
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class ReturnLabel(models.Model):
    """Optional return shipping label"""
    return_request = models.OneToOneField(ReturnRequest, on_delete=models.CASCADE, related_name='label')
    label_file = models.FileField(upload_to='returns/labels/', blank=True, null=True)
    label_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RTOCase(models.Model):
    """Track return-to-origin cases separately from normal order status."""

    STATUS_CHOICES = [
        ('DELIVERY_FAILED', 'Delivery Failed'),
        ('RTO_INITIATED', 'RTO Initiated'),
        ('RTO_IN_TRANSIT', 'RTO In Transit'),
        ('RTO_RECEIVED', 'RTO Received'),
        ('RTO_CLOSED', 'RTO Closed'),
    ]

    REASON_CHOICES = [
        ('WRONG_ADDRESS', 'Wrong Address'),
        ('CUSTOMER_UNAVAILABLE', 'Customer Unavailable'),
        ('CUSTOMER_REFUSED', 'Customer Refused Delivery'),
        ('FAKE_ORDER', 'Fake / High-Risk Order'),
        ('COURIER_ISSUE', 'Courier Issue'),
        ('OTHER', 'Other'),
    ]

    RESOLUTION_CHOICES = [
        ('RESTOCK', 'Restock'),
        ('HOLD', 'Hold for Review'),
        ('REPACK', 'Repack and Reship'),
        ('DISPOSE', 'Dispose / Damaged'),
        ('VENDOR_RETURN', 'Return to Vendor'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='rto_case')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DELIVERY_FAILED')
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, default='OTHER')
    reason_notes = models.TextField(blank=True)
    resolution_action = models.CharField(max_length=20, choices=RESOLUTION_CHOICES, blank=True)
    courier_name = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    admin_notes = models.TextField(blank=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    initiated_at = models.DateTimeField(default=timezone.now)
    received_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'RTO Case'
        verbose_name_plural = 'RTO Cases'

    def __str__(self):
        return f"RTO #{self.id} - Order #{self.order.order_number}"


class RTOHistory(models.Model):
    """Track RTO case workflow changes."""

    rto_case = models.ForeignKey(RTOCase, on_delete=models.CASCADE, related_name='history')
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'RTO Histories'

    def __str__(self):
        return f"RTO #{self.rto_case.id} - {self.old_status} -> {self.new_status}"


class ChatThread(models.Model):
    """Customer support chat thread"""
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='chat_threads')
    guest_name = models.CharField(max_length=120, blank=True)
    guest_email = models.EmailField(blank=True)
    session_key = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_message_at', '-created_at']

    def display_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return self.guest_name or 'Guest'


class ChatMessage(models.Model):
    """Individual messages in a support chat thread"""
    SENDER_CHOICES = [
        ('USER', 'User'),
        ('ADMIN', 'Admin'),
    ]

    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages')
    sender_type = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class ChatAttachment(models.Model):
    """Files shared in a support chat message"""
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='ChatMedia/')
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class AdminEmailSettings(models.Model):
    """Configurable admin email settings"""
    setting_name = models.CharField(max_length=100, default="order_notifications")
    admin_email = models.EmailField(default="info.vibemall@gmail.com", help_text="Email to receive order notifications")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Admin Email Settings"
    
    def __str__(self):
        return f"Admin Email: {self.admin_email}"


class BrandPartner(models.Model):
    """Brand Partner logos for homepage carousel"""
    name = models.CharField(max_length=100, help_text="Brand name")
    logo = models.ImageField(upload_to='brand_partners/', help_text="Brand logo image")
    link_url = models.URLField(blank=True, null=True, help_text="Optional link URL")
    order = models.IntegerField(default=0, help_text="Display order (lower numbers first)")
    is_active = models.BooleanField(default=True, help_text="Show/hide brand")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Brand Partner"
        verbose_name_plural = "Brand Partners"
    
    def __str__(self):
        return self.name


# ============================================
# NEW FEATURES - Order Management Extensions
# ============================================

class LoyaltyPoints(models.Model):
    """Customer loyalty points system - FIXED VERSION"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='loyalty_points')
    total_points = models.IntegerField(default=0, help_text="Total points earned (NEVER decrements)")
    points_used = models.IntegerField(default=0, help_text="Total points redeemed")
    points_available = models.IntegerField(default=0, help_text="Available points = total_points - points_used")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Loyalty Points"
    
    def __str__(self):
        return f"{self.user.username} - {self.points_available} points available"
    
    def save(self, *args, **kwargs):
        """Ensure points_available is correctly calculated"""
        self.points_available = self.total_points - self.points_used
        if self.points_available < 0:
            self.points_available = 0
        super().save(*args, **kwargs)
    
    def add_points(self, points, description=""):
        """Add points to user account - FIXED"""
        from .loyalty_manager import LoyaltyPointsManager
        return LoyaltyPointsManager.add_points(
            user=self.user,
            points=points,
            transaction_type='EARNED',
            description=description
        )
    
    def redeem_points(self, points, order=None, description=""):
        """Redeem points from user account - FIXED"""
        from .loyalty_manager import LoyaltyPointsManager
        return LoyaltyPointsManager.redeem_points(
            user=self.user,
            points=points,
            order=order,
            description=description
        )


class PointsTransaction(models.Model):
    """History of loyalty points transactions"""
    TRANSACTION_TYPES = [
        ('EARNED', 'Points Earned'),
        ('REDEEMED', 'Points Redeemed'),
        ('EXPIRED', 'Points Expired'),
        ('ADJUSTED', 'Manual Adjustment'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='points_transactions')
    points = models.IntegerField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.TextField(blank=True)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='points_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Points Transaction"
        verbose_name_plural = "Points Transactions"
    
    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} {self.points} points"


class WishlistPriceAlert(models.Model):
    """Track price changes for wishlist items"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_alerts')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='price_alerts')
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    target_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Alert when price drops below this")
    is_active = models.BooleanField(default=True)
    notified = models.BooleanField(default=False, help_text="Has user been notified of price drop?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Wishlist Price Alert"
        verbose_name_plural = "Wishlist Price Alerts"
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class Notification(models.Model):
    """User notifications"""
    NOTIFICATION_TYPES = [
        ('ORDER_PLACED', 'Order Placed'),
        ('ORDER_CONFIRMED', 'Order Confirmed'),
        ('ORDER_SHIPPED', 'Order Shipped'),
        ('ORDER_DELIVERED', 'Order Delivered'),
        ('PRICE_DROP', 'Price Drop Alert'),
        ('STOCK_AVAILABLE', 'Stock Available'),
        ('RETURN_APPROVED', 'Return Approved'),
        ('REFUND_PROCESSED', 'Refund Processed'),
        ('POINTS_EARNED', 'Loyalty Points Earned'),
        ('SPECIAL_OFFER', 'Special Offer'),
        ('EARNING_CONFIRMED', 'Reseller Earning Confirmed'),
        ('PAYOUT_COMPLETED', 'Payout Completed'),
        ('PAYOUT_FAILED', 'Payout Failed'),
        ('ORDER_CANCELLED', 'Order Cancelled'),
        ('NEW_RESELL_ORDER', 'New Resell Order'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True, help_text="URL to related page")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
    
    def __str__(self):
        return f"{self.user.username} - {self.notification_type}"


class EmailLog(models.Model):
    """Log of sent emails"""
    EMAIL_TYPES = [
        ('ORDER_CONFIRMATION', 'Order Confirmation'),
        ('ORDER_STATUS_UPDATE', 'Order Status Update'),
        ('DELIVERY_REMINDER', 'Delivery Reminder'),
        ('REVIEW_REQUEST', 'Review Request'),
        ('PRICE_ALERT', 'Price Alert'),
        ('PROMOTIONAL', 'Promotional Email'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_logs', null=True, blank=True)
    email_to = models.EmailField()
    email_type = models.CharField(max_length=30, choices=EMAIL_TYPES)
    subject = models.CharField(max_length=300)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='email_logs')
    sent_successfully = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-sent_at']
        verbose_name = "Email Log"
        verbose_name_plural = "Email Logs"
    
    def __str__(self):
        return f"{self.email_type} to {self.email_to}"


class MainPageProduct(models.Model):
    """Manage products displayed on main page by category"""
    CATEGORY_CHOICES = [
        ('category1', 'Category 1'),
        ('category2', 'Category 2'),
        ('category3', 'Category 3'),
        ('category4', 'Category 4'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='main_page_items')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    order = models.PositiveIntegerField(default=0, help_text="Display order (lower numbers appear first)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'order']
        unique_together = ['product', 'category']
        verbose_name_plural = "Main Page Products"
    
    def __str__(self):
        return f"{self.product.name} - {self.get_category_display()}"


class MainPageSubCategoryBanner(models.Model):
    """Custom image banners on home page that redirect to a selected sub-category."""
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional title shown over image. Leave blank to use sub-category name."
    )
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        related_name='main_page_banners'
    )
    image = models.ImageField(
        upload_to='main_page_subcategory_banners/',
        help_text="Recommended size: 800 x 600 px (4:3 ratio) for best display"
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order (lower appears first)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Main Page Sub-category Banner"
        verbose_name_plural = "Main Page Sub-category Banners"

    def __str__(self):
        return self.title or self.sub_category.name

    @property
    def display_title(self):
        return (self.title or '').strip() or self.sub_category.name


class MainPageBanner(models.Model):
    """Custom banners for main page banner areas (Promotion area 3 card & Marketing area 2 card)."""
    BANNER_AREA_CHOICES = [
        ('first', 'Promotion area 3 card'),
        ('second', 'Marketing area 2 card'),
    ]
    
    banner_area = models.CharField(
        max_length=20,
        choices=BANNER_AREA_CHOICES,
        default='first',
        help_text="Select which banner area this belongs to"
    )
    badge_text = models.CharField(
        max_length=100,
        blank=True,
        help_text="Text above the title (e.g., 'Bestseller Products', 'Featured Products')"
    )
    title = models.CharField(
        max_length=200,
        help_text="Main banner title/heading (e.g., 'PC & Docking Station')"
    )
    description = models.CharField(
        max_length=300,
        blank=True,
        help_text="Banner description/subtitle (e.g., 'Discount 20% Off, Top Quality Products')"
    )
    image = models.ImageField(
        upload_to='main_page_banners/',
        help_text="Banner background image. Recommended size: 600 x 400 px"
    )
    link_url = models.CharField(
        max_length=500,
        default='#',
        help_text="URL to redirect when banner is clicked (e.g., /shop?category=electronics)"
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order (lower numbers appear first in each area). Promotion area: 3 banners, Marketing area: 2 banners."
    )
    is_active = models.BooleanField(default=True, help_text="Activate/Deactivate this banner")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['banner_area', 'order', 'id']
        verbose_name = "Main Page Banner"
        verbose_name_plural = "Main Page Banners"
        indexes = [
            models.Index(fields=['banner_area', 'is_active', 'order']),
        ]

    def __str__(self):
        return f"{self.get_banner_area_display()} - {self.title}"

    @property
    def display_area(self):
        """Return display name for the banner area."""
        return dict(self.BANNER_AREA_CHOICES).get(self.banner_area, self.banner_area)


class ReadyShipStyle(models.Model):
    """Products shown in the Ready-to-Ship Styles section on home page."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ready_ship_styles')
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional custom title. Leave blank to use product name."
    )
    image = models.ImageField(
        upload_to='ready_ship_styles/',
        blank=True,
        null=True,
        help_text="Optional custom image. Recommended sizes: Hero (first item): 2100x900px (21:9), Cards: 1600x900px (16:9). Leave blank to use product image."
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order (lower numbers appear first)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Ready-to-Ship Style"
        verbose_name_plural = "Ready-to-Ship Styles"

    def __str__(self):
        return self.title or self.product.name

    @property
    def display_title(self):
        return (self.title or '').strip() or self.product.name


class SiteSettings(models.Model):
    """Global site settings - only one instance should exist"""
    site_name = models.CharField(max_length=100, default='VibeMall', help_text='Website name displayed across the site')
    site_name_html = models.TextField(blank=True, help_text='Optional styled HTML for brand name (supports multiple colors/fonts)')
    site_logo = models.ImageField(upload_to='site/', blank=True, null=True, help_text='Main logo (recommended: 150x50px PNG with transparent background)')
    site_favicon = models.ImageField(upload_to='site/', blank=True, null=True, help_text='Favicon icon (recommended: 32x32px PNG)')
    tagline = models.CharField(max_length=200, blank=True, help_text='Website tagline/slogan')
    
    # Contact Information
    contact_email = models.EmailField(default='info.vibemall@gmail.com')
    contact_phone = models.CharField(max_length=20, default='+91 1234567890')
    
    # Social Media Links
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    
    # Admin Panel Logo
    admin_logo = models.ImageField(upload_to='site/', blank=True, null=True, help_text='Admin panel logo (recommended: 120x40px)')
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'
    
    def __str__(self):
        return f"{self.site_name} Settings"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and SiteSettings.objects.exists():
            # Update existing instance instead of creating new
            existing = SiteSettings.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create site settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings



class Reel(models.Model):
    """Reels/Videos for social media and website"""
    title = models.CharField(max_length=200, help_text="Reel title")
    description = models.TextField(blank=True, help_text="Reel description")
    product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='watch_shop_reels',
        help_text="Linked product for watch-and-shop redirect"
    )
    video_file = models.FileField(upload_to='reels/', blank=True, null=True, help_text="Generated video file")
    thumbnail = models.ImageField(upload_to='reels/thumbnails/', blank=True, null=True, help_text="Video thumbnail")
    duration = models.IntegerField(default=0, help_text="Duration in seconds")
    view_count = models.PositiveIntegerField(default=25, help_text="Total reel views")
    like_count = models.PositiveIntegerField(default=3, help_text="Total reel likes")
    
    # Configuration
    duration_per_image = models.IntegerField(default=3, help_text="Seconds per image")
    transition_type = models.CharField(
        max_length=20, 
        default='zoom', 
        choices=[
            ('fade', 'Fade'),
            ('zoom', 'Zoom In'),
            ('slide', 'Slide'),
            ('none', 'None')
        ],
        help_text="Transition effect"
    )
    background_music = models.FileField(upload_to='reels/music/', blank=True, null=True, help_text="Background music (optional)")
    
    # Branding
    watermark_logo = models.ImageField(upload_to='reels/logos/', blank=True, null=True, help_text="Watermark logo (transparent PNG)")
    watermark_position = models.CharField(
        max_length=20,
        default='top-right',
        choices=[
            ('top-left', 'Top Left'),
            ('top-right', 'Top Right'),
            ('bottom-left', 'Bottom Left'),
            ('bottom-right', 'Bottom Right')
        ],
        help_text="Watermark position"
    )
    watermark_opacity = models.FloatField(default=0.7, help_text="Watermark opacity (0.0 to 1.0)")
    add_end_screen = models.BooleanField(default=True, help_text="Add branded end screen with logo")
    end_screen_duration = models.IntegerField(default=3, help_text="End screen duration in seconds")
    
    # Status
    is_published = models.BooleanField(default=False, help_text="Publish on website")
    is_processing = models.BooleanField(default=False, help_text="Video generation in progress")
    show_on_homepage = models.BooleanField(default=True, help_text="Show this reel in the homepage carousel")
    order = models.PositiveIntegerField(default=0, help_text="Display order on homepage (lower numbers appear first)")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reels')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "Reel"
        verbose_name_plural = "Reels"
    
    def __str__(self):
        return self.title


class ReelImage(models.Model):
    """Images used in a reel"""
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='reels/images/', help_text="Image for reel")
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    text_overlay = models.CharField(max_length=200, blank=True, help_text="Text to display on this image")
    text_position = models.CharField(max_length=20, default='center', help_text="Text position (center, top, bottom)")
    text_color = models.CharField(max_length=20, default='white', help_text="Text color")
    text_size = models.IntegerField(default=70, help_text="Text font size")
    
    class Meta:
        ordering = ['order']
        verbose_name = "Reel Image"
        verbose_name_plural = "Reel Images"
    
    def __str__(self):
        return f"{self.reel.title} - Image {self.order}"


# ============================================
# COUPON SYSTEM
# ============================================

class Coupon(models.Model):
    """Discount coupons for orders"""
    DISCOUNT_TYPE_CHOICES = [
        ('PERCENTAGE', 'Percentage'),
        ('FIXED', 'Fixed Amount'),
    ]
    
    COUPON_TYPE_CHOICES = [
        ('MANUAL', 'Manual Code'),
        ('FIRST_ORDER', 'First Order (5%)'),
        ('SPEND_5K', 'Spend 5000 (5%)'),
    ]
    
    code = models.CharField(max_length=50, unique=True, help_text="Coupon code (e.g., FIRST5)")
    coupon_type = models.CharField(max_length=20, choices=COUPON_TYPE_CHOICES, default='MANUAL')
    description = models.TextField(blank=True, help_text="Description shown to users")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Percentage or fixed amount")
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Minimum cart value")
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Maximum discount cap")
    usage_limit = models.IntegerField(null=True, blank=True, help_text="Total usage limit (null = unlimited)")
    usage_per_user = models.IntegerField(default=1, help_text="Usage limit per user")
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"
    
    def __str__(self):
        return f"{self.code} - {self.discount_value}{'%' if self.discount_type == 'PERCENTAGE' else '₹'}"
    
    def is_valid(self):
        """Check if coupon is currently valid"""
        from django.utils import timezone
        now = timezone.now()
        return self.is_active and self.valid_from <= now <= self.valid_to
    
    def get_discount_amount(self, cart_total):
        """Calculate discount amount for given cart total"""
        if self.discount_type == 'PERCENTAGE':
            discount = (cart_total * self.discount_value) / 100
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        else:
            discount = self.discount_value
        return min(discount, cart_total)
    
    def times_used(self):
        """Get total usage count"""
        return self.couponusage_set.count()


class CouponUsage(models.Model):
    """Track coupon usage by users"""
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey('Order', on_delete=models.CASCADE, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['coupon', 'order']
        ordering = ['-used_at']
        verbose_name = "Coupon Usage"
        verbose_name_plural = "Coupon Usages"
    
    def __str__(self):
        return f"{self.user.username} used {self.coupon.code} on {self.used_at.strftime('%Y-%m-%d')}"


class UserSpendTracker(models.Model):
    """Track user spending for automatic coupon generation"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='spend_tracker')
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total lifetime spending")
    current_cycle_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Spending in current 5K cycle")
    last_5k_coupon_at = models.DateTimeField(null=True, blank=True, help_text="When last 5K coupon was earned")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Spend Tracker"
        verbose_name_plural = "User Spend Trackers"
    
    def __str__(self):
        return f"{self.user.username} - Total: ₹{self.total_spent} | Cycle: ₹{self.current_cycle_spent}"
    
    def can_earn_5k_coupon(self):
        """Check if user has spent enough for 5K coupon"""
        return self.current_cycle_spent >= 5000


# ============================================
# RESELL FEATURE MODELS
# ============================================

class ResellLink(models.Model):
    """Tracks resell links created by users"""
    reseller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resell_links')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='resell_links')
    resell_code = models.CharField(max_length=20, unique=True, db_index=True)
    margin_amount = models.DecimalField(max_digits=10, decimal_places=2)
    margin_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    views_count = models.PositiveIntegerField(default=0)
    orders_count = models.PositiveIntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Resell Link"
        verbose_name_plural = "Resell Links"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['resell_code']),
            models.Index(fields=['reseller', 'is_active']),
        ]
    
    def __str__(self):
        return f"Resell Link {self.resell_code} - {self.reseller.username} - {self.product.name}"
    
    def clean(self):
        """Validate margin amount"""
        from django.core.exceptions import ValidationError
        
        if self.margin_amount is not None and self.product:
            # Margin must be positive
            if self.margin_amount <= 0:
                raise ValidationError({'margin_amount': 'Margin must be greater than zero.'})
            
            # Margin must not exceed 50% of product price
            max_margin = self.product.price * Decimal('0.5')
            if self.margin_amount > max_margin:
                raise ValidationError({
                    'margin_amount': f'Margin cannot exceed 50% of product price (₹{max_margin}).'
                })
    
    def save(self, *args, **kwargs):
        # Calculate margin percentage if not set
        if self.margin_percentage is None and self.product:
            self.margin_percentage = (self.margin_amount / self.product.price) * 100
        
        # Run validation
        self.full_clean()
        super().save(*args, **kwargs)


class ResellerProfile(models.Model):
    """Extended profile for users who are resellers"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='reseller_profile')
    is_reseller_enabled = models.BooleanField(default=False)
    business_name = models.CharField(max_length=200, blank=True)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    available_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    bank_account_name = models.CharField(max_length=200, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_ifsc_code = models.CharField(max_length=20, blank=True)
    upi_id = models.CharField(max_length=100, blank=True)
    pan_number = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Reseller Profile"
        verbose_name_plural = "Reseller Profiles"
    
    def __str__(self):
        return f"Reseller Profile - {self.user.username}"
    
    def clean(self):
        """Validate available balance cannot be negative"""
        from django.core.exceptions import ValidationError
        
        if self.available_balance < 0:
            raise ValidationError({'available_balance': 'Available balance cannot be negative.'})
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ResellerEarning(models.Model):
    """Tracks earnings for each reseller from orders"""
    EARNING_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    reseller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reseller_earnings')
    order = models.OneToOneField('Order', on_delete=models.CASCADE, related_name='reseller_earning')
    resell_link = models.ForeignKey(ResellLink, on_delete=models.SET_NULL, null=True)
    margin_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=EARNING_STATUS_CHOICES, default='PENDING')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payout_transaction = models.ForeignKey('PayoutTransaction', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Reseller Earning"
        verbose_name_plural = "Reseller Earnings"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reseller', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Earning {self.status} - {self.reseller.username} - Order #{self.order.order_number}"


class PayoutTransaction(models.Model):
    """Tracks payout transactions to resellers"""
    PAYOUT_STATUS_CHOICES = [
        ('INITIATED', 'Initiated'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    PAYOUT_METHOD_CHOICES = [
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('UPI', 'UPI'),
        ('WALLET', 'Wallet'),
    ]
    
    reseller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payout_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_method = models.CharField(max_length=20, choices=PAYOUT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, default='INITIATED')
    transaction_id = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=100, blank=True)
    upi_id = models.CharField(max_length=100, blank=True)
    admin_notes = models.TextField(blank=True)
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Payout Transaction"
        verbose_name_plural = "Payout Transactions"
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['reseller', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Payout {self.status} - {self.reseller.username} - ₹{self.amount}"
    
    def clean(self):
        """Validate payout amount and payment details"""
        from django.core.exceptions import ValidationError
        
        if self.amount <= 0:
            raise ValidationError({'amount': 'Payout amount must be greater than zero.'})
        
        # Validate payment method specific fields
        if self.payout_method == 'BANK_TRANSFER':
            if not self.bank_account:
                raise ValidationError({'bank_account': 'Bank account details required for bank transfer.'})
        elif self.payout_method == 'UPI':
            if not self.upi_id:
                raise ValidationError({'upi_id': 'UPI ID required for UPI payout.'})
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ==================== BACKUP SYSTEM MODELS ====================

class BackupConfiguration(models.Model):
    """Store backup scheduling and frequency configuration for automated backups."""
    
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('BIWEEKLY', 'Every 15 Days'),
        ('MONTHLY', 'Monthly'),
        ('CUSTOM', 'Custom Dates'),
    ]
    
    backup_frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='MONTHLY',
        help_text="How often should backups run?"
    )

    backup_root_path = models.CharField(
        max_length=500,
        default=r'D:\VibeMallBackUp',
        help_text="Local root folder for all backups"
    )

    regular_folder_name = models.CharField(
        max_length=100,
        default='RegularBackUp',
        help_text="Subfolder name for automated regular backups"
    )

    special_folder_name = models.CharField(
        max_length=100,
        default='SpecialBackup',
        help_text="Subfolder name for manual special backups and ITR reports"
    )
    
    schedule_time = models.TimeField(
        default='03:00',
        help_text="What time should the backup run? (HH:MM in 24-hour format)"
    )
    
    # For WEEKLY backups: 0=Monday, 1=Tuesday, ..., 6=Sunday
    schedule_weekday = models.IntegerField(
        default=0,
        help_text="Day of week for weekly backups (0=Monday, 6=Sunday)",
        null=True,
        blank=True
    )
    
    # For CUSTOM backups: store as comma-separated list [1, 7, 15, 30]
    custom_dates = models.CharField(
        max_length=50,
        default='1,7,15,30',
        help_text="Comma-separated dates for custom backups (e.g., 1,7,15,30)"
    )
    
    # Terabox Configuration
    enable_terabox_backup = models.BooleanField(
        default=False,
        help_text="Deprecated: Terabox backup is disabled in local backup mode"
    )
    
    terabox_auto_folder_create = models.BooleanField(
        default=True,
        help_text="Automatically create dated folders in Terabox (01, 07, 15, 30)?"
    )
    
    # Notification Settings
    notification_emails = models.TextField(
        default='',
        blank=True,
        help_text="Comma-separated email addresses for backup notifications"
    )
    
    send_success_email = models.BooleanField(
        default=True,
        help_text="Send email when backup completes successfully?"
    )
    
    send_failure_email = models.BooleanField(
        default=True,
        help_text="Send email when backup fails?"
    )
    
    # Data retention policy
    keep_local_backups_days = models.IntegerField(
        default=30,
        help_text="Keep local backups for how many days?"
    )
    
    keep_cloud_backups_days = models.IntegerField(
        default=365,
        help_text="Keep cloud backups for how many days?"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Enable or disable automatic backups?"
    )
    
    last_backup_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last completed backup"
    )
    
    next_backup_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Calculated timestamp of next scheduled backup"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Backup Configuration"
        verbose_name_plural = "Backup Configurations"
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Backup Config - {self.get_backup_frequency_display()}"
    
    def get_notification_emails(self):
        """Return list of notification emails."""
        if not self.notification_emails:
            return []
        return [email.strip() for email in self.notification_emails.split(',') if email.strip()]
    
    def get_custom_dates(self):
        """Return list of custom backup dates."""
        if self.backup_frequency != 'CUSTOM':
            return []
        try:
            return [int(d.strip()) for d in self.custom_dates.split(',') if d.strip()]
        except ValueError:
            return []


class BackupLog(models.Model):
    """Log entry for each backup operation - tracks success, failure, duration, size, etc."""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('PARTIAL', 'Partial Success'),
    ]
    
    BACKUP_TYPE_CHOICES = [
        ('MANUAL', 'Manual Trigger'),
        ('SCHEDULED', 'Scheduled'),
        ('ON_DEMAND', 'On Demand'),
        ('SPECIAL', 'Special Backup'),
        ('ITR_REPORT', 'ITR Financial Report'),
    ]

    BACKUP_SCOPE_CHOICES = [
        ('REGULAR', 'Regular Backup'),
        ('SPECIAL', 'Special Backup'),
        ('ITR', 'ITR Report Backup'),
    ]
    
    backup_type = models.CharField(
        max_length=20,
        choices=BACKUP_TYPE_CHOICES,
        default='SCHEDULED'
    )

    backup_scope = models.CharField(
        max_length=20,
        choices=BACKUP_SCOPE_CHOICES,
        default='REGULAR',
        help_text="Regular, special, or ITR report backup"
    )
    
    backup_frequency = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Which schedule triggered this backup?"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    # Timing
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    @property
    def duration_seconds(self):
        """Calculate backup duration in seconds."""
        if self.end_time and self.start_time:
            return int((self.end_time - self.start_time).total_seconds())
        return None
    
    # Data counts (stored as JSON to be flexible)
    users_count = models.IntegerField(default=0)
    orders_count = models.IntegerField(default=0)
    payments_count = models.IntegerField(default=0)
    products_count = models.IntegerField(default=0)
    returns_count = models.IntegerField(default=0)
    transactions_count = models.IntegerField(default=0)
    
    # File information
    local_file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to local backup file"
    )

    monthly_folder_label = models.CharField(
        max_length=20,
        blank=True,
        help_text="Monthly folder label (e.g., 2026-03)"
    )
    
    terabox_file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Deprecated cloud backup path"
    )
    
    file_size_mb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Size of backup file in MB"
    )
    
    # Status tracking
    terabox_synced = models.BooleanField(
        default=False,
        help_text="Deprecated cloud sync flag"
    )

    requires_cleanup_confirmation = models.BooleanField(
        default=False,
        help_text="Whether this backup generated an old-data cleanup confirmation request"
    )
    
    email_sent = models.BooleanField(
        default=False,
        help_text="Was notification email sent?"
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text="Error details if backup failed"
    )
    
    error_trace = models.TextField(
        blank=True,
        help_text="Full error traceback for debugging"
    )
    
    # Additional metadata
    backup_data_types = models.CharField(
        max_length=200,
        default='users,orders,payments,products,returns,transactions',
        help_text="Comma-separated list of data types in this backup"
    )
    
    notes = models.TextField(blank=True, help_text="Admin notes for this backup")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Backup Log"
        verbose_name_plural = "Backup Logs"
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['start_time']),
            models.Index(fields=['backup_type', 'status']),
        ]
    
    def __str__(self):
        return f"Backup {self.get_status_display()} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    def get_total_records(self):
        """Get total number of records backed up."""
        return (self.users_count + self.orders_count + self.payments_count + 
                self.products_count + self.returns_count + self.transactions_count)
    
    def get_data_summary(self):
        """Return summary of backed up data."""
        return {
            'users': self.users_count,
            'orders': self.orders_count,
            'payments': self.payments_count,
            'products': self.products_count,
            'returns': self.returns_count,
            'transactions': self.transactions_count,
            'total': self.get_total_records(),
        }


class TeraboxSettings(models.Model):
    """Store Terabox API authentication and configuration."""
    
    # Authentication
    api_access_token = models.TextField(
        blank=True,
        help_text="Terabox API access token (keep confidential!)"
    )
    
    refresh_token = models.TextField(
        blank=True,
        help_text="Terabox refresh token for token renewal"
    )
    
    token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When does the current token expire?"
    )
    
    # Folder Configuration
    folder_root_path = models.CharField(
        max_length=500,
        default='/VibeMall_Backups',
        help_text="Root folder path in Terabox for backups"
    )
    
    auto_create_folders = models.BooleanField(
        default=True,
        help_text="Automatically create dated folders (01, 07, 15, 30)?"
    )
    
    # Status
    is_connected = models.BooleanField(
        default=False,
        help_text="Is Terabox account successfully connected?"
    )
    
    connection_status_message = models.CharField(
        max_length=255,
        blank=True,
        help_text="Last connection status message"
    )
    
    # Usage tracking
    last_sync_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last successful sync/upload to Terabox"
    )
    
    total_backups_synced = models.IntegerField(
        default=0,
        help_text="Total number of backups uploaded to Terabox"
    )
    
    cloud_storage_used_mb = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Approximate storage used in Terabox (MB)"
    )
    
    # Metadata
    account_info = models.TextField(
        blank=True,
        help_text="Terabox account info (JSON - email, display_name, etc)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Terabox Settings"
        verbose_name_plural = "Terabox Settings"
    
    def __str__(self):
        return f"Terabox Config - {'Connected' if self.is_connected else 'Not Connected'}"
    
    def is_token_expired(self):
        """Check if access token has expired."""
        if not self.token_expires_at:
            return True
        return timezone.now() > self.token_expires_at
    
    def token_expiry_in_hours(self):
        """Get remaining hours before token expires."""
        if not self.token_expires_at:
            return 0
        delta = self.token_expires_at - timezone.now()
        return max(0, int(delta.total_seconds() / 3600))


class BackupCleanupRequest(models.Model):
    """Admin confirmation record before deleting previous backup folders."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending Confirmation'),
        ('CONFIRMED', 'Confirmed'),
        ('DECLINED', 'Declined'),
        ('COMPLETED', 'Completed'),
    ]

    backup_log = models.ForeignKey(
        BackupLog,
        on_delete=models.CASCADE,
        related_name='cleanup_requests'
    )
    folder_path = models.CharField(max_length=500)
    folder_label = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    confirmation_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email_sent = models.BooleanField(default=False)
    requested_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']
        verbose_name = "Backup Cleanup Request"
        verbose_name_plural = "Backup Cleanup Requests"

    def __str__(self):
        return f"Cleanup {self.folder_label} - {self.status}"


class Refund(models.Model):
    """Track refund requests and transactions"""
    REFUND_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='refunds')
    razorpay_payment_id = models.CharField(max_length=100, help_text="Razorpay Payment ID to refund")
    razorpay_refund_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Refund ID")
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount refunded in ₹")
    status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='PENDING')
    reason = models.TextField(help_text="Reason for refund")
    notes = models.TextField(blank=True, help_text="Additional notes")
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='refunds_requested')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('order', 'razorpay_refund_id')
    
    def __str__(self):
        return f"Refund #{self.id} - Order #{self.order.order_number} - ₹{self.refund_amount}"


class BankVerification(models.Model):
    """Track bank account verification using penny drop (₹1 transfer)"""
    VERIFICATION_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VERIFYING', 'Verifying'),
        ('VERIFIED', 'Verified'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bank_verification')
    account_number = models.CharField(max_length=50, help_text="Bank account number (masked)")
    ifsc = models.CharField(max_length=11, help_text="IFSC code")
    account_name = models.CharField(max_length=255, blank=True, help_text="Account holder name from bank")
    
    # Razorpay integration
    razorpay_contact_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Contact ID")
    razorpay_fund_account_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Fund Account ID")
    razorpay_payout_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Payout ID for verification")
    
    # Verification status
    status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='PENDING')
    is_verified = models.BooleanField(default=False)
    verification_error = models.TextField(blank=True, help_text="Error message if verification failed")
    
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"BankVerification - {self.user.username} - {self.account_number[-4:]}"


class UPIVerification(models.Model):
    """Track UPI verification via admin review"""
    VERIFICATION_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ADMIN_REVIEW', 'Pending Admin Review'),
        ('VERIFIED', 'Verified'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='upi_verifications')
    upi_id = models.CharField(max_length=255, help_text="UPI ID (e.g., name@bank)")
    
    # Optional link to a return request
    return_request = models.ForeignKey(
        'ReturnRequest', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='upi_verifications'
    )

    # Verification status
    status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='PENDING')
    is_verified = models.BooleanField(default=False)
    verification_error = models.TextField(blank=True, help_text="Error message if verification failed")
    admin_notes = models.TextField(blank=True, help_text="Admin notes on this verification")
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='upi_verifications_reviewed'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"UPIVerification - {self.user.username} - {self.upi_id} - {self.status}"


# ==================== WEBHOOK LOGGING & VERIFICATION MODELS ====================

class WebhookLog(models.Model):
    """Log all incoming webhooks for debugging and audit"""
    EVENT_TYPES = [
        ('payment.captured', 'Payment Captured'),
        ('payment.failed', 'Payment Failed'),
        ('payment.authorized', 'Payment Authorized'),
        ('refund.created', 'Refund Created'),
        ('settlement.processed', 'Settlement Processed'),
        ('unknown', 'Unknown Event'),
    ]
    
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
    ]
    
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    payment_id = models.CharField(max_length=100, blank=True, db_index=True)
    order_id = models.CharField(max_length=100, blank=True, db_index=True)
    raw_body = models.JSONField(help_text="Raw webhook payload from Razorpay")
    signature = models.CharField(max_length=256, blank=True, help_text="Webhook signature for verification")
    signature_valid = models.BooleanField(default=False, help_text="Whether signature was valid")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received', db_index=True)
    response_message = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    
    processed_by_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['-received_at', 'event_type']),
            models.Index(fields=['payment_id', 'order_id']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.payment_id} - {self.status}"
    
    def get_amount(self):
        """Extract amount from webhook payload"""
        try:
            if self.event_type == 'payment.captured':
                return self.raw_body.get('payload', {}).get('payment', {}).get('entity', {}).get('amount')
            elif self.event_type == 'refund.created':
                return self.raw_body.get('payload', {}).get('refund', {}).get('entity', {}).get('amount')
        except:
            pass
        return None


class VerificationTestLog(models.Model):
    """Log test verification attempts for debugging"""
    TEST_TYPES = [
        ('upi', 'UPI Verification'),
        ('bank', 'Bank Verification'),
        ('both', 'Both'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_test_logs')
    test_type = models.CharField(max_length=20, choices=TEST_TYPES)
    
    upi_id = models.CharField(max_length=255, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    
    test_amount = models.CharField(max_length=20, default='100')  # In paise
    test_status = models.CharField(max_length=50, blank=True)
    
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_response = models.JSONField(default=dict)
    
    webhook_received = models.BooleanField(default=False)
    webhook_received_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True, help_text="Test notes for debugging")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Test {self.test_type} - {self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
