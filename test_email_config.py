#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.conf import settings
import smtplib
import socket

print("=" * 60)
print("EMAIL CONFIGURATION TEST")
print("=" * 60)

# Check email configuration
print(f"\n1. Email Configuration:")
print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"   EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
print(f"   DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")

# Check if credentials are placeholders
if 'replace_with_' in settings.EMAIL_HOST_PASSWORD:
    print("\n   ⚠️  WARNING: EMAIL_HOST_PASSWORD contains 'replace_with_' placeholder!")
    sys.exit(1)

if 'replace_with_' in settings.EMAIL_HOST_USER:
    print("\n   ⚠️  WARNING: EMAIL_HOST_USER contains 'replace_with_' placeholder!")
    sys.exit(1)

print("\n2. Testing Gmail SMTP Connection...")
try:
    # Test connection and authentication
    server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10)
    print(f"   ✓ Connected to {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
    
    server.starttls()
    print(f"   ✓ TLS encryption enabled")
    
    server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
    print(f"   ✓ Authentication successful for {settings.EMAIL_HOST_USER}")
    
    server.quit()
    print("\n✓ Gmail SMTP Configuration is VALID and WORKING!")
    print("=" * 60)
    
except smtplib.SMTPAuthenticationError as e:
    print(f"\n   ✗ AUTHENTICATION FAILED")
    print(f"   Error: {e}")
    print(f"\n   Fix: Check your Gmail App Password in .env file")
    sys.exit(1)
except socket.timeout:
    print(f"\n   ✗ CONNECTION TIMEOUT")
    print(f"   Error: Could not reach {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
    sys.exit(1)
except Exception as e:
    print(f"\n   ✗ ERROR: {str(e)}")
    sys.exit(1)
