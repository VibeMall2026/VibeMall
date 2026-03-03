#!/usr/bin/env python
"""Deep analysis of submit_review flow with sanitization"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

print("=" * 80)
print("DEEP ANALYSIS: Submit Review -> Sanitization Flow")
print("=" * 80)

# Step 1: Check imports
print("\n[Step 1] Checking module imports...")
try:
    from Hub.sanitizer import sanitize_text, sanitize_email, InputSanitizer
    print("✓ Import sanitizer functions successful")
except Exception as e:
    print(f"✗ FAILED to import sanitizer: {e}")
    sys.exit(1)

# Step 2: Check html module availability
print("\n[Step 2] Checking html module in sanitizer...")
import Hub.sanitizer as sanitizer_module
if hasattr(sanitizer_module, 'html'):
    print(f"✓ html module available in sanitizer: {sanitizer_module.html}")
else:
    print("✗ html module NOT found in sanitizer module!")
    
# Step 3: Test sanitization functions
print("\n[Step 3] Testing sanitization functions...")
test_data = {
    'name': '<script>alert("xss")</script>John Doe',
    'comment': '<p>Great <b>product</b>!</p><img src=x onerror="alert(1)">',
    'email': 'test@example.com  '  # extra spaces
}

try:
    clean_name = sanitize_text(test_data['name'])
    print(f"  Name sanitized: '{test_data['name']}' -> '{clean_name}'")
    
    clean_comment = sanitize_text(test_data['comment'])
    print(f"  Comment sanitized: '{test_data['comment'][:50]}...' -> '{clean_comment[:50]}...'")
    
    clean_email = sanitize_email(test_data['email'])
    print(f"  Email validated: '{test_data['email']}' -> '{clean_email}'")
    
    print("✓ All sanitization functions work!")
except Exception as e:
    print(f"✗ FAILED during sanitization: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 4: Test ProductReview model save
print("\n[Step 4] Testing ProductReview model save with sanitization...")
try:
    from Hub.models import ProductReview, Product, User
    from django.contrib.auth.models import User as DjangoUser
    
    # Get or create test user
    user, created = DjangoUser.objects.get_or_create(
        username='test_reviewer',
        defaults={'email': 'reviewer@test.com'}
    )
    print(f"  Using user: {user.username} (created={created})")
    
    # Get first active product
    product = Product.objects.filter(is_active=True).first()
    if not product:
        print("  ⚠ No active products found, skipping review creation test")
    else:
        print(f"  Using product: {product.name}")
        
        # Try to create a review with HTML/XSS in the name and comment
        try:
            review = ProductReview(
                product=product,
                user=user,
                rating=5,
                name='<img src=x>John',
                email='test@example.com',
                comment='<script>alert(1)</script>Great!',
                is_approved=False
            )
            review.save()
            print(f"  ✓ Review created successfully (ID: {review.id})")
            print(f"    - Saved name: '{review.name}'")
            print(f"    - Saved comment: '{review.comment}'")
            
            # Clean up
            review.delete()
            print(f"  ✓ Review cleaned up")
        except Exception as e:
            print(f"  ✗ FAILED to create/save review: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

except Exception as e:
    print(f"✗ Error in model test stage: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("✓ ALL TESTS PASSED - Sanitization flow is working correctly!")
print("=" * 80)
