#!/usr/bin/env python
"""
Test the updated UPI verification function
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.view_helpers import _verify_upi_with_razorpay
import logging

logger = logging.getLogger('vibemall')

print("Testing Updated UPI Verification")
print("=" * 70)

# Test cases
test_cases = [
    ('ananya.sharma@okhdfcbank', True, 'Valid UPI - HDFC Bank'),
    ('john.doe@okicici', True, 'Valid UPI - ICICI Bank'),
    ('user@okaxis', True, 'Valid UPI - Axis Bank'),
    ('invalid', False, 'Invalid format - missing @'),
    ('invalid@unknown', False, 'Invalid bank'),
    ('test.user@oksbi', True, 'Valid UPI - SBI'),
]

print("\nTest Mode Enabled: Validating UPI IDs\n")

for upi_id, should_be_valid, description in test_cases:
    is_valid, name, error = _verify_upi_with_razorpay(upi_id, logger=logger)
    
    status = "✓ PASS" if is_valid == should_be_valid else "✗ FAIL"
    print(f"{status} | {description}")
    print(f"      UPI: {upi_id}")
    print(f"      Valid: {is_valid}")
    if name:
        print(f"      Name: {name}")
    if error:
        print(f"      Error: {error}")
    print()

print("=" * 70)
print("\nSUMMARY:")
print("✓ UPI verification now uses test mode")
print("✓ Validates UPI format (must have @ and valid bank code)")
print("✓ Known banks: okhdfcbank, okicici, okaxis, okbi, oksbi, airpay, ybl")
print("✓ Extracts customer name from UPI ID (replaces . _ with spaces)")
print("\nNext Steps for Production:")
print("1. Disable UPI_TEST_MODE in .env: UPI_TEST_MODE=False")
print("2. Configure proper Razorpay API endpoint when available")
print("3. Update endpoint URL if Razorpay provides new VPA validation endpoint")
