# Webhook Logging and Verification System Implementation

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json

class WebhookLog(models.Model):
    """Log all incoming webhooks for debugging and audit"""
    EVENT_TYPES = [
        ('payment.captured', 'Payment Captured'),
        ('payment.failed', 'Payment Failed'),
        ('payment.authorized', 'Payment Authorized'),
        ('refund.created', 'Refund Created'),
        ('settlement.processed', 'Settlement Processed'),
        ('unknown', 'Unknown Event'),
    ]
    
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
    ]
    
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    payment_id = models.CharField(max_length=100, blank=True, db_index=True)
    order_id = models.CharField(max_length=100, blank=True, db_index=True)
    raw_body = models.JSONField(help_text="Raw webhook payload from Razorpay")
    signature = models.CharField(max_length=256, blank=True, help_text="Webhook signature for verification")
    signature_valid = models.BooleanField(default=False, help_text="Whether signature was valid")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received', db_index=True)
    response_message = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    
    processed_by_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['-received_at', 'event_type']),
            models.Index(fields=['payment_id', 'order_id']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.payment_id} - {self.status}"
    
    def get_amount(self):
        """Extract amount from webhook payload"""
        try:
            if self.event_type == 'payment.captured':
                return self.raw_body.get('payload', {}).get('payment', {}).get('entity', {}).get('amount')
            elif self.event_type == 'refund.created':
                return self.raw_body.get('payload', {}).get('refund', {}).get('entity', {}).get('amount')
        except:
            pass
        return None


class VerificationTestLog(models.Model):
    """Log test verification attempts for debugging"""
    TEST_TYPES = [
        ('upi', 'UPI Verification'),
        ('bank', 'Bank Verification'),
        ('both', 'Both'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_test_logs')
    test_type = models.CharField(max_length=20, choices=TEST_TYPES)
    
    upi_id = models.CharField(max_length=255, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    
    test_amount = models.CharField(max_length=20, default='100')  # In paise
    test_status = models.CharField(max_length=50, blank=True)
    
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_response = models.JSONField(default=dict)
    
    webhook_received = models.BooleanField(default=False)
    webhook_received_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True, help_text="Test notes for debugging")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Test {self.test_type} - {self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
