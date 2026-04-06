#!/usr/bin/env python
"""
Test Razorpay UPI verification with detailed logging
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.conf import settings
import json
import base64
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

print("Testing Razorpay VPA Validation API")
print("=" * 60)

razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', '')
razorpay_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

print(f"Key: {razorpay_key[:15]}...")
print(f"Secret: {razorpay_secret[:15]}...")

# The endpoint that might be wrong
url = 'https://api.razorpay.com/v1/payments/validate/vpa'
upi_id = 'test@okhdfcbank'

print(f"\nEndpoint: {url}")
print(f"Testing UPI: {upi_id}")

payload = urlencode({'vpa': upi_id}).encode('utf-8')
auth = base64.b64encode(f"{razorpay_key}:{razorpay_secret}".encode('utf-8')).decode('utf-8')

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': f'Basic {auth}',
}

print(f"\nRequest Headers:")
print(f"  Authorization: Basic {auth[:20]}...")
print(f"  Content-Type: {headers['Content-Type']}")
print(f"\nRequest Payload: {urlencode({'vpa': upi_id})}")

request = Request(url, data=payload, headers=headers, method='POST')

try:
    print("\nSending request...")
    with urlopen(request, timeout=10) as response:
        response_data = response.read().decode('utf-8')
        print(f"\n✓ SUCCESS (HTTP {response.status})")
        print(f"Response: {response_data}")
except HTTPError as exc:
    print(f"\n✗ HTTP ERROR: {exc.code}")
    body = exc.read().decode('utf-8')
    print(f"Response body: {body}")
    
    # Try to parse error
    try:
        error_json = json.loads(body)
        print(f"Parsed error: {json.dumps(error_json, indent=2)}")
    except:
        pass
        
except URLError as exc:
    print(f"\n✗ URL ERROR: {exc.reason}")
except Exception as exc:
    print(f"\n✗ ERROR: {exc}")

print("\n" + "=" * 60)
print("\nPOSSIBLE SOLUTIONS:\n")
print("1. The Razorpay endpoint might be deprecated or incorrect")
print("2. Alternative endpoint to check: https://api.razorpay.com/v1/fund_account/validation")
print("3. Or use: https://api.razorpay.com/v1/validations/vpa")
print("4. Check Razorpay API docs: https://razorpay.com/docs/")
