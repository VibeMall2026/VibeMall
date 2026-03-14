"""
Test script for AdminVerifier functionality.

This script tests that AdminVerifier can:
1. Verify models appear at /admin/
2. Test list, add, and change views load without errors
3. Update ModelActivationStatus records
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.activation_tools import AdminVerifier, AdminScanner, ModelScanner


def test_admin_verifier():
    """Test AdminVerifier functionality."""
    
    print("=" * 70)
    print("TESTING ADMINVERIFIER")
    print("=" * 70)
    print()
    
    # Initialize components
    print("Initializing AdminVerifier, AdminScanner, and ModelScanner...")
    verifier = AdminVerifier()
    scanner = AdminScanner()
    model_scanner = ModelScanner()
    
    # Get all models
    print("Scanning all models...")
    all_models = model_scanner.scan_model_files()
    print(f"Found {len(all_models)} total models")
    print()
    
    # Get registered models
    print("Checking registered models...")
    registered_models = scanner.get_registered_models()
    print(f"Found {len(registered_models)} registered models")
    print()
    
    # Filter to only test a few registered models (for speed)
    test_models = [m for m in all_models if m.name in registered_models][:5]
    
    if not test_models:
        print("No registered models found to test!")
        return
    
    print(f"Testing {len(test_models)} registered models:")
    for model in test_models:
        print(f"  - {model.name}")
    print()
    
    # Test individual model verification
    print("-" * 70)
    print("TEST 1: Verify individual model in admin")
    print("-" * 70)
    
    test_model = test_models[0]
    print(f"Testing model: {test_model.name}")
    
    in_admin = verifier.verify_model_in_admin(test_model.name)
    print(f"  Model in admin: {in_admin}")
    
    if in_admin:
        print("  ✓ Model successfully found in admin")
    else:
        print("  ✗ Model not found in admin")
    print()
    
    # Test admin views
    print("-" * 70)
    print("TEST 2: Test admin views (list, add, change)")
    print("-" * 70)
    
    print(f"Testing views for: {test_model.name}")
    result = verifier.test_admin_views(test_model.name)
    
    print(f"  In admin: {result['in_admin']}")
    print(f"  List view status: {result['list_view_status']} - {'✓' if result['list_view_success'] else '✗'}")
    print(f"  Add view status: {result['add_view_status']} - {'✓' if result['add_view_success'] else '✗'}")
    print(f"  Change view status: {result['change_view_status']} - {'✓' if result['change_view_success'] else '✗'}")
    
    if result['error_message']:
        print(f"  Errors: {result['error_message']}")
    print()
    
    # Test updating activation status
    print("-" * 70)
    print("TEST 3: Update ModelActivationStatus records")
    print("-" * 70)
    
    print(f"Updating activation status for: {test_model.name}")
    verifier.update_activation_status(test_model.name, result)
    
    # Verify the update
    from Hub.models_activation_tracking import ModelActivationStatus
    
    try:
        status = ModelActivationStatus.objects.get(model_name=test_model.name)
        print(f"  Model name: {status.model_name}")
        print(f"  Admin registered: {status.admin_registered}")
        print(f"  Admin verified: {status.admin_verified}")
        print(f"  Error message: {status.error_message or 'None'}")
        print("  ✓ Status record updated successfully")
    except ModelActivationStatus.DoesNotExist:
        print("  ✗ Status record not found")
    print()
    
    # Test bulk verification
    print("-" * 70)
    print("TEST 4: Verify and update multiple models")
    print("-" * 70)
    
    print(f"Verifying {len(test_models)} models...")
    summary = verifier.verify_and_update_models(test_models)
    
    print()
    print("SUMMARY:")
    print(f"  Total models: {summary['total_models']}")
    print(f"  In admin: {summary['in_admin']}")
    print(f"  List view success: {summary['list_view_success']}")
    print(f"  Add view success: {summary['add_view_success']}")
    print(f"  Fully verified: {summary['fully_verified']}")
    print(f"  Failed: {summary['failed']}")
    print()
    
    # Generate and display report
    print("-" * 70)
    print("TEST 5: Generate verification report")
    print("-" * 70)
    print()
    
    report = verifier.generate_verification_report(summary)
    print(report)
    
    print()
    print("=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)


if __name__ == '__main__':
    try:
        test_admin_verifier()
    except Exception as e:
        print(f"Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
