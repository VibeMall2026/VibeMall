#!/usr/bin/env python
"""Quick test to verify razorpay is installed"""
try:
    import razorpay
    print("SUCCESS: razorpay is installed and can be imported")
except ImportError:
    print("FAIL: razorpay is NOT installed")
