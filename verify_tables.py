#!/usr/bin/env python
"""
Verification script to check that all Django models have corresponding database tables.
This script is for Task 6 checkpoint verification.
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.apps import apps
from django.db import connection

def verify_all_tables():
    """Verify that all models have corresponding database tables."""
    
    # Get all models from the Hub app
    hub_models = list(apps.get_app_config('Hub').get_models())
    
    # Get list of existing tables in the database
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}
    
    print(f"Total models in Hub app: {len(hub_models)}")
    print(f"Total tables in database: {len(existing_tables)}")
    print("\n" + "="*80)
    
    missing_tables = []
    models_with_tables = []
    
    for model in hub_models:
        table_name = model._meta.db_table
        if table_name in existing_tables:
            models_with_tables.append((model.__name__, table_name))
        else:
            missing_tables.append((model.__name__, table_name))
    
    # Display results
    print(f"\n✓ Models with tables: {len(models_with_tables)}")
    print(f"✗ Models without tables: {len(missing_tables)}")
    print("="*80)
    
    if missing_tables:
        print("\n⚠ MISSING TABLES:")
        for model_name, table_name in sorted(missing_tables):
            print(f"  - {model_name} → {table_name}")
        print("\n" + "="*80)
        return False
    else:
        print("\n✓ SUCCESS: All models have corresponding database tables!")
        print("\nModels verified:")
        for model_name, table_name in sorted(models_with_tables)[:10]:
            print(f"  ✓ {model_name} → {table_name}")
        if len(models_with_tables) > 10:
            print(f"  ... and {len(models_with_tables) - 10} more models")
        print("\n" + "="*80)
        return True

if __name__ == '__main__':
    success = verify_all_tables()
    sys.exit(0 if success else 1)
