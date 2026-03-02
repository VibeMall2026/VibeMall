#!/usr/bin/env python
"""
Test razorpay in Django's running context.
Run with: python manage.py shell < test_django_razorpay.py
"""

import sys
import os

print("\n" + "="*70)
print("RAZORPAY IMPORT TEST IN DJANGO CONTEXT")
print("="*70 + "\n")

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version.split()[0]}")
print(f"Current directory: {os.getcwd()}\n")

# Test in Django's context
try:
    import razorpay
    print("✓ Razorpay imported successfully in Django context")
    print(f"  Location: {razorpay.__file__}\n")
    
    # Verify client creation
    client = razorpay.Client(auth=("test_key", "test_secret"))
    print("✓ Razorpay client created successfully\n")
    
    print("="*70)
    print("SUCCESS: Razorpay is ready!")
    print("="*70)
    print("\nThe refund system should work now.")
    print("If you still see 'SDK not installed' error:")
    print("1. Restart Django server")
    print("2. Go to Admin Panel > Orders > Try refund again")
    print()
    
except ImportError as e:
    print(f"✗ Import error: {e}\n")
    print("This means razorpay is not in Django's Python path")
    print("Solution: Restart Django server\n")
    
except Exception as e:
    print(f"✗ Other error: {type(e).__name__}: {e}\n")
