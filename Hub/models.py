from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

class CategoryIcon(models.Model):
    """Category icons for Shop By Department section"""
    name = models.CharField(max_length=100, help_text="Category name (e.g., Mobiles, Food & Health)")
    icon_class = models.CharField(
        max_length=100,
        help_text="FontAwesome icon class (e.g., 'fas fa-mobile-alt')"
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
        help_text="Icon color (hex code)"
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order (lower numbers appear first)")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Category Icon"
        verbose_name_plural = "Category Icons"

    def __str__(self):
        return self.name

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


class Product(models.Model):
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
    old_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    discount_percent = models.PositiveIntegerField(default=0)

    sold = models.PositiveIntegerField(default=0)
    stock = models.PositiveIntegerField(default=0)

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        blank=True,
        null=True,
        help_text="Select product category for homepage sections"
    )
    
    # Product Details
    weight = models.CharField(max_length=50, blank=True, help_text="e.g., 2 lbs")
    dimensions = models.CharField(max_length=100, blank=True, help_text="e.g., 12 × 16 × 19 in")
    color = models.CharField(max_length=100, blank=True, help_text="Available colors")
    size = models.CharField(max_length=100, blank=True, help_text="Available sizes")
    brand = models.CharField(max_length=100, blank=True)
    shipping_info = models.CharField(max_length=200, blank=True, help_text="e.g., Standard shipping: $5.95")
    care_info = models.TextField(blank=True, help_text="Care instructions")
    tags = models.CharField(max_length=200, blank=True, help_text="Comma-separated tags")
    
    is_top_deal = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    rating = models.FloatField(default=0)
    review_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-id']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def progress_percent(self):
        if self.stock == 0:
            return 0
        return int((self.sold / self.stock) * 100)

    def get_tags_list(self):
        """Return tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    """Additional images for product gallery"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='additional_images')
    image = models.ImageField(upload_to='products/gallery/')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name} - Image {self.order}"


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

    def get_total_price(self):
        return self.product.price * self.quantity

    def __str__(self):
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
        """Override save to auto-update product rating and review count"""
        super().save(*args, **kwargs)

        from django.db.models import Avg
        product = self.product
        approved_reviews = ProductReview.objects.filter(product=product, is_approved=True)

        if approved_reviews.exists():
            product.review_count = approved_reviews.count()
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
    
    # Payment related fields
    razorpay_order_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Order ID")
    razorpay_payment_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Payment ID")
    razorpay_signature = models.CharField(max_length=200, blank=True, help_text="Razorpay Payment Signature")
    
    # Resell functionality
    is_resell = models.BooleanField(default=False, help_text="Is this a resell order?")
    resell_from_name = models.CharField(max_length=200, blank=True, help_text="Original seller name for resell orders")
    resell_from_phone = models.CharField(max_length=20, blank=True, help_text="Original seller phone for resell orders")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order #{self.order_number} - {self.user.username}"
    
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


class OrderItem(models.Model):
    """Items in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    
    # Product details at time of order (preserved even if product changes)
    product_name = models.CharField(max_length=255)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    product_image = models.CharField(max_length=500, blank=True)
    
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
