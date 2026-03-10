"""
Advanced Analytics Models - Added without modifying existing code
Features: Sales Comparison, CLV, Abandoned Cart, Traffic Analytics, Conversion Funnel
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class SalesComparison(models.Model):
    """Month-over-month, Year-over-year sales comparison"""
    COMPARISON_TYPE_CHOICES = [
        ('MOM', 'Month over Month'),
        ('YOY', 'Year over Year'),
        ('WOW', 'Week over Week'),
        ('DOD', 'Day over Day'),
    ]
    
    comparison_type = models.CharField(max_length=10, choices=COMPARISON_TYPE_CHOICES)
    current_period_start = models.DateField()
    current_period_end = models.DateField()
    previous_period_start = models.DateField()
    previous_period_end = models.DateField()
    
    current_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    previous_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    growth_percentage = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    current_orders = models.PositiveIntegerField(default=0)
    previous_orders = models.PositiveIntegerField(default=0)
    order_growth_percentage = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-generated_at']
        unique_together = ['comparison_type', 'current_period_start', 'current_period_end']
    
    def __str__(self):
        return f"{self.get_comparison_type_display()} - {self.current_period_start} to {self.current_period_end}"


class ProductPerformanceMatrix(models.Model):
    """Product performance with profit margin analysis"""
    product_id = models.PositiveIntegerField(db_index=True)
    product_name = models.CharField(max_length=255)
    
    # Sales metrics
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    total_quantity_sold = models.PositiveIntegerField(default=0)
    
    # Profit metrics
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    profit_margin_percentage = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Performance metrics
    conversion_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    return_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    # Time period
    period_start = models.DateField()
    period_end = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-total_profit']
        indexes = [
            models.Index(fields=['product_id', '-generated_at']),
            models.Index(fields=['-total_profit']),
        ]
    
    def __str__(self):
        return f"{self.product_name} - Profit: ₹{self.total_profit}"


class CustomerLifetimeValue(models.Model):
    """Customer Lifetime Value calculation"""
    customer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='clv_data')
    
    # Basic metrics
    first_order_date = models.DateField(null=True, blank=True)
    last_order_date = models.DateField(null=True, blank=True)
    total_orders = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # CLV calculations
    average_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    purchase_frequency = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    customer_lifespan_days = models.PositiveIntegerField(default=0)
    predicted_clv = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Segmentation
    CLV_SEGMENT_CHOICES = [
        ('HIGH', 'High Value'),
        ('MEDIUM', 'Medium Value'),
        ('LOW', 'Low Value'),
        ('AT_RISK', 'At Risk'),
        ('NEW', 'New Customer'),
    ]
    clv_segment = models.CharField(max_length=20, choices=CLV_SEGMENT_CHOICES, default='NEW')
    
    # Engagement metrics
    days_since_last_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    churn_probability = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-predicted_clv']
    
    def __str__(self):
        return f"{self.customer.username} - CLV: ₹{self.predicted_clv}"


class AbandonedCart(models.Model):
    """Abandoned cart tracking for recovery campaigns"""
    STATUS_CHOICES = [
        ('ABANDONED', 'Abandoned'),
        ('RECOVERED', 'Recovered'),
        ('EXPIRED', 'Expired'),
    ]
    
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='abandoned_carts')
    cart_items = models.JSONField(default=list, help_text="List of cart items with product details")
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    abandoned_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ABANDONED')
    
    # Recovery tracking
    recovery_emails_sent = models.PositiveIntegerField(default=0)
    last_email_sent = models.DateTimeField(null=True, blank=True)
    recovered_order_id = models.PositiveIntegerField(null=True, blank=True)
    recovered_at = models.DateTimeField(null=True, blank=True)
    
    # Analytics
    session_id = models.CharField(max_length=100, blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-abandoned_at']
        indexes = [
            models.Index(fields=['customer', '-abandoned_at']),
            models.Index(fields=['status', '-abandoned_at']),
        ]
    
    def __str__(self):
        return f"{self.customer.username} - ₹{self.total_value} ({self.status})"


class TrafficSource(models.Model):
    """Traffic source analytics"""
    SOURCE_TYPE_CHOICES = [
        ('ORGANIC', 'Organic Search'),
        ('PAID', 'Paid Advertising'),
        ('SOCIAL', 'Social Media'),
        ('EMAIL', 'Email Marketing'),
        ('DIRECT', 'Direct Traffic'),
        ('REFERRAL', 'Referral'),
        ('AFFILIATE', 'Affiliate'),
    ]
    
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    source_name = models.CharField(max_length=100, help_text="e.g., Google, Facebook, Instagram")
    campaign_name = models.CharField(max_length=100, blank=True)
    
    # Daily metrics
    date = models.DateField(db_index=True)
    visitors = models.PositiveIntegerField(default=0)
    sessions = models.PositiveIntegerField(default=0)
    page_views = models.PositiveIntegerField(default=0)
    bounce_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Conversion metrics
    conversions = models.PositiveIntegerField(default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    roas = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Return on Ad Spend")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['source_type', 'source_name', 'date']
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['source_type', '-date']),
        ]
    
    def __str__(self):
        return f"{self.source_name} ({self.get_source_type_display()}) - {self.date}"


class ConversionFunnel(models.Model):
    """Conversion funnel visualization data"""
    FUNNEL_STEP_CHOICES = [
        ('VISIT', 'Website Visit'),
        ('PRODUCT_VIEW', 'Product View'),
        ('ADD_TO_CART', 'Add to Cart'),
        ('CHECKOUT_START', 'Checkout Started'),
        ('PAYMENT', 'Payment Initiated'),
        ('ORDER_COMPLETE', 'Order Completed'),
    ]
    
    date = models.DateField(db_index=True)
    funnel_step = models.CharField(max_length=20, choices=FUNNEL_STEP_CHOICES)
    count = models.PositiveIntegerField(default=0)
    
    # Conversion rates
    conversion_rate_from_previous = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    conversion_rate_from_start = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Segmentation
    traffic_source = models.CharField(max_length=50, blank=True)
    device_type = models.CharField(max_length=20, blank=True, help_text="desktop, mobile, tablet")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date', 'funnel_step']
        unique_together = ['date', 'funnel_step', 'traffic_source', 'device_type']
        indexes = [
            models.Index(fields=['date', 'funnel_step']),
        ]
    
    def __str__(self):
        return f"{self.get_funnel_step_display()} - {self.date} ({self.count})"


class ScheduledReport(models.Model):
    """Scheduled email reports configuration"""
    REPORT_TYPE_CHOICES = [
        ('DAILY_SALES', 'Daily Sales Report'),
        ('WEEKLY_SUMMARY', 'Weekly Summary'),
        ('MONTHLY_ANALYTICS', 'Monthly Analytics'),
        ('PRODUCT_PERFORMANCE', 'Product Performance'),
        ('CUSTOMER_INSIGHTS', 'Customer Insights'),
        ('INVENTORY_STATUS', 'Inventory Status'),
    ]
    
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
    ]
    
    name = models.CharField(max_length=100)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    
    # Recipients
    email_recipients = models.JSONField(default=list, help_text="List of email addresses")
    
    # Schedule settings
    send_time = models.TimeField(help_text="Time to send report")
    send_day = models.PositiveIntegerField(null=True, blank=True, help_text="Day of week (1=Monday) or month")
    
    # Report settings
    include_charts = models.BooleanField(default=True)
    export_format = models.CharField(max_length=10, choices=[('PDF', 'PDF'), ('EXCEL', 'Excel')], default='PDF')
    
    # Status
    is_active = models.BooleanField(default=True)
    last_sent = models.DateTimeField(null=True, blank=True)
    next_send = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"