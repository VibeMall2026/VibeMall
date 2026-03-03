#!/usr/bin/env python
"""Test script to verify order approval email system"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from Hub.models import Order, EmailLog, User
from Hub.email_utils import send_order_approval_email
from django.utils import timezone
from datetime import timedelta

print("\n" + "="*70)
print("📧 ORDER APPROVAL EMAIL SYSTEM TEST")
print("="*70)

# Test 1: Check email configuration
print("\n[1] Checking Email Configuration...")
from django.conf import settings
email_config = {
    'Backend': settings.EMAIL_BACKEND,
    'Host': settings.EMAIL_HOST,
    'Port': settings.EMAIL_PORT,
    'Use TLS': settings.EMAIL_USE_TLS,
    'From Email': settings.DEFAULT_FROM_EMAIL,
}
for key, value in email_config.items():
    print(f"   {key}: {value}")

# Test 2: Find pending approval orders
print("\n[2] Finding Pending Approval Orders...")
pending_count = Order.objects.filter(approval_status='PENDING_APPROVAL').count()
print(f"   Total Pending: {pending_count}")

if pending_count == 0:
    print("   ⚠️  No pending orders found. Creating test order...")
    # Try to get a test user or create one
    try:
        user = User.objects.filter(is_staff=True).first() or User.objects.first()
        if not user:
            print("   ❌ No users found in database!")
            sys.exit(1)
        
        # Create a test order
        order = Order.objects.create(
            user=user,
            order_number=f"TEST-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            total_amount=999.99,
            approval_status='PENDING_APPROVAL',
            order_status='PENDING'
        )
        print(f"   ✅ Created test order: {order.order_number}")
        pending_orders = [order]
    except Exception as e:
        print(f"   ❌ Error creating test order: {e}")
        sys.exit(1)
else:
    pending_orders = list(Order.objects.filter(approval_status='PENDING_APPROVAL')[:3])
    print(f"   Found {len(pending_orders)} pending orders to test")

# Test 3: Test email sending for each pending order
print("\n[3] Testing Email Sending...")
test_admin = User.objects.filter(is_staff=True).first()

for order in pending_orders:
    print(f"\n   📦 Order: {order.order_number}")
    print(f"      Customer: {order.user.email}")
    print(f"      Amount: ₹{order.total_amount}")
    
    # Send approval email
    success = send_order_approval_email(order, approved_by=test_admin)
    
    if success:
        print(f"      ✅ Email sent successfully")
        
        # Check if EmailLog was created
        email_log = EmailLog.objects.filter(
            order=order,
            email_type='ORDER_APPROVED',
            sent_successfully=True
        ).first()
        
        if email_log:
            print(f"      ✅ EmailLog recorded: {email_log.id}")
        else:
            print(f"      ⚠️  No EmailLog found")
    else:
        print(f"      ❌ Email sending failed")
        
        # Check error log
        error_log = EmailLog.objects.filter(
            order=order,
            email_type='ORDER_APPROVED',
            sent_successfully=False
        ).first()
        
        if error_log:
            print(f"      Error: {error_log.error_message}")

# Test 4: Check EmailLog statistics
print("\n[4] EmailLog Statistics...")
approval_logs = EmailLog.objects.filter(email_type='ORDER_APPROVED')
success_count = approval_logs.filter(sent_successfully=True).count()
fail_count = approval_logs.filter(sent_successfully=False).count()

print(f"   Total ORDER_APPROVED emails: {approval_logs.count()}")
print(f"   ✅ Successful: {success_count}")
print(f"   ❌ Failed: {fail_count}")

if fail_count > 0:
    print("\n   Failed emails:")
    for log in approval_logs.filter(sent_successfully=False)[:5]:
        print(f"      - {log.email_to}: {log.error_message[:50]}")

# Test 5: Verify Gmail configuration
print("\n[5] Verifying Gmail Configuration...")
email_user = settings.EMAIL_HOST_USER
email_host = settings.EMAIL_HOST

if 'gmail' in email_host.lower() and email_user:
    print(f"   ✅ Gmail SMTP configured")
    print(f"      User: {email_user}")
    print(f"      Host: {email_host}:{settings.EMAIL_PORT}")
    print(f"      TLS: {settings.EMAIL_USE_TLS}")
else:
    print(f"   ⚠️  Not using Gmail SMTP (using {email_host})")

print("\n" + "="*70)
print("✅ EMAIL SYSTEM TEST COMPLETE")
print("="*70 + "\n")
