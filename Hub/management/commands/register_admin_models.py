"""
Django management command to execute admin registration - Task 8.1
"""

from django.core.management.base import BaseCommand
from Hub.activation_tools import AdminScanner, AdminCodeGenerator, ModelScanner
import os


class Command(BaseCommand):
    help = 'Execute admin registration for all unregistered models (Task 8.1)'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("ADMIN REGISTRATION EXECUTION - Task 8.1")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Step 1: Scan all models
        self.stdout.write("Step 1: Scanning all models...")
        model_scanner = ModelScanner('Hub')
        all_models = model_scanner.scan_model_files()
        self.stdout.write(f"Found {len(all_models)} total models")
        self.stdout.write("")

        # Step 2: Identify unregistered models
        self.stdout.write("Step 2: Identifying unregistered models...")
        admin_scanner = AdminScanner('Hub')
        registered = admin_scanner.get_registered_models()
        self.stdout.write(f"Currently registered: {len(registered)}")
        unregistered_models = admin_scanner.get_unregistered_models(all_models)
        self.stdout.write(f"Unregistered: {len(unregistered_models)}")
        self.stdout.write("")

        if not unregistered_models:
            self.stdout.write("All models are already registered in admin!")
            report = admin_scanner.get_registration_report(all_models)
            report_text = admin_scanner.generate_registration_report_text(report)
            self.stdout.write(report_text)
            return

        # Show unregistered models
        self.stdout.write("Unregistered models:")
        for m in unregistered_models:
            self.stdout.write(f"  - {m.name} ({m.file_path})")
        self.stdout.write("")

        # Step 3: Generate registration code
        self.stdout.write("Step 3: Generating registration code...")
        code_generator = AdminCodeGenerator('Hub')
        summary = code_generator.get_registration_summary(unregistered_models)
        self.stdout.write(f"Will register {summary['total_models']} models")
        self.stdout.write("")

        # Generate the registration code
        registration_code = code_generator.generate_bulk_registration_code(unregistered_models)

        # Step 4: Add registration code to admin.py
        self.stdout.write("Step 4: Adding registration code to Hub/admin.py...")
        admin_file_path = os.path.join('Hub', 'admin.py')

        try:
            with open(admin_file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()

            # Check if already added
            if "AUTO-GENERATED ADMIN REGISTRATIONS - Task 8.1" in current_content:
                self.stdout.write("Registration code already added to admin.py")
            else:
                # Build import statements for unregistered models
                models_by_file = {}
                for model in unregistered_models:
                    file_path = model.file_path
                    if file_path not in models_by_file:
                        models_by_file[file_path] = []
                    models_by_file[file_path].append(model.name)

                import_lines = []
                for file_path, model_names in sorted(models_by_file.items()):
                    module_name = os.path.basename(file_path).replace('.py', '')
                    models_str = ", ".join(sorted(model_names))
                    import_lines.append(f"from .{module_name} import {models_str}")

                imports_block = "\n".join(import_lines)

                new_section = (
                    "\n\n# ============================================\n"
                    "# AUTO-GENERATED ADMIN REGISTRATIONS - Task 8.1\n"
                    "# ============================================\n\n"
                    + imports_block
                    + "\n\n"
                    + registration_code
                )

                # Insert before the backup_admin import line
                backup_import_line = "# Load backup model admin registrations"
                if backup_import_line in current_content:
                    new_content = current_content.replace(
                        backup_import_line,
                        new_section + "\n\n" + backup_import_line
                    )
                else:
                    new_content = current_content + new_section

                with open(admin_file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                self.stdout.write(f"Successfully added registration code to admin.py")
                self.stdout.write(f"Added {len(unregistered_models)} model registrations")

        except Exception as e:
            self.stderr.write(f"Error updating admin.py: {e}")
            import traceback
            traceback.print_exc()
            return

        self.stdout.write("")

        # Step 5: Generate report
        self.stdout.write("Step 5: Generating admin registration report...")
        report = admin_scanner.get_registration_report(all_models)
        report_text = admin_scanner.generate_registration_report_text(report)
        self.stdout.write(report_text)

        # Save report
        reports_dir = os.path.join('.kiro', 'specs', 'admin-panel-feature-activation', 'reports')
        os.makedirs(reports_dir, exist_ok=True)

        with open(os.path.join(reports_dir, 'admin_registration_report.txt'), 'w', encoding='utf-8') as f:
            f.write(report_text)

        with open(os.path.join(reports_dir, 'generated_admin_code.py'), 'w', encoding='utf-8') as f:
            f.write(registration_code)

        self.stdout.write(f"Reports saved to {reports_dir}")
        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write("ADMIN REGISTRATION COMPLETE!")
        self.stdout.write("=" * 80)
