#!/usr/bin/env python
"""
Force install razorpay in the current Python environment
Used when pip install doesn't seem to work
"""
import subprocess
import sys
import os

print("=" * 70)
print("RAZORPAY INSTALL - FORCE MODE")
print("=" * 70)

print(f"\nPython executable: {sys.executable}")
print(f"Python version: {sys.version.split()[0]}")

# Step 1: Ensure pip is upgraded
print("\n1. Upgrading pip...")
result = subprocess.run(
    [sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'],
    capture_output=True,
    text=True
)
print("   Done")

# Step 2: Install setuptools (sometimes needed)
print("\n2. Installing setuptools...")
result = subprocess.run(
    [sys.executable, '-m', 'pip', 'install', 'setuptools'],
    capture_output=True,
    text=True
)
print("   Done")

# Step 3: Install razorpay with verbose output
print("\n3. Installing razorpay...")
result = subprocess.run(
    [sys.executable, '-m', 'pip', 'install', 'razorpay', '--verbose'],
    capture_output=False,  # Show output in real-time
    text=True
)

if result.returncode == 0:
    print("\n✓ Razorpay installation successful!")
else:
    print(f"\n✗ Installation failed with return code: {result.returncode}")

# Step 4: Verify import
print("\n4. Verifying import...")
try:
    import razorpay
    print(f"   ✓ razorpay imported successfully")
    print(f"   Location: {razorpay.__file__}")
except ImportError as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

# Step 5: List installed packages
print("\n5. Checking installed packages in this environment...")
result = subprocess.run(
    [sys.executable, '-m', 'pip', 'show', 'razorpay'],
    capture_output=True,
    text=True
)
print(result.stdout)

print("=" * 70)
print("✓ Environment setup complete!")
