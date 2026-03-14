"""
Test script for DependencyAnalyzer functionality.

This script tests the DependencyAnalyzer class to ensure it correctly:
- Builds dependency graphs from foreign key relationships
- Performs topological sort for migration ordering
- Detects circular dependencies between models
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

from Hub.activation_tools import ModelScanner, DependencyAnalyzer, DependencyGraph, ModelDependency


def test_dependency_graph_basic():
    """Test basic dependency graph operations."""
    print("\n=== Test 1: Basic Dependency Graph ===")
    
    graph = DependencyGraph()
    
    # Add some test dependencies
    # Order -> Customer (Order depends on Customer)
    graph.add_edge(ModelDependency(
        source_model='Order',
        target_model='Customer',
        field_name='customer',
        on_delete='CASCADE'
    ))
    
    # OrderItem -> Order (OrderItem depends on Order)
    graph.add_edge(ModelDependency(
        source_model='OrderItem',
        target_model='Order',
        field_name='order',
        on_delete='CASCADE'
    ))
    
    # OrderItem -> Product (OrderItem depends on Product)
    graph.add_edge(ModelDependency(
        source_model='OrderItem',
        target_model='Product',
        field_name='product',
        on_delete='PROTECT'
    ))
    
    print(f"Nodes: {sorted(graph.nodes)}")
    print(f"Total edges: {len(graph.edges)}")
    
    # Test topological sort
    try:
        migration_order = graph.topological_sort()
        print(f"Migration order: {migration_order}")
        print("✓ Topological sort successful")
    except ValueError as e:
        print(f"✗ Topological sort failed: {e}")
    
    # Test circular dependency detection
    has_circular = graph.has_circular_dependency()
    print(f"Has circular dependencies: {has_circular}")
    if not has_circular:
        print("✓ No circular dependencies detected")
    else:
        print("✗ Unexpected circular dependencies")


def test_circular_dependency_detection():
    """Test circular dependency detection."""
    print("\n=== Test 2: Circular Dependency Detection ===")
    
    graph = DependencyGraph()
    
    # Create a circular dependency: A -> B -> C -> A
    graph.add_edge(ModelDependency('ModelA', 'ModelB', 'field_b'))
    graph.add_edge(ModelDependency('ModelB', 'ModelC', 'field_c'))
    graph.add_edge(ModelDependency('ModelC', 'ModelA', 'field_a'))
    
    print(f"Nodes: {sorted(graph.nodes)}")
    
    has_circular = graph.has_circular_dependency()
    print(f"Has circular dependencies: {has_circular}")
    
    if has_circular:
        cycles = graph.find_circular_dependencies()
        print(f"Circular dependency chains found: {len(cycles)}")
        for i, cycle in enumerate(cycles, 1):
            print(f"  Cycle {i}: {' -> '.join(cycle)}")
        print("✓ Circular dependencies correctly detected")
    else:
        print("✗ Failed to detect circular dependencies")


def test_real_models():
    """Test with real models from the Hub app."""
    print("\n=== Test 3: Real Models Analysis ===")
    
    # Scan models
    scanner = ModelScanner('Hub')
    models = scanner.scan_model_files()
    
    print(f"Total models found: {len(models)}")
    print(f"Models with tables: {sum(1 for m in models if m.has_table)}")
    print(f"Models without tables: {sum(1 for m in models if not m.has_table)}")
    
    # Build dependency graph
    analyzer = DependencyAnalyzer()
    graph = analyzer.build_dependency_graph(models)
    
    print(f"\nDependency graph:")
    print(f"  Total nodes: {len(graph.nodes)}")
    print(f"  Total edges: {len(graph.edges)}")
    
    # Check for circular dependencies
    has_circular = graph.has_circular_dependency()
    print(f"  Has circular dependencies: {has_circular}")
    
    if has_circular:
        cycles = analyzer.detect_circular_dependencies()
        print(f"\n  Circular dependency chains found: {len(cycles)}")
        for i, cycle in enumerate(cycles[:5], 1):  # Show first 5
            print(f"    Cycle {i}: {' -> '.join(cycle)}")
        if len(cycles) > 5:
            print(f"    ... and {len(cycles) - 5} more cycles")
    else:
        # Get migration order
        try:
            migration_order = analyzer.get_migration_order()
            print(f"\n  Migration order determined: {len(migration_order)} models")
            print(f"  First 10 models to migrate: {migration_order[:10]}")
            print(f"  Last 10 models to migrate: {migration_order[-10:]}")
            print("✓ Migration order successfully determined")
        except ValueError as e:
            print(f"✗ Failed to determine migration order: {e}")
    
    # Get dependency report
    report = analyzer.get_dependency_report()
    print(f"\nDependency Report Summary:")
    print(f"  Total models: {report['total_models']}")
    print(f"  Total dependencies: {report['total_dependencies']}")
    print(f"  Models with no dependencies: {len(report['models_with_no_dependencies'])}")
    print(f"  Models with no dependents: {len(report['models_with_no_dependents'])}")
    
    if report['models_with_no_dependencies']:
        print(f"  Independent models (can migrate first): {report['models_with_no_dependencies'][:10]}")


def test_core_model_verification():
    """Test core model verification."""
    print("\n=== Test 4: Core Model Verification ===")
    
    scanner = ModelScanner('Hub')
    models = scanner.scan_model_files()
    
    analyzer = DependencyAnalyzer()
    
    # Check for common core models
    core_models = ['User', 'Product', 'Order', 'Customer', 'Category']
    verification = analyzer.verify_core_models_exist(models, core_models)
    
    print("Core model verification:")
    for model, exists in verification.items():
        status = "✓" if exists else "✗"
        print(f"  {status} {model}: {'exists' if exists else 'missing'}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("DependencyAnalyzer Test Suite")
    print("=" * 60)
    
    try:
        test_dependency_graph_basic()
        test_circular_dependency_detection()
        test_real_models()
        test_core_model_verification()
        
        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
