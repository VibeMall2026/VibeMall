"""
Test AdminCodeGenerator functionality.

This test verifies that AdminCodeGenerator correctly generates admin
registration code for models with appropriate list_display fields.
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

from Hub.activation_tools import AdminCodeGenerator, ModelScanner, FieldInfo, ModelInfo


def test_get_list_display_fields():
    """Test that get_list_display_fields returns appropriate fields."""
    generator = AdminCodeGenerator()
    
    # Create a test model with various field types
    test_model = ModelInfo(
        name='TestProduct',
        file_path='Hub/models.py',
        fields=[
            FieldInfo(name='id', field_type='AutoField'),
            FieldInfo(name='name', field_type='CharField'),
            FieldInfo(name='description', field_type='TextField'),  # Should be excluded
            FieldInfo(name='price', field_type='DecimalField'),
            FieldInfo(name='is_active', field_type='BooleanField'),
            FieldInfo(name='created_at', field_type='DateTimeField'),
            FieldInfo(name='password', field_type='CharField'),  # Should be excluded
        ]
    )
    
    fields = generator.get_list_display_fields(test_model)
    
    print("Test 1: get_list_display_fields")
    print(f"  Selected fields: {fields}")
    
    # Verify expected fields are included
    assert 'id' in fields, "id should be included"
    assert 'name' in fields, "name should be included"
    assert 'price' in fields, "price should be included"
    assert 'is_active' in fields, "is_active should be included"
    assert 'created_at' in fields, "created_at should be included"
    
    # Verify excluded fields are not included
    assert 'description' not in fields, "description (TextField) should be excluded"
    assert 'password' not in fields, "password should be excluded"
    
    # Verify field count is reasonable (5-7 fields)
    assert 1 <= len(fields) <= 7, f"Should have 1-7 fields, got {len(fields)}"
    
    print("  ✓ Test passed")
    print()


def test_generate_registration_code():
    """Test that generate_registration_code creates valid admin code."""
    generator = AdminCodeGenerator()
    
    test_model = ModelInfo(
        name='Product',
        file_path='Hub/models.py',
        fields=[
            FieldInfo(name='id', field_type='AutoField'),
            FieldInfo(name='name', field_type='CharField'),
            FieldInfo(name='price', field_type='DecimalField'),
            FieldInfo(name='is_active', field_type='BooleanField'),
        ]
    )
    
    code = generator.generate_registration_code(test_model)
    
    print("Test 2: generate_registration_code")
    print("Generated code:")
    print(code)
    print()
    
    # Verify code structure
    assert 'class ProductAdmin(admin.ModelAdmin):' in code, "Should have ModelAdmin class"
    assert 'list_display' in code, "Should have list_display"
    assert 'admin.site.register(Product, ProductAdmin)' in code, "Should have registration call"
    
    print("  ✓ Test passed")
    print()


def test_generate_bulk_registration_code():
    """Test generating code for multiple models."""
    generator = AdminCodeGenerator()
    
    models = [
        ModelInfo(
            name='Product',
            file_path='Hub/models.py',
            fields=[
                FieldInfo(name='id', field_type='AutoField'),
                FieldInfo(name='name', field_type='CharField'),
            ]
        ),
        ModelInfo(
            name='Order',
            file_path='Hub/models.py',
            fields=[
                FieldInfo(name='id', field_type='AutoField'),
                FieldInfo(name='status', field_type='CharField'),
            ]
        ),
    ]
    
    code = generator.generate_bulk_registration_code(models)
    
    print("Test 3: generate_bulk_registration_code")
    print("Generated code:")
    print(code)
    print()
    
    # Verify both models are included
    assert 'ProductAdmin' in code, "Should include ProductAdmin"
    assert 'OrderAdmin' in code, "Should include OrderAdmin"
    assert 'admin.site.register(Product, ProductAdmin)' in code
    assert 'admin.site.register(Order, OrderAdmin)' in code
    
    print("  ✓ Test passed")
    print()


def test_with_real_models():
    """Test with real models from the database."""
    print("Test 4: Testing with real models from database")
    
    scanner = ModelScanner()
    generator = AdminCodeGenerator()
    
    # Get a few models to test with
    all_models = scanner.scan_model_files()
    
    if not all_models:
        print("  ⚠ No models found, skipping test")
        return
    
    # Test with first 3 models
    test_models = all_models[:3]
    
    print(f"  Testing with {len(test_models)} models:")
    for model in test_models:
        print(f"    - {model.name}")
        fields = generator.get_list_display_fields(model)
        print(f"      list_display: {fields}")
    
    print()
    
    # Generate code for these models
    code = generator.generate_bulk_registration_code(test_models)
    
    # Verify code was generated
    assert len(code) > 0, "Should generate code"
    
    for model in test_models:
        assert f'{model.name}Admin' in code, f"Should include {model.name}Admin"
    
    print("  ✓ Test passed")
    print()


def test_get_registration_summary():
    """Test registration summary generation."""
    generator = AdminCodeGenerator()
    
    models = [
        ModelInfo(
            name='Product',
            file_path='Hub/models.py',
            fields=[
                FieldInfo(name='id', field_type='AutoField'),
                FieldInfo(name='name', field_type='CharField'),
                FieldInfo(name='price', field_type='DecimalField'),
            ]
        ),
        ModelInfo(
            name='Order',
            file_path='Hub/models.py',
            fields=[
                FieldInfo(name='id', field_type='AutoField'),
                FieldInfo(name='status', field_type='CharField'),
            ]
        ),
    ]
    
    summary = generator.get_registration_summary(models)
    
    print("Test 5: get_registration_summary")
    print(f"  Total models: {summary['total_models']}")
    print(f"  Models with list_display: {summary['models_with_list_display']}")
    print(f"  Average fields per model: {summary['avg_fields_per_model']:.1f}")
    print()
    
    assert summary['total_models'] == 2, "Should have 2 models"
    assert summary['models_with_list_display'] > 0, "Should have models with list_display"
    
    print("  ✓ Test passed")
    print()


if __name__ == '__main__':
    print("=" * 70)
    print("Testing AdminCodeGenerator")
    print("=" * 70)
    print()
    
    try:
        test_get_list_display_fields()
        test_generate_registration_code()
        test_generate_bulk_registration_code()
        test_with_real_models()
        test_get_registration_summary()
        
        print("=" * 70)
        print("All tests passed! ✓")
        print("=" * 70)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
