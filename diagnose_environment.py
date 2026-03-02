#!/usr/bin/env python
"""
Diagnose Python environment and razorpay import issues
"""
import sys
import os
import subprocess

print("=" * 70)
print("PYTHON ENVIRONMENT DIAGNOSTIC")
print("=" * 70)

print(f"\n1. Python Executable Path:")
print(f"   {sys.executable}")

print(f"\n2. Python Version:")
print(f"   {sys.version}")

print(f"\n3. Virtual Environment Status:")
if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    print(f"   ✓ In virtual environment")
    print(f"   Path: {sys.prefix}")
else:
    print(f"   ✗ NOT in virtual environment (using system Python)")
    print(f"   Path: {sys.prefix}")

print(f"\n4. Python Path (sys.path):")
for path in sys.path[:5]:  # Show first 5 paths
    print(f"   - {path}")

print(f"\n5. Attempting to import razorpay...")
try:
    import razorpay
    print(f"   ✓ SUCCESS: razorpay imported")
    print(f"   Location: {razorpay.__file__}")
    print(f"   Version: {razorpay.__version__}")
except ImportError as e:
    print(f"   ✗ FAILED: {e}")
    print(f"\n   This means razorpay is not installed in this environment")
    print(f"   Trying to install in current environment...")
    
    # Try to install
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', 'razorpay'],
        capture_output=True,
        text=True
    )
    
    print(f"\n   Installation output:")
    print(result.stdout)
    if result.stderr:
        print(f"   Errors: {result.stderr}")
    
    # Try import again
    print(f"\n   Retrying import...")
    try:
        import razorpay
        print(f"   ✓ SUCCESS: razorpay now imported!")
    except ImportError as e2:
        print(f"   ✗ STILL FAILED: {e2}")

print(f"\n6. Checking site-packages...")
try:
    import site
    for site_pkg in site.getsitepackages():
        if os.path.exists(site_pkg):
            print(f"   - {site_pkg}")
            # Check if razorpay is there
            razorpay_dir = os.path.join(site_pkg, 'razorpay')
            if os.path.exists(razorpay_dir):
                print(f"     ✓ razorpay found here!")
except:
    pass

print("\n" + "=" * 70)
