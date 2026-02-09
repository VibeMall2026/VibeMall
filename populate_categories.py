"""
Script to populate initial CategoryIcon data
Run: python populate_categories.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import CategoryIcon


def populate_categories():
    """Create initial category icons"""

    categories = [
        {
            'name': 'Mobiles',
            'icon_class': 'fas fa-mobile-alt',
            'category_key': 'MOBILES',
            'background_gradient': 'linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)',
            'icon_color': '#0288d1',
            'order': 1
        },
        {
            'name': 'Food & Health',
            'icon_class': 'fas fa-apple-alt',
            'category_key': 'FOOD_HEALTH',
            'background_gradient': 'linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)',
            'icon_color': '#0288d1',
            'order': 2
        },
        {
            'name': 'Home & Kitchen',
            'icon_class': 'fas fa-blender',
            'category_key': 'HOME_KITCHEN',
            'background_gradient': 'linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)',
            'icon_color': '#0288d1',
            'order': 3
        },
        {
            'name': 'Auto Acc',
            'icon_class': 'fas fa-car',
            'category_key': 'AUTO_ACC',
            'background_gradient': 'linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)',
            'icon_color': '#0288d1',
            'order': 4
        },
        {
            'name': 'Furniture',
            'icon_class': 'fas fa-couch',
            'category_key': 'FURNITURE',
            'background_gradient': 'linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)',
            'icon_color': '#0288d1',
            'order': 5
        },
        {
            'name': 'Sports',
            'icon_class': 'fas fa-futbol',
            'category_key': 'SPORTS',
            'background_gradient': 'linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)',
            'icon_color': '#0288d1',
            'order': 6
        },
        {
            'name': 'GenZ Trends',
            'icon_class': 'fas fa-tshirt',
            'category_key': 'GENZ_TRENDS',
            'background_gradient': 'linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)',
            'icon_color': '#0288d1',
            'order': 7
        },
        {
            'name': 'Next Gen',
            'icon_class': 'fas fa-hand-peace',
            'category_key': 'NEXT_GEN',
            'background_gradient': 'linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)',
            'icon_color': '#0288d1',
            'order': 8
        },
    ]

    created_count = 0
    updated_count = 0

    for category_data in categories:
        category, created = CategoryIcon.objects.update_or_create(
            category_key=category_data['category_key'],
            defaults=category_data
        )

        if created:
            created_count += 1
            print(f"Created: {category.name}")
        else:
            updated_count += 1
            print(f"Updated: {category.name}")

    print("\nSummary:")
    print(f"   Created: {created_count} categories")
    print(f"   Updated: {updated_count} categories")
    print(f"   Total: {CategoryIcon.objects.count()} categories in database")
    print("\nCategory icons populated successfully.")
    print("   You can now edit them in the admin panel at /admin/")


if __name__ == '__main__':
    populate_categories()
