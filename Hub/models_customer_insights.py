"""
Customer Insights & CRM Models - Phase 5
Features: Customer Segmentation, Purchase History, RFM Analysis, Support Tickets, Feedback Surveys
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class CustomerSegmentationRule(models.Model):
    """Advanced customer segmentation with custom rules"""
    SEGMENT_TYPE_CHOICES = [
        ('VIP', 'VIP Customers'),
        ('REGULAR', 'Regular Customers'),
        ('NEW', 'New Customers'),
        ('AT_RISK', 'At Risk Customers'),
        ('HIGH_VALUE', 'High Value'),
        ('FREQUENT_BUYERS', 'Frequent Buyers'),
        ('INACTIVE', 'Inactive Customers'),
        ('SEASONAL', 'Seasonal Buyers'),
        ('PRICE_SENSITIVE', 'Price Sensitive'),
        ('BRAND_LOYAL', 'Brand Loyal'),
        ('CUSTOM', 'Custom Segment'),
    ]
    
    name = models.CharField(max_length=100)
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Segmentation criteria
    min_orders = models.PositiveIntegerField(null=True, blank=True)
    max_orders = models.PositiveIntegerField(null=True, blank=True)
    min_total_spent = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_total_spent = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    min_avg_order_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_avg_order_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Time-based criteria
    days_since_last_order_min = models.PositiveIntegerField(null=True, blank=True)
    days_since_last_order_max = models.PositiveIntegerField(null=True, blank=True)
    days_since_signup_min = models.PositiveIntegerField(null=True, blank=True)
    days_since_signup_max = models.PositiveIntegerField(null=True, blank=True)
    
    # Advanced criteria
    preferred_categories = models.JSONField(default=list, help_text="List of preferred product categories")
    purchase_frequency_days = models.PositiveIntegerField(null=True, blank=True, help_text="Average days between purchases")
    return_rate_threshold = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Segment benefits
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    free_shipping = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    early_access = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    auto_assign = models.BooleanField(default=True, help_text="Automatically assign customers to this segment")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_segment_type_display()})"


class CustomerProfile(models.Model):
    """Enhanced customer profile with insights"""
    customer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    
    # Basic information
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other'),
    ], blank=True)
    
    # Preferences
    preferred_categories = models.JSONField(default=list, help_text="Customer's preferred product categories")
    preferred_brands = models.JSONField(default=list, help_text="Customer's preferred brands")
    price_range_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_range_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Communication preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    whatsapp_notifications = models.BooleanField(default=False)
    marketing_emails = models.BooleanField(default=True)
    
    # Customer insights
    customer_segment = models.ForeignKey(CustomerSegmentationRule, on_delete=models.SET_NULL, null=True, blank=True)
    customer_tags = models.JSONField(default=list, help_text="Custom tags for this customer")
    notes = models.TextField(blank=True, help_text="Internal notes about customer")
    
    # Behavioral data
    avg_session_duration = models.PositiveIntegerField(default=0, help_text="Average session duration in seconds")
    pages_per_session = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    bounce_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Social media
    instagram_handle = models.CharField(max_length=100, blank=True)
    facebook_profile = models.URLField(blank=True)
    referral_source = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.username} Profile"


class PurchaseHistoryTimeline(models.Model):
    """Detailed purchase history timeline"""
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchase_timeline')
    order_id = models.PositiveIntegerField(db_index=True)
    order_number = models.CharField(max_length=50)
    
    # Order details
    order_date = models.DateTimeField()
    order_value = models.DecimalField(max_digits=10, decimal_places=2)
    items_count = models.PositiveIntegerField()
    
    # Product information
    products_purchased = models.JSONField(default=list, help_text="List of products with details")
    categories_purchased = models.JSONField(default=list, help_text="Categories of purchased products")
    
    # Payment and shipping
    payment_method = models.CharField(max_length=50, blank=True)
    shipping_method = models.CharField(max_length=50, blank=True)
    delivery_time_days = models.PositiveIntegerField(null=True, blank=True)
    
    # Customer behavior
    time_to_purchase_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Hours from first visit to purchase")
    cart_abandonment_count = models.PositiveIntegerField(default=0)
    
    # Satisfaction
    order_rating = models.PositiveIntegerField(null=True, blank=True, help_text="Customer rating for this order (1-5)")
    has_review = models.BooleanField(default=False)
    has_return = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-order_date']
        indexes = [
            models.Index(fields=['customer', '-order_date']),
            models.Index(fields=['order_id']),
        ]
    
    def __str__(self):
        return f"{self.customer.username} - Order {self.order_number}"


class RFMAnalysis(models.Model):
    """RFM (Recency, Frequency, Monetary) Analysis"""
    customer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rfm_analysis')
    
    # Recency (days since last purchase)
    recency_days = models.PositiveIntegerField(default=0)
    recency_score = models.PositiveIntegerField(default=1, help_text="1-5 scale (5 = most recent)")
    
    # Frequency (number of purchases)
    frequency_count = models.PositiveIntegerField(default=0)
    frequency_score = models.PositiveIntegerField(default=1, help_text="1-5 scale (5 = most frequent)")
    
    # Monetary (total amount spent)
    monetary_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monetary_score = models.PositiveIntegerField(default=1, help_text="1-5 scale (5 = highest value)")
    
    # Combined RFM score
    rfm_score = models.CharField(max_length=3, help_text="Combined RFM score (e.g., 555)")
    rfm_segment = models.CharField(max_length=20, choices=[
        ('CHAMPIONS', 'Champions'),
        ('LOYAL_CUSTOMERS', 'Loyal Customers'),
        ('POTENTIAL_LOYALISTS', 'Potential Loyalists'),
        ('NEW_CUSTOMERS', 'New Customers'),
        ('PROMISING', 'Promising'),
        ('NEED_ATTENTION', 'Need Attention'),
        ('ABOUT_TO_SLEEP', 'About to Sleep'),
        ('AT_RISK', 'At Risk'),
        ('CANNOT_LOSE', 'Cannot Lose Them'),
        ('HIBERNATING', 'Hibernating'),
        ('LOST', 'Lost'),
    ], default='NEW_CUSTOMERS')
    
    # Analysis period
    analysis_start_date = models.DateField()
    analysis_end_date = models.DateField()
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-monetary_value']
    
    def __str__(self):
        return f"{self.customer.username} - RFM: {self.rfm_score} ({self.rfm_segment})"


class CustomerSupportTicket(models.Model):
    """Customer support ticket system"""
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('WAITING_CUSTOMER', 'Waiting for Customer'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    CATEGORY_CHOICES = [
        ('ORDER_ISSUE', 'Order Issue'),
        ('PAYMENT_ISSUE', 'Payment Issue'),
        ('PRODUCT_INQUIRY', 'Product Inquiry'),
        ('SHIPPING_ISSUE', 'Shipping Issue'),
        ('RETURN_REFUND', 'Return/Refund'),
        ('TECHNICAL_ISSUE', 'Technical Issue'),
        ('ACCOUNT_ISSUE', 'Account Issue'),
        ('COMPLAINT', 'Complaint'),
        ('SUGGESTION', 'Suggestion'),
        ('OTHER', 'Other'),
    ]
    
    ticket_number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    
    # Ticket details
    subject = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    
    # Related information
    related_order_id = models.PositiveIntegerField(null=True, blank=True)
    related_product_id = models.PositiveIntegerField(null=True, blank=True)
    
    # Assignment
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # SLA tracking
    first_response_time = models.DurationField(null=True, blank=True)
    resolution_time = models.DurationField(null=True, blank=True)
    
    # Customer satisfaction
    satisfaction_rating = models.PositiveIntegerField(null=True, blank=True, help_text="1-5 rating")
    satisfaction_feedback = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"Ticket {self.ticket_number} - {self.subject}"


class TicketMessage(models.Model):
    """Messages within support tickets"""
    ticket = models.ForeignKey(CustomerSupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Message content
    message = models.TextField()
    is_internal = models.BooleanField(default=False, help_text="Internal note not visible to customer")
    
    # Attachments
    attachment = models.FileField(upload_to='ticket_attachments/', null=True, blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    read_by_customer = models.BooleanField(default=False)
    read_by_staff = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message in {self.ticket.ticket_number} by {self.sender.username}"


class CustomerFeedbackSurvey(models.Model):
    """Customer feedback surveys"""
    SURVEY_TYPE_CHOICES = [
        ('POST_PURCHASE', 'Post Purchase'),
        ('PRODUCT_FEEDBACK', 'Product Feedback'),
        ('SERVICE_FEEDBACK', 'Service Feedback'),
        ('WEBSITE_FEEDBACK', 'Website Feedback'),
        ('NPS', 'Net Promoter Score'),
        ('GENERAL', 'General Feedback'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    survey_type = models.CharField(max_length=20, choices=SURVEY_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Survey configuration
    questions = models.JSONField(default=list, help_text="List of survey questions with types")
    
    # Targeting
    target_all_customers = models.BooleanField(default=False)
    target_segments = models.JSONField(default=list, help_text="List of customer segment IDs")
    target_after_order = models.BooleanField(default=False)
    target_after_days = models.PositiveIntegerField(default=7, help_text="Days after order to send survey")
    
    # Timing
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    total_sent = models.PositiveIntegerField(default=0)
    total_responses = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def response_rate(self):
        if self.total_sent > 0:
            return (self.total_responses / self.total_sent) * 100
        return 0
    
    def __str__(self):
        return f"{self.title} ({self.get_survey_type_display()})"


class SurveyResponse(models.Model):
    """Individual survey responses"""
    survey = models.ForeignKey(CustomerFeedbackSurvey, on_delete=models.CASCADE, related_name='responses')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='survey_responses')
    
    # Response data
    responses = models.JSONField(default=dict, help_text="Question ID to answer mapping")
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    completion_time_seconds = models.PositiveIntegerField(null=True, blank=True)
    
    # Status
    is_complete = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-submitted_at']
        unique_together = ['survey', 'customer']
    
    def __str__(self):
        return f"{self.customer.username} - {self.survey.title}"


class BirthdayAnniversaryReminder(models.Model):
    """Birthday and anniversary reminders"""
    REMINDER_TYPE_CHOICES = [
        ('BIRTHDAY', 'Birthday'),
        ('ANNIVERSARY', 'Anniversary'),
        ('FIRST_ORDER', 'First Order Anniversary'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
    ]
    
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reminders')
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPE_CHOICES)
    
    # Reminder details
    reminder_date = models.DateField()
    message_template = models.TextField(blank=True)
    discount_coupon_code = models.CharField(max_length=50, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Delivery channels
    send_email = models.BooleanField(default=True)
    send_sms = models.BooleanField(default=False)
    send_whatsapp = models.BooleanField(default=False)
    
    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    email_opened = models.BooleanField(default=False)
    coupon_used = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['reminder_date']
        indexes = [
            models.Index(fields=['reminder_date', 'status']),
            models.Index(fields=['customer', 'reminder_type']),
        ]
    
    def __str__(self):
        return f"{self.customer.username} - {self.get_reminder_type_display()} ({self.reminder_date})"