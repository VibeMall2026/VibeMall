#!/usr/bin/env python
"""
Comprehensive UPI Verification Debug
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.conf import settings
from Hub.view_helpers import _verify_upi_with_razorpay
import logging

print("=" * 80)
print("COMPLETE UPI VERIFICATION DEBUG")
print("=" * 80)

# 1. Check settings
print("\n1. SETTINGS CHECK:")
print(f"   DEBUG: {settings.DEBUG}")
print(f"   UPI_TEST_MODE: {getattr(settings, 'UPI_TEST_MODE', 'NOT SET')}")
print(f"   RAZORPAY_KEY_ID: {'✓ SET' if getattr(settings, 'RAZORPAY_KEY_ID', '') else '✗ NOT SET'}")
print(f"   RAZORPAY_KEY_SECRET: {'✓ SET' if getattr(settings, 'RAZORPAY_KEY_SECRET', '') else '✗ NOT SET'}")

# 2. Test UPI verification directly
print("\n2. DIRECT UPI VERIFICATION TEST:")
logger = logging.getLogger('vibemall')

test_upi = 'ananya.sharma@okhdfcbank'
print(f"\n   Testing: {test_upi}")
is_valid, name, error = _verify_upi_with_razorpay(test_upi, logger=logger)

print(f"   Valid: {is_valid}")
print(f"   Name: {name}")
print(f"   Error: {error}")

if is_valid and name:
    print(f"   ✓ PASS - Verification working!")
else:
    print(f"   ✗ FAIL - Check settings and logs")

# 3. Check endpoint
print("\n3. ENDPOINT CHECK:")
try:
    from django.urls import reverse
    url = reverse('verify_upi')
    print(f"   ✓ Endpoint registered: {url}")
except Exception as e:
    print(f"   ✗ Endpoint error: {e}")

# 4. Test different UPI formats
print("\n4. TESTING DIFFERENT UPI FORMATS:")
test_cases = [
    'user@okhdfcbank',
    'john.doe@okicici', 
    'test@okaxis',
    'name@oksbi',
    'invalid',
    'user@unknown',
]

for upi in test_cases:
    is_valid, name, error = _verify_upi_with_razorpay(upi, logger=logger)
    status = "✓" if is_valid else "✗"
    print(f"   {status} {upi:25s} -> {name if is_valid else error}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)

if not getattr(settings, 'UPI_TEST_MODE', False):
    print("\n⚠️  UPI_TEST_MODE is disabled!")
    print("   → Check your .env file or settings.py")
    print("   → Add: UPI_TEST_MODE=True")
    print("   → Then restart Django server")

print("\nTo fix in Django shell:")
print("   python manage.py shell")
print("   >>> from django.conf import settings")
print("   >>> print(settings.UPI_TEST_MODE)")
print("   >>> from Hub.view_helpers import _verify_upi_with_razorpay")
print("   >>> _verify_upi_with_razorpay('user@okhdfcbank')")
print("\n" + "=" * 80)
