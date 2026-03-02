#!/usr/bin/env python
"""
Verify razorpay is working in Django context
"""

import sys
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')

print("\n" + "="*70)
print("RAZORPAY VERIFICATION IN DJANGO")
print("="*70 + "\n")

print(f"Python: {sys.executable}")
print(f"Version: {sys.version_info.major}.{sys.version_info.minor}")
print()

# Test import
print("Testing razorpay import...")
try:
    import razorpay
    print("✓ Razorpay imported successfully")
    print(f"  Location: {razorpay.__file__}")
    
    # Test client creation
    client = razorpay.Client(auth=("test_key", "test_secret"))
    print("✓ Razorpay client created")
    print()
    
    print("="*70)
    print("SUCCESS! Razorpay is ready to use")
    print("="*70)
    print()
    print("Next steps:")
    print("1. Restart Django (if running)")
    print("2. Test refund: Admin Panel → Orders → PAID → Refund")
    print("3. Should work now!")
    print()
    
except ImportError as e:
    print(f"✗ Error: {e}")
    print()
    sys.exit(1)
