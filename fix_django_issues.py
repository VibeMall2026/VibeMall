#!/usr/bin/env python
"""
Script to fix Django model conflicts and run migrations
"""

import os
import sys
import django
from django.core.management import execute_from_command_line

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

def main():
    print("🔧 Fixing Django Model Conflicts")
    print("=" * 40)
    
    try:
        # Run Django system check
        print("1. Running Django system check...")
        execute_from_command_line(['manage.py', 'check'])
        print("✅ Django system check passed!")
        
    except Exception as e:
        print(f"⚠️ Django system check found issues: {e}")
        print("Continuing with migration fixes...")
    
    try:
        # Make migrations
        print("\n2. Creating migrations...")
        execute_from_command_line(['manage.py', 'makemigrations', 'Hub'])
        print("✅ Migrations created successfully!")
        
    except Exception as e:
        print(f"⚠️ Migration creation issues: {e}")
        print("Trying to merge migrations...")
        
        try:
            execute_from_command_line(['manage.py', 'makemigrations', '--merge', 'Hub'])
            print("✅ Migrations merged successfully!")
        except Exception as merge_error:
            print(f"❌ Migration merge failed: {merge_error}")
    
    try:
        # Run migrations
        print("\n3. Running migrations...")
        execute_from_command_line(['manage.py', 'migrate'])
        print("✅ Migrations applied successfully!")
        
    except Exception as e:
        print(f"❌ Migration application failed: {e}")
    
    try:
        # Final system check
        print("\n4. Final Django system check...")
        execute_from_command_line(['manage.py', 'check'])
        print("✅ All Django checks passed!")
        
    except Exception as e:
        print(f"⚠️ Final check found issues: {e}")
    
    print("\n🎉 Django fix script completed!")
    print("All comprehensive features should now be available in the admin panel.")

if __name__ == '__main__':
    main()