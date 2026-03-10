"""
New Feature Models - Added without modifying existing code
Features: Bulk Operations, Activity Logs, Coupons, Low Stock Alerts, Role Management
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class ActivityLog(models.Model):
    """Track all admin actions for audit trail"""
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('VIEW', 'Viewed'),
        ('EXPORT', 'Exported'),
        ('IMPORT', 'Imported'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
    ]
    
    admin_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='activity_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, help_text="Model that was modified (e.g., Product, Order)")
    object_id = models.PositiveIntegerField(null=True, blank=True, help_text="ID of the object modified")
    object_name = models.CharField(max_length=255, blank=True, help_text="Name/description of the object")
    changes = models.JSONField(default=dict, blank=True, help_text="JSON of what changed (old vs new)")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['admin_user', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.admin_user.username} - {self.action} - {self.model_name} ({self.timestamp})"


class DiscountCoupon(models.Model):
    """Discount coupon system for marketing"""
    DISCOUNT_TYPE_CHOICES = [
        ('PERCENTAGE', 'Percentage Discount'),
        ('FIXED', 'Fixed Amount Discount'),
        ('FREE_SHIPPING', 'Free Shipping'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('EXPIRED', 'Expired'),
    ]
    
    code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Percentage or fixed amount")
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Max discount cap for percentage discounts")
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Minimum purchase required")
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Total uses allowed (null = unlimited)")
    max_uses_per_customer = models.PositiveIntegerField(default=1, help_text="Uses per customer")
    current_uses = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    applicable_categories = models.CharField(max_length=500, blank=True, help_text="Comma-separated category names (blank = all)")
    applicable_products = models.CharField(max_length=500, blank=True, help_text="Comma-separated product IDs (blank = all)")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_coupons')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status', 'valid_until']),
        ]
    
    def is_valid(self):
        """Check if coupon is currently valid"""
        now = timezone.now()
        return (self.status == 'ACTIVE' and 
                self.valid_from <= now <= self.valid_until and
                (self.max_uses is None or self.current_uses < self.max_uses))
    
    def can_use_for_customer(self, customer_uses):
        """Check if customer can use this coupon"""
        return customer_uses < self.max_uses_per_customer
    
    def calculate_discount(self, purchase_amount):
        """Calculate discount amount"""
        if not self.is_valid():
            return Decimal('0')
        
        if self.discount_type == 'PERCENTAGE':
            discount = (purchase_amount * self.discount_value) / Decimal('100')
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
            return discount
        elif self.discount_type == 'FIXED':
            return min(self.discount_value, purchase_amount)
        elif self.discount_type == 'FREE_SHIPPING':
            return Decimal('0')  # Handled separately
        
        return Decimal('0')
    
    def __str__(self):
        return f"{self.code} - {self.get_discount_type_display()}"


class LowStockAlert(models.Model):
    """Alert system for low stock products"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('ACKNOWLEDGED', 'Acknowledged'),
    ]
    
    product_id = models.PositiveIntegerField(db_index=True)
    product_name = models.CharField(max_length=255)
    current_stock = models.PositiveIntegerField()
    threshold_stock = models.PositiveIntegerField(help_text="Stock level that triggers alert")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    alert_sent_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product_id', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"Low Stock Alert - {self.product_name} ({self.current_stock} units)"


class BulkProductImport(models.Model):
    """Track bulk product imports"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    file_name = models.CharField(max_length=255)
    csv_file = models.FileField(upload_to='bulk_imports/')
    total_rows = models.PositiveIntegerField(default=0)
    successful_imports = models.PositiveIntegerField(default=0)
    failed_imports = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_log = models.JSONField(default=list, blank=True, help_text="List of errors encountered")
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Bulk Import - {self.file_name} ({self.status})"


class AdminRole(models.Model):
    """Role-based access control for admin users"""
    PERMISSION_CHOICES = [
        ('view_dashboard', 'View Dashboard'),
        ('manage_products', 'Manage Products'),
        ('manage_orders', 'Manage Orders'),
        ('manage_customers', 'Manage Customers'),
        ('manage_coupons', 'Manage Coupons'),
        ('view_reports', 'View Reports'),
        ('manage_users', 'Manage Users'),
        ('manage_settings', 'Manage Settings'),
        ('view_activity_logs', 'View Activity Logs'),
        ('bulk_operations', 'Bulk Operations'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list, help_text="List of permission codes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def has_permission(self, permission_code):
        """Check if role has specific permission"""
        return permission_code in self.permissions


class AdminUserRole(models.Model):
    """Assign roles to admin users"""
    admin_user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_role')
    role = models.ForeignKey(AdminRole, on_delete=models.SET_NULL, null=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_roles')
    
    class Meta:
        verbose_name = 'Admin User Role'
        verbose_name_plural = 'Admin User Roles'
    
    def __str__(self):
        return f"{self.admin_user.username} - {self.role.name if self.role else 'No Role'}"


class SalesReport(models.Model):
    """Pre-generated sales reports for quick access"""
    REPORT_TYPE_CHOICES = [
        ('DAILY', 'Daily Report'),
        ('WEEKLY', 'Weekly Report'),
        ('MONTHLY', 'Monthly Report'),
        ('YEARLY', 'Yearly Report'),
        ('CUSTOM', 'Custom Report'),
    ]
    
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    report_date = models.DateField(db_index=True)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    total_customers = models.PositiveIntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    top_products = models.JSONField(default=list, help_text="Top 5 products by sales")
    top_categories = models.JSONField(default=list, help_text="Top 5 categories by sales")
    payment_methods_breakdown = models.JSONField(default=dict, help_text="Sales by payment method")
    report_data = models.JSONField(default=dict, help_text="Complete report data")
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-report_date']
        unique_together = ['report_type', 'report_date']
        indexes = [
            models.Index(fields=['-report_date']),
            models.Index(fields=['report_type', '-report_date']),
        ]
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.report_date}"


class EmailTemplate(models.Model):
    """Email templates for automated emails"""
    TEMPLATE_TYPE_CHOICES = [
        ('ORDER_CONFIRMATION', 'Order Confirmation'),
        ('SHIPPING_UPDATE', 'Shipping Update'),
        ('DELIVERY_CONFIRMATION', 'Delivery Confirmation'),
        ('LOW_STOCK_ALERT', 'Low Stock Alert'),
        ('ABANDONED_CART', 'Abandoned Cart'),
        ('NEWSLETTER', 'Newsletter'),
        ('CUSTOM', 'Custom'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPE_CHOICES)
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="Use {{variable}} for dynamic content")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
