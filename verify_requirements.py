#!/usr/bin/env python
"""
VibeMall Requirements Verification
Checks all packages from requirements.txt are installed
"""
import subprocess
import sys

print("=" * 70)
print("VIBEMALL REQUIREMENTS CHECK")
print("=" * 70)

# Key packages needed
required_packages = {
    'django': 'Django',
    'razorpay': 'Razorpay SDK',
    'PIL': 'Pillow (Image Processing)',
    'pandas': 'Pandas (Data Processing)',
    'openpyxl': 'openpyxl (Excel)',
    'weasyprint': 'WeasyPrint (PDF)',
    'bleach': 'Bleach (HTML Sanitization)',
    'requests': 'Requests (HTTP)',
}

print("\nCritical Packages Status:")
print("-" * 70)

missing = []
installed = []

for import_name, display_name in required_packages.items():
    try:
        __import__(import_name)
        print(f"✓ {display_name}")
        installed.append(display_name)
    except ImportError as e:
        print(f"✗ {display_name} - NOT INSTALLED")
        missing.append((import_name, display_name))

print("-" * 70)
print(f"\nSummary: {len(installed)}/{len(required_packages)} packages installed")

if missing:
    print(f"\n⚠ {len(missing)} package(s) missing:")
    for import_name, display_name in missing:
        print(f"  - {display_name} (package: {import_name})")
    
    print(f"\nInstall missing packages with:")
    print("  pip install " + " ".join([name for name, _ in missing]))
    print("\nOr install all requirements with:")
    print("  pip install -r requirements.txt")
    sys.exit(1)
else:
    print("\n✓ All critical packages are installed!")
    sys.exit(0)
