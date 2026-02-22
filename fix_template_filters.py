#!/usr/bin/env python
"""
Script to check and fix missing template filter loads in HTML files
"""

import os
import re

def check_and_fix_templates():
    """Check all templates that use get_item filter and ensure they load custom_filters"""
    
    templates_to_check = [
        'Hub/templates/shop.html',
        'Hub/templates/index.html',
        'Hub/templates/review_enhanced.html',
        'Hub/templates/partials/mobile_product_swiper_card.html',
        'Hub/templates/admin_panel/main_page_products.html',
    ]
    
    print("=" * 60)
    print("Template Filter Load Check")
    print("=" * 60)
    
    for template_path in templates_to_check:
        if not os.path.exists(template_path):
            print(f"⚠️  {template_path} - NOT FOUND")
            continue
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if template uses get_item filter
        uses_get_item = '|get_item' in content
        
        # Check if custom_filters or hub_filters is loaded
        has_custom_filters = '{% load custom_filters %}' in content
        has_hub_filters = '{% load hub_filters %}' in content
        
        if uses_get_item:
            if has_custom_filters or has_hub_filters:
                filter_type = 'custom_filters' if has_custom_filters else 'hub_filters'
                print(f"✅ {template_path}")
                print(f"   Uses get_item: Yes")
                print(f"   Loads {filter_type}: Yes")
            else:
                print(f"❌ {template_path}")
                print(f"   Uses get_item: Yes")
                print(f"   Loads filters: NO - NEEDS FIX!")
                
                # Try to fix by adding load statement after {% load static %}
                if '{% load static %}' in content:
                    content = content.replace(
                        '{% load static %}',
                        '{% load static %}\n{% load custom_filters %}'
                    )
                    
                    with open(template_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"   ✅ FIXED: Added {{% load custom_filters %}}")
        else:
            print(f"ℹ️  {template_path}")
            print(f"   Uses get_item: No (skipped)")
        
        print()
    
    print("=" * 60)
    print("✅ Check complete!")
    print("=" * 60)
    print("\n📝 Note: Restart Django server for changes to take effect")
    print("   python manage.py runserver")

if __name__ == "__main__":
    check_and_fix_templates()
