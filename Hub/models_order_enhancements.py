"""
Order Management Enhancement Models - Added without modifying existing code
Features: Bulk Processing, Shipping Integration, Route Optimization, COD Tracking
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class ShippingProvider(models.Model):
    """Shipping and courier service providers"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    
    # API Configuration
    api_endpoint = models.URLField(blank=True)
    api_key = models.CharField(max_length=200, blank=True)
    api_secret = models.CharField(max_length=200, blank=True)
    
    # Service details
    is_active = models.BooleanField(default=True)
    supports_cod = models.BooleanField(default=False)
    supports_tracking = models.BooleanField(default=True)
    supports_bulk_booking = models.BooleanField(default=False)
    
    # Pricing
    base_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    per_kg_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cod_charges_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=2.0)
    
    # Service areas
    serviceable_pincodes = models.JSONField(default=list, help_text="List of serviceable pincodes")
    
    # Contact information
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class ShippingRate(models.Model):
    """Dynamic shipping rate calculation"""
    provider = models.ForeignKey(ShippingProvider, on_delete=models.CASCADE, related_name='rates')
    
    # Zone-based pricing
    zone_name = models.CharField(max_length=50)
    from_pincode = models.CharField(max_length=10, blank=True)
    to_pincode_pattern = models.CharField(max_length=20, help_text="Pincode pattern (e.g., 110*, 400001-400100)")
    
    # Weight-based pricing
    min_weight = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    max_weight = models.DecimalField(max_digits=6, decimal_places=2, default=999)
    
    # Rates
    base_rate = models.DecimalField(max_digits=8, decimal_places=2)
    additional_kg_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    # Service type
    SERVICE_TYPE_CHOICES = [
        ('STANDARD', 'Standard Delivery'),
        ('EXPRESS', 'Express Delivery'),
        ('SAME_DAY', 'Same Day Delivery'),
        ('NEXT_DAY', 'Next Day Delivery'),
    ]
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, default='STANDARD')
    
    # Delivery time
    min_delivery_days = models.PositiveIntegerField(default=1)
    max_delivery_days = models.PositiveIntegerField(default=7)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['provider', 'zone_name', 'min_weight']
    
    def __str__(self):
        return f"{self.provider.name} - {self.zone_name} ({self.service_type})"


class BulkOrderOperation(models.Model):
    """Bulk order processing operations"""
    OPERATION_TYPE_CHOICES = [
        ('PRINT_INVOICES', 'Print Multiple Invoices'),
        ('PRINT_LABELS', 'Print Shipping Labels'),
        ('UPDATE_STATUS', 'Update Order Status'),
        ('ASSIGN_COURIER', 'Assign Courier'),
        ('GENERATE_MANIFEST', 'Generate Shipping Manifest'),
        ('EXPORT_DATA', 'Export Order Data'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    operation_type = models.CharField(max_length=30, choices=OPERATION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Order selection
    order_ids = models.JSONField(default=list, help_text="List of order IDs to process")
    total_orders = models.PositiveIntegerField(default=0)
    processed_orders = models.PositiveIntegerField(default=0)
    failed_orders = models.PositiveIntegerField(default=0)
    
    # Operation parameters
    operation_params = models.JSONField(default=dict, help_text="Operation-specific parameters")
    
    # Results
    result_file_path = models.CharField(max_length=500, blank=True)
    error_log = models.JSONField(default=list, help_text="List of errors encountered")
    
    # Tracking
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_operation_type_display()} - {self.total_orders} orders ({self.status})"


class OrderTracking(models.Model):
    """Enhanced order tracking with courier integration"""
    order_id = models.PositiveIntegerField(db_index=True)
    order_number = models.CharField(max_length=50)
    
    # Shipping details
    shipping_provider = models.ForeignKey(ShippingProvider, on_delete=models.SET_NULL, null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    awb_number = models.CharField(max_length=100, blank=True)
    
    # Current status
    TRACKING_STATUS_CHOICES = [
        ('ORDER_PLACED', 'Order Placed'),
        ('PICKED_UP', 'Picked Up'),
        ('IN_TRANSIT', 'In Transit'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('DELIVERY_ATTEMPTED', 'Delivery Attempted'),
        ('RETURNED', 'Returned'),
        ('CANCELLED', 'Cancelled'),
    ]
    current_status = models.CharField(max_length=30, choices=TRACKING_STATUS_CHOICES, default='ORDER_PLACED')
    
    # Location tracking
    current_location = models.CharField(max_length=200, blank=True)
    destination_city = models.CharField(max_length=100, blank=True)
    
    # Delivery information
    estimated_delivery_date = models.DateTimeField(null=True, blank=True)
    actual_delivery_date = models.DateTimeField(null=True, blank=True)
    delivery_person_name = models.CharField(max_length=100, blank=True)
    delivery_person_phone = models.CharField(max_length=20, blank=True)
    
    # Delivery proof
    delivery_signature = models.ImageField(upload_to='delivery_signatures/', null=True, blank=True)
    delivery_photo = models.ImageField(upload_to='delivery_photos/', null=True, blank=True)
    delivery_otp = models.CharField(max_length=10, blank=True)
    
    # Tracking updates
    last_updated = models.DateTimeField(auto_now=True)
    last_api_sync = models.DateTimeField(null=True, blank=True)
    
    # Customer notifications
    sms_notifications_sent = models.PositiveIntegerField(default=0)
    email_notifications_sent = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-last_updated']
        unique_together = ['order_id']
        indexes = [
            models.Index(fields=['order_id']),
            models.Index(fields=['tracking_number']),
            models.Index(fields=['current_status']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number} - {self.get_current_status_display()}"


class TrackingUpdate(models.Model):
    """Individual tracking updates/events"""
    order_tracking = models.ForeignKey(OrderTracking, on_delete=models.CASCADE, related_name='updates')
    
    # Update details
    status = models.CharField(max_length=30, choices=OrderTracking.TRACKING_STATUS_CHOICES)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    
    # Timing
    event_timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Source
    update_source = models.CharField(max_length=20, choices=[
        ('API', 'Courier API'),
        ('MANUAL', 'Manual Update'),
        ('WEBHOOK', 'Webhook'),
        ('SMS', 'SMS Gateway'),
    ], default='API')
    
    class Meta:
        ordering = ['-event_timestamp']
    
    def __str__(self):
        return f"{self.order_tracking.order_number} - {self.get_status_display()} at {self.location}"


class DeliveryRoute(models.Model):
    """Delivery route optimization"""
    route_name = models.CharField(max_length=100)
    delivery_date = models.DateField()
    
    # Route details
    delivery_person = models.CharField(max_length=100)
    delivery_person_phone = models.CharField(max_length=20)
    vehicle_number = models.CharField(max_length=20, blank=True)
    
    # Route optimization
    start_location = models.CharField(max_length=200)
    start_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    start_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Route statistics
    total_orders = models.PositiveIntegerField(default=0)
    total_distance_km = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    estimated_time_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Status
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    
    # Tracking
    route_started_at = models.DateTimeField(null=True, blank=True)
    route_completed_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-delivery_date']
    
    def __str__(self):
        return f"{self.route_name} - {self.delivery_date} ({self.total_orders} orders)"


class RouteStop(models.Model):
    """Individual stops in a delivery route"""
    route = models.ForeignKey(DeliveryRoute, on_delete=models.CASCADE, related_name='stops')
    order_id = models.PositiveIntegerField()
    order_number = models.CharField(max_length=50)
    
    # Stop details
    stop_sequence = models.PositiveIntegerField()
    customer_name = models.CharField(max_length=100)
    delivery_address = models.TextField()
    customer_phone = models.CharField(max_length=20)
    
    # Location
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Delivery details
    cod_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    special_instructions = models.TextField(blank=True)
    
    # Status
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed Delivery'),
        ('RESCHEDULED', 'Rescheduled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Delivery tracking
    attempted_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=200, blank=True)
    
    class Meta:
        ordering = ['route', 'stop_sequence']
        unique_together = ['route', 'order_id']
    
    def __str__(self):
        return f"Stop {self.stop_sequence}: {self.customer_name} - Order {self.order_number}"


class CODRemittance(models.Model):
    """COD (Cash on Delivery) remittance tracking"""
    remittance_id = models.CharField(max_length=50, unique=True)
    shipping_provider = models.ForeignKey(ShippingProvider, on_delete=models.CASCADE)
    
    # Remittance period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Financial details
    total_cod_orders = models.PositiveIntegerField(default=0)
    total_cod_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    courier_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cod_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tds_deducted = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_remittance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Status
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RECEIVED', 'Received'),
        ('RECONCILED', 'Reconciled'),
        ('DISPUTED', 'Disputed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Dates
    expected_remittance_date = models.DateField(null=True, blank=True)
    actual_remittance_date = models.DateField(null=True, blank=True)
    
    # Bank details
    bank_reference_number = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    
    # Documents
    remittance_advice = models.FileField(upload_to='cod_remittance/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-period_end']
    
    def __str__(self):
        return f"COD Remittance {self.remittance_id} - ₹{self.net_remittance}"


class CODRemittanceItem(models.Model):
    """Individual COD orders in remittance"""
    remittance = models.ForeignKey(CODRemittance, on_delete=models.CASCADE, related_name='items')
    order_id = models.PositiveIntegerField()
    order_number = models.CharField(max_length=50)
    
    # Order details
    customer_name = models.CharField(max_length=100)
    delivery_date = models.DateField()
    cod_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Charges
    shipping_charges = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    cod_charges = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Status
    is_delivered = models.BooleanField(default=True)
    is_remitted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['delivery_date']
        unique_together = ['remittance', 'order_id']
    
    def __str__(self):
        return f"Order {self.order_number} - ₹{self.cod_amount}"


class OrderCancellationAnalytics(models.Model):
    """Analytics for order cancellations"""
    CANCELLATION_REASON_CHOICES = [
        ('CUSTOMER_REQUEST', 'Customer Request'),
        ('PAYMENT_FAILED', 'Payment Failed'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('PRICING_ERROR', 'Pricing Error'),
        ('DELIVERY_ISSUE', 'Delivery Issue'),
        ('FRAUD_SUSPECTED', 'Fraud Suspected'),
        ('DUPLICATE_ORDER', 'Duplicate Order'),
        ('OTHER', 'Other'),
    ]
    
    order_id = models.PositiveIntegerField(db_index=True)
    order_number = models.CharField(max_length=50)
    
    # Cancellation details
    cancellation_reason = models.CharField(max_length=30, choices=CANCELLATION_REASON_CHOICES)
    detailed_reason = models.TextField(blank=True)
    cancelled_by = models.CharField(max_length=20, choices=[
        ('CUSTOMER', 'Customer'),
        ('ADMIN', 'Admin'),
        ('SYSTEM', 'System'),
    ])
    
    # Financial impact
    order_value = models.DecimalField(max_digits=10, decimal_places=2)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cancellation_charges = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Timing
    order_date = models.DateTimeField()
    cancellation_date = models.DateTimeField()
    hours_to_cancellation = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Customer information
    customer_id = models.PositiveIntegerField()
    customer_segment = models.CharField(max_length=20, blank=True)
    is_repeat_customer = models.BooleanField(default=False)
    
    # Product information
    product_categories = models.JSONField(default=list, help_text="Categories of cancelled products")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-cancellation_date']
        indexes = [
            models.Index(fields=['cancellation_reason', '-cancellation_date']),
            models.Index(fields=['cancelled_by', '-cancellation_date']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number} - {self.get_cancellation_reason_display()}"


class PartialFulfillment(models.Model):
    """Partial order fulfillment tracking"""
    order_id = models.PositiveIntegerField(db_index=True)
    order_number = models.CharField(max_length=50)
    
    # Fulfillment details
    fulfillment_number = models.CharField(max_length=50, unique=True)
    total_items = models.PositiveIntegerField()
    fulfilled_items = models.PositiveIntegerField()
    pending_items = models.PositiveIntegerField()
    
    # Financial
    total_order_value = models.DecimalField(max_digits=12, decimal_places=2)
    fulfilled_value = models.DecimalField(max_digits=12, decimal_places=2)
    pending_value = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status
    STATUS_CHOICES = [
        ('PARTIAL', 'Partially Fulfilled'),
        ('COMPLETED', 'Fully Fulfilled'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PARTIAL')
    
    # Shipping
    shipping_provider = models.ForeignKey(ShippingProvider, on_delete=models.SET_NULL, null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    
    # Dates
    fulfillment_date = models.DateTimeField(auto_now_add=True)
    expected_completion_date = models.DateField(null=True, blank=True)
    
    # Notes
    reason_for_partial = models.TextField(blank=True)
    customer_notified = models.BooleanField(default=False)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-fulfillment_date']
    
    def __str__(self):
        return f"Partial Fulfillment {self.fulfillment_number} - Order {self.order_number}"