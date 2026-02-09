#!/usr/bin/env python
"""
Script to create admin user and sample products
Run with: python manage.py shell < create_test_data.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.contrib.auth.models import User
from Hub.models import Product

# Create superuser
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@vibemall.com', 'admin123')
    print("Admin user created: admin / admin123")
else:
    print("Admin user already exists")

# Create sample products with categories
if Product.objects.count() == 0:
    # TOP DEALS - 4 products
    top_deals = [
        {'name': 'Solo3 Wireless Headphones', 'price': 200.00, 'old_price': 270.00, 'stock': 15, 'discount_percent': 25},
        {'name': 'Beats Studio Pro', 'price': 180.00, 'old_price': 250.00, 'stock': 12, 'discount_percent': 28},
        {'name': 'AirPods Max', 'price': 220.00, 'old_price': 300.00, 'stock': 8, 'discount_percent': 26},
        {'name': 'JBL Flip 6', 'price': 95.00, 'old_price': 130.00, 'stock': 20, 'discount_percent': 26},
    ]

    # TOP SELLING - 4 products
    top_selling = [
        {'name': 'iPhone 15 Case', 'price': 25.00, 'old_price': 35.00, 'stock': 50, 'discount_percent': 28},
        {'name': 'USB-C Cable', 'price': 12.00, 'old_price': 18.00, 'stock': 100, 'discount_percent': 33},
        {'name': 'Wireless Charger', 'price': 35.00, 'old_price': 50.00, 'stock': 30, 'discount_percent': 30},
        {'name': 'Phone Stand', 'price': 15.00, 'old_price': 22.00, 'stock': 45, 'discount_percent': 31},
    ]

    # TOP FEATURED - 4 products
    top_featured = [
        {'name': 'Premium Laptop Backpack', 'price': 75.00, 'old_price': 110.00, 'stock': 18, 'discount_percent': 31},
        {'name': 'Mechanical Keyboard', 'price': 85.00, 'old_price': 120.00, 'stock': 25, 'discount_percent': 29},
        {'name': 'Wireless Mouse', 'price': 35.00, 'old_price': 50.00, 'stock': 40, 'discount_percent': 30},
        {'name': 'Monitor Stand', 'price': 45.00, 'old_price': 65.00, 'stock': 22, 'discount_percent': 30},
    ]

    # RECOMMENDED - 4 products
    recommended = [
        {'name': 'Desk Lamp LED', 'price': 55.00, 'old_price': 80.00, 'stock': 35, 'discount_percent': 31},
        {'name': 'Cable Organizer', 'price': 18.00, 'old_price': 28.00, 'stock': 60, 'discount_percent': 35},
        {'name': 'USB Hub 7-Port', 'price': 42.00, 'old_price': 60.00, 'stock': 28, 'discount_percent': 30},
        {'name': 'Webcam HD', 'price': 65.00, 'old_price': 95.00, 'stock': 15, 'discount_percent': 31},
    ]

    categories = {
        'TOP_DEALS': top_deals,
        'TOP_SELLING': top_selling,
        'TOP_FEATURED': top_featured,
        'RECOMMENDED': recommended,
    }

    for category, products_data in categories.items():
        for data in products_data:
            product = Product.objects.create(
                name=data['name'],
                price=data['price'],
                old_price=data['old_price'],
                stock=data['stock'],
                discount_percent=data['discount_percent'],
                category=category,
                is_active=True,
                rating=3 if category == 'RECOMMENDED' else 4,
                review_count=20
            )
            print(f"Product created: {product.name} (Category: {category}, ID: {product.id})")
else:
    print(f"{Product.objects.count()} products already exist")
