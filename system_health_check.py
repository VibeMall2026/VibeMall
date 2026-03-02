#!/usr/bin/env python
"""
Comprehensive System Health Check for VibeMall
Tests all critical components and displays results
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.conf import settings
from django.template.loader import get_template
from django.template.exceptions import TemplateSyntaxError
import smtplib
from Hub.models import Order, OrderItem, ReturnRequest
from django.db import connection

print("\n" + "=" * 70)
print("VIBEMALL SYSTEM HEALTH CHECK")
print("=" * 70)

# 1. Django health check
print("\n1. DJANGO PROJECT:")
from django.core.management import call_command
from io import StringIO
try:
    out = StringIO()
    call_command('check', stdout=out)
    result = out.getvalue()
    if 'identified no issues' in result.lower():
        print("   ✓ Django system check: PASSED")
    else:
        print(f"   ⚠ {result}")
except Exception as e:
    print(f"   ✗ Django check failed: {str(e)[:50]}")

# 2. Templates
print("\n2. TEMPLATES:")
templates_to_check = [
    'order_details.html',
    'admin_panel/order_details.html',
    'admin_panel/resell/payouts.html',
    'base.html',
    'admin_panel/base_admin.html',
]

for tmpl_name in templates_to_check:
    try:
        tmpl = get_template(tmpl_name)
        print(f"   ✓ {tmpl_name}")
    except TemplateSyntaxError as e:
        print(f"   ✗ {tmpl_name}: Syntax Error - {str(e)[:40]}")
    except Exception as e:
        print(f"   ⚠ {tmpl_name}: {str(e)[:40]}")

# 3. Email Configuration
print("\n3. EMAIL CONFIGURATION:")
print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"   EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")

# Check for placeholders
has_placeholder = False
if 'replace_with_' in settings.EMAIL_HOST_PASSWORD:
    print(f"   ✗ EMAIL_HOST_PASSWORD is a placeholder!")
    has_placeholder = True
if 'replace_with_' in settings.EMAIL_HOST_USER:
    print(f"   ✗ EMAIL_HOST_USER is a placeholder!")
    has_placeholder = True

if not has_placeholder:
    try:
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10)
        server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        server.quit()
        print(f"   ✓ SMTP Authentication: VALID")
    except smtplib.SMTPAuthenticationError:
        print(f"   ✗ SMTP Authentication failed - Check Gmail App Password")
    except Exception as e:
        print(f"   ⚠ SMTP Test: {str(e)[:40]}")

# 4. Razorpay Configuration
print("\n4. RAZORPAY CONFIGURATION:")
rz_key = settings.RAZORPAY_KEY_ID if hasattr(settings, 'RAZORPAY_KEY_ID') else 'NOT_SET'
rz_secret = settings.RAZORPAY_KEY_SECRET if hasattr(settings, 'RAZORPAY_KEY_SECRET') else 'NOT_SET'

print(f"   RAZORPAY_KEY_ID: {'*' * 10} (last 5: {rz_key[-5:] if len(rz_key) > 0 else 'N/A'})")
print(f"   RAZORPAY_KEY_SECRET: {'*' * 10} (configured: {rz_secret != 'NOT_SET'})")

if rz_key == 'NOT_SET' or rz_secret == 'NOT_SET':
    print(f"   ⚠ Razorpay credentials may not be configured")
elif 'replace_with_' in rz_key or 'replace_with_' in rz_secret:
    print(f"   ✗ Razorpay has placeholder values")
else:
    print(f"   ✓ Razorpay credentials appear configured")

# 5. Database
print("\n5. DATABASE:")
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM hub_order")
        order_count = cursor.fetchone()[0]
    print(f"   ✓ Database connection: OK")
    print(f"   Orders in database: {order_count}")
except Exception as e:
    print(f"   ✗ Database error: {str(e)[:50]}")

# 6. Critical Models
print("\n6. CRITICAL MODELS:")
try:
    order_count = Order.objects.count()
    print(f"   ✓ Order model: {order_count} orders")
except Exception as e:
    print(f"   ✗ Order model error: {str(e)[:40]}")

try:
    item_count = OrderItem.objects.count()
    print(f"   ✓ OrderItem model: {item_count} items")
except Exception as e:
    print(f"   ✗ OrderItem model error: {str(e)[:40]}")

try:
    return_count = ReturnRequest.objects.count()
    print(f"   ✓ ReturnRequest model: {return_count} returns")
except Exception as e:
    print(f"   ✗ ReturnRequest model error: {str(e)[:40]}")

# 7. Critical Packages
print("\n7. REQUIRED PACKAGES:")
packages_to_check = ['bleach', 'razorpay', 'django', 'pandas', 'openpyxl', 'weasyprint']

for pkg in packages_to_check:
    try:
        __import__(pkg)
        print(f"   ✓ {pkg}")
    except ImportError:
        print(f"   ✗ {pkg} NOT INSTALLED")

print("\n" + "=" * 70)
print("✓ SYSTEM HEALTH CHECK COMPLETE")
print("=" * 70 + "\n")
