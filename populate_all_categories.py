#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import Product

# Add MOBILES products
print("Creating MOBILES products...")
mobiles = [
    {'name': 'iPhone 15 Pro', 'price': 999, 'old_price': 1099},
    {'name': 'Samsung Galaxy S24', 'price': 899, 'old_price': 999},
    {'name': 'Google Pixel 8', 'price': 799, 'old_price': 899},
    {'name': 'OnePlus 12', 'price': 699, 'old_price': 799},
]
for data in mobiles:
    Product.objects.get_or_create(
        name=data['name'],
        defaults={'price': data['price'], 'old_price': data['old_price'], 'category': 'MOBILES', 'is_active': True, 'stock': 20}
    )
print(f"  Added {len(mobiles)} mobile products")

# Add FOOD_HEALTH products
print("Creating FOOD_HEALTH products...")
food = [
    {'name': 'Organic Green Tea', 'price': 12, 'old_price': 15},
    {'name': 'Protein Powder', 'price': 35, 'old_price': 45},
    {'name': 'Vitamin Supplements', 'price': 18, 'old_price': 25},
    {'name': 'Honey Jar', 'price': 8, 'old_price': 12},
]
for data in food:
    Product.objects.get_or_create(
        name=data['name'],
        defaults={'price': data['price'], 'old_price': data['old_price'], 'category': 'FOOD_HEALTH', 'is_active': True, 'stock': 50}
    )
print(f"  Added {len(food)} food/health products")

# Add HOME_KITCHEN products
print("Creating HOME_KITCHEN products...")
home = [
    {'name': 'Stainless Steel Knife Set', 'price': 45, 'old_price': 60},
    {'name': 'Non-stick Frying Pan', 'price': 35, 'old_price': 50},
    {'name': 'Coffee Maker', 'price': 55, 'old_price': 75},
    {'name': 'Microwave Oven', 'price': 120, 'old_price': 150},
]
for data in home:
    Product.objects.get_or_create(
        name=data['name'],
        defaults={'price': data['price'], 'old_price': data['old_price'], 'category': 'HOME_KITCHEN', 'is_active': True, 'stock': 15}
    )
print(f"  Added {len(home)} home/kitchen products")

# Add AUTO_ACC products
print("Creating AUTO_ACC products...")
auto = [
    {'name': 'Car Phone Mount', 'price': 15, 'old_price': 22},
    {'name': 'Dash Cam HD', 'price': 85, 'old_price': 120},
    {'name': 'Car Air Freshener', 'price': 8, 'old_price': 12},
    {'name': 'USB Car Charger', 'price': 18, 'old_price': 25},
]
for data in auto:
    Product.objects.get_or_create(
        name=data['name'],
        defaults={'price': data['price'], 'old_price': data['old_price'], 'category': 'AUTO_ACC', 'is_active': True, 'stock': 30}
    )
print(f"  Added {len(auto)} auto accessories")

# Add FURNITURE products
print("Creating FURNITURE products...")
furniture = [
    {'name': 'Office Chair', 'price': 180, 'old_price': 250},
    {'name': 'Desk Wooden', 'price': 220, 'old_price': 300},
    {'name': 'Book Shelf', 'price': 95, 'old_price': 130},
    {'name': 'Sofa Set', 'price': 450, 'old_price': 600},
]
for data in furniture:
    Product.objects.get_or_create(
        name=data['name'],
        defaults={'price': data['price'], 'old_price': data['old_price'], 'category': 'FURNITURE', 'is_active': True, 'stock': 8}
    )
print(f"  Added {len(furniture)} furniture products")

# Add SPORTS products
print("Creating SPORTS products...")
sports = [
    {'name': 'Yoga Mat', 'price': 25, 'old_price': 35},
    {'name': 'Dumbbells Set', 'price': 65, 'old_price': 85},
    {'name': 'Running Shoes', 'price': 85, 'old_price': 120},
    {'name': 'Bicycle', 'price': 250, 'old_price': 350},
]
for data in sports:
    Product.objects.get_or_create(
        name=data['name'],
        defaults={'price': data['price'], 'old_price': data['old_price'], 'category': 'SPORTS', 'is_active': True, 'stock': 12}
    )
print(f"  Added {len(sports)} sports products")

# Add GENZ_TRENDS products
print("Creating GENZ_TRENDS products...")
genz = [
    {'name': 'Trendy Backpack', 'price': 45, 'old_price': 65},
    {'name': 'LED Lights', 'price': 28, 'old_price': 40},
    {'name': 'Phone Ring Stand', 'price': 12, 'old_price': 18},
    {'name': 'Polaroid Camera', 'price': 95, 'old_price': 130},
]
for data in genz:
    Product.objects.get_or_create(
        name=data['name'],
        defaults={'price': data['price'], 'old_price': data['old_price'], 'category': 'GENZ_TRENDS', 'is_active': True, 'stock': 25}
    )
print(f"  Added {len(genz)} GenZ trend products")

# Add NEXT_GEN products
print("Creating NEXT_GEN products...")
nextgen = [
    {'name': 'Smart Watch', 'price': 199, 'old_price': 280},
    {'name': 'Wireless Earbuds', 'price': 79, 'old_price': 120},
    {'name': 'Smart Home Hub', 'price': 89, 'old_price': 130},
    {'name': 'Bluetooth Speaker', 'price': 65, 'old_price': 95},
]
for data in nextgen:
    Product.objects.get_or_create(
        name=data['name'],
        defaults={'price': data['price'], 'old_price': data['old_price'], 'category': 'NEXT_GEN', 'is_active': True, 'stock': 18}
    )
print(f"  Added {len(nextgen)} next-gen products")

print(f"\n✅ Total products in database: {Product.objects.count()}")
