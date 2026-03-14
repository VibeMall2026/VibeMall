"""
Test script for ModelScanner functionality.

This script tests the ModelScanner to ensure it correctly identifies
models and their database table status.
"""

import os
import sys

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.activation_tools import ModelScanner


def test_model_scanner():
    """Test the ModelScanner functionality."""
    print("=" * 80)
    print("Testing ModelScanner")
    print("=" * 80)
    
    # Initialize scanner
    scanner = ModelScanner(app_name='Hub')
    
    # Test 1: Get model files
    print("\n1. Model Files Found:")
    print("-" * 80)
    for file_path in scanner.model_files:
        print(f"  - {os.path.basename(file_path)}")
    
    # Test 2: Scan all models
    print("\n2. Scanning All Models:")
    print("-" * 80)
    all_models = scanner.scan_model_files()
    print(f"Total models found: {len(all_models)}")
    
    # Test 3: Get model counts
    print("\n3. Model Counts:")
    print("-" * 80)
    counts = scanner.get_model_count()
    print(f"  Total models: {counts['total']}")
    print(f"  Models with tables: {counts['with_tables']}")
    print(f"  Models without tables: {counts['without_tables']}")
    
    # Test 4: Models by file
    print("\n4. Models by File:")
    print("-" * 80)
    models_by_file = scanner.get_models_by_file()
    for file_path, models in models_by_file.items():
        print(f"\n  {os.path.basename(file_path)} ({len(models)} models):")
        for model in models[:3]:  # Show first 3 models per file
            status = "✓ Has table" if model.has_table else "✗ No table"
            print(f"    - {model.name}: {status}")
        if len(models) > 3:
            print(f"    ... and {len(models) - 3} more")
    
    # Test 5: Models without tables
    print("\n5. Models Without Tables:")
    print("-" * 80)
    models_without_tables = scanner.get_models_without_tables()
    if models_without_tables:
        print(f"Found {len(models_without_tables)} models without tables:")
        for model in models_without_tables[:10]:  # Show first 10
            print(f"  - {model.name} (from {os.path.basename(model.file_path)})")
            print(f"    Expected table: {model.table_name}")
            if model.foreign_keys:
                print(f"    Foreign keys: {', '.join([f'{fk[0]} -> {fk[1]}' for fk in model.foreign_keys[:3]])}")
        if len(models_without_tables) > 10:
            print(f"  ... and {len(models_without_tables) - 10} more")
    else:
        print("All models have database tables!")
    
    # Test 6: Sample model details
    print("\n6. Sample Model Details:")
    print("-" * 80)
    if all_models:
        sample_model = all_models[0]
        print(f"Model: {sample_model.name}")
        print(f"File: {sample_model.file_path}")
        print(f"Table: {sample_model.table_name}")
        print(f"Has table: {sample_model.has_table}")
        print(f"Fields ({len(sample_model.fields)}):")
        for field in sample_model.fields[:5]:  # Show first 5 fields
            fk_info = f" -> {field.related_model}" if field.is_foreign_key else ""
            print(f"  - {field.name}: {field.field_type}{fk_info}")
        if len(sample_model.fields) > 5:
            print(f"  ... and {len(sample_model.fields) - 5} more fields")
    
    print("\n" + "=" * 80)
    print("ModelScanner Test Complete")
    print("=" * 80)


if __name__ == '__main__':
    test_model_scanner()
