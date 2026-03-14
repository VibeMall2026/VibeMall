"""
Management command to verify table creation after migrations.

This command:
1. Scans all models to check which have tables
2. Uses SchemaVerifier to verify table structure
3. Updates ModelActivationStatus records
4. Generates comprehensive verification report
"""

from django.core.management.base import BaseCommand
from Hub.activation_tools import ModelScanner, SchemaVerifier


class Command(BaseCommand):
    help = 'Verify table creation for all models and generate report'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('TABLE VERIFICATION REPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        # Step 1: Scan all models
        self.stdout.write('Step 1: Scanning all models...')
        scanner = ModelScanner(app_name='Hub')
        all_models = scanner.scan_model_files()
        models_without_tables = [m for m in all_models if not m.has_table]

        self.stdout.write(f'  Total models: {len(all_models)}')
        self.stdout.write(f'  Models with tables: {len(all_models) - len(models_without_tables)}')
        self.stdout.write(f'  Models without tables: {len(models_without_tables)}')
        self.stdout.write('')

        # Step 2: Verify table creation
        self.stdout.write('Step 2: Verifying table structure...')
        verifier = SchemaVerifier(app_name='Hub')
        verification_result = verifier.verify_models(all_models)

        self.stdout.write(f'  Tables verified: {verification_result["tables_verified"]}')
        self.stdout.write(f'  Tables missing: {verification_result["tables_missing"]}')
        self.stdout.write('')

        # Step 3: Update activation status
        self.stdout.write('Step 3: Updating ModelActivationStatus records...')
        updated_count = verifier.update_activation_status(all_models)
        self.stdout.write(f'  Updated {updated_count} activation status record(s)')
        self.stdout.write('')

        # Step 4: Generate detailed report
        self.stdout.write('Step 4: Generating detailed verification report...')
        self.stdout.write('')

        self._generate_detailed_report(all_models, verification_result)

        # Final summary
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('VERIFICATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        if verification_result['tables_missing'] == 0:
            self.stdout.write(self.style.SUCCESS('✓ All models have database tables'))
        else:
            self.stdout.write(self.style.WARNING(
                f'⚠ {verification_result["tables_missing"]} model(s) still missing tables'
            ))

    def _generate_detailed_report(self, all_models, verification_result):
        """Generate detailed verification report."""
        from collections import defaultdict

        # Group models by file
        models_by_file = defaultdict(list)
        for model in all_models:
            models_by_file[model.file_path].append(model)

        # Section 1: Models with tables (grouped by file)
        models_with_tables = [m for m in all_models if m.has_table]
        if models_with_tables:
            self.stdout.write(self.style.SUCCESS('MODELS WITH TABLES:'))
            self.stdout.write('')

            for file_path in sorted(models_by_file.keys()):
                file_models = [m for m in models_by_file[file_path] if m.has_table]
                if file_models:
                    self.stdout.write(f'  {file_path}:')
                    for model in sorted(file_models, key=lambda m: m.name):
                        # Find verification details
                        detail = next(
                            (d for d in verification_result['verification_details']
                             if d['model_name'] == model.name),
                            None
                        )
                        if detail:
                            self.stdout.write(
                                f'    ✓ {model.name} ({model.table_name}) - '
                                f'PK: {"Yes" if detail["has_primary_key"] else "No"}, '
                                f'Indexes: {detail["index_count"]}, '
                                f'Constraints: {detail["constraint_count"]}'
                            )
                        else:
                            self.stdout.write(f'    ✓ {model.name} ({model.table_name})')
                    self.stdout.write('')

        # Section 2: Models without tables (grouped by file)
        models_without_tables = [m for m in all_models if not m.has_table]
        if models_without_tables:
            self.stdout.write(self.style.WARNING('MODELS WITHOUT TABLES:'))
            self.stdout.write('')

            for file_path in sorted(models_by_file.keys()):
                file_models = [m for m in models_by_file[file_path] if not m.has_table]
                if file_models:
                    self.stdout.write(f'  {file_path}:')
                    for model in sorted(file_models, key=lambda m: m.name):
                        self.stdout.write(f'    ✗ {model.name} (expected table: {model.table_name})')
                    self.stdout.write('')

        # Section 3: Summary statistics
        self.stdout.write('SUMMARY STATISTICS:')
        self.stdout.write(f'  Total Models: {len(all_models)}')
        self.stdout.write(f'  Models with Tables: {len(models_with_tables)}')
        self.stdout.write(f'  Models without Tables: {len(models_without_tables)}')
        self.stdout.write(f'  Coverage: {len(models_with_tables) / len(all_models) * 100:.1f}%')
        self.stdout.write('')

        # Section 4: Models by file statistics
        self.stdout.write('MODELS BY FILE:')
        for file_path in sorted(models_by_file.keys()):
            file_models = models_by_file[file_path]
            with_tables = sum(1 for m in file_models if m.has_table)
            without_tables = sum(1 for m in file_models if not m.has_table)
            self.stdout.write(
                f'  {file_path}: {len(file_models)} total, '
                f'{with_tables} with tables, {without_tables} without tables'
            )
        self.stdout.write('')
