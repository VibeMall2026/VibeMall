#!/usr/bin/env python
"""
VibeMall Django Startup with Razorpay Verification

This script:
1. Activates venv
2. Verifies razorpay is installed
3. Auto-installs if needed
4. Starts Django server

Usage: python start_django.py
"""

import sys
import os
import subprocess
from datetime import datetime

# Project directory
project_dir = r"d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall"
os.chdir(project_dir)

print("\n" + "="*70)
print("VIBEMALL DJANGO STARTUP")
print("="*70)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Directory: {os.getcwd()}")
print()

# Step 1: Verify venv
print("Step 1: Verifying virtual environment...")
venv_python = os.path.join(project_dir, "venv", "Scripts", "python.exe")

if not os.path.exists(venv_python):
    print("[ERROR] Virtual environment not found!")
    print(f"Expected at: {venv_python}")
    sys.exit(1)

print(f"[OK] venv found at: {venv_python}")
print()

# Step 2: Verify Python version
print("Step 2: Verifying Python...")
result = subprocess.run([venv_python, "--version"], capture_output=True, text=True)
print(result.stdout.strip())
print("[OK] Python working")
print()

# Step 3: Check razorpay
print("Step 3: Checking razorpay installation...")
result = subprocess.run(
    [venv_python, "-c", "import razorpay; print('razorpay found')"],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    print("[WARNING] Razorpay not found, installing now...")
    
    install_result = subprocess.run(
        [venv_python, "-m", "pip", "install", "razorpay", "--upgrade", "--quiet"],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    if install_result.returncode == 0:
        print("[OK] Razorpay installed successfully")
    else:
        print("[ERROR] Failed to install razorpay")
        print(install_result.stderr[:200])
        sys.exit(1)
else:
    print("[OK] Razorpay is available")

print()

# Step 4: Start Django
print("Step 4: Starting Django server...")
print("="*70)
print("Django will start on: http://localhost:8000")
print("Admin panel: http://localhost:8000/admin")
print()
print("To stop server: Press Ctrl+C")
print("="*70)
print()

# Run Django
subprocess.run([venv_python, "manage.py", "runserver"])
