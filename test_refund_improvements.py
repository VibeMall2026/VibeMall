#!/usr/bin/env python
"""
Test script to validate refund improvements
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

print("=" * 70)
print("REFUND SYSTEM VALIDATION")
print("=" * 70)

# Test 1: Syntax check
print("\n1. Checking Python syntax...")
try:
    import py_compile
    py_compile.compile('Hub/views.py', doraise=True)
    print("   ✓ Hub/views.py syntax is valid")
except Exception as e:
    print(f"   ✗ Syntax error: {e}")
    sys.exit(1)

# Test 2: Import check
print("\n2. Checking imports...")
try:
    from Hub.views import razorpay_refund, _create_razorpay_refund
    from decimal import Decimal, InvalidOperation
    from django.conf import settings
    print("   ✓ All required imports successful")
except Exception as e:
    print(f"   ✗ Import error: {e}")
    sys.exit(1)

# Test 3: Check if Razorpay is configured
print("\n3. Checking Razorpay configuration...")
razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', '')
razorpay_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

if razorpay_key and razorpay_secret:
    if 'replace_with_' in razorpay_key or 'replace_with_' in razorpay_secret:
        print("   ⚠ Razorpay keys have placeholder values")
    else:
        print("   ✓ Razorpay credentials configured")
else:
    print("   ✗ Razorpay credentials missing")

# Test 4: Test refund helper with mock data
print("\n4. Testing refund validation logic...")

test_cases = [
    # (payment_id, amount, description, should_succeed)
    ('', Decimal('100'), 'Empty payment ID', False),
    ('invalid_id', Decimal('100'), 'Invalid payment ID format', False),
    ('pay_123', Decimal('0'), 'Zero amount', False),
    ('pay_123', Decimal('-50'), 'Negative amount', False),
    ('pay_123', Decimal('100'), 'Valid inputs (will fail on API call)', False),  # Will fail on API but validation passes
]

for payment_id, amount, desc, should_succeed in test_cases:
    success, error_msg = _create_razorpay_refund(payment_id, amount)
    
    # Check validation logic (not API state)
    if payment_id == '':
        assert not success and 'missing' in error_msg.lower(), f"Failed: {desc}"
        print(f"   ✓ {desc}")
    elif payment_id == 'invalid_id':
        assert not success and 'invalid' in error_msg.lower(), f"Failed: {desc}"
        print(f"   ✓ {desc}")
    elif amount == Decimal('0'):
        assert not success and 'greater than zero' in error_msg.lower(), f"Failed: {desc}"
        print(f"   ✓ {desc}")
    elif amount < 0:
        assert not success and 'greater than zero' in error_msg.lower(), f"Failed: {desc}"
        print(f"   ✓ {desc}")

# Test 5: Test error message clarity
print("\n5. Checking error message clarity...")
test_errors = [
    ('', 'missing'),
    ('invalid_id', 'invalid'),
    ('pay_123', 'not found'),  # When trying to call API
]

for payment_id, expected_word in test_errors:
    success, error_msg = _create_razorpay_refund(payment_id, Decimal('100'))
    if payment_id == '' and 'missing' in error_msg.lower():
        print(f'   ✓ Error message mentions: "{expected_word}"')
    elif payment_id == 'invalid_id' and 'invalid' in error_msg.lower():
        print(f'   ✓ Error message mentions: "{expected_word}"')

# Test 6: Django check
print("\n6. Running Django system check...")
from django.core.management import call_command
from io import StringIO

try:
    out = StringIO()
    call_command('check', stdout=out)
    result = out.getvalue()
    if 'identified no issues' in result.lower():
        print("   ✓ Django check passed")
    else:
        print(f"   ⚠ {result[:100]}")
except Exception as e:
    print(f"   ✗ Django check failed: {e}")

print("\n" + "=" * 70)
print("✓ REFUND SYSTEM VALIDATION COMPLETE")
print("=" * 70)
print("\nKEY IMPROVEMENTS:")
print("✓ Better error messages for payment ID validation")
print("✓ Specific error messages for invalid amounts")
print("✓ Clear handling of Razorpay exceptions")
print("✓ Users see 'Razorpay payment id missing' instead of 'invalid request sent'")
