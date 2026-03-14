#!/usr/bin/env python
"""
Test script for AdminScanner functionality.

This script tests the AdminScanner class to verify it correctly identifies
registered and unregistered models in Hub/admin.py.
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.activation_tools import AdminScanner, ModelScanner


def test_admin_scanner():
    """Test AdminScanner functionality."""
    print("=" * 70)
    print("TESTING ADMIN SCANNER")
    print("=" * 70)
    print()
    
    # Initialize scanner
    print("1. Initializing AdminScanner...")
    scanner = AdminScanner(app_name='Hub')
    print(f"   Admin file path: {scanner.admin_file_path}")
    print(f"   File exists: {os.path.exists(scanner.admin_file_path)}")
    print()
    
    # Get registered models
    print("2. Scanning registered models in admin.py...")
    registered_models = scanner.get_registered_models()
    print(f"   Found {len(registered_models)} registered models")
    print()
    
    # Show some registered models
    if registered_models:
        print("   Sample registered models:")
        for model_name in sorted(list(registered_models))[:10]:
            print(f"     ✓ {model_name}")
        if len(registered_models) > 10:
            print(f"     ... and {len(registered_models) - 10} more")
        print()
    
    # Get all models
    print("3. Scanning all models in Hub app...")
    model_scanner = ModelScanner(app_name='Hub')
    all_models = model_scanner.scan_model_files()
    print(f"   Found {len(all_models)} total models")
    print()
    
    # Get unregistered models
    print("4. Identifying unregistered models...")
    unregistered_models = scanner.get_unregistered_models(all_models)
    print(f"   Found {len(unregistered_models)} unregistered models")
    print()
    
    # Show unregistered models by file
    if unregistered_models:
        print("   Unregistered models by file:")
        unregistered_by_file = {}
        for model in unregistered_models:
            if model.file_path not in unregistered_by_file:
                unregistered_by_file[model.file_path] = []
            unregistered_by_file[model.file_path].append(model.name)
        
        for file_path, model_names in sorted(unregistered_by_file.items()):
            print(f"     {file_path}:")
            for model_name in sorted(model_names):
                print(f"       ✗ {model_name}")
        print()
    
    # Generate full report
    print("5. Generating comprehensive registration report...")
    report = scanner.get_registration_report(all_models)
    print()
    print(scanner.generate_registration_report_text(report))
    
    # Summary
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Total Models: {report['total_models']}")
    print(f"Registered: {report['registered_count']} ({report['registration_percentage']:.1f}%)")
    print(f"Unregistered: {report['unregistered_count']}")
    print()
    
    if report['unregistered_count'] == 0:
        print("✓ SUCCESS: All models are registered in Django admin!")
    else:
        print(f"⚠ INFO: {report['unregistered_count']} models need registration")
    
    print("=" * 70)
    
    return report


if __name__ == '__main__':
    try:
        report = test_admin_scanner()
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
