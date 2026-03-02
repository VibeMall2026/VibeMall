#!/usr/bin/env python
"""
Direct test of razorpay import without full Django setup.
"""

import sys

print("\n" + "="*70)
print("RAZORPAY IMPORT TEST")
print("="*70 + "\n")

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version.split()[0]}\n")

# Test direct import
print("Testing direct razorpay import...")
try:
    import razorpay
    print("SUCCESS: razorpay imported!")
    print(f"Location: {razorpay.__file__}\n")
    
    # Try creating a client
    client = razorpay.Client(auth=("test_key", "test_secret"))
    print("SUCCESS: Razorpay client created!\n")
    
except ImportError as e:
    print(f"FAILED: ImportError - {e}\n")
    sys.exit(1)

# Test sys.path to verify package location
print("Python sys.path entries:")
for path_item in sys.path[:5]:
    print(f"  {path_item}")

print("\n" + "="*70)
print("RESULT: Razorpay is properly installed and importable!")
print("="*70)
print("\nThe 'Razorpay SDK not installed' error should now be FIXED.")
print("\nNext steps:")
print("1. Restart Django (if running in development)")
print("2. Test the refund feature in Admin Panel > Orders > Refund")
print()
