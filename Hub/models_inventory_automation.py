"""
Inventory Automation Models - Added without modifying existing code
Features: Auto-reorder, Stock Aging, Expiry Tracking, Multi-warehouse, Forecasting
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class InventoryForecast(models.Model):
    """Demand forecasting and inventory planning"""
    product_id = models.PositiveIntegerField(db_index=True)
    product_name = models.CharField(max_length=255)
    
    # Historical data
    avg_daily_sales = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    avg_weekly_sales = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    avg_monthly_sales = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Seasonal factors
    seasonal_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    trend_factor = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    
    # Forecasts
    forecast_7_days = models.PositiveIntegerField(default=0)
    forecast_30_days = models.PositiveIntegerField(default=0)
    forecast_90_days = models.PositiveIntegerField(default=0)
    
    # Recommendations
    recommended_stock_level = models.PositiveIntegerField(default=0)
    reorder_point = models.PositiveIntegerField(default=0)
    economic_order_quantity = models.PositiveIntegerField(default=0)
    
    # Lead time
    supplier_lead_time_days = models.PositiveIntegerField(default=7)
    safety_stock_days = models.PositiveIntegerField(default=3)
    
    # Accuracy tracking
    forecast_accuracy = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    last_forecast_date = models.DateField()
    
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-avg_monthly_sales']
        indexes = [
            models.Index(fields=['product_id']),
            models.Index(fields=['-avg_monthly_sales']),
        ]
    
    def __str__(self):
        return f"{self.product_name} - Forecast: {self.forecast_30_days}/month"


class AutoReorderRule(models.Model):
    """Automatic reorder suggestions and rules"""
    product_id = models.PositiveIntegerField(db_index=True)
    product_name = models.CharField(max_length=255)
    
    # Reorder settings
    is_active = models.BooleanField(default=True)
    reorder_point = models.PositiveIntegerField(help_text="Stock level that triggers reorder")
    reorder_quantity = models.PositiveIntegerField(help_text="Quantity to reorder")
    max_stock_level = models.PositiveIntegerField(help_text="Maximum stock to maintain")
    
    # Supplier information
    supplier_name = models.CharField(max_length=100, blank=True)
    supplier_email = models.EmailField(blank=True)
    supplier_phone = models.CharField(max_length=20, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Lead time and safety stock
    lead_time_days = models.PositiveIntegerField(default=7)
    safety_stock_quantity = models.PositiveIntegerField(default=0)
    
    # Automation settings
    auto_generate_po = models.BooleanField(default=False, help_text="Automatically generate purchase order")
    auto_send_email = models.BooleanField(default=True, help_text="Send email notification when reorder needed")
    
    # Tracking
    last_reorder_date = models.DateField(null=True, blank=True)
    total_reorders = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['product_name']
        unique_together = ['product_id']
    
    def __str__(self):
        return f"{self.product_name} - Reorder at {self.reorder_point}"


class StockAgingReport(models.Model):
    """Stock aging analysis for slow-moving products"""
    AGING_CATEGORY_CHOICES = [
        ('FAST_MOVING', 'Fast Moving (0-30 days)'),
        ('MEDIUM_MOVING', 'Medium Moving (31-90 days)'),
        ('SLOW_MOVING', 'Slow Moving (91-180 days)'),
        ('DEAD_STOCK', 'Dead Stock (180+ days)'),
    ]
    
    product_id = models.PositiveIntegerField(db_index=True)
    product_name = models.CharField(max_length=255)
    
    # Stock information
    current_stock = models.PositiveIntegerField(default=0)
    stock_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Aging analysis
    days_in_stock = models.PositiveIntegerField(default=0)
    aging_category = models.CharField(max_length=20, choices=AGING_CATEGORY_CHOICES)
    last_sale_date = models.DateField(null=True, blank=True)
    
    # Sales velocity
    sales_last_30_days = models.PositiveIntegerField(default=0)
    sales_last_90_days = models.PositiveIntegerField(default=0)
    average_monthly_sales = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Recommendations
    recommended_action = models.CharField(max_length=50, choices=[
        ('MAINTAIN', 'Maintain Current Stock'),
        ('REDUCE_PRICE', 'Reduce Price'),
        ('PROMOTIONAL_SALE', 'Run Promotional Sale'),
        ('LIQUIDATE', 'Liquidate Stock'),
        ('RETURN_SUPPLIER', 'Return to Supplier'),
    ], default='MAINTAIN')
    
    # Financial impact
    carrying_cost_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    potential_loss = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    report_date = models.DateField(auto_now_add=True)
    
    class Meta:
        ordering = ['-days_in_stock']
        indexes = [
            models.Index(fields=['aging_category', '-stock_value']),
            models.Index(fields=['-days_in_stock']),
        ]
    
    def __str__(self):
        return f"{self.product_name} - {self.get_aging_category_display()}"


class ProductExpiryTracking(models.Model):
    """Product expiry date tracking for perishables"""
    product_id = models.PositiveIntegerField(db_index=True)
    product_name = models.CharField(max_length=255)
    batch_number = models.CharField(max_length=50)
    
    # Expiry information
    manufacturing_date = models.DateField()
    expiry_date = models.DateField(db_index=True)
    shelf_life_days = models.PositiveIntegerField()
    
    # Stock information
    quantity = models.PositiveIntegerField()
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    total_value = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status
    STATUS_CHOICES = [
        ('FRESH', 'Fresh'),
        ('NEAR_EXPIRY', 'Near Expiry'),
        ('EXPIRED', 'Expired'),
        ('SOLD', 'Sold'),
        ('DISPOSED', 'Disposed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='FRESH')
    
    # Alerts
    days_to_expiry = models.IntegerField(default=0)
    alert_sent = models.BooleanField(default=False)
    alert_sent_date = models.DateTimeField(null=True, blank=True)
    
    # Disposal tracking
    disposal_date = models.DateField(null=True, blank=True)
    disposal_reason = models.CharField(max_length=100, blank=True)
    disposal_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['expiry_date']
        indexes = [
            models.Index(fields=['expiry_date']),
            models.Index(fields=['status', 'expiry_date']),
        ]
    
    def update_status(self):
        """Update status based on expiry date"""
        today = timezone.now().date()
        self.days_to_expiry = (self.expiry_date - today).days
        
        if self.days_to_expiry < 0:
            self.status = 'EXPIRED'
        elif self.days_to_expiry <= 7:
            self.status = 'NEAR_EXPIRY'
        else:
            self.status = 'FRESH'
        
        self.save()
    
    def __str__(self):
        return f"{self.product_name} - Batch {self.batch_number} (Expires: {self.expiry_date})"


class Warehouse(models.Model):
    """Multi-warehouse management"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    
    # Location
    address = models.TextField()
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    pincode = models.CharField(max_length=10)
    
    # Contact information
    manager_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Warehouse settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    storage_capacity = models.PositiveIntegerField(help_text="Maximum storage capacity")
    current_utilization = models.PositiveIntegerField(default=0)
    
    # Operational settings
    working_hours_start = models.TimeField(default='09:00')
    working_hours_end = models.TimeField(default='18:00')
    working_days = models.JSONField(default=list, help_text="List of working days (0=Monday, 6=Sunday)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def utilization_percentage(self):
        if self.storage_capacity > 0:
            return (self.current_utilization / self.storage_capacity) * 100
        return 0
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class WarehouseStock(models.Model):
    """Stock levels per warehouse"""
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stock_items')
    product_id = models.PositiveIntegerField(db_index=True)
    product_name = models.CharField(max_length=255)
    
    # Stock levels
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0, help_text="Reserved for pending orders")
    available_quantity = models.PositiveIntegerField(default=0)
    
    # Location within warehouse
    aisle = models.CharField(max_length=10, blank=True)
    rack = models.CharField(max_length=10, blank=True)
    shelf = models.CharField(max_length=10, blank=True)
    
    # Reorder settings per warehouse
    min_stock_level = models.PositiveIntegerField(default=0)
    max_stock_level = models.PositiveIntegerField(default=0)
    reorder_point = models.PositiveIntegerField(default=0)
    
    # Tracking
    last_updated = models.DateTimeField(auto_now=True)
    last_stock_count_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['warehouse', 'product_name']
        unique_together = ['warehouse', 'product_id']
        indexes = [
            models.Index(fields=['warehouse', 'product_id']),
            models.Index(fields=['product_id']),
        ]
    
    def update_available_quantity(self):
        """Update available quantity after reservations"""
        self.available_quantity = max(0, self.quantity - self.reserved_quantity)
        self.save()
    
    def __str__(self):
        return f"{self.warehouse.name} - {self.product_name} ({self.quantity})"


class StockTransfer(models.Model):
    """Stock transfer between warehouses"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_TRANSIT', 'In Transit'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    transfer_number = models.CharField(max_length=50, unique=True)
    
    # Warehouses
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='outbound_transfers')
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inbound_transfers')
    
    # Transfer details
    product_id = models.PositiveIntegerField()
    product_name = models.CharField(max_length=255)
    quantity_requested = models.PositiveIntegerField()
    quantity_sent = models.PositiveIntegerField(default=0)
    quantity_received = models.PositiveIntegerField(default=0)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reason = models.TextField(help_text="Reason for transfer")
    
    # Dates
    requested_date = models.DateTimeField(auto_now_add=True)
    sent_date = models.DateTimeField(null=True, blank=True)
    expected_delivery_date = models.DateTimeField(null=True, blank=True)
    received_date = models.DateTimeField(null=True, blank=True)
    
    # People involved
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_transfers')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-requested_date']
    
    def __str__(self):
        return f"{self.transfer_number} - {self.from_warehouse.name} → {self.to_warehouse.name}"


class InventoryAlert(models.Model):
    """Enhanced inventory alerts and notifications"""
    ALERT_TYPE_CHOICES = [
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('OVERSTOCK', 'Overstock'),
        ('REORDER_NEEDED', 'Reorder Needed'),
        ('EXPIRY_WARNING', 'Expiry Warning'),
        ('DEAD_STOCK', 'Dead Stock'),
        ('NEGATIVE_STOCK', 'Negative Stock'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Resolved'),
        ('DISMISSED', 'Dismissed'),
    ]
    
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    # Product information
    product_id = models.PositiveIntegerField(db_index=True)
    product_name = models.CharField(max_length=255)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, null=True, blank=True)
    
    # Alert details
    current_stock = models.IntegerField()
    threshold_value = models.IntegerField(null=True, blank=True)
    message = models.TextField()
    
    # Notification settings
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    notification_recipients = models.JSONField(default=list, help_text="List of email addresses to notify")
    
    # Resolution tracking
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_alerts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['alert_type', 'priority']),
            models.Index(fields=['product_id']),
        ]
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.product_name} ({self.get_priority_display()})"


class PurchaseOrder(models.Model):
    """Purchase orders for inventory replenishment"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent to Supplier'),
        ('CONFIRMED', 'Confirmed'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Received'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    po_number = models.CharField(max_length=50, unique=True)
    supplier_name = models.CharField(max_length=100)
    supplier_email = models.EmailField(blank=True)
    supplier_phone = models.CharField(max_length=20, blank=True)
    
    # Order details
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Financial
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dates
    order_date = models.DateTimeField(auto_now_add=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    actual_delivery_date = models.DateField(null=True, blank=True)
    
    # People
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-order_date']
    
    def __str__(self):
        return f"PO-{self.po_number} - {self.supplier_name}"


class PurchaseOrderItem(models.Model):
    """Items in a purchase order"""
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product_id = models.PositiveIntegerField()
    product_name = models.CharField(max_length=255)
    
    # Order quantities
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    quantity_pending = models.PositiveIntegerField(default=0)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Tracking
    received_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['product_name']
    
    def save(self, *args, **kwargs):
        self.total_cost = self.quantity_ordered * self.unit_cost
        self.quantity_pending = self.quantity_ordered - self.quantity_received
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.product_name} - {self.quantity_ordered} units"