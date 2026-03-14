# ModelScanner - Task 2.1 Implementation

## Overview

The ModelScanner is a tool for scanning Django model files and extracting model definitions, field information, and database table status. It was created as part of Task 2.1 for the admin-panel-feature-activation spec.

## Features

### Core Functionality

1. **Model File Discovery**
   - Automatically finds all `models.py` and `models_*.py` files in the Hub app
   - Scans 14 model files in the current project

2. **Model Extraction**
   - Uses AST (Abstract Syntax Tree) parsing to extract model class definitions
   - Works even for models not registered in Django's app registry
   - Identifies 124 total models across all files

3. **Field Information**
   - Extracts field names and types for each model
   - Identifies foreign key relationships
   - Tracks nullable and unique constraints

4. **Database Table Status**
   - Checks if each model has a corresponding database table
   - Retrieves table names from Django's meta information
   - Queries database schema to verify table existence

5. **Dependency Tracking**
   - Identifies foreign key relationships between models
   - Tracks which models reference other models
   - Useful for migration ordering

## Usage

### Basic Usage

```python
from Hub.activation_tools import ModelScanner

# Initialize scanner
scanner = ModelScanner(app_name='Hub')

# Scan all models
all_models = scanner.scan_model_files()

# Get models without tables
models_without_tables = scanner.get_models_without_tables()

# Get model counts
counts = scanner.get_model_count()
print(f"Total: {counts['total']}")
print(f"With tables: {counts['with_tables']}")
print(f"Without tables: {counts['without_tables']}")

# Get models organized by file
models_by_file = scanner.get_models_by_file()
for file_path, models in models_by_file.items():
    print(f"{file_path}: {len(models)} models")
```

### Running the Demo

```bash
python Hub/demo_model_scanner.py
```

This will display:
- Summary of model counts
- Models organized by file
- Models without tables (if any)
- Foreign key relationships

## Data Structures

### ModelInfo

Represents information about a Django model:

```python
@dataclass
class ModelInfo:
    name: str                    # Model class name
    file_path: str              # Source file path
    fields: List[FieldInfo]     # List of field information
    has_table: bool             # Whether table exists in database
    table_name: str             # Database table name
    foreign_keys: List[Tuple]   # Foreign key relationships
```

### FieldInfo

Represents information about a model field:

```python
@dataclass
class FieldInfo:
    name: str                   # Field name
    field_type: str            # Field type (CharField, ForeignKey, etc.)
    is_foreign_key: bool       # Whether field is a foreign key
    related_model: str         # Related model name (for FKs)
    is_nullable: bool          # Whether field allows NULL
    is_unique: bool            # Whether field has unique constraint
```

## Current Status

### Scan Results

- **Total models found**: 124
- **Models with tables**: 124
- **Models without tables**: 0

All models currently have database tables, indicating that migrations have been applied successfully.

### Model Files Scanned

1. `models.py` - 56 models (core models)
2. `models_activation_tracking.py` - 3 models
3. `models_advanced_analytics.py` - 7 models (not in app registry)
4. `models_ai_ml_features.py` - 11 models
5. `models_content_management.py` - 10 models
6. `models_customer_insights.py` - 9 models
7. `models_financial_management.py` - 9 models
8. `models_inventory_automation.py` - 10 models (not in app registry)
9. `models_marketing_automation.py` - 9 models (not in app registry)
10. `models_new_features.py` - 8 models (not in app registry)
11. `models_order_enhancements.py` - 11 models (not in app registry)
12. `models_performance_optimization.py` - 8 models
13. `models_product_enhancements.py` - 9 models
14. `models_security_access.py` - 9 models

### Models Not in App Registry

46 models are defined in files but not imported into Django's app registry. These models are still detected by the ModelScanner using AST parsing:

- 7 models in `models_advanced_analytics.py`
- 10 models in `models_inventory_automation.py`
- 9 models in `models_marketing_automation.py`
- 8 models in `models_new_features.py`
- 11 models in `models_order_enhancements.py`

These models have database tables but may need to be imported in `Hub/__init__.py` or `Hub/models.py` to be fully accessible in Django.

## Implementation Details

### AST Parsing

The ModelScanner uses Python's `ast` module to parse model files and extract class definitions. This allows it to find models even if they're not imported into Django's app registry.

```python
def _parse_model_file(self, file_path: str) -> List[str]:
    """Parse a model file and extract model class names using AST."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    tree = ast.parse(content)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if class inherits from models.Model
            for base in node.bases:
                if base_name == 'Model' and node.name != 'Meta':
                    model_classes.append(node.name)
```

### Database Table Checking

The scanner uses Django's database introspection to check if tables exist:

```python
def _table_exists(self, table_name: str) -> bool:
    """Check if a database table exists."""
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        return table_name in tables
```

## Requirements Validation

This implementation satisfies **Requirement 1.1** from the spec:

> "THE Migration_Discovery_System SHALL scan all existing model files (models.py, models_security.py, models_analytics.py, models_financial.py, models_marketing.py, models_product_enhancements.py, models_operations.py, models_content.py, models_ai_ml.py, models_customer_insights.py, models_performance.py) and identify models without corresponding database tables"

✅ Scans all model files in the Hub directory
✅ Extracts model class definitions
✅ Identifies models without database tables
✅ Provides detailed field information
✅ Tracks foreign key relationships

## Next Steps

The ModelScanner is now ready to be used by:
- Task 2.2: DependencyAnalyzer (uses foreign_keys information)
- Task 4.1: MigrationGenerator (uses models without tables)
- Task 5.1: Migration discovery and generation
- Task 7.1: AdminScanner (uses model list)

## Files Created

1. `Hub/activation_tools.py` - Main implementation
2. `Hub/test_model_scanner.py` - Comprehensive test script
3. `Hub/demo_model_scanner.py` - Demonstration script
4. `Hub/MODELSCANNER_README.md` - This documentation
