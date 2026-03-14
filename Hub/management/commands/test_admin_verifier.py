"""
Django management command to test AdminVerifier functionality.
"""

from django.core.management.base import BaseCommand
from Hub.activation_tools import AdminVerifier, AdminScanner, ModelScanner


class Command(BaseCommand):
    help = 'Test AdminVerifier functionality'

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write("TESTING ADMINVERIFIER")
        self.stdout.write("=" * 70)
        self.stdout.write("")
        
        # Initialize components
        self.stdout.write("Initializing AdminVerifier, AdminScanner, and ModelScanner...")
        verifier = AdminVerifier()
        scanner = AdminScanner()
        model_scanner = ModelScanner()
        
        # Get all models
        self.stdout.write("Scanning all models...")
        all_models = model_scanner.scan_model_files()
        self.stdout.write(f"Found {len(all_models)} total models")
        self.stdout.write("")
        
        # Get registered models
        self.stdout.write("Checking registered models...")
        registered_models = scanner.get_registered_models()
        self.stdout.write(f"Found {len(registered_models)} registered models")
        self.stdout.write("")
        
        # Filter to only test a few registered models (for speed)
        test_models = [m for m in all_models if m.name in registered_models][:5]
        
        if not test_models:
            self.stdout.write(self.style.ERROR("No registered models found to test!"))
            return
        
        self.stdout.write(f"Testing {len(test_models)} registered models:")
        for model in test_models:
            self.stdout.write(f"  - {model.name}")
        self.stdout.write("")
        
        # Test individual model verification
        self.stdout.write("-" * 70)
        self.stdout.write("TEST 1: Verify individual model in admin")
        self.stdout.write("-" * 70)
        
        test_model = test_models[0]
        self.stdout.write(f"Testing model: {test_model.name}")
        
        in_admin = verifier.verify_model_in_admin(test_model.name)
        self.stdout.write(f"  Model in admin: {in_admin}")
        
        if in_admin:
            self.stdout.write(self.style.SUCCESS("  ✓ Model successfully found in admin"))
        else:
            self.stdout.write(self.style.ERROR("  ✗ Model not found in admin"))
        self.stdout.write("")
        
        # Test admin views
        self.stdout.write("-" * 70)
        self.stdout.write("TEST 2: Test admin views (list, add, change)")
        self.stdout.write("-" * 70)
        
        self.stdout.write(f"Testing views for: {test_model.name}")
        result = verifier.test_admin_views(test_model.name)
        
        self.stdout.write(f"  In admin: {result['in_admin']}")
        self.stdout.write(f"  List view status: {result['list_view_status']} - {'✓' if result['list_view_success'] else '✗'}")
        self.stdout.write(f"  Add view status: {result['add_view_status']} - {'✓' if result['add_view_success'] else '✗'}")
        self.stdout.write(f"  Change view status: {result['change_view_status']} - {'✓' if result['change_view_success'] else '✗'}")
        
        if result['error_message']:
            self.stdout.write(self.style.WARNING(f"  Errors: {result['error_message']}"))
        self.stdout.write("")
        
        # Test updating activation status
        self.stdout.write("-" * 70)
        self.stdout.write("TEST 3: Update ModelActivationStatus records")
        self.stdout.write("-" * 70)
        
        self.stdout.write(f"Updating activation status for: {test_model.name}")
        verifier.update_activation_status(test_model.name, result)
        
        # Verify the update
        from Hub.models_activation_tracking import ModelActivationStatus
        
        try:
            status = ModelActivationStatus.objects.get(model_name=test_model.name)
            self.stdout.write(f"  Model name: {status.model_name}")
            self.stdout.write(f"  Admin registered: {status.admin_registered}")
            self.stdout.write(f"  Admin verified: {status.admin_verified}")
            self.stdout.write(f"  Error message: {status.error_message or 'None'}")
            self.stdout.write(self.style.SUCCESS("  ✓ Status record updated successfully"))
        except ModelActivationStatus.DoesNotExist:
            self.stdout.write(self.style.ERROR("  ✗ Status record not found"))
        self.stdout.write("")
        
        # Test bulk verification
        self.stdout.write("-" * 70)
        self.stdout.write("TEST 4: Verify and update multiple models")
        self.stdout.write("-" * 70)
        
        self.stdout.write(f"Verifying {len(test_models)} models...")
        summary = verifier.verify_and_update_models(test_models)
        
        self.stdout.write("")
        self.stdout.write("SUMMARY:")
        self.stdout.write(f"  Total models: {summary['total_models']}")
        self.stdout.write(f"  In admin: {summary['in_admin']}")
        self.stdout.write(f"  List view success: {summary['list_view_success']}")
        self.stdout.write(f"  Add view success: {summary['add_view_success']}")
        self.stdout.write(f"  Fully verified: {summary['fully_verified']}")
        self.stdout.write(f"  Failed: {summary['failed']}")
        self.stdout.write("")
        
        # Generate and display report
        self.stdout.write("-" * 70)
        self.stdout.write("TEST 5: Generate verification report")
        self.stdout.write("-" * 70)
        self.stdout.write("")
        
        report = verifier.generate_verification_report(summary)
        self.stdout.write(report)
        
        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("ALL TESTS COMPLETED"))
        self.stdout.write("=" * 70)
