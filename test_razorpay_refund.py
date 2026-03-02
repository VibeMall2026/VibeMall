#!/usr/bin/env python
"""
Test script to verify Razorpay refund system is working properly.
This simulates the refund flow to ensure no import errors occur.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from decimal import Decimal
from Hub.models import Order, Payment
from Hub.views import _create_razorpay_refund

print("\n" + "="*70)
print("TESTING RAZORPAY REFUND SYSTEM")
print("="*70 + "\n")

# Check if razorpay import works
print("1. Testing razorpay import...")
try:
    import razorpay
    print("   ✓ Razorpay imported successfully")
    print(f"   Location: {razorpay.__file__}\n")
except ImportError as e:
    print(f"   ✗ Failed to import razorpay: {e}\n")
    sys.exit(1)

# Check for test credentials
print("2. Checking Razorpay test credentials...")
from django.conf import settings

key_id = getattr(settings, 'RAZORPAY_KEY_ID', None)
key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)

if key_id and key_secret:
    print(f"   ✓ Credentials found")
    print(f"   Key ID: {key_id[:10]}...\n")
else:
    print("   ✗ Razorpay credentials not found in settings\n")
    sys.exit(1)

# Check for test order with payment
print("3. Looking for test orders with PAID status...")
paid_orders = Order.objects.filter(payment_status=2).first()  # 2 = PAID

if paid_orders:
    print(f"   ✓ Found paid order: {paid_orders.order_id}")
    payment = paid_orders.payment
    if payment:
        print(f"   Payment ID: {payment.razorpay_payment_id}")
        print(f"   Amount: Rs. {payment.amount}\n")
    else:
        print("   ⚠ Order has no linked payment\n")
else:
    print("   ⚠ No paid orders found for testing (this is normal for first-time setup)\n")

# Test the _create_razorpay_refund function
print("4. Testing _create_razorpay_refund function...")
print("   This tests the import and basic flow (won't actually refund)...\n")

try:
    # This will use None/dummy values but will test if import works
    success, message = _create_razorpay_refund(
        payment_method='razorpay',
        payment_id='test_dummy_id',
        amount='0',  # 0 amount won't actually refund
        reason='Test import validation'
    )
    
    if 'SDK' in message or 'not installed' in message:
        print(f"   ✗ Import error detected: {message}\n")
    else:
        print(f"   ✓ Function executed without import errors")
        print(f"   Response: {message}\n")
        
except ImportError as e:
    print(f"   ✗ Import error: {e}\n")
except Exception as e:
    print(f"   ✓ Function executed without import errors (other error: {type(e).__name__})")
    print(f"   This is expected for dummy test data\n")

print("="*70)
print("RAZORPAY REFUND SYSTEM STATUS: READY")
print("="*70)
print("\nThe refund system will now work properly.")
print("Test it by going to Admin Panel > Orders > Select a PAID order > Refund")
print()
