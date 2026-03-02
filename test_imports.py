#!/usr/bin/env python
import sys

# Test if razorpay can be imported
print("Testing Razorpay SDK installation...")
print("=" * 60)

try:
    import razorpay
    print("✓ razorpay module imported successfully")
    print(f"  Version: {razorpay.__version__}")
except ImportError as e:
    print(f"✗ Failed to import razorpay: {e}")
    sys.exit(1)

# Test other critical imports
print("\nTesting other critical packages...")
packages_to_test = [
    ('django', 'Django'),
    ('PIL', 'Pillow'),
    ('pandas', 'pandas'),
    ('openpyxl', 'openpyxl'),
    ('weasyprint', 'weasyprint'),
    ('bleach', 'bleach'),
    ('requests', 'requests'),
    ('decimal', 'decimal (built-in)'),
]

all_ok = True
for package_name, display_name in packages_to_test:
    try:
        __import__(package_name)
        print(f"✓ {display_name}")
    except ImportError as e:
        print(f"✗ {display_name} - {str(e)[:50]}")
        all_ok = False

print("\n" + "=" * 60)
if all_ok:
    print("✓ All critical packages installed successfully!")
else:
    print("⚠ Some packages are missing. Run: pip install -r requirements.txt")

sys.exit(0 if all_ok else 1)
