"""
Test script for MigrationExecutor functionality.

This script tests the MigrationExecutor class to ensure it can:
1. Apply migrations using Django's migrate command
2. Handle migration errors gracefully
3. Log migration results
4. Get pending and applied migrations
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.activation_tools import MigrationExecutor, ModelScanner, DependencyAnalyzer


def test_migration_executor():
    """Test the MigrationExecutor class."""
    
    print("=" * 80)
    print("Testing MigrationExecutor")
    print("=" * 80)
    
    # Initialize the executor
    executor = MigrationExecutor(app_name='Hub')
    
    # Test 1: Get pending migrations
    print("\n1. Getting pending migrations...")
    pending = executor.get_pending_migrations()
    print(f"   Found {len(pending)} pending migrations:")
    for migration in pending[:5]:  # Show first 5
        print(f"   - {migration}")
    if len(pending) > 5:
        print(f"   ... and {len(pending) - 5} more")
    
    # Test 2: Get applied migrations
    print("\n2. Getting applied migrations...")
    applied = executor.get_applied_migrations()
    print(f"   Found {len(applied)} applied migrations:")
    for migration in applied[-5:]:  # Show last 5
        print(f"   - {migration}")
    if len(applied) > 5:
        print(f"   ... and {len(applied) - 5} more")
    
    # Test 3: Apply migrations (if any pending)
    if pending:
        print("\n3. Applying pending migrations...")
        result = executor.apply_migrations()
        
        print(f"\n   Migration Results:")
        print(f"   - Total migrations: {result['total_migrations']}")
        print(f"   - Successful: {result['successful']}")
        print(f"   - Failed: {result['failed']}")
        
        if result['applied_migrations']:
            print(f"\n   Applied migrations:")
            for migration in result['applied_migrations']:
                print(f"   - {migration}")
        
        if result['errors']:
            print(f"\n   Errors:")
            for error in result['errors']:
                print(f"   - {error['migration']}: {error['error'][:100]}...")
        
        # Test 4: Save execution logs to database
        if result['execution_logs']:
            print("\n4. Saving execution logs to database...")
            executor.execution_logs = result['execution_logs']
            saved_count = executor.save_execution_logs()
            print(f"   Saved {saved_count} log entries to MigrationExecutionLog")
    else:
        print("\n3. No pending migrations to apply.")
        print("   All migrations are up to date!")
    
    # Test 5: Integration with ModelScanner and DependencyAnalyzer
    print("\n5. Testing integration with ModelScanner and DependencyAnalyzer...")
    
    scanner = ModelScanner(app_name='Hub')
    models_without_tables = scanner.get_models_without_tables()
    
    print(f"   Found {len(models_without_tables)} models without tables:")
    for model in models_without_tables[:5]:
        print(f"   - {model.name} (from {model.file_path})")
    if len(models_without_tables) > 5:
        print(f"   ... and {len(models_without_tables) - 5} more")
    
    if models_without_tables:
        analyzer = DependencyAnalyzer()
        graph = analyzer.build_dependency_graph(models_without_tables)
        
        try:
            migration_order = analyzer.get_migration_order(graph)
            print(f"\n   Recommended migration order for models without tables:")
            for idx, model_name in enumerate(migration_order[:10], start=1):
                print(f"   {idx}. {model_name}")
            if len(migration_order) > 10:
                print(f"   ... and {len(migration_order) - 10} more")
        except ValueError as e:
            print(f"\n   Warning: {e}")
            circular_deps = analyzer.detect_circular_dependencies(graph)
            if circular_deps:
                print(f"   Found {len(circular_deps)} circular dependency chains:")
                for chain in circular_deps[:3]:
                    print(f"   - {' -> '.join(chain)}")
    
    print("\n" + "=" * 80)
    print("MigrationExecutor test completed successfully!")
    print("=" * 80)


if __name__ == '__main__':
    try:
        test_migration_executor()
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
