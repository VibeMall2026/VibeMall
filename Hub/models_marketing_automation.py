"""
Marketing Automation Models - Added without modifying existing code
Features: Flash Sales, Email Automation, Customer Segmentation, WhatsApp, SMS, Push Notifications
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class FlashSale(models.Model):
    """Flash sale scheduler with countdown"""
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('ACTIVE', 'Active'),
        ('ENDED', 'Ended'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Timing
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # Discount settings
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Product selection
    applicable_products = models.JSONField(default=list, help_text="List of product IDs")
    applicable_categories = models.JSONField(default=list, help_text="List of category names")
    
    # Limits
    max_quantity_per_customer = models.PositiveIntegerField(default=1)
    total_quantity_limit = models.PositiveIntegerField(null=True, blank=True)
    current_quantity_sold = models.PositiveIntegerField(default=0)
    
    # Display settings
    banner_image = models.ImageField(upload_to='flash_sales/', null=True, blank=True)
    banner_text = models.CharField(max_length=200, blank=True)
    show_countdown = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_time']
    
    def is_active(self):
        now = timezone.now()
        return self.status == 'ACTIVE' and self.start_time <= now <= self.end_time
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class EmailCampaign(models.Model):
    """Email marketing campaigns"""
    CAMPAIGN_TYPE_CHOICES = [
        ('ABANDONED_CART', 'Abandoned Cart Recovery'),
        ('WELCOME', 'Welcome Series'),
        ('PROMOTIONAL', 'Promotional'),
        ('NEWSLETTER', 'Newsletter'),
        ('BIRTHDAY', 'Birthday Wishes'),
        ('REACTIVATION', 'Customer Reactivation'),
        ('PRODUCT_RECOMMENDATION', 'Product Recommendations'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('PAUSED', 'Paused'),
    ]
    
    name = models.CharField(max_length=100)
    campaign_type = models.CharField(max_length=30, choices=CAMPAIGN_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Email content
    subject = models.CharField(max_length=200)
    email_template = models.TextField(help_text="HTML email template")
    
    # Targeting
    target_segment = models.CharField(max_length=50, blank=True, help_text="Customer segment to target")
    target_customers = models.JSONField(default=list, help_text="Specific customer IDs")
    
    # Scheduling
    send_immediately = models.BooleanField(default=False)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    
    # Automation triggers
    trigger_event = models.CharField(max_length=50, blank=True, help_text="Event that triggers this campaign")
    trigger_delay_hours = models.PositiveIntegerField(default=0, help_text="Hours to wait after trigger")
    
    # Tracking
    total_recipients = models.PositiveIntegerField(default=0)
    emails_sent = models.PositiveIntegerField(default=0)
    emails_delivered = models.PositiveIntegerField(default=0)
    emails_opened = models.PositiveIntegerField(default=0)
    emails_clicked = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def open_rate(self):
        if self.emails_delivered > 0:
            return (self.emails_opened / self.emails_delivered) * 100
        return 0
    
    def click_rate(self):
        if self.emails_delivered > 0:
            return (self.emails_clicked / self.emails_delivered) * 100
        return 0
    
    def __str__(self):
        return f"{self.name} ({self.get_campaign_type_display()})"


class CustomerSegment(models.Model):
    """Customer segmentation for targeted campaigns"""
    SEGMENT_TYPE_CHOICES = [
        ('VIP', 'VIP Customers'),
        ('REGULAR', 'Regular Customers'),
        ('NEW', 'New Customers'),
        ('AT_RISK', 'At Risk Customers'),
        ('HIGH_VALUE', 'High Value'),
        ('FREQUENT_BUYERS', 'Frequent Buyers'),
        ('INACTIVE', 'Inactive Customers'),
        ('CUSTOM', 'Custom Segment'),
    ]
    
    name = models.CharField(max_length=100)
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Segmentation criteria
    criteria = models.JSONField(default=dict, help_text="Segmentation rules and conditions")
    
    # Customer list (cached)
    customer_ids = models.JSONField(default=list, help_text="List of customer IDs in this segment")
    customer_count = models.PositiveIntegerField(default=0)
    
    # Auto-update settings
    auto_update = models.BooleanField(default=True, help_text="Automatically update segment based on criteria")
    last_updated = models.DateTimeField(auto_now=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.customer_count} customers)"


class WhatsAppCampaign(models.Model):
    """WhatsApp broadcast campaigns"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
    ]
    
    name = models.CharField(max_length=100)
    message_template = models.TextField(help_text="WhatsApp message template")
    
    # Media
    media_type = models.CharField(max_length=20, choices=[
        ('TEXT', 'Text Only'),
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
        ('DOCUMENT', 'Document'),
    ], default='TEXT')
    media_file = models.FileField(upload_to='whatsapp_media/', null=True, blank=True)
    
    # Targeting
    target_segment = models.ForeignKey(CustomerSegment, on_delete=models.SET_NULL, null=True, blank=True)
    target_numbers = models.JSONField(default=list, help_text="List of phone numbers")
    
    # Scheduling
    send_immediately = models.BooleanField(default=False)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    total_recipients = models.PositiveIntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    messages_delivered = models.PositiveIntegerField(default=0)
    messages_read = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def delivery_rate(self):
        if self.messages_sent > 0:
            return (self.messages_delivered / self.messages_sent) * 100
        return 0
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class SMSCampaign(models.Model):
    """SMS marketing campaigns"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
    ]
    
    name = models.CharField(max_length=100)
    message_text = models.TextField(max_length=160, help_text="SMS message (max 160 characters)")
    
    # Targeting
    target_segment = models.ForeignKey(CustomerSegment, on_delete=models.SET_NULL, null=True, blank=True)
    target_numbers = models.JSONField(default=list, help_text="List of phone numbers")
    
    # Scheduling
    send_immediately = models.BooleanField(default=False)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    total_recipients = models.PositiveIntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    messages_delivered = models.PositiveIntegerField(default=0)
    
    # Cost tracking
    cost_per_sms = models.DecimalField(max_digits=6, decimal_places=4, default=0.50)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def delivery_rate(self):
        if self.messages_sent > 0:
            return (self.messages_delivered / self.messages_sent) * 100
        return 0
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class PushNotification(models.Model):
    """Push notification campaigns"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
    ]
    
    NOTIFICATION_TYPE_CHOICES = [
        ('PROMOTIONAL', 'Promotional'),
        ('ORDER_UPDATE', 'Order Update'),
        ('FLASH_SALE', 'Flash Sale'),
        ('NEW_PRODUCT', 'New Product'),
        ('ABANDONED_CART', 'Abandoned Cart'),
        ('GENERAL', 'General'),
    ]
    
    title = models.CharField(max_length=100)
    message = models.TextField(max_length=200)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    
    # Action settings
    action_url = models.URLField(blank=True, help_text="URL to open when notification is clicked")
    action_button_text = models.CharField(max_length=50, blank=True)
    
    # Media
    icon_image = models.ImageField(upload_to='push_notifications/', null=True, blank=True)
    banner_image = models.ImageField(upload_to='push_notifications/', null=True, blank=True)
    
    # Targeting
    target_all_users = models.BooleanField(default=False)
    target_segment = models.ForeignKey(CustomerSegment, on_delete=models.SET_NULL, null=True, blank=True)
    target_users = models.JSONField(default=list, help_text="List of user IDs")
    
    # Scheduling
    send_immediately = models.BooleanField(default=False)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    total_recipients = models.PositiveIntegerField(default=0)
    notifications_sent = models.PositiveIntegerField(default=0)
    notifications_delivered = models.PositiveIntegerField(default=0)
    notifications_clicked = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def click_rate(self):
        if self.notifications_delivered > 0:
            return (self.notifications_clicked / self.notifications_delivered) * 100
        return 0
    
    def __str__(self):
        return f"{self.title} ({self.get_notification_type_display()})"


class LoyaltyProgram(models.Model):
    """Enhanced loyalty points and rewards program"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Point earning rules
    points_per_rupee = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    signup_bonus_points = models.PositiveIntegerField(default=100)
    referral_bonus_points = models.PositiveIntegerField(default=500)
    review_bonus_points = models.PositiveIntegerField(default=50)
    birthday_bonus_points = models.PositiveIntegerField(default=200)
    
    # Point redemption rules
    min_points_to_redeem = models.PositiveIntegerField(default=100)
    points_to_rupee_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=1, help_text="How many points = 1 rupee")
    max_redemption_percentage = models.PositiveIntegerField(default=50, help_text="Max % of order value that can be paid with points")
    
    # Program settings
    is_active = models.BooleanField(default=True)
    point_expiry_days = models.PositiveIntegerField(default=365, help_text="Days after which points expire")
    
    # Tier system
    enable_tiers = models.BooleanField(default=False)
    tier_thresholds = models.JSONField(default=dict, help_text="Tier thresholds and benefits")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class CustomerTier(models.Model):
    """Customer tier in loyalty program"""
    TIER_CHOICES = [
        ('BRONZE', 'Bronze'),
        ('SILVER', 'Silver'),
        ('GOLD', 'Gold'),
        ('PLATINUM', 'Platinum'),
        ('DIAMOND', 'Diamond'),
    ]
    
    customer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='loyalty_tier')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='BRONZE')
    
    # Tier metrics
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    tier_points = models.PositiveIntegerField(default=0)
    
    # Tier benefits
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    free_shipping = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    early_access = models.BooleanField(default=False)
    
    # Tier progression
    next_tier_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tier_achieved_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-total_spent']
    
    def __str__(self):
        return f"{self.customer.username} - {self.get_tier_display()}"


class AutomationRule(models.Model):
    """Marketing automation rules"""
    TRIGGER_CHOICES = [
        ('USER_SIGNUP', 'User Signup'),
        ('FIRST_ORDER', 'First Order'),
        ('ORDER_COMPLETED', 'Order Completed'),
        ('CART_ABANDONED', 'Cart Abandoned'),
        ('PRODUCT_VIEWED', 'Product Viewed'),
        ('BIRTHDAY', 'Customer Birthday'),
        ('INACTIVE_USER', 'User Inactive'),
        ('HIGH_VALUE_CUSTOMER', 'High Value Customer'),
    ]
    
    ACTION_CHOICES = [
        ('SEND_EMAIL', 'Send Email'),
        ('SEND_SMS', 'Send SMS'),
        ('SEND_WHATSAPP', 'Send WhatsApp'),
        ('SEND_PUSH', 'Send Push Notification'),
        ('ADD_TO_SEGMENT', 'Add to Segment'),
        ('ASSIGN_COUPON', 'Assign Coupon'),
        ('ADD_POINTS', 'Add Loyalty Points'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Trigger settings
    trigger_event = models.CharField(max_length=30, choices=TRIGGER_CHOICES)
    trigger_conditions = models.JSONField(default=dict, help_text="Additional conditions for trigger")
    
    # Action settings
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    action_config = models.JSONField(default=dict, help_text="Action configuration")
    
    # Timing
    delay_minutes = models.PositiveIntegerField(default=0, help_text="Minutes to wait before executing action")
    
    # Status
    is_active = models.BooleanField(default=True)
    execution_count = models.PositiveIntegerField(default=0)
    last_executed = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_trigger_event_display()} → {self.get_action_type_display()})"