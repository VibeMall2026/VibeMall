#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import Product

print("=" * 60)
print("PRODUCT DATABASE STATUS")
print("=" * 60)

total = Product.objects.count()
print(f"Total Products: {total}")
print()

if total == 0:
    print("ERROR: No products in database!")
else:
    print("First 10 products:")
    for i, p in enumerate(Product.objects.all()[:10], 1):
        has_image = 'Yes' if p.image else 'No'
        active = getattr(p, 'is_active', 'N/A')
        print(f"{i:2}. {p.name:30} | Category: {p.category:12} | Image: {has_image} | Active: {active}")
    
    print()
    print("Products by category:")
    for category_code, category_name in Product.CATEGORY_CHOICES:
        count = Product.objects.filter(category=category_code).count()
        if count > 0:
            print(f"  ✓ {category_name:.<30} {count:>2} products")
