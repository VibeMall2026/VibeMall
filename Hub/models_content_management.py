"""
Content Management Models - Phase 9
Features: Blog/Article Management, FAQ System, Page Builder, Email Templates, WhatsApp Templates
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class BlogCategory(models.Model):
    """Blog/article categories"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    
    # SEO
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    
    # Display
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code")
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    featured_image = models.ImageField(upload_to='blog_categories/', null=True, blank=True)
    
    # Hierarchy
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    
    # Settings
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = "Blog Categories"
    
    def __str__(self):
        return self.name


class BlogPost(models.Model):
    """Blog posts and articles"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('SCHEDULED', 'Scheduled'),
        ('ARCHIVED', 'Archived'),
    ]
    
    POST_TYPE_CHOICES = [
        ('ARTICLE', 'Article'),
        ('NEWS', 'News'),
        ('TUTORIAL', 'Tutorial'),
        ('REVIEW', 'Product Review'),
        ('ANNOUNCEMENT', 'Announcement'),
        ('GUIDE', 'How-to Guide'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    excerpt = models.TextField(max_length=300, help_text="Short description for listings")
    content = models.TextField()
    
    # Classification
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, related_name='posts')
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default='ARTICLE')
    tags = models.JSONField(default=list, help_text="List of tags")
    
    # Media
    featured_image = models.ImageField(upload_to='blog_posts/', null=True, blank=True)
    gallery_images = models.JSONField(default=list, help_text="List of additional image URLs")
    
    # SEO
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    meta_keywords = models.TextField(blank=True)
    canonical_url = models.URLField(blank=True)
    
    # Social sharing
    og_title = models.CharField(max_length=100, blank=True)
    og_description = models.CharField(max_length=200, blank=True)
    og_image = models.ImageField(upload_to='blog_og/', null=True, blank=True)
    
    # Publishing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    published_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    
    # Author information
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='blog_posts')
    guest_author_name = models.CharField(max_length=100, blank=True)
    guest_author_bio = models.TextField(blank=True)
    
    # Engagement
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    
    # Settings
    allow_comments = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_sticky = models.BooleanField(default=False)
    
    # Related content
    related_products = models.JSONField(default=list, help_text="List of related product IDs")
    related_posts = models.JSONField(default=list, help_text="List of related post IDs")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['is_featured', '-published_at']),
        ]
    
    def is_published(self):
        return self.status == 'PUBLISHED' and (not self.published_at or self.published_at <= timezone.now())
    
    def __str__(self):
        return self.title


class BlogComment(models.Model):
    """Blog post comments"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('SPAM', 'Marked as Spam'),
    ]
    
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # Commenter information
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    guest_name = models.CharField(max_length=100, blank=True)
    guest_email = models.EmailField(blank=True)
    guest_website = models.URLField(blank=True)
    
    # Comment content
    content = models.TextField()
    
    # Moderation
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    moderated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderated_comments')
    moderated_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Engagement
    like_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        commenter = self.user.username if self.user else self.guest_name
        return f"Comment by {commenter} on {self.post.title}"


class FAQCategory(models.Model):
    """FAQ categories"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    
    # Display settings
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = "FAQ Categories"
    
    def __str__(self):
        return self.name


class FAQ(models.Model):
    """Frequently Asked Questions"""
    category = models.ForeignKey(FAQCategory, on_delete=models.CASCADE, related_name='faqs')
    
    # Question and answer
    question = models.CharField(max_length=300)
    answer = models.TextField()
    
    # Additional information
    tags = models.JSONField(default=list, help_text="List of tags for better searchability")
    related_products = models.JSONField(default=list, help_text="List of related product IDs")
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    helpful_votes = models.PositiveIntegerField(default=0)
    not_helpful_votes = models.PositiveIntegerField(default=0)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    
    # Authoring
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'sort_order', 'question']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['is_featured', 'sort_order']),
        ]
    
    def helpfulness_ratio(self):
        total_votes = self.helpful_votes + self.not_helpful_votes
        if total_votes > 0:
            return (self.helpful_votes / total_votes) * 100
        return 0
    
    def __str__(self):
        return self.question


class PageTemplate(models.Model):
    """Page builder templates"""
    TEMPLATE_TYPE_CHOICES = [
        ('LANDING', 'Landing Page'),
        ('PRODUCT', 'Product Page'),
        ('CATEGORY', 'Category Page'),
        ('BLOG', 'Blog Page'),
        ('CONTACT', 'Contact Page'),
        ('ABOUT', 'About Page'),
        ('CUSTOM', 'Custom Page'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    
    # Template structure
    layout_config = models.JSONField(default=dict, help_text="Page layout configuration")
    components = models.JSONField(default=list, help_text="List of page components")
    
    # Styling
    css_styles = models.TextField(blank=True, help_text="Custom CSS styles")
    theme_settings = models.JSONField(default=dict, help_text="Theme configuration")
    
    # Preview
    preview_image = models.ImageField(upload_to='page_templates/', null=True, blank=True)
    
    # Usage
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    usage_count = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['template_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class CustomPage(models.Model):
    """Custom pages built with page builder"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    
    # Template and content
    template = models.ForeignKey(PageTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    content_blocks = models.JSONField(default=list, help_text="Page content blocks")
    
    # SEO
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    meta_keywords = models.TextField(blank=True)
    
    # Publishing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    
    # Settings
    require_login = models.BooleanField(default=False)
    allowed_roles = models.JSONField(default=list, help_text="List of role IDs that can access this page")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def is_published(self):
        return self.status == 'PUBLISHED' and (not self.published_at or self.published_at <= timezone.now())
    
    def __str__(self):
        return self.title


class ContentEmailTemplate(models.Model):
    """Email template management for content system"""
    TEMPLATE_TYPE_CHOICES = [
        ('ORDER_CONFIRMATION', 'Order Confirmation'),
        ('SHIPPING_UPDATE', 'Shipping Update'),
        ('DELIVERY_NOTIFICATION', 'Delivery Notification'),
        ('WELCOME_EMAIL', 'Welcome Email'),
        ('PASSWORD_RESET', 'Password Reset'),
        ('ABANDONED_CART', 'Abandoned Cart'),
        ('PROMOTIONAL', 'Promotional Email'),
        ('NEWSLETTER', 'Newsletter'),
        ('BIRTHDAY_WISHES', 'Birthday Wishes'),
        ('REVIEW_REQUEST', 'Review Request'),
        ('RESTOCK_NOTIFICATION', 'Restock Notification'),
        ('CUSTOM', 'Custom Template'),
    ]
    
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Email content
    subject = models.CharField(max_length=200)
    html_content = models.TextField(help_text="HTML email template")
    text_content = models.TextField(blank=True, help_text="Plain text version")
    
    # Template variables
    available_variables = models.JSONField(default=list, help_text="List of available template variables")
    
    # Design settings
    header_image = models.ImageField(upload_to='email_templates/', null=True, blank=True)
    footer_text = models.TextField(blank=True)
    primary_color = models.CharField(max_length=7, default='#007bff')
    secondary_color = models.CharField(max_length=7, default='#6c757d')
    
    # Usage settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    # Analytics
    sent_count = models.PositiveIntegerField(default=0)
    open_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['template_type', 'name']
    
    def open_rate(self):
        if self.sent_count > 0:
            return (self.open_count / self.sent_count) * 100
        return 0
    
    def click_rate(self):
        if self.sent_count > 0:
            return (self.click_count / self.sent_count) * 100
        return 0
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class WhatsAppTemplate(models.Model):
    """WhatsApp message templates"""
    TEMPLATE_TYPE_CHOICES = [
        ('ORDER_UPDATE', 'Order Update'),
        ('SHIPPING_UPDATE', 'Shipping Update'),
        ('DELIVERY_NOTIFICATION', 'Delivery Notification'),
        ('PAYMENT_REMINDER', 'Payment Reminder'),
        ('PROMOTIONAL', 'Promotional Message'),
        ('WELCOME', 'Welcome Message'),
        ('SUPPORT', 'Customer Support'),
        ('FEEDBACK_REQUEST', 'Feedback Request'),
        ('CUSTOM', 'Custom Template'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending WhatsApp Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Template content
    message_text = models.TextField(help_text="WhatsApp message template")
    
    # Media support
    header_type = models.CharField(max_length=20, choices=[
        ('NONE', 'No Header'),
        ('TEXT', 'Text Header'),
        ('IMAGE', 'Image Header'),
        ('VIDEO', 'Video Header'),
        ('DOCUMENT', 'Document Header'),
    ], default='NONE')
    header_text = models.CharField(max_length=60, blank=True)
    header_media = models.FileField(upload_to='whatsapp_media/', null=True, blank=True)
    
    # Footer
    footer_text = models.CharField(max_length=60, blank=True)
    
    # Buttons
    buttons = models.JSONField(default=list, help_text="List of action buttons")
    
    # Template variables
    variables = models.JSONField(default=list, help_text="List of template variables")
    
    # WhatsApp Business API
    whatsapp_template_id = models.CharField(max_length=100, blank=True)
    language_code = models.CharField(max_length=10, default='en')
    
    # Usage tracking
    sent_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    read_count = models.PositiveIntegerField(default=0)
    
    # Settings
    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['template_type', 'name']
    
    def delivery_rate(self):
        if self.sent_count > 0:
            return (self.delivered_count / self.sent_count) * 100
        return 0
    
    def read_rate(self):
        if self.delivered_count > 0:
            return (self.read_count / self.delivered_count) * 100
        return 0
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class ContentBlock(models.Model):
    """Reusable content blocks"""
    BLOCK_TYPE_CHOICES = [
        ('TEXT', 'Text Block'),
        ('HTML', 'HTML Block'),
        ('IMAGE', 'Image Block'),
        ('VIDEO', 'Video Block'),
        ('PRODUCT_GRID', 'Product Grid'),
        ('BANNER', 'Banner'),
        ('TESTIMONIAL', 'Testimonial'),
        ('FAQ', 'FAQ Block'),
        ('CONTACT_FORM', 'Contact Form'),
        ('NEWSLETTER_SIGNUP', 'Newsletter Signup'),
    ]
    
    name = models.CharField(max_length=100)
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Content
    content = models.TextField()
    settings = models.JSONField(default=dict, help_text="Block-specific settings")
    
    # Styling
    css_classes = models.CharField(max_length=200, blank=True)
    inline_styles = models.TextField(blank=True)
    
    # Usage
    is_active = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['block_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_block_type_display()})"