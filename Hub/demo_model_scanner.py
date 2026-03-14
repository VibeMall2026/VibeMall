"""
Demonstration script for ModelScanner.

This script demonstrates the ModelScanner's ability to:
1. Scan all model files in the Hub app
2. Extract model definitions and field information
3. Identify models without database tables
4. Organize models by their source files
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


def main():
    """Demonstrate ModelScanner functionality."""
    print("\n" + "=" * 80)
    print("ModelScanner Demonstration")
    print("=" * 80)
    
    # Initialize scanner
    scanner = ModelScanner(app_name='Hub')
    
    # Get model counts
    counts = scanner.get_model_count()
    
    print(f"\n📊 Summary:")
    print(f"  • Total models found: {counts['total']}")
    print(f"  • Models with tables: {counts['with_tables']}")
    print(f"  • Models without tables: {counts['without_tables']}")
    
    # Show models by file
    print(f"\n📁 Models by File:")
    models_by_file = scanner.get_models_by_file()
    for file_path, models in sorted(models_by_file.items()):
        filename = os.path.basename(file_path)
        print(f"\n  {filename} ({len(models)} models)")
        for model in models[:3]:
            status = "✓" if model.has_table else "✗"
            fk_count = len(model.foreign_keys)
            fk_info = f" ({fk_count} FKs)" if fk_count > 0 else ""
            print(f"    {status} {model.name}{fk_info}")
        if len(models) > 3:
            print(f"    ... and {len(models) - 3} more")
    
    # Show models without tables (if any)
    models_without_tables = scanner.get_models_without_tables()
    if models_without_tables:
        print(f"\n⚠️  Models Without Tables ({len(models_without_tables)}):")
        for model in models_without_tables[:10]:
            print(f"  • {model.name}")
            print(f"    File: {os.path.basename(model.file_path)}")
            print(f"    Expected table: {model.table_name}")
            if model.foreign_keys:
                fk_list = ', '.join([f"{fk[0]}->{fk[1]}" for fk in model.foreign_keys[:2]])
                print(f"    Foreign keys: {fk_list}")
        if len(models_without_tables) > 10:
            print(f"  ... and {len(models_without_tables) - 10} more")
    else:
        print(f"\n✅ All models have database tables!")
    
    print("\n" + "=" * 80)
    print("Task 2.1 Complete: ModelScanner successfully created and tested")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
