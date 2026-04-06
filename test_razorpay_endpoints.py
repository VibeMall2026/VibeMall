#!/usr/bin/env python
"""
Test alternative Razorpay UPI validation endpoints
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

razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', '')
razorpay_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

# Test different endpoint URLs
endpoints = [
    'https://api.razorpay.com/v1/validations/vpa',
    'https://api.razorpay.com/v1/fund_account/validation',
]

upi_id = 'ananya.sharma@okhdfcbank'

print("Testing Razorpay UPI Validation Endpoints")
print("=" * 70)

for url in endpoints:
    print(f"\nTesting: {url}")
    print("-" * 70)
    
    payload = urlencode({'vpa': upi_id}).encode('utf-8')
    auth = base64.b64encode(f"{razorpay_key}:{razorpay_secret}".encode('utf-8')).decode('utf-8')
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth}',
    }
    
    request = Request(url, data=payload, headers=headers, method='POST')
    
    try:
        with urlopen(request, timeout=10) as response:
            response_data = response.read().decode('utf-8')
            print(f"✓ SUCCESS (HTTP {response.status})")
            try:
                json_data = json.loads(response_data)
                print(f"Response:\n{json.dumps(json_data, indent=2)}")
            except:
                print(f"Response: {response_data}")
            
    except HTTPError as exc:
        print(f"✗ HTTP ERROR: {exc.code}")
        body = exc.read().decode('utf-8')
        try:
            error_json = json.loads(body)
            error_msg = error_json.get('error', {}).get('description', body)
            print(f"Error: {error_msg}")
        except:
            print(f"Error: {body[:200]}")
            
    except URLError as exc:
        print(f"✗ Connection Error: {exc.reason}")
    except Exception as exc:
        print(f"✗ Error: {type(exc).__name__}: {exc}")

print("\n" + "=" * 70)
print("\nRazorpay Documentation:")
print("- Main API docs: https://razorpay.com/docs/")
print("- VPA Validation: https://razorpay.com/docs/funds-management/validations/")
