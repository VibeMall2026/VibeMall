"""
Script to add Refund, BankVerification, and UPIVerification models to models.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

# Read the current models.py
models_file_path = 'Hub/models.py'
with open(models_file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# New models to add
new_models = '''

class Refund(models.Model):
    """Track refund requests and transactions"""
    REFUND_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='refunds')
    razorpay_payment_id = models.CharField(max_length=100, help_text="Razorpay Payment ID to refund")
    razorpay_refund_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Refund ID")
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount refunded in ₹")
    status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='PENDING')
    reason = models.TextField(help_text="Reason for refund")
    notes = models.TextField(blank=True, help_text="Additional notes")
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='refunds_requested')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('order', 'razorpay_refund_id')
    
    def __str__(self):
        return f"Refund #{self.id} - Order #{self.order.order_number} - ₹{self.refund_amount}"


class BankVerification(models.Model):
    """Track bank account verification using penny drop (₹1 transfer)"""
    VERIFICATION_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VERIFYING', 'Verifying'),
        ('VERIFIED', 'Verified'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bank_verification')
    account_number = models.CharField(max_length=50, help_text="Bank account number (masked)")
    ifsc = models.CharField(max_length=11, help_text="IFSC code")
    account_name = models.CharField(max_length=255, blank=True, help_text="Account holder name from bank")
    
    # Razorpay integration
    razorpay_contact_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Contact ID")
    razorpay_fund_account_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Fund Account ID")
    razorpay_payout_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Payout ID for verification")
    
    # Verification status
    status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='PENDING')
    is_verified = models.BooleanField(default=False)
    verification_error = models.TextField(blank=True, help_text="Error message if verification failed")
    
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"BankVerification - {self.user.username} - {self.account_number[-4:]}"


class UPIVerification(models.Model):
    """Track UPI verification using ₹1 collect request"""
    VERIFICATION_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('WAITING_PAYMENT', 'Waiting for Payment'),
        ('VERIFIED', 'Verified'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='upi_verification')
    upi_id = models.CharField(max_length=255, help_text="UPI ID (e.g., name@bank)")
    
    # Razorpay payment details
    razorpay_payment_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Payment ID for ₹1 verification")
    razorpay_order_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Order ID for ₹1 verification")
    
    # Verification status
    status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='PENDING')
    is_verified = models.BooleanField(default=False)
    verification_error = models.TextField(blank=True, help_text="Error message if verification failed")
    
    # For refund tracking
    refund_attempted = models.BooleanField(default=False, help_text="Whether ₹1 refund was attempted after verification")
    
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"UPIVerification - {self.user.username} - {self.upi_id}"
'''

# Append new models to the file
with open(models_file_path, 'a', encoding='utf-8') as f:
    f.write(new_models)

print("✅ Added Refund, BankVerification, and UPIVerification models to models.py")
