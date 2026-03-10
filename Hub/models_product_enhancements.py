"""
Product Management Enhancement Models - Phase 7
Features: Product Variants, Bundling, Related Products, SEO Optimization, Video Support, 360° View
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class ProductVariant(models.Model):
    """Product variants management (size, color combinations)"""
    VARIANT_TYPE_CHOICES = [
        ('SIZE', 'Size'),
        ('COLOR', 'Color'),
        ('MATERIAL', 'Material'),
        ('STYLE', 'Style'),
        ('PATTERN', 'Pattern'),
        ('WEIGHT', 'Weight'),
        ('CUSTOM', 'Custom'),
    ]
    
    product_id = models.PositiveIntegerField(db_index=True)
    variant_type = models.CharField(max_length=20, choices=VARIANT_TYPE_CHOICES)
    
    # Variant details
    name = models.CharField(max_length=100, help_text="e.g., Red, Large, Cotton")
    display_name = models.CharField(max_length=100, help_text="Display name for frontend")
    value = models.CharField(max_length=100, help_text="Variant value")
    
    # Pricing
    price_adjustment = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Price difference from base product")
    cost_adjustment = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Cost difference from base product")
    
    # Inventory
    stock_quantity = models.PositiveIntegerField(default=0)
    sku_suffix = models.CharField(max_length=20, blank=True, help_text="SKU suffix for this variant")
    
    # Visual representation
    color_hex = models.CharField(max_length=7, blank=True, help_text="Hex color code for color variants")
    image = models.ImageField(upload_to='product_variants/', null=True, blank=True)
    
    # Availability
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['product_id', 'variant_type', 'sort_order']
        indexes = [
            models.Index(fields=['product_id', 'variant_type']),
            models.Index(fields=['product_id', 'is_active']),
        ]
    
    def __str__(self):
        return f"Product {self.product_id} - {self.get_variant_type_display()}: {self.display_name}"


class ProductVariantCombination(models.Model):
    """Specific combinations of variants (e.g., Red + Large)"""
    product_id = models.PositiveIntegerField(db_index=True)
    combination_sku = models.CharField(max_length=100, unique=True)
    
    # Variant combination
    variants = models.JSONField(default=list, help_text="List of variant IDs in this combination")
    variant_display = models.CharField(max_length=200, help_text="Human readable variant combination")
    
    # Pricing for this specific combination
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Inventory
    stock_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    
    # Images specific to this combination
    primary_image = models.ImageField(upload_to='variant_combinations/', null=True, blank=True)
    additional_images = models.JSONField(default=list, help_text="List of additional image URLs")
    
    # Availability
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text="Default combination to show")
    
    # Sales tracking
    total_sold = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['product_id', '-is_default', 'variant_display']
        indexes = [
            models.Index(fields=['product_id', 'is_active']),
            models.Index(fields=['combination_sku']),
        ]
    
    def available_quantity(self):
        return max(0, self.stock_quantity - self.reserved_quantity)
    
    def __str__(self):
        return f"Product {self.product_id} - {self.variant_display}"


class ProductBundle(models.Model):
    """Product bundling for combo offers"""
    BUNDLE_TYPE_CHOICES = [
        ('FIXED', 'Fixed Bundle'),
        ('MIX_MATCH', 'Mix and Match'),
        ('TIERED', 'Tiered Discount'),
        ('BOGO', 'Buy One Get One'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    bundle_type = models.CharField(max_length=20, choices=BUNDLE_TYPE_CHOICES)
    
    # Bundle products
    products = models.JSONField(default=list, help_text="List of product IDs with quantities")
    
    # Pricing
    individual_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Sum of individual product prices")
    bundle_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Bundle settings
    min_quantity = models.PositiveIntegerField(default=1)
    max_quantity = models.PositiveIntegerField(null=True, blank=True)
    
    # Availability
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Display
    bundle_image = models.ImageField(upload_to='product_bundles/', null=True, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    
    # Sales tracking
    total_sold = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'name']
    
    def is_available(self):
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return self.is_active
    
    def save(self, *args, **kwargs):
        if self.individual_total > 0:
            self.discount_amount = self.individual_total - self.bundle_price
            self.discount_percentage = (self.discount_amount / self.individual_total) * 100
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} - ₹{self.bundle_price}"


class RelatedProduct(models.Model):
    """Related products suggestions"""
    RELATION_TYPE_CHOICES = [
        ('CROSS_SELL', 'Cross Sell'),
        ('UP_SELL', 'Up Sell'),
        ('FREQUENTLY_BOUGHT', 'Frequently Bought Together'),
        ('SIMILAR', 'Similar Products'),
        ('COMPLEMENTARY', 'Complementary Products'),
        ('ALTERNATIVE', 'Alternative Products'),
    ]
    
    primary_product_id = models.PositiveIntegerField(db_index=True)
    related_product_id = models.PositiveIntegerField(db_index=True)
    relation_type = models.CharField(max_length=20, choices=RELATION_TYPE_CHOICES)
    
    # Relationship strength
    relevance_score = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="0-100 relevance score")
    
    # Auto-generated or manual
    is_auto_generated = models.BooleanField(default=False)
    auto_generation_reason = models.CharField(max_length=100, blank=True)
    
    # Performance tracking
    view_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    conversion_count = models.PositiveIntegerField(default=0)
    
    # Display settings
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['primary_product_id', 'relation_type', 'display_order']
        unique_together = ['primary_product_id', 'related_product_id', 'relation_type']
        indexes = [
            models.Index(fields=['primary_product_id', 'relation_type']),
            models.Index(fields=['related_product_id']),
        ]
    
    def click_through_rate(self):
        if self.view_count > 0:
            return (self.click_count / self.view_count) * 100
        return 0
    
    def conversion_rate(self):
        if self.click_count > 0:
            return (self.conversion_count / self.click_count) * 100
        return 0
    
    def __str__(self):
        return f"Product {self.primary_product_id} → {self.related_product_id} ({self.get_relation_type_display()})"


class ProductComparison(models.Model):
    """Product comparison feature"""
    comparison_id = models.CharField(max_length=50, unique=True)
    products = models.JSONField(default=list, help_text="List of product IDs being compared")
    
    # Comparison attributes
    comparison_attributes = models.JSONField(default=list, help_text="List of attributes to compare")
    
    # User tracking
    created_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Analytics
    view_count = models.PositiveIntegerField(default=1)
    last_viewed = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comparison {self.comparison_id} - {len(self.products)} products"


class ProductSEO(models.Model):
    """SEO optimization for products"""
    product_id = models.PositiveIntegerField(unique=True, db_index=True)
    
    # Meta tags
    meta_title = models.CharField(max_length=60, blank=True, help_text="SEO title (max 60 chars)")
    meta_description = models.CharField(max_length=160, blank=True, help_text="SEO description (max 160 chars)")
    meta_keywords = models.TextField(blank=True, help_text="Comma-separated keywords")
    
    # URL optimization
    custom_slug = models.SlugField(max_length=200, blank=True, help_text="Custom URL slug")
    canonical_url = models.URLField(blank=True, help_text="Canonical URL if different")
    
    # Schema markup
    schema_markup = models.JSONField(default=dict, help_text="Structured data for rich snippets")
    
    # Content optimization
    focus_keyword = models.CharField(max_length=100, blank=True)
    keyword_density = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Social media
    og_title = models.CharField(max_length=100, blank=True, help_text="Open Graph title")
    og_description = models.CharField(max_length=200, blank=True, help_text="Open Graph description")
    og_image = models.ImageField(upload_to='seo_images/', null=True, blank=True)
    
    # Twitter cards
    twitter_title = models.CharField(max_length=70, blank=True)
    twitter_description = models.CharField(max_length=200, blank=True)
    twitter_image = models.ImageField(upload_to='seo_images/', null=True, blank=True)
    
    # SEO scores
    seo_score = models.PositiveIntegerField(default=0, help_text="Overall SEO score (0-100)")
    readability_score = models.PositiveIntegerField(default=0, help_text="Content readability score")
    
    # Indexing
    is_indexable = models.BooleanField(default=True)
    robots_meta = models.CharField(max_length=100, default='index,follow')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['product_id']
    
    def __str__(self):
        return f"SEO for Product {self.product_id} (Score: {self.seo_score})"


class ProductVideo(models.Model):
    """Product video management"""
    VIDEO_TYPE_CHOICES = [
        ('PRODUCT_DEMO', 'Product Demo'),
        ('UNBOXING', 'Unboxing'),
        ('TUTORIAL', 'How to Use'),
        ('REVIEW', 'Customer Review'),
        ('COMPARISON', 'Product Comparison'),
        ('360_VIEW', '360° View'),
        ('AR_VIEW', 'AR View'),
    ]
    
    product_id = models.PositiveIntegerField(db_index=True)
    video_type = models.CharField(max_length=20, choices=VIDEO_TYPE_CHOICES)
    
    # Video details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Video files
    video_file = models.FileField(upload_to='product_videos/', null=True, blank=True)
    video_url = models.URLField(blank=True, help_text="External video URL (YouTube, Vimeo)")
    thumbnail = models.ImageField(upload_to='video_thumbnails/', null=True, blank=True)
    
    # Video metadata
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    file_size_mb = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    resolution = models.CharField(max_length=20, blank=True, help_text="e.g., 1920x1080")
    
    # Display settings
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    play_count = models.PositiveIntegerField(default=0)
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['product_id', 'display_order']
        indexes = [
            models.Index(fields=['product_id', 'is_active']),
            models.Index(fields=['video_type']),
        ]
    
    def __str__(self):
        return f"Product {self.product_id} - {self.title} ({self.get_video_type_display()})"


class Product360View(models.Model):
    """360-degree product view"""
    product_id = models.PositiveIntegerField(unique=True, db_index=True)
    
    # 360° images
    image_sequence = models.JSONField(default=list, help_text="Ordered list of image URLs for 360° view")
    total_frames = models.PositiveIntegerField(default=36, help_text="Number of frames in 360° sequence")
    
    # Settings
    auto_rotate = models.BooleanField(default=True)
    rotation_speed = models.PositiveIntegerField(default=5, help_text="Rotation speed (1-10)")
    zoom_enabled = models.BooleanField(default=True)
    fullscreen_enabled = models.BooleanField(default=True)
    
    # Hotspots (interactive points)
    hotspots = models.JSONField(default=list, help_text="Interactive hotspots with descriptions")
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    interaction_count = models.PositiveIntegerField(default=0)
    average_view_time = models.PositiveIntegerField(default=0, help_text="Average view time in seconds")
    
    # Status
    is_active = models.BooleanField(default=True)
    processing_status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ], default='PENDING')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['product_id']
    
    def __str__(self):
        return f"360° View for Product {self.product_id} ({self.total_frames} frames)"


class ProductBulkOperation(models.Model):
    """Bulk product operations tracking"""
    OPERATION_TYPE_CHOICES = [
        ('IMPORT', 'Bulk Import'),
        ('EXPORT', 'Bulk Export'),
        ('UPDATE', 'Bulk Update'),
        ('DELETE', 'Bulk Delete'),
        ('PRICE_UPDATE', 'Price Update'),
        ('STOCK_UPDATE', 'Stock Update'),
        ('SEO_UPDATE', 'SEO Update'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('PARTIALLY_COMPLETED', 'Partially Completed'),
    ]
    
    operation_id = models.CharField(max_length=50, unique=True)
    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # File handling
    input_file = models.FileField(upload_to='bulk_operations/', null=True, blank=True)
    output_file = models.FileField(upload_to='bulk_operations/', null=True, blank=True)
    error_log_file = models.FileField(upload_to='bulk_operations/', null=True, blank=True)
    
    # Progress tracking
    total_records = models.PositiveIntegerField(default=0)
    processed_records = models.PositiveIntegerField(default=0)
    successful_records = models.PositiveIntegerField(default=0)
    failed_records = models.PositiveIntegerField(default=0)
    
    # Operation parameters
    operation_params = models.JSONField(default=dict, help_text="Operation-specific parameters")
    
    # Error tracking
    errors = models.JSONField(default=list, help_text="List of errors encountered")
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def progress_percentage(self):
        if self.total_records > 0:
            return (self.processed_records / self.total_records) * 100
        return 0
    
    def success_rate(self):
        if self.processed_records > 0:
            return (self.successful_records / self.processed_records) * 100
        return 0
    
    def __str__(self):
        return f"{self.get_operation_type_display()} - {self.operation_id} ({self.status})"