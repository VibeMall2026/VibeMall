"""
Demonstration of AdminCodeGenerator functionality.

This script shows how AdminCodeGenerator generates admin registration code
for unregistered models.
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

from Hub.activation_tools import AdminCodeGenerator, AdminScanner, ModelScanner


def main():
    print("=" * 70)
    print("AdminCodeGenerator Demonstration")
    print("=" * 70)
    print()
    
    # Initialize components
    scanner = ModelScanner()
    admin_scanner = AdminScanner()
    generator = AdminCodeGenerator()
    
    # Step 1: Scan all models
    print("Step 1: Scanning all models...")
    all_models = scanner.scan_model_files()
    print(f"  Found {len(all_models)} total models")
    print()
    
    # Step 2: Identify unregistered models
    print("Step 2: Identifying unregistered models...")
    unregistered_models = admin_scanner.get_unregistered_models(all_models)
    print(f"  Found {len(unregistered_models)} unregistered models")
    print()
    
    if not unregistered_models:
        print("All models are already registered!")
        return
    
    # Step 3: Show a few examples
    print("Step 3: Example registration code for first 3 unregistered models:")
    print()
    
    for model in unregistered_models[:3]:
        print(f"Model: {model.name} (from {model.file_path})")
        print(f"Fields: {len(model.fields)} fields")
        
        # Get list_display fields
        list_display = generator.get_list_display_fields(model)
        print(f"Selected list_display fields: {list_display}")
        print()
        
        # Generate registration code
        code = generator.generate_registration_code(model)
        print("Generated code:")
        print("-" * 70)
        print(code)
        print("-" * 70)
        print()
    
    # Step 4: Generate summary
    print("Step 4: Registration summary for all unregistered models:")
    print()
    
    summary_report = generator.generate_summary_report(unregistered_models)
    print(summary_report)
    print()
    
    # Step 5: Show how to generate complete code with imports
    print("Step 5: Complete registration code (first 5 models):")
    print()
    
    complete_code = generator.generate_registration_with_imports(unregistered_models[:5])
    print(complete_code)
    print()
    
    print("=" * 70)
    print("Demonstration complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
