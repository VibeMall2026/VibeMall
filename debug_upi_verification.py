#!/usr/bin/env python
"""
Debug UPI verification configuration
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.conf import settings
import json

print("=" * 60)
print("UPI VERIFICATION DEBUG CHECK")
print("=" * 60)

# 1. Check Razorpay credentials
razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', '')
razorpay_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

print("\n1. RAZORPAY CREDENTIALS:")
print(f"   RAZORPAY_KEY_ID configured: {'✓ YES' if razorpay_key else '✗ NO'}")
if razorpay_key:
    print(f"   Key starts with: {razorpay_key[:10]}...")
print(f"   RAZORPAY_KEY_SECRET configured: {'✓ YES' if razorpay_secret else '✗ NO'}")

if not razorpay_key or not razorpay_secret:
    print("\n   ⚠  ERROR: Razorpay credentials missing!")
    print("   → Add to your .env or settings.py:")
    print("      RAZORPAY_KEY_ID = 'your_key_id'")
    print("      RAZORPAY_KEY_SECRET = 'your_secret'")

# 2. Check debug mode
debug_mode = getattr(settings, 'RAZORPAY_UPI_DEBUG', False)
print(f"\n2. DEBUG MODE: {'✓ ENABLED' if debug_mode else '✗ DISABLED'}")
if not debug_mode:
    print("   → Enable debugging by adding to settings.py:")
    print("      RAZORPAY_UPI_DEBUG = True")

# 3. Test the verification function
print("\n3. TESTING UPI VERIFICATION FOR SAMPLE DATA:")
from Hub.view_helpers import _verify_upi_with_razorpay
import logging

logger = logging.getLogger('vibemall')

# Test with sample UPI IDs
test_upis = [
    'user@okhdfcbank',      # HDFC Bank
    'user@okicici',         # ICICI Bank
    'user@okaxis',          # Axis Bank
]

print("\n   Testing with sample UPI IDs:")
for upi_test in test_upis:
    is_valid, name, error = _verify_upi_with_razorpay(upi_test, logger=logger)
    status = "✓ Valid" if is_valid else "✗ Invalid"
    print(f"   {upi_test}: {status}")
    if name:
        print(f"      Name: {name}")
    if error:
        print(f"      Error: {error}")

# 4. Check if endpoint is registered
print("\n4. CHECKING URL ROUTING:")
from django.urls import reverse
try:
    url = reverse('verify_upi')
    print(f"   ✓ verify_upi endpoint registered: {url}")
except:
    print(f"   ✗ verify_upi endpoint NOT registered")
    print("   → Add to Hub/urls.py:")
    print("      path('verify-upi/', views.verify_upi, name='verify_upi'),")

print("\n" + "=" * 60)
print("END DEBUG CHECK")
print("=" * 60)
