"""
Performance Optimization Models - Phase 10
Features: Image Compression, CDN Integration, Database Query Optimization, Page Load Monitoring, Error Tracking
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class ImageOptimization(models.Model):
    """Image compression and optimization tracking"""
    OPTIMIZATION_TYPE_CHOICES = [
        ('PRODUCT_IMAGE', 'Product Image'),
        ('BANNER_IMAGE', 'Banner Image'),
        ('BLOG_IMAGE', 'Blog Image'),
        ('USER_AVATAR', 'User Avatar'),
        ('CATEGORY_IMAGE', 'Category Image'),
        ('BRAND_LOGO', 'Brand Logo'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Optimization'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('SKIPPED', 'Skipped'),
    ]
    
    # Image details
    original_filename = models.CharField(max_length=255)
    optimized_filename = models.CharField(max_length=255, blank=True)
    image_type = models.CharField(max_length=20, choices=OPTIMIZATION_TYPE_CHOICES)
    
    # File paths
    original_path = models.CharField(max_length=500)
    optimized_path = models.CharField(max_length=500, blank=True)
    
    # Size information
    original_size_bytes = models.PositiveIntegerField()
    optimized_size_bytes = models.PositiveIntegerField(default=0)
    compression_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Dimensions
    original_width = models.PositiveIntegerField()
    original_height = models.PositiveIntegerField()
    optimized_width = models.PositiveIntegerField(default=0)
    optimized_height = models.PositiveIntegerField(default=0)
    
    # Optimization settings
    quality_setting = models.PositiveIntegerField(default=85, help_text="JPEG quality (1-100)")
    format_conversion = models.CharField(max_length=10, blank=True, help_text="Target format (webp, jpg, png)")
    
    # Processing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    processing_time_ms = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    # CDN integration
    cdn_url = models.URLField(blank=True)
    is_uploaded_to_cdn = models.BooleanField(default=False)
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    bandwidth_saved_bytes = models.PositiveBigIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['image_type', 'status']),
        ]
    
    def size_reduction_percentage(self):
        if self.original_size_bytes > 0 and self.optimized_size_bytes > 0:
            return ((self.original_size_bytes - self.optimized_size_bytes) / self.original_size_bytes) * 100
        return 0
    
    def __str__(self):
        return f"{self.original_filename} - {self.get_image_type_display()} ({self.status})"


class CDNConfiguration(models.Model):
    """CDN (Content Delivery Network) configuration"""
    PROVIDER_CHOICES = [
        ('CLOUDFLARE', 'Cloudflare'),
        ('AWS_CLOUDFRONT', 'AWS CloudFront'),
        ('AZURE_CDN', 'Azure CDN'),
        ('GOOGLE_CDN', 'Google Cloud CDN'),
        ('FASTLY', 'Fastly'),
        ('KEYCDN', 'KeyCDN'),
        ('BUNNYCDN', 'BunnyCDN'),
        ('CUSTOM', 'Custom CDN'),
    ]
    
    name = models.CharField(max_length=100)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    
    # Configuration
    base_url = models.URLField(help_text="CDN base URL")
    api_key = models.CharField(max_length=200, blank=True)
    api_secret = models.CharField(max_length=200, blank=True)
    zone_id = models.CharField(max_length=100, blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    # File type configuration
    supported_file_types = models.JSONField(default=list, help_text="List of supported file extensions")
    cache_duration_seconds = models.PositiveIntegerField(default=86400)  # 24 hours
    
    # Performance settings
    compression_enabled = models.BooleanField(default=True)
    minification_enabled = models.BooleanField(default=True)
    
    # Analytics
    total_files_uploaded = models.PositiveIntegerField(default=0)
    total_bandwidth_gb = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"


class DatabaseQueryLog(models.Model):
    """Database query optimization monitoring"""
    QUERY_TYPE_CHOICES = [
        ('SELECT', 'SELECT Query'),
        ('INSERT', 'INSERT Query'),
        ('UPDATE', 'UPDATE Query'),
        ('DELETE', 'DELETE Query'),
        ('BULK_INSERT', 'Bulk Insert'),
        ('BULK_UPDATE', 'Bulk Update'),
    ]
    
    # Query details
    query_hash = models.CharField(max_length=64, db_index=True, help_text="MD5 hash of the query")
    query_type = models.CharField(max_length=20, choices=QUERY_TYPE_CHOICES)
    raw_query = models.TextField()
    
    # Performance metrics
    execution_time_ms = models.DecimalField(max_digits=10, decimal_places=3)
    rows_examined = models.PositiveIntegerField(default=0)
    rows_returned = models.PositiveIntegerField(default=0)
    
    # Context
    view_name = models.CharField(max_length=100, blank=True)
    url_path = models.CharField(max_length=500, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Request information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Analysis
    is_slow_query = models.BooleanField(default=False)
    needs_optimization = models.BooleanField(default=False)
    optimization_suggestions = models.JSONField(default=list, help_text="List of optimization suggestions")
    
    # Frequency tracking
    execution_count = models.PositiveIntegerField(default=1)
    last_executed = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-execution_time_ms']
        indexes = [
            models.Index(fields=['query_hash', '-last_executed']),
            models.Index(fields=['is_slow_query', '-execution_time_ms']),
            models.Index(fields=['view_name', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_query_type_display()} - {self.execution_time_ms}ms"


class PageLoadMetrics(models.Model):
    """Page load time monitoring"""
    # Page information
    url_path = models.CharField(max_length=500, db_index=True)
    page_title = models.CharField(max_length=200, blank=True)
    
    # Performance metrics (in milliseconds)
    dns_lookup_time = models.PositiveIntegerField(default=0)
    tcp_connect_time = models.PositiveIntegerField(default=0)
    server_response_time = models.PositiveIntegerField(default=0)
    dom_content_loaded = models.PositiveIntegerField(default=0)
    page_load_complete = models.PositiveIntegerField(default=0)
    first_contentful_paint = models.PositiveIntegerField(default=0)
    largest_contentful_paint = models.PositiveIntegerField(default=0)
    
    # Resource metrics
    total_page_size_kb = models.PositiveIntegerField(default=0)
    total_requests = models.PositiveIntegerField(default=0)
    js_size_kb = models.PositiveIntegerField(default=0)
    css_size_kb = models.PositiveIntegerField(default=0)
    image_size_kb = models.PositiveIntegerField(default=0)
    
    # User context
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    # Device and browser
    device_type = models.CharField(max_length=20, choices=[
        ('DESKTOP', 'Desktop'),
        ('MOBILE', 'Mobile'),
        ('TABLET', 'Tablet'),
    ], blank=True)
    browser = models.CharField(max_length=50, blank=True)
    operating_system = models.CharField(max_length=50, blank=True)
    
    # Network
    connection_type = models.CharField(max_length=20, blank=True, help_text="4g, 3g, wifi, etc.")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Performance score
    performance_score = models.PositiveIntegerField(default=0, help_text="Performance score 0-100")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['url_path', '-created_at']),
            models.Index(fields=['performance_score', '-created_at']),
            models.Index(fields=['device_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.url_path} - {self.page_load_complete}ms"


class ErrorLog(models.Model):
    """Error tracking and logging"""
    ERROR_TYPE_CHOICES = [
        ('PYTHON_EXCEPTION', 'Python Exception'),
        ('JAVASCRIPT_ERROR', 'JavaScript Error'),
        ('HTTP_ERROR', 'HTTP Error'),
        ('DATABASE_ERROR', 'Database Error'),
        ('VALIDATION_ERROR', 'Validation Error'),
        ('PERMISSION_ERROR', 'Permission Error'),
        ('EXTERNAL_API_ERROR', 'External API Error'),
        ('PAYMENT_ERROR', 'Payment Error'),
    ]
    
    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('INVESTIGATING', 'Under Investigation'),
        ('RESOLVED', 'Resolved'),
        ('IGNORED', 'Ignored'),
    ]
    
    # Error identification
    error_hash = models.CharField(max_length=64, db_index=True, help_text="MD5 hash of error signature")
    error_type = models.CharField(max_length=30, choices=ERROR_TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    
    # Error details
    message = models.TextField()
    stack_trace = models.TextField(blank=True)
    
    # Context
    url_path = models.CharField(max_length=500, blank=True)
    view_name = models.CharField(max_length=100, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Request information
    request_method = models.CharField(max_length=10, blank=True)
    request_data = models.JSONField(default=dict, help_text="Request parameters and data")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Environment
    server_name = models.CharField(max_length=100, blank=True)
    python_version = models.CharField(max_length=20, blank=True)
    django_version = models.CharField(max_length=20, blank=True)
    
    # Frequency tracking
    occurrence_count = models.PositiveIntegerField(default=1)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    
    # Resolution
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_errors')
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['error_hash', '-last_seen']),
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['error_type', '-last_seen']),
        ]
    
    def __str__(self):
        return f"{self.get_error_type_display()} - {self.message[:100]}"


class PerformanceAlert(models.Model):
    """Performance monitoring alerts"""
    ALERT_TYPE_CHOICES = [
        ('SLOW_PAGE', 'Slow Page Load'),
        ('HIGH_ERROR_RATE', 'High Error Rate'),
        ('DATABASE_SLOW', 'Slow Database Queries'),
        ('HIGH_MEMORY_USAGE', 'High Memory Usage'),
        ('HIGH_CPU_USAGE', 'High CPU Usage'),
        ('DISK_SPACE_LOW', 'Low Disk Space'),
        ('CDN_FAILURE', 'CDN Failure'),
        ('API_TIMEOUT', 'API Timeout'),
    ]
    
    SEVERITY_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('CRITICAL', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Resolved'),
        ('DISMISSED', 'Dismissed'),
    ]
    
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    # Alert details
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Metrics
    threshold_value = models.DecimalField(max_digits=10, decimal_places=2)
    current_value = models.DecimalField(max_digits=10, decimal_places=2)
    metric_unit = models.CharField(max_length=20, blank=True, help_text="ms, %, MB, etc.")
    
    # Context
    affected_url = models.CharField(max_length=500, blank=True)
    affected_component = models.CharField(max_length=100, blank=True)
    
    # Response
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Notifications
    notifications_sent = models.JSONField(default=list, help_text="List of notifications sent")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['alert_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_severity_display()})"


class CacheMetrics(models.Model):
    """Cache performance monitoring"""
    CACHE_TYPE_CHOICES = [
        ('REDIS', 'Redis Cache'),
        ('MEMCACHED', 'Memcached'),
        ('DATABASE', 'Database Cache'),
        ('FILE', 'File Cache'),
        ('CDN', 'CDN Cache'),
    ]
    
    cache_type = models.CharField(max_length=20, choices=CACHE_TYPE_CHOICES)
    cache_key_pattern = models.CharField(max_length=200, help_text="Cache key pattern or prefix")
    
    # Metrics
    hit_count = models.PositiveIntegerField(default=0)
    miss_count = models.PositiveIntegerField(default=0)
    total_requests = models.PositiveIntegerField(default=0)
    
    # Performance
    average_response_time_ms = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    
    # Storage
    memory_usage_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    key_count = models.PositiveIntegerField(default=0)
    
    # Time period
    measurement_date = models.DateField(auto_now_add=True)
    measurement_hour = models.PositiveIntegerField(help_text="Hour of the day (0-23)")
    
    class Meta:
        ordering = ['-measurement_date', '-measurement_hour']
        unique_together = ['cache_type', 'cache_key_pattern', 'measurement_date', 'measurement_hour']
    
    def hit_rate(self):
        if self.total_requests > 0:
            return (self.hit_count / self.total_requests) * 100
        return 0
    
    def __str__(self):
        return f"{self.get_cache_type_display()} - {self.cache_key_pattern} ({self.hit_rate():.1f}% hit rate)"


class SystemResourceUsage(models.Model):
    """System resource usage monitoring"""
    # CPU metrics
    cpu_usage_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cpu_load_average = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Memory metrics
    memory_total_mb = models.PositiveIntegerField(default=0)
    memory_used_mb = models.PositiveIntegerField(default=0)
    memory_usage_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Disk metrics
    disk_total_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    disk_used_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    disk_usage_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Network metrics
    network_in_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    network_out_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Database metrics
    active_connections = models.PositiveIntegerField(default=0)
    slow_queries = models.PositiveIntegerField(default=0)
    
    # Application metrics
    active_users = models.PositiveIntegerField(default=0)
    requests_per_minute = models.PositiveIntegerField(default=0)
    
    # Timestamp
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['-recorded_at']),
        ]
    
    def __str__(self):
        return f"System Usage - {self.recorded_at} (CPU: {self.cpu_usage_percent}%, Memory: {self.memory_usage_percent}%)"