#!/usr/bin/env python
"""Test sanitizer module in Django context"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.sanitizer import sanitize_text, sanitize_email

# Test exactly what happens when a review is submitted
test_name = "<script>xss</script>John Doe"
test_comment = "<p>Great product</p>"
test_email = "test@example.com"

try:
    print("Testing sanitization...")
    name_clean = sanitize_text(test_name)
    comment_clean = sanitize_text(test_comment)
    email_clean = sanitize_email(test_email)
    
    print("✓ SUCCESS: All sanitization functions work!")
    print(f"  Name: {name_clean}")
    print(f"  Comment: {comment_clean}")
    print(f"  Email: {email_clean}")
except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
