"""
Django management command to discover models without tables and generate migrations.

This command orchestrates the migration discovery and generation process by:
1. Using ModelScanner to identify all models
2. Using SchemaVerifier to identify models without tables
3. Using DependencyAnalyzer to determine migration order
4. Using MigrationGenerator to generate missing migrations
5. Reporting results

Usage:
    python manage.py discover_and_generate_migrations
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from Hub.activation_tools import (
    ModelScanner,
    DependencyAnalyzer,
    MigrationGenerator,
    SchemaVerifier
)
import json


class Command(BaseCommand):
    help = 'Discover models without tables and generate missing migrations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually generating migrations',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('Migration Discovery and Generation'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')
        
        # Step 1: Scan all models
        self.stdout.write(self.style.WARNING('Step 1: Scanning all models...'))
        scanner = ModelScanner(app_name='Hub')
        
        try:
            all_models = scanner.scan_model_files()
            self.stdout.write(self.style.SUCCESS(f'✓ Found {len(all_models)} models'))
            
            if verbose:
                models_by_file = scanner.get_models_by_file()
                for file_name, models in models_by_file.items():
                    self.stdout.write(f'  - {file_name}: {len(models)} models')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error scanning models: {str(e)}'))
            return
        
        self.stdout.write('')
        
        # Step 2: Identify models without tables
        self.stdout.write(self.style.WARNING('Step 2: Identifying models without tables...'))
        
        try:
            models_without_tables = scanner.get_models_without_tables()
            self.stdout.write(self.style.SUCCESS(
                f'✓ Found {len(models_without_tables)} models without tables'
            ))
            
            if verbose and models_without_tables:
                self.stdout.write('  Models without tables:')
                for model in models_without_tables:
                    # Extract just the filename from the full path
                    import os
                    file_name = os.path.basename(model.file_path)
                    self.stdout.write(f'    - {model.name} (from {file_name})')
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'✗ Error identifying models without tables: {str(e)}'
            ))
            return
        
        self.stdout.write('')
        
        # Step 3: Build dependency graph
        self.stdout.write(self.style.WARNING('Step 3: Analyzing model dependencies...'))
        analyzer = DependencyAnalyzer()
        
        try:
            dependency_graph = analyzer.build_dependency_graph(all_models)
            self.stdout.write(self.style.SUCCESS('✓ Dependency graph built'))
            
            # Check for circular dependencies
            circular_deps = analyzer.detect_circular_dependencies(dependency_graph)
            if circular_deps:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ Found {len(circular_deps)} circular dependencies:'
                ))
                for cycle in circular_deps:
                    self.stdout.write(f'    - {" → ".join(cycle)}')
            else:
                self.stdout.write('  ✓ No circular dependencies detected')
            
            if verbose:
                # Show dependency counts
                dep_report = analyzer.get_dependency_report(dependency_graph)
                self.stdout.write(f'  Total dependencies: {dep_report["total_dependencies"]}')
                self.stdout.write(f'  Models with no dependencies: {len(dep_report["models_with_no_dependencies"])}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'✗ Error analyzing dependencies: {str(e)}'
            ))
            return
        
        self.stdout.write('')
        
        # Step 4: Determine migration order
        self.stdout.write(self.style.WARNING('Step 4: Determining migration order...'))
        
        try:
            # Only attempt topological sort if no circular dependencies
            if not circular_deps:
                migration_order = analyzer.get_migration_order(dependency_graph)
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Migration order determined for {len(migration_order)} models'
                ))
                
                if verbose and migration_order:
                    self.stdout.write('  Migration order (first 10):')
                    for i, model_name in enumerate(migration_order[:10], 1):
                        self.stdout.write(f'    {i}. {model_name}')
                    if len(migration_order) > 10:
                        self.stdout.write(f'    ... and {len(migration_order) - 10} more')
            else:
                self.stdout.write(self.style.WARNING(
                    '  ⚠ Cannot determine strict migration order due to circular dependencies'
                ))
                self.stdout.write('  ℹ Django migrations can handle circular dependencies using multiple passes')
                migration_order = []
        except Exception as e:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ Cannot determine migration order: {str(e)}'
            ))
            self.stdout.write('  ℹ Django migrations can still be generated and applied')
            migration_order = []
        
        self.stdout.write('')
        
        # Step 5: Generate migrations
        if models_without_tables:
            self.stdout.write(self.style.WARNING('Step 5: Generating missing migrations...'))
            
            if dry_run:
                self.stdout.write(self.style.NOTICE(
                    '  [DRY RUN] Would generate migrations for:'
                ))
                for model in models_without_tables:
                    self.stdout.write(f'    - {model.name}')
            else:
                generator = MigrationGenerator(app_name='Hub')
                
                try:
                    generated_files = generator.generate_migrations(models_without_tables)
                    
                    if generated_files:
                        self.stdout.write(self.style.SUCCESS(
                            f'✓ Generated {len(generated_files)} migration file(s)'
                        ))
                        
                        if verbose:
                            self.stdout.write('  Generated migrations:')
                            for migration_file in generated_files:
                                self.stdout.write(f'    - {migration_file}')
                    else:
                        self.stdout.write(self.style.NOTICE(
                            '  ℹ No new migrations generated (migrations may already exist)'
                        ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'✗ Error generating migrations: {str(e)}'
                    ))
                    return
        else:
            self.stdout.write(self.style.SUCCESS(
                'Step 5: No migrations needed - all models have tables'
            ))
        
        self.stdout.write('')
        
        # Step 6: Verify schema
        self.stdout.write(self.style.WARNING('Step 6: Verifying database schema...'))
        verifier = SchemaVerifier(app_name='Hub')
        
        try:
            # Limit verification to models without tables for performance
            if models_without_tables:
                verification_result = verifier.verify_models(models_without_tables)
            else:
                verification_result = verifier.verify_models(all_models)
            
            verified_count = verification_result.get('verified_count', 0)
            missing_count = verification_result.get('missing_count', 0)
            
            self.stdout.write(self.style.SUCCESS(
                f'✓ Verified {verified_count} tables exist'
            ))
            
            if missing_count > 0:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ {missing_count} tables still missing (migrations need to be applied)'
                ))
                
                if verbose:
                    missing_tables = verification_result.get('missing_tables', [])
                    if missing_tables:
                        self.stdout.write('  Missing tables:')
                        for table in missing_tables[:10]:
                            self.stdout.write(f'    - {table}')
                        if len(missing_tables) > 10:
                            self.stdout.write(f'    ... and {len(missing_tables) - 10} more')
        except Exception as e:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ Error verifying schema: {str(e)}'
            ))
            self.stdout.write('  ℹ Skipping schema verification')
        
        self.stdout.write('')
        
        # Summary
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('Summary'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'Total models scanned: {len(all_models)}')
        self.stdout.write(f'Models without tables: {len(models_without_tables)}')
        self.stdout.write(f'Circular dependencies: {len(circular_deps) if circular_deps else 0}')
        
        if not dry_run and models_without_tables:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE('Next steps:'))
            self.stdout.write('  1. Review the generated migration files')
            self.stdout.write('  2. Run: python manage.py migrate')
            self.stdout.write('  3. Verify tables were created successfully')
        
        self.stdout.write('')
