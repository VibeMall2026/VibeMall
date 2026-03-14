"""
Execute Admin Registration - Task 8.1

This script runs the admin registration process:
1. Scans for unregistered models using AdminScanner
2. Generates registration code using AdminCodeGenerator
3. Adds registration code to Hub/admin.py
4. Verifies models appear in admin interface using AdminVerifier
5. Generates comprehensive admin registration report
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.activation_tools import AdminScanner, AdminCodeGenerator, AdminVerifier, ModelScanner


def execute_admin_registration():
    """Execute the complete admin registration process."""
    
    print("=" * 80)
    print("ADMIN REGISTRATION EXECUTION - Task 8.1")
    print("=" * 80)
    print()
    
    # Step 1: Scan all models
    print("Step 1: Scanning all models...")
    model_scanner = ModelScanner('Hub')
    all_models = model_scanner.scan_model_files()
    print(f"✓ Found {len(all_models)} total models")
    print()
    
    # Step 2: Identify unregistered models
    print("Step 2: Identifying unregistered models...")
    admin_scanner = AdminScanner('Hub')
    unregistered_models = admin_scanner.get_unregistered_models(all_models)
    print(f"✓ Found {len(unregistered_models)} unregistered models")
    print()
    
    if not unregistered_models:
        print("✓ All models are already registered in admin!")
        print()
        
        # Generate report anyway
        report = admin_scanner.get_registration_report(all_models)
        report_text = admin_scanner.generate_registration_report_text(report)
        print(report_text)
        return
    
    # Step 3: Generate registration code
    print("Step 3: Generating registration code...")
    code_generator = AdminCodeGenerator('Hub')
    
    # Generate summary first
    summary = code_generator.get_registration_summary(unregistered_models)
    print(f"✓ Will register {summary['total_models']} models")
    print(f"✓ Average {summary['avg_fields_per_model']:.1f} fields per model in list_display")
    print()
    
    # Generate the registration code with imports
    registration_code = code_generator.generate_registration_with_imports(unregistered_models)
    
    # Step 4: Add registration code to admin.py
    print("Step 4: Adding registration code to Hub/admin.py...")
    admin_file_path = 'Hub/admin.py'
    
    try:
        # Read current admin.py content
        with open(admin_file_path, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        # Find the position to insert (before the backup_admin import line)
        backup_import_line = "from . import backup_admin"
        
        if backup_import_line in current_content:
            # Insert before the backup_admin import
            parts = current_content.split(backup_import_line)
            new_content = (
                parts[0] +
                "\n\n# ============================================\n" +
                "# AUTO-GENERATED ADMIN REGISTRATIONS - Task 8.1\n" +
                "# ============================================\n\n" +
                registration_code +
                "\n\n" +
                backup_import_line +
                parts[1]
            )
        else:
            # Append to the end
            new_content = (
                current_content +
                "\n\n# ============================================\n" +
                "# AUTO-GENERATED ADMIN REGISTRATIONS - Task 8.1\n" +
                "# ============================================\n\n" +
                registration_code +
                "\n"
            )
        
        # Write updated content
        with open(admin_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✓ Successfully added registration code to {admin_file_path}")
        print()
        
    except Exception as e:
        print(f"✗ Error updating admin.py: {e}")
        print()
        return
    
    # Step 5: Verify models in admin interface
    print("Step 5: Verifying models in admin interface...")
    print("(This may take a moment as we test each model's admin views)")
    print()
    
    admin_verifier = AdminVerifier('Hub')
    verification_summary = admin_verifier.verify_and_update_models(unregistered_models)
    
    print(f"✓ Verified {verification_summary['total_models']} models")
    print(f"✓ {verification_summary['in_admin']} models registered in admin")
    print(f"✓ {verification_summary['fully_verified']} models fully verified (list + add views working)")
    
    if verification_summary['failed'] > 0:
        print(f"⚠ {verification_summary['failed']} models had verification issues")
    
    print()
    
    # Step 6: Generate comprehensive reports
    print("Step 6: Generating reports...")
    print()
    
    # Registration report
    registration_report = admin_scanner.get_registration_report(all_models)
    registration_report_text = admin_scanner.generate_registration_report_text(registration_report)
    
    # Verification report
    verification_report_text = admin_verifier.generate_verification_report(verification_summary)
    
    # Code generation summary
    code_summary_text = code_generator.generate_summary_report(unregistered_models)
    
    # Print all reports
    print(registration_report_text)
    print()
    print(verification_report_text)
    print()
    print(code_summary_text)
    print()
    
    # Save reports to files
    reports_dir = '.kiro/specs/admin-panel-feature-activation/reports'
    os.makedirs(reports_dir, exist_ok=True)
    
    with open(f'{reports_dir}/admin_registration_report.txt', 'w', encoding='utf-8') as f:
        f.write(registration_report_text)
    
    with open(f'{reports_dir}/admin_verification_report.txt', 'w', encoding='utf-8') as f:
        f.write(verification_report_text)
    
    with open(f'{reports_dir}/admin_code_generation_summary.txt', 'w', encoding='utf-8') as f:
        f.write(code_summary_text)
    
    with open(f'{reports_dir}/generated_admin_code.py', 'w', encoding='utf-8') as f:
        f.write(registration_code)
    
    print(f"✓ Reports saved to {reports_dir}/")
    print()
    
    print("=" * 80)
    print("ADMIN REGISTRATION COMPLETE!")
    print("=" * 80)
    print()
    print(f"Summary:")
    print(f"  - Total models: {len(all_models)}")
    print(f"  - Previously registered: {len(all_models) - len(unregistered_models)}")
    print(f"  - Newly registered: {len(unregistered_models)}")
    print(f"  - Fully verified: {verification_summary['fully_verified']}")
    print(f"  - Registration coverage: {registration_report['registration_percentage']:.1f}%")
    print()


if __name__ == '__main__':
    try:
        execute_admin_registration()
    except Exception as e:
        print(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
