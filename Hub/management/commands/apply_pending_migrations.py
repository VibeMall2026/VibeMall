"""
Management command to apply all pending migrations and verify table creation.

This command:
1. Uses MigrationExecutor to apply all pending migrations
2. Uses SchemaVerifier to verify tables were created
3. Updates ModelActivationStatus records
4. Generates comprehensive migration report
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from Hub.activation_tools import (
    ModelScanner,
    DependencyAnalyzer,
    MigrationExecutor,
    SchemaVerifier
)


class Command(BaseCommand):
    help = 'Apply all pending migrations and verify table creation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually applying migrations',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('APPLYING PENDING MIGRATIONS'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        # Step 1: Check for pending migrations
        self.stdout.write('Step 1: Checking for pending migrations...')
        executor = MigrationExecutor(app_name='Hub')
        pending_migrations = executor.get_pending_migrations()

        if not pending_migrations:
            self.stdout.write(self.style.WARNING('No pending migrations found.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {len(pending_migrations)} pending migration(s):'))
        for migration in pending_migrations:
            self.stdout.write(f'  - {migration}')
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No migrations will be applied'))
            return

        # Step 2: Scan models before migration
        self.stdout.write('Step 2: Scanning models before migration...')
        scanner = ModelScanner(app_name='Hub')
        models_before = scanner.scan_model_files()
        models_without_tables_before = [m for m in models_before if not m.has_table]

        self.stdout.write(f'  Total models: {len(models_before)}')
        self.stdout.write(f'  Models without tables: {len(models_without_tables_before)}')
        self.stdout.write('')

        # Step 3: Apply migrations
        self.stdout.write('Step 3: Applying migrations...')
        self.stdout.write('')

        result = executor.apply_migrations()

        success = result['failed'] == 0 and result['total_migrations'] > 0
        
        if success:
            self.stdout.write(self.style.SUCCESS('✓ Migrations applied successfully!'))
        elif result['total_migrations'] == 0:
            self.stdout.write(self.style.WARNING('⚠ No migrations were applied'))
        else:
            self.stdout.write(self.style.ERROR('✗ Migration application encountered errors'))

        self.stdout.write(f'  Total migrations: {result["total_migrations"]}')
        self.stdout.write(f'  Successful: {result["successful"]}')
        self.stdout.write(f'  Failed: {result["failed"]}')
        self.stdout.write('')

        # Display applied migrations
        if result.get('applied_migrations'):
            self.stdout.write('Applied migrations:')
            for migration in result['applied_migrations']:
                self.stdout.write(f'  ✓ {migration}')
            self.stdout.write('')

        # Display errors if any
        if result.get('errors'):
            self.stdout.write(self.style.ERROR('Errors encountered:'))
            for error in result['errors']:
                self.stdout.write(self.style.ERROR(f'  Migration: {error.get("migration", "Unknown")}'))
                self.stdout.write(self.style.ERROR(f'  Error: {error.get("error", "Unknown error")}'))
            self.stdout.write('')

        # Step 4: Verify table creation
        self.stdout.write('Step 4: Verifying table creation...')
        verifier = SchemaVerifier(app_name='Hub')

        # Rescan models after migration
        models_after = scanner.scan_model_files()
        models_without_tables_after = [m for m in models_after if not m.has_table]

        verification_result = verifier.verify_models(models_after)

        self.stdout.write(f'  Total models: {verification_result["total_models"]}')
        self.stdout.write(f'  Tables verified: {verification_result["tables_verified"]}')
        self.stdout.write(f'  Tables missing: {verification_result["tables_missing"]}')
        self.stdout.write('')

        # Show newly created tables
        tables_created = len(models_without_tables_before) - len(models_without_tables_after)
        if tables_created > 0:
            self.stdout.write(self.style.SUCCESS(f'✓ {tables_created} new table(s) created!'))
            self.stdout.write('')

            # List newly created tables
            before_names = {m.name for m in models_without_tables_before}
            after_names = {m.name for m in models_without_tables_after}
            newly_created = before_names - after_names

            if newly_created:
                self.stdout.write('Newly created tables:')
                for model_name in sorted(newly_created):
                    model = next((m for m in models_after if m.name == model_name), None)
                    if model:
                        self.stdout.write(f'  ✓ {model.table_name} ({model_name})')
                self.stdout.write('')

        # Step 5: Update ModelActivationStatus records
        self.stdout.write('Step 5: Updating ModelActivationStatus records...')
        updated_count = verifier.update_activation_status(models_after)
        self.stdout.write(f'  Updated {updated_count} activation status record(s)')
        self.stdout.write('')

        # Step 6: Save execution logs
        self.stdout.write('Step 6: Saving execution logs...')
        saved_logs = executor.save_execution_logs()
        self.stdout.write(f'  Saved {saved_logs} execution log(s)')
        self.stdout.write('')

        # Step 7: Generate comprehensive report
        self.stdout.write('Step 7: Generating migration report...')
        self.stdout.write('')

        self._generate_migration_report(
            pending_migrations=pending_migrations,
            migration_result=result,
            verification_result=verification_result,
            models_before=models_without_tables_before,
            models_after=models_without_tables_after
        )

        # Final summary
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('MIGRATION APPLICATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        if success and verification_result['tables_missing'] == 0:
            self.stdout.write(self.style.SUCCESS('✓ All migrations applied successfully'))
            self.stdout.write(self.style.SUCCESS('✓ All tables verified'))
        elif success:
            self.stdout.write(self.style.SUCCESS('✓ Migrations applied successfully'))
            self.stdout.write(self.style.WARNING(f'⚠ {verification_result["tables_missing"]} table(s) still missing'))
        else:
            self.stdout.write(self.style.ERROR('✗ Migration application encountered errors'))

    def _generate_migration_report(self, pending_migrations, migration_result,
                                   verification_result, models_before, models_after):
        """Generate comprehensive migration report."""
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('MIGRATION REPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        # Section 1: Pending Migrations
        self.stdout.write('PENDING MIGRATIONS APPLIED:')
        for migration in pending_migrations:
            self.stdout.write(f'  ✓ {migration}')
        self.stdout.write('')

        # Section 2: Migration Execution Summary
        success = migration_result['failed'] == 0 and migration_result['total_migrations'] > 0
        self.stdout.write('MIGRATION EXECUTION SUMMARY:')
        self.stdout.write(f'  Status: {"Success" if success else "Failed"}')
        self.stdout.write(f'  Total Migrations: {migration_result["total_migrations"]}')
        self.stdout.write(f'  Successful: {migration_result["successful"]}')
        self.stdout.write(f'  Failed: {migration_result["failed"]}')
        self.stdout.write('')

        # Section 3: Table Creation Summary
        tables_created = len(models_before) - len(models_after)
        self.stdout.write('TABLE CREATION SUMMARY:')
        self.stdout.write(f'  Models without tables (before): {len(models_before)}')
        self.stdout.write(f'  Models without tables (after): {len(models_after)}')
        self.stdout.write(f'  New tables created: {tables_created}')
        self.stdout.write('')

        # Section 4: Newly Created Tables
        if tables_created > 0:
            before_names = {m.name for m in models_before}
            after_names = {m.name for m in models_after}
            newly_created = before_names - after_names

            if newly_created:
                self.stdout.write('NEWLY CREATED TABLES:')
                # Group by model file
                from collections import defaultdict
                by_file = defaultdict(list)

                for model_name in newly_created:
                    # Find the model in the full list
                    scanner = ModelScanner(app_name='Hub')
                    all_models = scanner.scan_model_files()
                    model = next((m for m in all_models if m.name == model_name), None)
                    if model:
                        by_file[model.file_path].append(model)

                for file_path in sorted(by_file.keys()):
                    self.stdout.write(f'  {file_path}:')
                    for model in sorted(by_file[file_path], key=lambda m: m.name):
                        self.stdout.write(f'    ✓ {model.table_name} ({model.name})')
                self.stdout.write('')

        # Section 5: Verification Details
        self.stdout.write('VERIFICATION DETAILS:')
        self.stdout.write(f'  Total Models: {verification_result["total_models"]}')
        self.stdout.write(f'  Tables Verified: {verification_result["tables_verified"]}')
        self.stdout.write(f'  Tables Missing: {verification_result["tables_missing"]}')
        self.stdout.write('')

        # Section 6: Remaining Missing Tables
        if verification_result['missing_tables']:
            self.stdout.write(self.style.WARNING('REMAINING MISSING TABLES:'))
            for table in verification_result['missing_tables']:
                self.stdout.write(self.style.WARNING(f'  ✗ {table}'))
            self.stdout.write('')

        # Section 7: Detailed Verification
        if verification_result.get('verification_details'):
            self.stdout.write('DETAILED VERIFICATION (Sample):')
            # Show first 10 verified tables
            verified_details = [d for d in verification_result['verification_details'] if d['table_exists']][:10]
            for detail in verified_details:
                self.stdout.write(f'  ✓ {detail["model_name"]} ({detail["table_name"]})')
                self.stdout.write(f'      Primary Key: {"Yes" if detail["has_primary_key"] else "No"}')
                self.stdout.write(f'      Indexes: {detail["index_count"]}')
                self.stdout.write(f'      Constraints: {detail["constraint_count"]}')
            self.stdout.write('')

        self.stdout.write(self.style.SUCCESS('=' * 70))
