#!/usr/bin/env python
"""
VibeMall Comprehensive Testing Suite
Runs all critical tests before production deployment
"""

import os
import sys
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.test.utils import get_runner
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.core.mail import send_mail

print("\n" + "="*80)
print("VIBEMALL PRODUCTION TESTING SUITE")
print("="*80)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

test_results = {
    'passed': [],
    'failed': [],
    'warnings': []
}

def print_test(name, status, message=""):
    """Print test result"""
    if status == "PASS":
        print(f"{GREEN}✓{RESET} {name}")
        test_results['passed'].append(name)
    elif status == "FAIL":
        print(f"{RED}✗{RESET} {name}")
        if message:
            print(f"  {RED}Error: {message}{RESET}")
        test_results['failed'].append(name)
    else:  # WARNING
        print(f"{YELLOW}⚠{RESET} {name}")
        if message:
            print(f"  {YELLOW}Warning: {message}{RESET}")
        test_results['warnings'].append(name)

# ==============================================================================
# PHASE 1: ENVIRONMENT CHECKS
# ==============================================================================
print("\n" + "-"*80)
print("PHASE 1: Environment Configuration")
print("-"*80 + "\n")

# Check DEBUG setting
try:
    if settings.DEBUG:
        print_test("DEBUG Mode", "FAIL", "DEBUG=True (must be False in production)")
    else:
        print_test("DEBUG Mode", "PASS")
except:
    print_test("DEBUG Mode", "FAIL", "Could not read DEBUG setting")

# Check ALLOWED_HOSTS
try:
    if not settings.ALLOWED_HOSTS or settings.ALLOWED_HOSTS == ['*']:
        print_test("ALLOWED_HOSTS", "FAIL", "Not configured for production")
    else:
        print_test("ALLOWED_HOSTS", "PASS", f"Configured: {settings.ALLOWED_HOSTS}")
except:
    print_test("ALLOWED_HOSTS", "FAIL", "Not configured")

# Check SECRET_KEY length
try:
    if len(settings.SECRET_KEY) < 50:
        print_test("SECRET_KEY", "FAIL", "Too short (min 50 chars)")
    else:
        print_test("SECRET_KEY", "PASS", "Properly configured")
except:
    print_test("SECRET_KEY", "FAIL", "Not configured")

# Check Database
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        print_test("Database Connection", "PASS")
except Exception as e:
    print_test("Database Connection", "FAIL", str(e)[:100])

# Check Email Configuration
try:
    email_host = settings.EMAIL_HOST
    email_user = settings.EMAIL_HOST_USER
    if email_host and email_user:
        print_test("Email Configuration", "PASS", f"Using {email_host}")
    else:
        print_test("Email Configuration", "FAIL", "Not configured")
except:
    print_test("Email Configuration", "FAIL", "Missing settings")

# Check HTTPS/SSL
try:
    ssl_redirect = settings.SECURE_SSL_REDIRECT
    if ssl_redirect:
        print_test("SSL/HTTPS", "PASS", "Enabled")
    else:
        print_test("SSL/HTTPS", "WARN", "Not enabled (OK for development)")
except:
    print_test("SSL/HTTPS", "WARN", "Setting not found")

# ==============================================================================
# PHASE 2: DEPENDENCY CHECKS
# ==============================================================================
print("\n" + "-"*80)
print("PHASE 2: Dependencies & Packages")
print("-"*80 + "\n")

# Check critical packages
critical_packages = {
    'django': 'Django',
    'razorpay': 'Razorpay',
    'requests': 'Requests',
    'pillow': 'Pillow',
    'django_cors_headers': 'Django CORS',
}

for package, name in critical_packages.items():
    try:
        __import__(package)
        print_test(f"{name} Package", "PASS")
    except ImportError:
        print_test(f"{name} Package", "FAIL", f"Not installed: {package}")

# ==============================================================================
# PHASE 3: DJANGO SYSTEM CHECKS
# ==============================================================================
print("\n" + "-"*80)
print("PHASE 3: Django System Checks")
print("-"*80 + "\n")

try:
    from django.core.management import call_command
    from io import StringIO
    import sys
    
    # Capture django check output
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    try:
        call_command('check', '--deploy')
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        print_test("Django System Check (--deploy)", "PASS")
    except SystemExit as e:
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        if e.code == 0:
            print_test("Django System Check (--deploy)", "PASS")
        else:
            print_test("Django System Check (--deploy)", "FAIL", output[:100])
    except Exception as e:
        sys.stdout = old_stdout
        print_test("Django System Check (--deploy)", "FAIL", str(e)[:100])
        
except Exception as e:
    print_test("Django System Check", "FAIL", str(e)[:100])

# ==============================================================================
# PHASE 4: DATA INTEGRITY
# ==============================================================================
print("\n" + "-"*80)
print("PHASE 4: Data Integrity")
print("-"*80 + "\n")

try:
    from Hub.models import User, Order, Product
    
    # Check users exist
    user_count = User.objects.count()
    if user_count > 0:
        print_test("Users Table", "PASS", f"Found {user_count} users")
    else:
        print_test("Users Table", "WARN", "No users created yet")
    
    # Check products exist
    product_count = Product.objects.count()
    if product_count > 0:
        print_test("Products Table", "PASS", f"Found {product_count} products")
    else:
        print_test("Products Table", "WARN", "No products created yet")
    
    # Check orders
    order_count = Order.objects.count()
    print_test("Orders Table", "PASS", f"Found {order_count} orders")
    
except Exception as e:
    print_test("Data Integrity Check", "FAIL", str(e)[:100])

# ==============================================================================
# PHASE 5: CRITICAL FEATURE TESTS
# ==============================================================================
print("\n" + "-"*80)
print("PHASE 5: Critical Features")
print("-"*80 + "\n")

# Test Razorpay Import
try:
    import razorpay
    client = razorpay.Client(auth=("test", "test"))
    print_test("Razorpay Integration", "PASS", "SDK available")
except ImportError as e:
    print_test("Razorpay Integration", "FAIL", "SDK not installed")
except Exception as e:
    print_test("Razorpay Integration", "FAIL", str(e)[:100])

# Test JSON Serialization
try:
    from django.core.serializers.json import DjangoJSONEncoder
    import json
    from datetime import datetime, date
    
    test_data = {
        'date': date.today(),
        'datetime': datetime.now(),
        'string': 'test',
        'number': 123
    }
    json_str = json.dumps(test_data, cls=DjangoJSONEncoder)
    print_test("JSON Serialization (DjangoJSONEncoder)", "PASS")
except Exception as e:
    print_test("JSON Serialization", "FAIL", str(e)[:100])

# Test Email
try:
    send_mail(
        'VibeMall Production Test',
        'This is a test email from VibeMall production testing suite.',
        settings.EMAIL_HOST_USER,
        [settings.EMAIL_HOST_USER],
        fail_silently=False,
    )
    print_test("Email Sending", "PASS", "Test email sent successfully")
except Exception as e:
    print_test("Email Sending", "WARN", f"Could not send test email: {str(e)[:50]}")

# ==============================================================================
# PHASE 6: SECURITY CHECKS
# ==============================================================================
print("\n" + "-"*80)
print("PHASE 6: Security Configuration")
print("-"*80 + "\n")

# CSRF Protection
try:
    csrf_enabled = 'django.middleware.csrf.CsrfViewMiddleware' in settings.MIDDLEWARE
    if csrf_enabled:
        print_test("CSRF Protection", "PASS")
    else:
        print_test("CSRF Protection", "FAIL", "Not enabled")
except:
    print_test("CSRF Protection", "FAIL", "Could not check")

# Security Middleware
try:
    security_middleware = 'django.middleware.security.SecurityMiddleware' in settings.MIDDLEWARE
    if security_middleware:
        print_test("Security Middleware", "PASS")
    else:
        print_test("Security Middleware", "WARN", "Not enabled")
except:
    print_test("Security Middleware", "WARN", "Could not check")

# Session Security
try:
    session_secure = settings.SESSION_COOKIE_SECURE
    if session_secure:
        print_test("Session Security", "PASS")
    else:
        print_test("Session Security", "WARN", "SESSION_COOKIE_SECURE not enabled")
except:
    print_test("Session Security", "WARN", "Could not check")

# ==============================================================================
# FINAL REPORT
# ==============================================================================
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80 + "\n")

total_passed = len(test_results['passed'])
total_failed = len(test_results['failed'])
total_warnings = len(test_results['warnings'])
total_tests = total_passed + total_failed + total_warnings

print(f"Total Tests: {total_tests}")
print(f"{GREEN}Passed: {total_passed}{RESET}")
print(f"{YELLOW}Warnings: {total_warnings}{RESET}")
print(f"{RED}Failed: {total_failed}{RESET}\n")

if total_failed == 0:
    print(f"{GREEN}✓ ALL CRITICAL TESTS PASSED!{RESET}")
    if total_warnings > 0:
        print(f"{YELLOW}⚠ Warning: {total_warnings} non-critical issues found{RESET}")
    print(f"\n{GREEN}Ready for production deployment!{RESET}\n")
else:
    print(f"{RED}✗ {total_failed} CRITICAL TESTS FAILED{RESET}")
    print(f"{RED}Fix these issues before deploying to production:{RESET}")
    for failed in test_results['failed']:
        print(f"  - {failed}")
    print()

print("="*80 + "\n")
