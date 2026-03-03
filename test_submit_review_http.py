#!/usr/bin/env python
"""Test the actual submit_review view endpoint"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth.models import User

print("=" * 80)
print("TESTING: Full submit_review HTTP Request")
print("=" * 80)

# Get test product
from Hub.models import Product

product = Product.objects.filter(is_active=True).first()
if not product:
    print("✗ No active products found")
    sys.exit(1)

print(f"\n✓ Found product: {product.name} (ID: {product.id})")

# Create or get test user
user, created = User.objects.get_or_create(
    username='test_reviewer_http',
    defaults={'email': 'test@example.com'}
)
print(f"✓ Using user: {user.username}")

# Use Django test client to submit review
client = Client()

print(f"\nStep 1: Simulating POST /product/{product.id}/submit-review/")
try:
    response = client.post(
        f'/product/{product.id}/submit-review/',
        {
            'rating': '5',
            'comment': '<p>Great <b>product</b>!</p>',
            'name': '<script>xss</script>John',
            'email': 'reviewer@test.com'
        },
        follow=True
    )
    
    print(f"  Status Code: {response.status_code}")
    if response.status_code != 200:
        print(f"  ✗ ERROR: Expected 200, got {response.status_code}")
        print(f"  Response Content (first 500 chars):\n{response.content[:500]}")
        sys.exit(1)
    
    print(f"  ✓ Request processed successfully")
    
except Exception as e:
    print(f"  ✗ EXCEPTION during POST: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\nStep 2: Verifying review was sanitized and saved")
try:
    from Hub.models import ProductReview
    
    # Get the most recent review
    review = ProductReview.objects.filter(product=product).order_by('-created_at').first()
    if not review:
        print("  ✗ No review found in database")
        sys.exit(1)
    
    print(f"  Review ID: {review.id}")
    print(f"  Name (should be sanitized): '{review.name}'")
    print(f"  Comment (should be sanitized): '{review.comment}'")
    print(f"  Email: '{review.email}'")
    
    # Verify no script tags in name
    if '<script>' in review.name or 'xss' in review.name:
        print(f"  ✗ SECURITY ISSUE: Name contains malicious content!")
        sys.exit(1)
    
    print(f"  ✓ Data properly sanitized")
    
    # Clean up
    review.delete()
    print(f"  ✓ Test review cleaned up")
    
except Exception as e:
    print(f"  ✗ EXCEPTION verifying review: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("✓ ALL HTTP TESTS PASSED!")
print("=" * 80)
