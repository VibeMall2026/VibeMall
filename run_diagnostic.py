#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.conf import settings
from Hub.models import UPIVerification, Order

print("\n" + "=" * 80)
print("VERIFICATION SYSTEM DIAGNOSTIC REPORT")
print("=" * 80)

# 1. Check Razorpay credentials
print("\n1. RAZORPAY CONFIGURATION CHECK:")
print("-" * 80)
has_key_id = bool(getattr(settings, 'RAZORPAY_KEY_ID', ''))
has_key_secret = bool(getattr(settings, 'RAZORPAY_KEY_SECRET', ''))
has_webhook_secret = bool(getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', ''))

print(f"   RAZORPAY_KEY_ID configured:      {has_key_id}")
print(f"   RAZORPAY_KEY_SECRET configured: {has_key_secret}")
print(f"   RAZORPAY_WEBHOOK_SECRET:        {has_webhook_secret}")

if not (has_key_id and has_key_secret):
    print("\n   ❌ CRITICAL: Razorpay credentials missing! Payment system CANNOT work.")
    sys.exit(1)

# 2. Check UPIVerification records
print("\n2. UPI VERIFICATION RECORDS:")
print("-" * 80)

total_upi = UPIVerification.objects.count()
verified = UPIVerification.objects.filter(is_verified=True).count()
waiting = UPIVerification.objects.filter(status='WAITING_PAYMENT').count()
pending = UPIVerification.objects.filter(status='PENDING').count()

print(f"   Total UPI records:          {total_upi}")
print(f"   ✓ Verified:                 {verified}")
print(f"   ⏳ Waiting for payment:      {waiting}")
print(f"   ⏳ Pending:                  {pending}")

if total_upi > 0:
    print("\n   Recent UPI records:")
    recent = UPIVerification.objects.all().order_by('-created_at')[:5]
    for i, upi in enumerate(recent, 1):
        print(f"\n   {i}. {upi.user.username}: {upi.upi_id}")
        print(f"      Status: {upi.status} | Verified: {upi.is_verified}")
        print(f"      Order ID: {upi.razorpay_order_id or 'NONE'}")
        print(f"      Payment ID: {upi.razorpay_payment_id or 'NONE'}")
        if upi.verification_error:
            print(f"      Error: {upi.verification_error}")

# 3. Check Bank Verification
print("\n3. BANK VERIFICATION (DIRECT TRANSFER):")
print("-" * 80)
try:
    from Hub.models import BankVerification
    bank_count = BankVerification.objects.count()
    print(f"   Total Bank Verification records: {bank_count}")
    
    if bank_count > 0:
        recent_bank = BankVerification.objects.all().order_by('-created_at')[:3]
        for i, b in enumerate(recent_bank, 1):
            print(f"\n   {i}. {b.user.username}")
            print(f"      Account: {b.bank_account_number}")
            print(f"      Status: {b.verification_status}")
    else:
        print("   ℹ️  No Bank Verification records yet")
except Exception as e:
    print(f"   ℹ️  Bank Verification model: {str(e)}")

# 4. Check webhook configuration
print("\n4. WEBHOOK CONFIGURATION:")
print("-" * 80)
webhook_url = getattr(settings, 'RAZORPAY_WEBHOOK_URL', '')
print(f"   Webhook URL: {webhook_url if webhook_url else '❌ NOT CONFIGURED'}")

if not webhook_url:
    print("\n   ❌ CRITICAL: Razorpay Webhook URL not configured!")
    print("   Without this, payment confirmations are NEVER received.")

# 5. Check if endpoints exist
print("\n5. API ENDPOINTS:")
print("-" * 80)
from django.urls import reverse
try:
    verify_upi_url = reverse('verify_upi')
    print(f"   ✓ /api/verify-upi/           exists")
except:
    print(f"   ❌ /api/verify-upi/           NOT FOUND")

try:
    status_url = reverse('verify_upi_collect_status')
    print(f"   ✓ /api/verify-upi-collect-status/ exists")
except:
    print(f"   ❌ /api/verify-upi-collect-status/ NOT FOUND")

# 6. Summary
print("\n" + "=" * 80)
print("ANALYSIS SUMMARY:")
print("=" * 80)

issues = []
if not has_key_id or not has_key_secret:
    issues.append("Razorpay credentials missing")
if not has_webhook_secret:
    issues.append("Webhook secret missing")
if not webhook_url:
    issues.append("Webhook URL not configured - payments CANNOT be confirmed")

if issues:
    print("\n❌ CRITICAL ISSUES FOUND:")
    for issue in issues:
        print(f"   • {issue}")
else:
    print("\n✅ All core configuration appears correct")

print("\n" + "=" * 80)
