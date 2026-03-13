"""
Security & Access Control Models - Phase 8
Features: Role-based Permissions, Activity Logs, 2FA, IP Whitelist, Session Management, Login Tracking
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class SecurityRole(models.Model):
    """Enhanced role-based access control"""
    ROLE_TYPE_CHOICES = [
        ('SUPER_ADMIN', 'Super Administrator'),
        ('ADMIN', 'Administrator'),
        ('MANAGER', 'Manager'),
        ('STAFF', 'Staff Member'),
        ('VIEWER', 'View Only'),
        ('CUSTOMER_SERVICE', 'Customer Service'),
        ('INVENTORY_MANAGER', 'Inventory Manager'),
        ('SALES_MANAGER', 'Sales Manager'),
        ('MARKETING_MANAGER', 'Marketing Manager'),
        ('FINANCE_MANAGER', 'Finance Manager'),
        ('CUSTOM', 'Custom Role'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    role_type = models.CharField(max_length=30, choices=ROLE_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Permission categories
    can_manage_products = models.BooleanField(default=False)
    can_manage_orders = models.BooleanField(default=False)
    can_manage_customers = models.BooleanField(default=False)
    can_manage_inventory = models.BooleanField(default=False)
    can_manage_finances = models.BooleanField(default=False)
    can_manage_marketing = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_export_data = models.BooleanField(default=False)
    
    # Granular permissions
    permissions = models.JSONField(default=dict, help_text="Detailed permission mapping")
    
    # Access restrictions
    allowed_ip_ranges = models.JSONField(default=list, help_text="List of allowed IP ranges")
    working_hours_start = models.TimeField(null=True, blank=True)
    working_hours_end = models.TimeField(null=True, blank=True)
    working_days = models.JSONField(default=list, help_text="List of working days (0=Monday)")
    
    # Role settings
    is_active = models.BooleanField(default=True)
    max_concurrent_sessions = models.PositiveIntegerField(default=3)
    session_timeout_minutes = models.PositiveIntegerField(default=480)  # 8 hours
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_role_type_display()})"


class UserRoleAssignment(models.Model):
    """User role assignments with time-based access"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(SecurityRole, on_delete=models.CASCADE, related_name='user_assignments')
    
    # Assignment details
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='security_roles_assigned')
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    # Time-based access
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False, help_text="Primary role for the user")
    
    # Additional restrictions
    additional_permissions = models.JSONField(default=dict, help_text="Additional permissions beyond role")
    restricted_permissions = models.JSONField(default=list, help_text="Permissions to restrict from role")
    
    class Meta:
        ordering = ['-is_primary', 'assigned_at']
        unique_together = ['user', 'role']
    
    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True
    
    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


class SecurityAuditLog(models.Model):
    """Comprehensive security audit logging"""
    EVENT_TYPE_CHOICES = [
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('LOGIN_FAILED', 'Failed Login'),
        ('PASSWORD_CHANGE', 'Password Change'),
        ('PERMISSION_CHANGE', 'Permission Change'),
        ('DATA_ACCESS', 'Data Access'),
        ('DATA_MODIFY', 'Data Modification'),
        ('DATA_DELETE', 'Data Deletion'),
        ('EXPORT', 'Data Export'),
        ('ADMIN_ACTION', 'Admin Action'),
        ('SECURITY_VIOLATION', 'Security Violation'),
        ('SYSTEM_EVENT', 'System Event'),
    ]
    
    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    # Event details
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='LOW')
    description = models.TextField()
    
    # User information
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField(max_length=150, blank=True, help_text="Username at time of event")
    
    # Request information
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    
    # Additional context
    affected_object_type = models.CharField(max_length=100, blank=True)
    affected_object_id = models.CharField(max_length=100, blank=True)
    old_values = models.JSONField(default=dict, help_text="Previous values before change")
    new_values = models.JSONField(default=dict, help_text="New values after change")
    
    # Geolocation
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Status
    is_suspicious = models.BooleanField(default=False)
    is_investigated = models.BooleanField(default=False)
    investigation_notes = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
            models.Index(fields=['is_suspicious', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.username or 'Anonymous'} ({self.timestamp})"


class TwoFactorAuthentication(models.Model):
    """Two-factor authentication management"""
    METHOD_CHOICES = [
        ('TOTP', 'Time-based OTP (Google Authenticator)'),
        ('SMS', 'SMS OTP'),
        ('EMAIL', 'Email OTP'),
        ('BACKUP_CODES', 'Backup Codes'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Setup'),
        ('ACTIVE', 'Active'),
        ('DISABLED', 'Disabled'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='two_factor_auth')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # TOTP settings
    secret_key = models.CharField(max_length=32, blank=True)
    qr_code_url = models.TextField(blank=True)
    
    # SMS/Email settings
    phone_number = models.CharField(max_length=20, blank=True)
    email_address = models.EmailField(blank=True)
    
    # Backup codes
    backup_codes = models.JSONField(default=list, help_text="List of backup codes")
    used_backup_codes = models.JSONField(default=list, help_text="List of used backup codes")
    
    # Usage tracking
    last_used = models.DateTimeField(null=True, blank=True)
    total_uses = models.PositiveIntegerField(default=0)
    failed_attempts = models.PositiveIntegerField(default=0)
    
    # Settings
    is_primary = models.BooleanField(default=False)
    require_for_admin = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_primary', 'method']
        unique_together = ['user', 'method']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_method_display()} ({self.status})"


class IPWhitelist(models.Model):
    """IP address whitelist management"""
    ENTRY_TYPE_CHOICES = [
        ('SINGLE', 'Single IP'),
        ('RANGE', 'IP Range'),
        ('SUBNET', 'Subnet'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    
    # IP configuration
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    ip_range_start = models.GenericIPAddressField(null=True, blank=True)
    ip_range_end = models.GenericIPAddressField(null=True, blank=True)
    subnet = models.CharField(max_length=20, blank=True, help_text="e.g., 192.168.1.0/24")
    
    # Access control
    allowed_users = models.ManyToManyField(User, blank=True, related_name='allowed_ip_whitelist', help_text="Specific users allowed from this IP")
    allowed_roles = models.ManyToManyField(SecurityRole, blank=True, help_text="Roles allowed from this IP")
    
    # Time restrictions
    allowed_hours_start = models.TimeField(null=True, blank=True)
    allowed_hours_end = models.TimeField(null=True, blank=True)
    allowed_days = models.JSONField(default=list, help_text="List of allowed days (0=Monday)")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_permanent = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_ip_whitelist')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def is_valid(self):
        if not self.is_active:
            return False
        if not self.is_permanent and self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
    
    def __str__(self):
        return f"{self.name} - {self.get_entry_type_display()}"


class UserSession(models.Model):
    """Enhanced user session management"""
    SESSION_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('TERMINATED', 'Terminated'),
        ('SUSPICIOUS', 'Suspicious'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_sessions')
    session_key = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=20, choices=SESSION_STATUS_CHOICES, default='ACTIVE')
    
    # Session details
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_type = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    operating_system = models.CharField(max_length=100, blank=True)
    
    # Geolocation
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    
    # Session tracking
    login_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    
    # Security flags
    is_suspicious = models.BooleanField(default=False)
    suspicious_reasons = models.JSONField(default=list, help_text="List of suspicious activity reasons")
    
    # Activity tracking
    page_views = models.PositiveIntegerField(default=0)
    actions_performed = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-login_time']
        indexes = [
            models.Index(fields=['user', '-login_time']),
            models.Index(fields=['status', '-login_time']),
            models.Index(fields=['ip_address', '-login_time']),
        ]
    
    def duration(self):
        end_time = self.logout_time or timezone.now()
        return end_time - self.login_time
    
    def __str__(self):
        return f"{self.user.username} - {self.ip_address} ({self.status})"


class LoginAttempt(models.Model):
    """Failed login attempt tracking"""
    ATTEMPT_TYPE_CHOICES = [
        ('SUCCESS', 'Successful Login'),
        ('FAILED_PASSWORD', 'Wrong Password'),
        ('FAILED_USERNAME', 'Wrong Username'),
        ('FAILED_2FA', 'Failed 2FA'),
        ('BLOCKED_IP', 'Blocked IP'),
        ('ACCOUNT_LOCKED', 'Account Locked'),
        ('SUSPICIOUS', 'Suspicious Activity'),
    ]
    
    # Attempt details
    username = models.CharField(max_length=150)
    attempt_type = models.CharField(max_length=20, choices=ATTEMPT_TYPE_CHOICES)
    
    # Request information
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    # Geolocation
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Additional context
    failure_reason = models.CharField(max_length=200, blank=True)
    
    # Security analysis
    is_brute_force = models.BooleanField(default=False)
    risk_score = models.PositiveIntegerField(default=0, help_text="Risk score 0-100")
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['username', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
            models.Index(fields=['attempt_type', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.username} - {self.get_attempt_type_display()} from {self.ip_address}"


class SecurityAlert(models.Model):
    """Security alerts and notifications"""
    ALERT_TYPE_CHOICES = [
        ('BRUTE_FORCE', 'Brute Force Attack'),
        ('SUSPICIOUS_LOGIN', 'Suspicious Login'),
        ('MULTIPLE_FAILURES', 'Multiple Login Failures'),
        ('UNUSUAL_ACTIVITY', 'Unusual Activity'),
        ('PERMISSION_ESCALATION', 'Permission Escalation'),
        ('DATA_BREACH_ATTEMPT', 'Data Breach Attempt'),
        ('SYSTEM_INTRUSION', 'System Intrusion'),
        ('MALWARE_DETECTED', 'Malware Detected'),
    ]
    
    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('INVESTIGATING', 'Under Investigation'),
        ('RESOLVED', 'Resolved'),
        ('FALSE_POSITIVE', 'False Positive'),
        ('DISMISSED', 'Dismissed'),
    ]
    
    alert_id = models.CharField(max_length=50, unique=True)
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    
    # Alert details
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Affected entities
    affected_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    affected_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Evidence
    evidence_data = models.JSONField(default=dict, help_text="Supporting evidence and data")
    
    # Response
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_security_alerts')
    response_actions = models.JSONField(default=list, help_text="Actions taken in response")
    resolution_notes = models.TextField(blank=True)
    
    # Timing
    detected_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Notifications
    notifications_sent = models.JSONField(default=list, help_text="List of notifications sent")
    
    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['status', '-detected_at']),
            models.Index(fields=['severity', '-detected_at']),
            models.Index(fields=['alert_type', '-detected_at']),
        ]
    
    def __str__(self):
        return f"{self.alert_id} - {self.title} ({self.get_severity_display()})"


class DataAccessLog(models.Model):
    """Detailed data access logging for compliance"""
    ACCESS_TYPE_CHOICES = [
        ('READ', 'Read Access'),
        ('CREATE', 'Create Record'),
        ('UPDATE', 'Update Record'),
        ('DELETE', 'Delete Record'),
        ('EXPORT', 'Export Data'),
        ('BULK_OPERATION', 'Bulk Operation'),
    ]
    
    # Access details
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPE_CHOICES)
    
    # Data details
    table_name = models.CharField(max_length=100)
    record_id = models.CharField(max_length=100, blank=True)
    field_names = models.JSONField(default=list, help_text="List of accessed fields")
    
    # Request context
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    
    # Data sensitivity
    contains_pii = models.BooleanField(default=False, help_text="Contains Personally Identifiable Information")
    contains_financial = models.BooleanField(default=False, help_text="Contains financial data")
    data_classification = models.CharField(max_length=20, choices=[
        ('PUBLIC', 'Public'),
        ('INTERNAL', 'Internal'),
        ('CONFIDENTIAL', 'Confidential'),
        ('RESTRICTED', 'Restricted'),
    ], default='INTERNAL')
    
    # Compliance
    purpose = models.CharField(max_length=200, blank=True, help_text="Business purpose for access")
    legal_basis = models.CharField(max_length=100, blank=True, help_text="Legal basis for processing")
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['table_name', '-timestamp']),
            models.Index(fields=['access_type', '-timestamp']),
            models.Index(fields=['contains_pii', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username if self.user else 'Unknown'} - {self.get_access_type_display()} {self.table_name}"