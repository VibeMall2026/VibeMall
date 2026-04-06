import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.view_helpers import _verify_upi_with_razorpay

# Test cases
test_cases = [
    ('ananya.sharma@okhdfcbank', True, 'Ananya Sharma'),
    ('john.doe@kotak', True, 'John Doe'),  # The failing one - NOW FIXED!
    ('user@okaxis', True, 'User'),
    ('test@phonepe', True, 'Test'),
    ('invalid', False, None),
    ('user@unknownbank', False, None),
]

print("🧪 Testing UPI Verification with Updated Banks:\n")
for upi, should_pass, expected_name in test_cases:
    valid, name, error = _verify_upi_with_razorpay(upi)
    status = "✓" if (valid == should_pass) else "✗"
    result = f"{status} {upi:30} → "
    
    if valid:
        result += f"✓ {name}"
    else:
        result += f"✗ {error}"
    
    print(result)

print("\n✅ All tests completed!")
