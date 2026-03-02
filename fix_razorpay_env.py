#!/usr/bin/env python
"""
Fix Razorpay SDK installation issue by installing it in the correct Python environment.
This script ensures razorpay is installed in the same Python that Django uses.
"""

import sys
import subprocess
import os

def main():
    print(f"\n{'='*70}")
    print("RAZORPAY ENVIRONMENT FIX")
    print(f"{'='*70}\n")
    
    # Show current environment
    print(f"➤ Current Python Executable: {sys.executable}")
    print(f"➤ Python Version: {sys.version}")
    print(f"➤ Virtual Environment: {'Yes' if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 'No'}\n")
    
    # Try importing razorpay
    print("Checking for razorpay installation...")
    try:
        import razorpay
        print(f"✓ razorpay is already installed: {razorpay.__file__}")
        print("\nNo action needed!")
        return
    except ImportError:
        print("✗ razorpay is NOT installed in this environment")
    
    print(f"\nAttempting to install razorpay to: {sys.executable}\n")
    
    # Upgrade pip first
    print("Step 1: Upgrading pip...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("✓ pip upgraded successfully")
    else:
        print(f"⚠ pip upgrade had issues: {result.stderr[:200]}")
    
    # Install razorpay
    print("\nStep 2: Installing razorpay...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "razorpay==1.4.1", "-v"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ razorpay installed successfully!")
    else:
        print(f"✗ Installation failed!")
        print(f"Error: {result.stderr[-500:]}")
        sys.exit(1)
    
    # Verify import
    print("\nStep 3: Verifying installation...")
    try:
        import razorpay
        print(f"✓ razorpay import successful!")
        print(f"  Location: {razorpay.__file__}")
        print(f"  Version: {razorpay.__version__ if hasattr(razorpay, '__version__') else 'unknown'}")
    except ImportError as e:
        print(f"✗ Import still failing: {e}")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print("SUCCESS! Razorpay SDK is now properly installed.")
    print("You can now test the refund functionality.")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
