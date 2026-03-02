#!/usr/bin/env python
"""
CRITICAL DIAGNOSTIC: Show which Python is running and where packages are
Run this to understand why razorpay import is failing
"""

import sys
import os
import subprocess

print("\n" + "="*80)
print("CRITICAL DIAGNOSTIC: Why is Razorpay Import Failing?")
print("="*80 + "\n")

# 1. Show current Python
print("1. CURRENT PYTHON RUNNING THIS SCRIPT")
print("-" * 80)
print(f"   Executable: {sys.executable}")
print(f"   Version: {sys.version_info.major}.{sys.version_info.minor}")
is_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
print(f"   In venv: {is_venv}")
print(f"   Prefix: {sys.prefix}")
print()

# 2. Check if this matches manage.py expectation
print("2. WHAT PYTHON SHOULD DJANGO USE?")
print("-" * 80)
expected_venv = r"d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall\venv"
expected_python = os.path.join(expected_venv, "Scripts", "python.exe")
print(f"   Expected: {expected_python}")
print(f"   Exists: {os.path.exists(expected_python)}")
print(f"   Current matches expected: {sys.executable.lower() == expected_python.lower()}")
print()

# 3. Show all Python paths where razorpay might be
print("3. WHERE IS RAZORPAY INSTALLED?")
print("-" * 80)

# Check sys.path
for i, path in enumerate(sys.path[:7], 1):
    razorpay_path = os.path.join(path, "razorpay")
    exists = os.path.exists(razorpay_path)
    status = "FOUND!" if exists else "no"
    print(f"   [{i}] {path}")
    print(f"       razorpay exists: {status}")

print()

# 4. Try importing razorpay right now
print("4. CAN WE IMPORT RAZORPAY RIGHT NOW?")
print("-" * 80)
try:
    import razorpay
    print(f"   YES - Import successful!")
    print(f"   Location: {razorpay.__file__}")
except ImportError as e:
    print(f"   NO - ImportError: {e}")

print()

# 5. THE REAL ISSUE
print("5. THE REAL ISSUE - Django might be using wrong Python!")
print("-" * 80)
print(f"   If 'In venv' above is False, Django is using SYSTEM Python")
print(f"   This means razorpay is installed somewhere Django can't find it")
print()

# 6. The FIX
print("6. THE FIX - PERMANENT SOLUTION")
print("-" * 80)
print("""
   STEP 1: Use the provided run_django.bat script
   ------
   Location: run_django.bat (in project root)
   This activates venv BEFORE starting Django
   
   Action: Double-click run_django.bat instead of running manage.py manually
   
   OR
   
   STEP 2: Manually activate venv, then run Django
   ------
   a) Open Command Prompt
   b) Navigate to project: cd d:\Iu University\...\\VibeMall
   c) Activate venv: venv\\Scripts\\activate.bat
   d) Run Django: python manage.py runserver
   e) You should see: (venv) prompt at start
   
   OR
   
   STEP 3: Use explicit venv Python
   ------
   Run this exact command:
   venv\\Scripts\\python.exe manage.py runserver
   
   This FORCES the use of venv Python with razorpay installed.
""")

print()

# 7. Verification
print("7. VERIFY THE FIX WORKED")
print("-" * 80)
print("""
   After fixing, try this:
   
   1. Start Django with one of the methods above
   2. Go to Admin Panel > Orders > PAID order > Refund
   3. Should work now (or show specific error, not "SDK not found")
   
   If still failing:
   - Check Django logs for the detailed error we added
   - Run this script again to verify Python/paths
   - Contact support with the output
""")

print("\n" + "="*80 + "\n")
