#!/usr/bin/env python
"""
FORCE FIX: Install razorpay in Django's currently running Python
This script identifies which Python Django is using and installs razorpay there
"""

import sys
import subprocess
import os

print("\n" + "="*80)
print("FORCE RAZORPAY INSTALLATION IN DJANGO'S PYTHON")
print("="*80 + "\n")

# 1. Show current Python
print("Step 1: Detecting Python")
print("-" * 80)
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
print()

# 2. Check if venv is activated
is_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
print(f"In virtual environment: {is_venv}")
if not is_venv:
    print("⚠️  WARNING: Not in venv! Django might be using system Python")
print()

# 3. Upgrade pip
print("Step 2: Upgrading pip")
print("-" * 80)
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools"],
    capture_output=True,
    text=True
)
if result.returncode == 0:
    print("✓ pip upgraded")
else:
    print("⚠️ pip upgrade had issues")

# 4. Install razorpay
print("\nStep 3: Installing razorpay")
print("-" * 80)
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "razorpay==1.4.1", "--upgrade", "--force-reinstall"],
    capture_output=True,
    text=True,
    timeout=60
)

if "Successfully installed" in result.stdout or result.returncode == 0:
    print("✓ razorpay installed successfully")
else:
    print("Installation output:")
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr[:200])

# 5. Verify import
print("\nStep 4: Verifying razorpay import")
print("-" * 80)

try:
    import razorpay
    print(f"✓ SUCCESS: razorpay imported!")
    print(f"  Location: {razorpay.__file__}")
    
    # Try creating client
    client = razorpay.Client(auth=("test_key", "test_secret"))
    print(f"✓ Razorpay client created successfully")
    
except ImportError as e:
    print(f"✗ FAILED: {e}")
    print("\nTroubleshooting:")
    print("1. Check sys.path:")
    print(f"   {sys.path[0]}")
    sys.exit(1)

# 6. Check site-packages
print("\nStep 5: Verifying site-packages location")
print("-" * 80)

import site
site_packages = site.getsitepackages()
if site_packages:
    sp = site_packages[0]
    razorpay_path = os.path.join(sp, "razorpay")
    if os.path.exists(razorpay_path):
        print(f"✓ razorpay found in: {razorpay_path}")
    else:
        print(f"✗ razorpay NOT found in: {sp}")

print("\n" + "="*80)
print("INSTALLATION COMPLETE")
print("="*80)
print("\nNext steps:")
print("1. RESTART Django")
print("2. Test refund: Admin Panel → Orders → PAID → Refund")
print("3. Should now work!")
print("\n")
