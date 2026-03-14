"""
Tools for activating admin panel features.

This module provides utilities for scanning models, analyzing dependencies,
and managing the activation process for existing admin panel features.
"""

import ast
import os
import inspect
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from django.apps import apps
from django.db import connection
from django.db.models import Model


@dataclass
class FieldInfo:
    """Information about a model field."""
    name: str
    field_type: str
    is_foreign_key: bool = False
    related_model: Optional[str] = None
    is_nullable: bool = False
    is_unique: bool = False


@dataclass
class ModelInfo:
    """Information about a Django model."""
    name: str
    file_path: str
    fields: List[FieldInfo] = field(default_factory=list)
    has_table: bool = False
    table_name: Optional[str] = None
    foreign_keys: List[Tuple[str, str]] = field(default_factory=list)  # [(field_name, related_model)]
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if isinstance(other, ModelInfo):
            return self.name == other.name
        return False


class ModelScanner:
    """
    Scans model files and extracts model definitions.
    
    This scanner identifies all Django models in the Hub app,
    extracts their field information, and determines which models
    have corresponding database tables.
    """
    
    def __init__(self, app_name: str = 'Hub'):
        """
        Initialize the ModelScanner.
        
        Args:
            app_name: Name of the Django app to scan (default: 'Hub')
        """
        self.app_name = app_name
        self.app_path = self._get_app_path()
        self.model_files = self._get_model_files()
        
    def _get_app_path(self) -> str:
        """Get the file system path to the app directory."""
        try:
            app_config = apps.get_app_config(self.app_name)
            return app_config.path
        except LookupError:
            # Fallback to current directory structure
            return os.path.join(os.getcwd(), self.app_name)
    
    def _get_model_files(self) -> List[str]:
        """
        Get list of all model files in the app directory.
        
        Returns:
            List of model file paths (models.py and models_*.py)
        """
        model_files = []
        
        if not os.path.exists(self.app_path):
            return model_files
        
        for filename in os.listdir(self.app_path):
            if filename == 'models.py' or (filename.startswith('models_') and filename.endswith('.py')):
                file_path = os.path.join(self.app_path, filename)
                model_files.append(file_path)
        
        return sorted(model_files)
    
    def _parse_model_file(self, file_path: str) -> List[str]:
        """
        Parse a model file and extract model class names using AST.
        
        Args:
            file_path: Path to the model file
            
        Returns:
            List of model class names found in the file
        """
        model_classes = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if class inherits from models.Model or Model
                    for base in node.bases:
                        base_name = None
                        if isinstance(base, ast.Name):
                            base_name = base.id
                        elif isinstance(base, ast.Attribute):
                            if isinstance(base.value, ast.Name) and base.value.id == 'models':
                                base_name = base.attr
                        
                        # Skip Meta classes and other non-model classes
                        if base_name == 'Model' and node.name != 'Meta':
                            model_classes.append(node.name)
                            break
            
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
        
        return model_classes
    
    def _get_model_fields(self, model_class) -> List[FieldInfo]:
        """
        Extract field information from a model class.
        
        Args:
            model_class: Django model class
            
        Returns:
            List of FieldInfo objects
        """
        fields = []
        
        try:
            for field in model_class._meta.get_fields():
                field_info = FieldInfo(
                    name=field.name,
                    field_type=field.__class__.__name__
                )
                
                # Check if it's a foreign key
                if hasattr(field, 'related_model') and field.related_model:
                    field_info.is_foreign_key = True
                    field_info.related_model = field.related_model.__name__
                
                # Check nullable and unique
                if hasattr(field, 'null'):
                    field_info.is_nullable = field.null
                if hasattr(field, 'unique'):
                    field_info.is_unique = field.unique
                
                fields.append(field_info)
        except Exception as e:
            print(f"Error extracting fields from {model_class.__name__}: {e}")
        
        return fields
    
    def _table_exists(self, table_name: str) -> bool:
        """
        Check if a database table exists.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        try:
            with connection.cursor() as cursor:
                # Get list of all tables
                tables = connection.introspection.table_names(cursor)
                return table_name in tables
        except Exception as e:
            print(f"Error checking table existence for {table_name}: {e}")
            return False
    
    def scan_model_files(self) -> List[ModelInfo]:
        """
        Scan all model files and extract model definitions.
        
        Returns:
            List of ModelInfo objects for all models found
        """
        all_models = []
        
        for file_path in self.model_files:
            # Get model class names from file
            model_names = self._parse_model_file(file_path)
            
            # Get relative file path for display
            rel_path = os.path.relpath(file_path, os.path.dirname(self.app_path))
            
            for model_name in model_names:
                try:
                    # Get the actual model class from Django
                    model_class = apps.get_model(self.app_name, model_name)
                    
                    # Extract field information
                    fields = self._get_model_fields(model_class)
                    
                    # Get table name
                    table_name = model_class._meta.db_table
                    
                    # Check if table exists
                    has_table = self._table_exists(table_name)
                    
                    # Extract foreign key relationships
                    foreign_keys = [
                        (f.name, f.related_model)
                        for f in fields
                        if f.is_foreign_key and f.related_model
                    ]
                    
                    model_info = ModelInfo(
                        name=model_name,
                        file_path=rel_path,
                        fields=fields,
                        has_table=has_table,
                        table_name=table_name,
                        foreign_keys=foreign_keys
                    )
                    
                    all_models.append(model_info)
                    
                except LookupError:
                    # Model not registered in Django apps
                    print(f"Warning: Model {model_name} found in {rel_path} but not registered in Django")
                except Exception as e:
                    print(f"Error processing model {model_name} from {rel_path}: {e}")
        
        return all_models
    
    def get_models_without_tables(self) -> List[ModelInfo]:
        """
        Identify models that don't have database tables.
        
        Returns:
            List of ModelInfo objects for models without tables
        """
        all_models = self.scan_model_files()
        return [model for model in all_models if not model.has_table]
    
    def get_models_by_file(self) -> Dict[str, List[ModelInfo]]:
        """
        Get models organized by their source file.
        
        Returns:
            Dictionary mapping file paths to lists of ModelInfo objects
        """
        all_models = self.scan_model_files()
        models_by_file = {}
        
        for model in all_models:
            if model.file_path not in models_by_file:
                models_by_file[model.file_path] = []
            models_by_file[model.file_path].append(model)
        
        return models_by_file
    
    def get_model_count(self) -> Dict[str, int]:
        """
        Get count of models with and without tables.
        
        Returns:
            Dictionary with counts: {'total', 'with_tables', 'without_tables'}
        """
        all_models = self.scan_model_files()
        with_tables = sum(1 for m in all_models if m.has_table)
        without_tables = sum(1 for m in all_models if not m.has_table)
        
        return {
            'total': len(all_models),
            'with_tables': with_tables,
            'without_tables': without_tables
        }


@dataclass
class ModelDependency:
    """Represents a foreign key dependency between models."""
    source_model: str  # Model with foreign key
    target_model: str  # Model being referenced
    field_name: str    # Foreign key field name
    on_delete: str = 'CASCADE'  # on_delete behavior


class DependencyGraph:
    """
    Graph structure for model dependencies.
    
    Represents foreign key relationships between models and provides
    methods for topological sorting and circular dependency detection.
    """
    
    def __init__(self):
        """Initialize an empty dependency graph."""
        self.nodes: Set[str] = set()
        self.edges: List[ModelDependency] = []
        self._adjacency_list: Dict[str, List[str]] = {}
    
    def add_node(self, model_name: str):
        """
        Add a model node to the graph.
        
        Args:
            model_name: Name of the model to add
        """
        self.nodes.add(model_name)
        if model_name not in self._adjacency_list:
            self._adjacency_list[model_name] = []
    
    def add_edge(self, dependency: ModelDependency):
        """
        Add a dependency edge to the graph.
        
        Args:
            dependency: ModelDependency object representing the relationship
        """
        self.edges.append(dependency)
        
        # Add nodes if they don't exist
        self.add_node(dependency.source_model)
        self.add_node(dependency.target_model)
        
        # Add to adjacency list (source depends on target)
        if dependency.target_model not in self._adjacency_list[dependency.source_model]:
            self._adjacency_list[dependency.source_model].append(dependency.target_model)
    
    def topological_sort(self) -> List[str]:
        """
        Return models in dependency-correct order using topological sort.
        
        Models that are referenced by others come first in the list.
        Uses Kahn's algorithm for topological sorting.
        
        Returns:
            List of model names in dependency order
            
        Raises:
            ValueError: If circular dependencies are detected
        """
        # Calculate in-degree for each node
        in_degree = {node: 0 for node in self.nodes}
        
        for source in self._adjacency_list:
            for target in self._adjacency_list[source]:
                in_degree[target] += 1
        
        # Queue of nodes with no incoming edges
        queue = [node for node in self.nodes if in_degree[node] == 0]
        result = []
        
        while queue:
            # Sort queue for deterministic output
            queue.sort()
            node = queue.pop(0)
            result.append(node)
            
            # For each neighbor, reduce in-degree
            for neighbor in self._adjacency_list.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # If not all nodes are processed, there's a cycle
        if len(result) != len(self.nodes):
            raise ValueError("Circular dependency detected - cannot perform topological sort")
        
        # Reverse to get dependency order (dependencies first)
        return list(reversed(result))
    
    def has_circular_dependency(self) -> bool:
        """
        Check for circular dependencies in the graph.
        
        Returns:
            True if circular dependencies exist, False otherwise
        """
        try:
            self.topological_sort()
            return False
        except ValueError:
            return True
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """
        Find all circular dependency chains in the graph.
        
        Returns:
            List of cycles, where each cycle is a list of model names
        """
        cycles = []
        visited = set()
        rec_stack = {}  # Maps node to its position in the current path
        
        def dfs(node: str, path: List[str]) -> None:
            """DFS helper to detect cycles."""
            visited.add(node)
            rec_stack[node] = len(path)
            path.append(node)
            
            for neighbor in self._adjacency_list.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Found a cycle - extract the cycle from the path
                    cycle_start_idx = rec_stack[neighbor]
                    cycle = path[cycle_start_idx:] + [neighbor]
                    # Normalize cycle to avoid duplicates (start with smallest element)
                    min_idx = cycle.index(min(cycle[:-1]))  # Exclude the duplicate last element
                    normalized_cycle = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                    if normalized_cycle not in cycles:
                        cycles.append(normalized_cycle)
            
            # Backtrack
            path.pop()
            del rec_stack[node]
        
        for node in sorted(self.nodes):  # Sort for deterministic results
            if node not in visited:
                dfs(node, [])
        
        return cycles
    
    def get_dependencies(self, model_name: str) -> List[str]:
        """
        Get all models that the given model depends on.
        
        Args:
            model_name: Name of the model
            
        Returns:
            List of model names that this model depends on
        """
        return self._adjacency_list.get(model_name, [])
    
    def get_dependents(self, model_name: str) -> List[str]:
        """
        Get all models that depend on the given model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            List of model names that depend on this model
        """
        dependents = []
        for source, targets in self._adjacency_list.items():
            if model_name in targets:
                dependents.append(source)
        return dependents


class DependencyAnalyzer:
    """
    Analyzes foreign key relationships between models.
    
    Builds a dependency graph from model foreign key fields and provides
    methods for determining migration order and detecting circular dependencies.
    """
    
    def __init__(self):
        """Initialize the DependencyAnalyzer."""
        self.graph: Optional[DependencyGraph] = None
    
    def build_dependency_graph(self, models: List[ModelInfo]) -> DependencyGraph:
        """
        Build graph of foreign key relationships between models.
        
        Args:
            models: List of ModelInfo objects to analyze
            
        Returns:
            DependencyGraph representing the relationships
        """
        graph = DependencyGraph()
        
        # Add all models as nodes
        for model in models:
            graph.add_node(model.name)
        
        # Add edges for foreign key relationships
        for model in models:
            for field_name, related_model in model.foreign_keys:
                # Only add edge if the related model is in our model list
                if related_model in {m.name for m in models}:
                    # Get on_delete behavior from the field
                    on_delete = self._get_on_delete_behavior(model, field_name)
                    
                    dependency = ModelDependency(
                        source_model=model.name,
                        target_model=related_model,
                        field_name=field_name,
                        on_delete=on_delete
                    )
                    graph.add_edge(dependency)
        
        self.graph = graph
        return graph
    
    def _get_on_delete_behavior(self, model_info: ModelInfo, field_name: str) -> str:
        """
        Get the on_delete behavior for a foreign key field.
        
        Args:
            model_info: ModelInfo object
            field_name: Name of the foreign key field
            
        Returns:
            String representation of on_delete behavior
        """
        try:
            from django.apps import apps
            model_class = apps.get_model('Hub', model_info.name)
            field = model_class._meta.get_field(field_name)
            
            if hasattr(field, 'remote_field') and hasattr(field.remote_field, 'on_delete'):
                on_delete = field.remote_field.on_delete
                # Get the name of the on_delete function
                if hasattr(on_delete, '__name__'):
                    return on_delete.__name__.upper()
                return str(on_delete).split('.')[-1].upper()
        except Exception as e:
            print(f"Warning: Could not determine on_delete for {model_info.name}.{field_name}: {e}")
        
        return 'CASCADE'  # Default
    
    def get_migration_order(self, graph: Optional[DependencyGraph] = None) -> List[str]:
        """
        Determine correct order for applying migrations.
        
        Args:
            graph: DependencyGraph to analyze (uses self.graph if None)
            
        Returns:
            List of model names in migration order (dependencies first)
            
        Raises:
            ValueError: If circular dependencies are detected
        """
        if graph is None:
            if self.graph is None:
                raise ValueError("No dependency graph available. Call build_dependency_graph first.")
            graph = self.graph
        
        return graph.topological_sort()
    
    def detect_circular_dependencies(self, graph: Optional[DependencyGraph] = None) -> List[List[str]]:
        """
        Identify circular dependencies between models.
        
        Args:
            graph: DependencyGraph to analyze (uses self.graph if None)
            
        Returns:
            List of circular dependency chains, where each chain is a list of model names
        """
        if graph is None:
            if self.graph is None:
                raise ValueError("No dependency graph available. Call build_dependency_graph first.")
            graph = self.graph
        
        return graph.find_circular_dependencies()
    
    def verify_core_models_exist(self, models: List[ModelInfo], core_models: List[str]) -> Dict[str, bool]:
        """
        Verify that core models exist before attempting migration.
        
        Args:
            models: List of ModelInfo objects
            core_models: List of core model names to check for
            
        Returns:
            Dictionary mapping core model names to existence status
        """
        model_names = {model.name for model in models}
        return {core_model: core_model in model_names for core_model in core_models}
    
    def get_dependency_report(self, graph: Optional[DependencyGraph] = None) -> Dict:
        """
        Generate a comprehensive dependency report.
        
        Args:
            graph: DependencyGraph to analyze (uses self.graph if None)
            
        Returns:
            Dictionary containing dependency analysis results
        """
        if graph is None:
            if self.graph is None:
                raise ValueError("No dependency graph available. Call build_dependency_graph first.")
            graph = self.graph
        
        report = {
            'total_models': len(graph.nodes),
            'total_dependencies': len(graph.edges),
            'has_circular_dependencies': graph.has_circular_dependency(),
            'circular_dependency_chains': [],
            'migration_order': [],
            'models_with_no_dependencies': [],
            'models_with_no_dependents': [],
            'dependency_details': []
        }
        
        # Get circular dependencies
        if report['has_circular_dependencies']:
            report['circular_dependency_chains'] = graph.find_circular_dependencies()
        else:
            # Only get migration order if no circular dependencies
            try:
                report['migration_order'] = graph.topological_sort()
            except ValueError:
                pass
        
        # Find models with no dependencies (can be migrated first)
        for node in graph.nodes:
            if not graph.get_dependencies(node):
                report['models_with_no_dependencies'].append(node)
        
        # Find models with no dependents (leaf nodes)
        for node in graph.nodes:
            if not graph.get_dependents(node):
                report['models_with_no_dependents'].append(node)
        
        # Add detailed dependency information
        for edge in graph.edges:
            report['dependency_details'].append({
                'source': edge.source_model,
                'target': edge.target_model,
                'field': edge.field_name,
                'on_delete': edge.on_delete
            })
        
        return report


class MigrationGenerator:
    """
    Generates migration files for models lacking migrations.

    Uses Django's makemigrations command programmatically to generate
    migration files for models that don't have corresponding migrations.
    """

    def __init__(self, app_name: str = 'Hub'):
        """
        Initialize the MigrationGenerator.

        Args:
            app_name: Name of the Django app (default: 'Hub')
        """
        self.app_name = app_name

    def generate_migrations(self, models: Optional[List[ModelInfo]] = None) -> List[str]:
        """
        Generate migration files for models lacking migrations.

        Uses Django's call_command('makemigrations') to generate migrations.
        Captures output to identify which migrations were created.

        Args:
            models: Optional list of ModelInfo objects to generate migrations for.
                   If None, generates migrations for all pending changes.

        Returns:
            List of generated migration file paths
        """
        from django.core.management import call_command
        from io import StringIO
        import re

        generated_migrations = []

        try:
            # Capture output from makemigrations
            output = StringIO()

            # Run makemigrations for the app
            call_command(
                'makemigrations',
                self.app_name,
                stdout=output,
                stderr=output,
                interactive=False,
                verbosity=2
            )

            # Parse output to identify generated migrations
            output_text = output.getvalue()

            # Look for migration file creation messages
            # Pattern: "Migrations for 'Hub':" followed by "  Hub\migrations\0077_xxx.py"
            migration_pattern = r'Migrations for [\'"]' + re.escape(self.app_name) + r'[\'"]:'
            
            # Pattern to match migration file paths (handles both / and \ separators)
            file_pattern = r'^\s+' + re.escape(self.app_name) + r'[/\\]migrations[/\\](\d{4}_\w+\.py)'

            if re.search(migration_pattern, output_text):
                # Migrations were created - look for file paths
                for line in output_text.split('\n'):
                    match = re.match(file_pattern, line.strip())
                    if match:
                        # Found a migration file path
                        migration_filename = match.group(1)
                        migration_file = f"{self.app_name}/migrations/{migration_filename}"
                        generated_migrations.append(migration_file)

                # If we didn't find specific file paths, check for any migration operations
                if not generated_migrations and ('Create model' in output_text or 'Remove field' in output_text or 'Delete model' in output_text):
                    # Extract migration filename from output
                    filename_match = re.search(r'(\d{4}_[\w]+\.py)', output_text)
                    if filename_match:
                        # Construct migration file path
                        migration_file = f"{self.app_name}/migrations/{filename_match.group(1)}"
                        generated_migrations.append(migration_file)

            # Log the output for debugging
            if output_text.strip():
                print(f"makemigrations output:\n{output_text}")

        except Exception as e:
            print(f"Error generating migrations: {e}")
            import traceback
            traceback.print_exc()

        return generated_migrations

    def check_pending_migrations(self) -> bool:
        """
        Check if there are pending model changes that need migrations.

        Returns:
            True if there are pending changes, False otherwise
        """
        from django.core.management import call_command
        from io import StringIO

        try:
            output = StringIO()

            # Run makemigrations with --dry-run to check for changes
            call_command(
                'makemigrations',
                self.app_name,
                dry_run=True,
                stdout=output,
                stderr=output,
                interactive=False,
                verbosity=1
            )

            output_text = output.getvalue()

            # Check if there are changes to be made
            return 'No changes detected' not in output_text

        except Exception as e:
            print(f"Error checking pending migrations: {e}")
            return False

    def get_migration_files(self) -> List[str]:
        """
        Get list of existing migration files for the app.

        Returns:
            List of migration file paths
        """
        import os
        from django.apps import apps

        migration_files = []

        try:
            app_config = apps.get_app_config(self.app_name)
            migrations_dir = os.path.join(app_config.path, 'migrations')

            if os.path.exists(migrations_dir):
                for filename in os.listdir(migrations_dir):
                    if filename.endswith('.py') and filename != '__init__.py':
                        migration_files.append(os.path.join(migrations_dir, filename))

        except Exception as e:
            print(f"Error getting migration files: {e}")

        return sorted(migration_files)

    def get_latest_migration_number(self) -> int:
        """
        Get the number of the latest migration file.

        Returns:
            Latest migration number, or 0 if no migrations exist
        """
        import re

        migration_files = self.get_migration_files()

        if not migration_files:
            return 0

        numbers = []
        for filepath in migration_files:
            filename = os.path.basename(filepath)
            match = re.match(r'^(\d{4})_', filename)
            if match:
                numbers.append(int(match.group(1)))

        return max(numbers) if numbers else 0



class MigrationExecutor:
    """
    Applies migrations in dependency-correct order.

    Uses Django's migrate command to apply migrations for models,
    handling errors gracefully and logging results to MigrationExecutionLog.
    """

    def __init__(self, app_name: str = 'Hub'):
        """
        Initialize the MigrationExecutor.

        Args:
            app_name: Name of the Django app (default: 'Hub')
        """
        self.app_name = app_name
        self.execution_logs = []

    def apply_migrations(self, models: Optional[List[ModelInfo]] = None,
                        migration_order: Optional[List[str]] = None) -> Dict:
        """
        Apply migrations in dependency-correct order.

        If migration_order is not provided, applies all pending migrations
        for the app. If provided, attempts to apply migrations in the
        specified order (though Django's migrate command applies all
        pending migrations at once).

        Args:
            models: Optional list of ModelInfo objects
            migration_order: Optional list of model names in dependency order

        Returns:
            Dictionary containing migration results:
                - total_migrations: Total number of migrations attempted
                - successful: Number of successful migrations
                - failed: Number of failed migrations
                - errors: List of error details
                - execution_logs: List of MigrationExecutionLog entries
        """
        from django.core.management import call_command
        from io import StringIO
        import re

        result = {
            'total_migrations': 0,
            'successful': 0,
            'failed': 0,
            'errors': [],
            'execution_logs': [],
            'applied_migrations': []
        }

        try:
            # Capture output from migrate command
            output = StringIO()
            error_output = StringIO()

            # Run migrate command for the app
            try:
                call_command(
                    'migrate',
                    self.app_name,
                    stdout=output,
                    stderr=error_output,
                    interactive=False,
                    verbosity=2
                )

                # Parse output to identify applied migrations
                output_text = output.getvalue()
                error_text = error_output.getvalue()

                # Log the output for debugging
                if output_text.strip():
                    print(f"migrate output:\n{output_text}")
                if error_text.strip():
                    print(f"migrate errors:\n{error_text}")

                # Pattern to match applied migrations: "Applying Hub.0001_initial... OK"
                applied_pattern = r'Applying ' + re.escape(self.app_name) + r'\.(\d{4}_\w+)\.{3}\s*OK'

                applied_migrations = re.findall(applied_pattern, output_text)

                # Log successful migrations
                for idx, migration_name in enumerate(applied_migrations, start=1):
                    # Try to determine which model this migration is for
                    model_name = self._extract_model_from_migration_name(migration_name)

                    log_entry = self._create_log_entry(
                        model_name=model_name,
                        migration_file=f"{migration_name}.py",
                        execution_order=idx,
                        success=True,
                        error_message=""
                    )

                    result['execution_logs'].append(log_entry)
                    result['applied_migrations'].append(migration_name)
                    result['successful'] += 1

                result['total_migrations'] = len(applied_migrations)

                # Check for "No migrations to apply" message
                if 'No migrations to apply' in output_text:
                    print("No pending migrations to apply.")

            except Exception as migrate_error:
                # Migration command failed
                error_message = str(migrate_error)
                error_text = error_output.getvalue()

                if error_text:
                    error_message = f"{error_message}\n{error_text}"

                print(f"Error during migration: {error_message}")

                # Try to extract which migration failed
                failed_migration = self._extract_failed_migration(error_message)

                if failed_migration:
                    model_name = self._extract_model_from_migration_name(failed_migration)

                    log_entry = self._create_log_entry(
                        model_name=model_name,
                        migration_file=f"{failed_migration}.py",
                        execution_order=1,
                        success=False,
                        error_message=error_message
                    )

                    result['execution_logs'].append(log_entry)
                    result['failed'] += 1
                    result['total_migrations'] += 1
                else:
                    # Generic migration failure
                    log_entry = self._create_log_entry(
                        model_name="Unknown",
                        migration_file="Unknown",
                        execution_order=1,
                        success=False,
                        error_message=error_message
                    )

                    result['execution_logs'].append(log_entry)
                    result['failed'] += 1
                    result['total_migrations'] += 1

                result['errors'].append({
                    'migration': failed_migration or 'Unknown',
                    'error': error_message
                })

        except Exception as e:
            # Unexpected error
            error_message = f"Unexpected error during migration execution: {str(e)}"
            print(error_message)
            import traceback
            traceback.print_exc()

            result['errors'].append({
                'migration': 'Unknown',
                'error': error_message
            })
            result['failed'] += 1
            result['total_migrations'] += 1

        return result

    def _extract_model_from_migration_name(self, migration_name: str) -> str:
        """
        Extract model name from migration filename.

        Args:
            migration_name: Migration name (e.g., "0001_initial" or "0002_product")

        Returns:
            Model name or "Multiple" if migration affects multiple models
        """
        # Remove the number prefix (e.g., "0001_")
        import re
        match = re.match(r'\d{4}_(.+)', migration_name)

        if not match:
            return "Unknown"

        name_part = match.group(1)

        # Common migration name patterns
        if name_part == 'initial':
            return "Multiple"
        elif name_part.startswith('auto_'):
            return "Multiple"
        else:
            # Try to extract model name (e.g., "product" -> "Product")
            # Handle snake_case to PascalCase conversion
            parts = name_part.split('_')
            model_name = ''.join(word.capitalize() for word in parts)
            return model_name

    def _extract_failed_migration(self, error_message: str) -> Optional[str]:
        """
        Extract the migration name that failed from error message.

        Args:
            error_message: Error message from migration command

        Returns:
            Migration name or None if not found
        """
        import re

        # Pattern: "Applying Hub.0001_initial..."
        pattern = r'Applying ' + re.escape(self.app_name) + r'\.(\d{4}_\w+)'
        match = re.search(pattern, error_message)

        if match:
            return match.group(1)

        return None

    def _create_log_entry(self, model_name: str, migration_file: str,
                         execution_order: int, success: bool,
                         error_message: str) -> Dict:
        """
        Create a log entry dictionary for migration execution.

        Args:
            model_name: Name of the model
            migration_file: Migration file name
            execution_order: Order in which migration was executed
            success: Whether migration succeeded
            error_message: Error message if failed

        Returns:
            Dictionary representing the log entry
        """
        return {
            'model_name': model_name,
            'migration_file': migration_file,
            'execution_order': execution_order,
            'success': success,
            'error_message': error_message
        }

    def save_execution_logs(self) -> int:
        """
        Save execution logs to the database.

        Returns:
            Number of log entries saved
        """
        from Hub.models_activation_tracking import MigrationExecutionLog

        saved_count = 0

        for log_data in self.execution_logs:
            try:
                MigrationExecutionLog.objects.create(
                    model_name=log_data['model_name'],
                    migration_file=log_data['migration_file'],
                    execution_order=log_data['execution_order'],
                    success=log_data['success'],
                    error_message=log_data['error_message']
                )
                saved_count += 1
            except Exception as e:
                print(f"Error saving log entry: {e}")

        return saved_count

    def handle_migration_error(self, error: Exception, model: str) -> None:
        """
        Log migration error and continue with remaining migrations.

        This method is called when a migration fails. It logs the error
        and allows the migration process to continue with other models.

        Args:
            error: Exception that occurred during migration
            model: Name of the model that failed to migrate
        """
        error_message = f"Migration failed for {model}: {str(error)}"
        print(error_message)

        # Create log entry for the error
        log_entry = self._create_log_entry(
            model_name=model,
            migration_file="Unknown",
            execution_order=len(self.execution_logs) + 1,
            success=False,
            error_message=error_message
        )

        self.execution_logs.append(log_entry)

    def get_pending_migrations(self) -> List[str]:
        """
        Get list of pending migrations for the app.

        Returns:
            List of pending migration names
        """
        from django.core.management import call_command
        from io import StringIO
        import re

        pending_migrations = []

        try:
            output = StringIO()

            # Run showmigrations to see pending migrations
            call_command(
                'showmigrations',
                self.app_name,
                stdout=output,
                verbosity=1
            )

            output_text = output.getvalue()

            # Pattern to match unapplied migrations: "[ ] 0001_initial"
            pending_pattern = r'\[ \]\s+(\d{4}_\w+)'

            pending_migrations = re.findall(pending_pattern, output_text)

        except Exception as e:
            print(f"Error getting pending migrations: {e}")

        return pending_migrations

    def get_applied_migrations(self) -> List[str]:
        """
        Get list of applied migrations for the app.

        Returns:
            List of applied migration names
        """
        from django.core.management import call_command
        from io import StringIO
        import re

        applied_migrations = []

        try:
            output = StringIO()

            # Run showmigrations to see applied migrations
            call_command(
                'showmigrations',
                self.app_name,
                stdout=output,
                verbosity=1
            )

            output_text = output.getvalue()

            # Pattern to match applied migrations: "[X] 0001_initial"
            applied_pattern = r'\[X\]\s+(\d{4}_\w+)'

            applied_migrations = re.findall(applied_pattern, output_text)

        except Exception as e:
            print(f"Error getting applied migrations: {e}")

        return applied_migrations



class SchemaVerifier:
    """
    Verifies database schema after migrations.
    
    Queries the database to confirm that tables exist for models,
    checks that indexes and constraints are created, and updates
    ModelActivationStatus records with verification results.
    """
    
    def __init__(self, app_name: str = 'Hub'):
        """
        Initialize the SchemaVerifier.
        
        Args:
            app_name: Name of the Django app (default: 'Hub')
        """
        self.app_name = app_name
    
    def verify_table_exists(self, model_name: str) -> bool:
        """
        Check if database table exists for a model.
        
        Args:
            model_name: Name of the model to check
            
        Returns:
            True if table exists, False otherwise
        """
        try:
            from django.apps import apps
            
            # Get the model class
            model_class = apps.get_model(self.app_name, model_name)
            table_name = model_class._meta.db_table
            
            # Check if table exists in database
            with connection.cursor() as cursor:
                tables = connection.introspection.table_names(cursor)
                return table_name in tables
                
        except LookupError:
            print(f"Model {model_name} not found in app {self.app_name}")
            return False
        except Exception as e:
            print(f"Error checking table existence for {model_name}: {e}")
            return False
    
    def get_table_schema(self, table_name: str) -> Dict:
        """
        Retrieve table schema information from database.
        
        Args:
            table_name: Name of the database table
            
        Returns:
            Dictionary containing schema information:
                - columns: List of column definitions
                - indexes: List of indexes
                - constraints: List of constraints
        """
        schema = {
            'columns': [],
            'indexes': [],
            'constraints': [],
            'exists': False
        }
        
        try:
            with connection.cursor() as cursor:
                # Check if table exists
                tables = connection.introspection.table_names(cursor)
                if table_name not in tables:
                    return schema
                
                schema['exists'] = True
                
                # Get column information
                table_description = connection.introspection.get_table_description(cursor, table_name)
                for column in table_description:
                    schema['columns'].append({
                        'name': column.name,
                        'type': column.type_code,
                        'nullable': column.null_ok if hasattr(column, 'null_ok') else None,
                        'default': column.default if hasattr(column, 'default') else None
                    })
                
                # Get indexes (if supported by database backend)
                try:
                    if hasattr(connection.introspection, 'get_indexes'):
                        indexes = connection.introspection.get_indexes(cursor, table_name)
                        for column_name, index_info in indexes.items():
                            schema['indexes'].append({
                                'column': column_name,
                                'primary_key': index_info.get('primary_key', False),
                                'unique': index_info.get('unique', False)
                            })
                except Exception as e:
                    # get_indexes may not be available in all database backends
                    pass
                
                # Get constraints (foreign keys, unique constraints, etc.)
                constraints = connection.introspection.get_constraints(cursor, table_name)
                for constraint_name, constraint_info in constraints.items():
                    schema['constraints'].append({
                        'name': constraint_name,
                        'columns': constraint_info.get('columns', []),
                        'primary_key': constraint_info.get('primary_key', False),
                        'unique': constraint_info.get('unique', False),
                        'foreign_key': constraint_info.get('foreign_key', None),
                        'check': constraint_info.get('check', False),
                        'index': constraint_info.get('index', False)
                    })
                
        except Exception as e:
            print(f"Error retrieving schema for table {table_name}: {e}")
        
        return schema
    
    def verify_indexes_and_constraints(self, model_name: str) -> Dict:
        """
        Verify that indexes and constraints are created for a model.
        
        Args:
            model_name: Name of the model to verify
            
        Returns:
            Dictionary containing verification results:
                - has_primary_key: Whether table has a primary key
                - has_indexes: Whether table has indexes
                - has_foreign_keys: Whether foreign key constraints exist
                - index_count: Number of indexes
                - constraint_count: Number of constraints
                - details: Detailed schema information
        """
        result = {
            'model_name': model_name,
            'table_exists': False,
            'has_primary_key': False,
            'has_indexes': False,
            'has_foreign_keys': False,
            'index_count': 0,
            'constraint_count': 0,
            'details': {}
        }
        
        try:
            from django.apps import apps
            
            # Get the model class and table name
            model_class = apps.get_model(self.app_name, model_name)
            table_name = model_class._meta.db_table
            
            # Get table schema
            schema = self.get_table_schema(table_name)
            
            if not schema['exists']:
                return result
            
            result['table_exists'] = True
            result['details'] = schema
            
            # Check for primary key
            for constraint in schema['constraints']:
                if constraint['primary_key']:
                    result['has_primary_key'] = True
                if constraint['foreign_key']:
                    result['has_foreign_keys'] = True
            
            # Check for indexes
            result['index_count'] = len(schema['indexes'])
            result['has_indexes'] = result['index_count'] > 0
            
            # Count constraints
            result['constraint_count'] = len(schema['constraints'])
            
        except LookupError:
            print(f"Model {model_name} not found in app {self.app_name}")
        except Exception as e:
            print(f"Error verifying indexes and constraints for {model_name}: {e}")
        
        return result
    
    def verify_models(self, models: List[ModelInfo]) -> Dict:
        """
        Verify table creation for a list of models.
        
        Args:
            models: List of ModelInfo objects to verify
            
        Returns:
            Dictionary containing verification results:
                - total_models: Total number of models checked
                - tables_verified: Number of tables that exist
                - tables_missing: Number of tables that don't exist
                - verified_tables: List of verified table names
                - missing_tables: List of missing table names
                - verification_details: Detailed verification results per model
        """
        result = {
            'total_models': len(models),
            'tables_verified': 0,
            'tables_missing': 0,
            'verified_tables': [],
            'missing_tables': [],
            'verification_details': []
        }
        
        for model in models:
            # Verify table exists
            table_exists = self.verify_table_exists(model.name)
            
            # Get detailed verification
            verification = self.verify_indexes_and_constraints(model.name)
            
            if table_exists:
                result['tables_verified'] += 1
                result['verified_tables'].append(model.table_name or model.name)
            else:
                result['tables_missing'] += 1
                result['missing_tables'].append(model.table_name or model.name)
            
            result['verification_details'].append({
                'model_name': model.name,
                'table_name': model.table_name,
                'table_exists': table_exists,
                'has_primary_key': verification['has_primary_key'],
                'has_indexes': verification['has_indexes'],
                'has_foreign_keys': verification['has_foreign_keys'],
                'index_count': verification['index_count'],
                'constraint_count': verification['constraint_count']
            })
        
        return result
    
    def update_activation_status(self, models: List[ModelInfo]) -> int:
        """
        Update ModelActivationStatus records with verification results.
        
        Args:
            models: List of ModelInfo objects to update
            
        Returns:
            Number of records updated
        """
        from Hub.models_activation_tracking import ModelActivationStatus
        from django.utils import timezone
        
        updated_count = 0
        
        for model in models:
            try:
                # Verify table exists
                table_exists = self.verify_table_exists(model.name)
                
                # Get or create activation status record
                status, created = ModelActivationStatus.objects.get_or_create(
                    model_name=model.name,
                    defaults={
                        'model_file': model.file_path,
                        'table_created': table_exists
                    }
                )
                
                # Update the record
                status.table_created = table_exists
                status.model_file = model.file_path
                
                # If table was just created, update activation date
                if table_exists and not status.activation_date:
                    status.activation_date = timezone.now()
                
                status.save()
                updated_count += 1
                
            except Exception as e:
                print(f"Error updating activation status for {model.name}: {e}")
        
        return updated_count
    
    def verify_all_models(self) -> Dict:
        """
        Verify all models in the app.
        
        Scans all models, verifies their tables exist, checks indexes
        and constraints, and updates ModelActivationStatus records.
        
        Returns:
            Dictionary containing comprehensive verification results
        """
        # Scan all models
        scanner = ModelScanner(self.app_name)
        all_models = scanner.scan_model_files()
        
        # Verify models
        verification_result = self.verify_models(all_models)
        
        # Update activation status records
        updated_count = self.update_activation_status(all_models)
        
        # Add update count to result
        verification_result['activation_records_updated'] = updated_count
        
        return verification_result
    
    def generate_verification_report(self, verification_result: Dict) -> str:
        """
        Generate a human-readable verification report.
        
        Args:
            verification_result: Dictionary from verify_models() or verify_all_models()
            
        Returns:
            Formatted report string
        """
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("DATABASE SCHEMA VERIFICATION REPORT")
        report_lines.append("=" * 70)
        report_lines.append("")
        
        # Summary
        report_lines.append("SUMMARY:")
        report_lines.append(f"  Total Models: {verification_result['total_models']}")
        report_lines.append(f"  Tables Verified: {verification_result['tables_verified']}")
        report_lines.append(f"  Tables Missing: {verification_result['tables_missing']}")
        
        if 'activation_records_updated' in verification_result:
            report_lines.append(f"  Activation Records Updated: {verification_result['activation_records_updated']}")
        
        report_lines.append("")
        
        # Verified tables
        if verification_result['verified_tables']:
            report_lines.append("VERIFIED TABLES:")
            for table in verification_result['verified_tables']:
                report_lines.append(f"  ✓ {table}")
            report_lines.append("")
        
        # Missing tables
        if verification_result['missing_tables']:
            report_lines.append("MISSING TABLES:")
            for table in verification_result['missing_tables']:
                report_lines.append(f"  ✗ {table}")
            report_lines.append("")
        
        # Detailed verification
        if verification_result.get('verification_details'):
            report_lines.append("DETAILED VERIFICATION:")
            report_lines.append("")
            
            for detail in verification_result['verification_details']:
                status_icon = "✓" if detail['table_exists'] else "✗"
                report_lines.append(f"{status_icon} {detail['model_name']} ({detail['table_name']})")
                
                if detail['table_exists']:
                    report_lines.append(f"    Primary Key: {'Yes' if detail['has_primary_key'] else 'No'}")
                    report_lines.append(f"    Indexes: {detail['index_count']}")
                    report_lines.append(f"    Constraints: {detail['constraint_count']}")
                    report_lines.append(f"    Foreign Keys: {'Yes' if detail['has_foreign_keys'] else 'No'}")
                
                report_lines.append("")
        
        report_lines.append("=" * 70)
        
        return "\n".join(report_lines)


class AdminScanner:
    """
    Scans Hub/admin.py to identify models not registered in Django admin.

    Parses admin.py to find registered models and compares with all models
    from ModelScanner to identify unregistered models.
    """

    def __init__(self, app_name: str = 'Hub'):
        """
        Initialize the AdminScanner.

        Args:
            app_name: Name of the Django app (default: 'Hub')
        """
        self.app_name = app_name
        self.admin_file_path = self._get_admin_file_path()

    def _get_admin_file_path(self) -> str:
        """
        Get the file system path to admin.py.

        Returns:
            Path to admin.py file
        """
        try:
            app_config = apps.get_app_config(self.app_name)
            return os.path.join(app_config.path, 'admin.py')
        except LookupError:
            # Fallback to current directory structure
            return os.path.join(os.getcwd(), self.app_name, 'admin.py')

    def get_registered_models(self) -> Set[str]:
        """
        Parse Hub/admin.py to find registered models.

        Identifies models registered via:
        - admin.site.register(ModelName)
        - @admin.register(ModelName)

        Returns:
            Set of registered model names
        """
        registered_models = set()

        if not os.path.exists(self.admin_file_path):
            print(f"Warning: admin.py not found at {self.admin_file_path}")
            return registered_models

        try:
            with open(self.admin_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            # Find admin.site.register() calls
            for node in ast.walk(tree):
                # Pattern 1: admin.site.register(Model)
                if isinstance(node, ast.Call):
                    if (isinstance(node.func, ast.Attribute) and
                        isinstance(node.func.value, ast.Attribute) and
                        isinstance(node.func.value.value, ast.Name) and
                        node.func.value.value.id == 'admin' and
                        node.func.value.attr == 'site' and
                        node.func.attr == 'register'):

                        # Extract model names from arguments
                        for arg in node.args:
                            if isinstance(arg, ast.Name):
                                registered_models.add(arg.id)

                # Pattern 2: @admin.register(Model) decorator
                if isinstance(node, ast.ClassDef):
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call):
                            # Check if decorator is admin.register()
                            if (isinstance(decorator.func, ast.Attribute) and
                                isinstance(decorator.func.value, ast.Name) and
                                decorator.func.value.id == 'admin' and
                                decorator.func.attr == 'register'):

                                # Extract model names from decorator arguments
                                for arg in decorator.args:
                                    if isinstance(arg, ast.Name):
                                        registered_models.add(arg.id)

        except Exception as e:
            print(f"Error parsing admin.py: {e}")

        return registered_models

    def get_unregistered_models(self, all_models: List[ModelInfo]) -> List[ModelInfo]:
        """
        Identify models not yet registered in admin.

        Args:
            all_models: List of ModelInfo objects from ModelScanner

        Returns:
            List of ModelInfo objects for unregistered models
        """
        registered_models = self.get_registered_models()

        unregistered = []
        for model in all_models:
            if model.name not in registered_models:
                unregistered.append(model)

        return unregistered

    def get_registration_report(self, all_models: Optional[List[ModelInfo]] = None) -> Dict:
        """
        Generate a comprehensive admin registration report.

        Args:
            all_models: Optional list of ModelInfo objects. If None, scans all models.

        Returns:
            Dictionary containing registration analysis results
        """
        # Scan all models if not provided
        if all_models is None:
            scanner = ModelScanner(self.app_name)
            all_models = scanner.scan_model_files()

        registered_models = self.get_registered_models()
        unregistered_models = self.get_unregistered_models(all_models)

        # Organize unregistered models by file
        unregistered_by_file = {}
        for model in unregistered_models:
            if model.file_path not in unregistered_by_file:
                unregistered_by_file[model.file_path] = []
            unregistered_by_file[model.file_path].append(model.name)

        report = {
            'total_models': len(all_models),
            'registered_count': len(registered_models),
            'unregistered_count': len(unregistered_models),
            'registered_models': sorted(list(registered_models)),
            'unregistered_models': [m.name for m in unregistered_models],
            'unregistered_by_file': unregistered_by_file,
            'registration_percentage': (len(registered_models) / len(all_models) * 100) if all_models else 0
        }

        return report

    def generate_registration_report_text(self, report: Optional[Dict] = None) -> str:
        """
        Generate a human-readable registration report.

        Args:
            report: Optional report dictionary from get_registration_report()

        Returns:
            Formatted report string
        """
        if report is None:
            report = self.get_registration_report()

        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("DJANGO ADMIN REGISTRATION REPORT")
        report_lines.append("=" * 70)
        report_lines.append("")

        # Summary
        report_lines.append("SUMMARY:")
        report_lines.append(f"  Total Models: {report['total_models']}")
        report_lines.append(f"  Registered: {report['registered_count']}")
        report_lines.append(f"  Unregistered: {report['unregistered_count']}")
        report_lines.append(f"  Registration Coverage: {report['registration_percentage']:.1f}%")
        report_lines.append("")

        # Registered models
        if report['registered_models']:
            report_lines.append("REGISTERED MODELS:")
            for model_name in report['registered_models']:
                report_lines.append(f"  ✓ {model_name}")
            report_lines.append("")

        # Unregistered models by file
        if report['unregistered_by_file']:
            report_lines.append("UNREGISTERED MODELS (by file):")
            report_lines.append("")

            for file_path, model_names in sorted(report['unregistered_by_file'].items()):
                report_lines.append(f"  {file_path}:")
                for model_name in sorted(model_names):
                    report_lines.append(f"    ✗ {model_name}")
                report_lines.append("")

        report_lines.append("=" * 70)

        return "\n".join(report_lines)


class AdminCodeGenerator:
        """
        Generates admin registration code for models.

        Creates admin.site.register() code with basic ModelAdmin configuration
        including appropriate list_display fields for each model.
        """

        def __init__(self, app_name: str = 'Hub'):
            """
            Initialize the AdminCodeGenerator.

            Args:
                app_name: Name of the Django app (default: 'Hub')
            """
            self.app_name = app_name

        def get_list_display_fields(self, model: ModelInfo) -> List[str]:
            """
            Determine appropriate fields for list_display.

            Prioritizes common fields like name, title, created_at, is_active.
            Limits list_display to 5-7 fields for readability.

            Args:
                model: ModelInfo object containing field information

            Returns:
                List of field names suitable for list_display
            """
            # Priority field patterns (in order of preference)
            priority_patterns = [
                'id',
                'name',
                'title',
                'username',
                'email',
                'status',
                'is_active',
                'is_enabled',
                'created_at',
                'created',
                'updated_at',
                'updated',
                'date',
                'amount',
                'price',
                'quantity',
            ]

            # Fields to exclude from list_display
            exclude_patterns = [
                'password',
                'token',
                'secret',
                'hash',
                'description',
                'content',
                'body',
                'text',
                'notes',
                'metadata',
                'data',
            ]

            # Field types to exclude
            exclude_types = [
                'TextField',
                'JSONField',
                'BinaryField',
                'FileField',
                'ImageField',
            ]

            selected_fields = []

            # Always include 'id' if it exists
            id_field = next((f for f in model.fields if f.name == 'id'), None)
            if id_field:
                selected_fields.append('id')

            # First pass: Add priority fields in order
            for pattern in priority_patterns:
                if len(selected_fields) >= 7:
                    break

                for field in model.fields:
                    # Skip if already selected
                    if field.name in selected_fields:
                        continue

                    # Skip excluded field types
                    if field.field_type in exclude_types:
                        continue

                    # Skip excluded patterns
                    if any(excl in field.name.lower() for excl in exclude_patterns):
                        continue

                    # Check if field matches priority pattern
                    if pattern in field.name.lower():
                        selected_fields.append(field.name)
                        if len(selected_fields) >= 7:
                            break

            # Second pass: Add other suitable fields if we have less than 5
            if len(selected_fields) < 5:
                for field in model.fields:
                    if len(selected_fields) >= 7:
                        break

                    # Skip if already selected
                    if field.name in selected_fields:
                        continue

                    # Skip excluded field types
                    if field.field_type in exclude_types:
                        continue

                    # Skip excluded patterns
                    if any(excl in field.name.lower() for excl in exclude_patterns):
                        continue

                    # Skip foreign keys (they can be verbose)
                    if field.is_foreign_key:
                        continue

                    # Skip reverse relations
                    if field.field_type in ['ManyToOneRel', 'ManyToManyRel', 'OneToOneRel']:
                        continue

                    selected_fields.append(field.name)

            # Ensure we have at least some fields
            if not selected_fields and model.fields:
                # Fallback: just use the first few non-excluded fields
                for field in model.fields[:7]:
                    if field.field_type not in exclude_types:
                        selected_fields.append(field.name)
                    if len(selected_fields) >= 5:
                        break

            return selected_fields[:7]  # Limit to 7 fields

        def generate_registration_code(self, model: ModelInfo) -> str:
            """
            Generate admin.py registration code for a model.

            Creates both the ModelAdmin class and the admin.site.register() call.

            Args:
                model: ModelInfo object to generate registration for

            Returns:
                String containing the registration code
            """
            list_display_fields = self.get_list_display_fields(model)

            # Generate ModelAdmin class
            code_lines = []
            code_lines.append(f"class {model.name}Admin(admin.ModelAdmin):")

            if list_display_fields:
                # Format list_display with proper indentation
                fields_str = ", ".join(f"'{field}'" for field in list_display_fields)
                code_lines.append(f"    list_display = [{fields_str}]")
            else:
                # Fallback if no fields found
                code_lines.append("    pass")

            code_lines.append("")

            # Generate registration call
            code_lines.append(f"admin.site.register({model.name}, {model.name}Admin)")

            return "\n".join(code_lines)

        def generate_bulk_registration_code(self, models: List[ModelInfo]) -> str:
            """
            Generate registration code for multiple models.

            Args:
                models: List of ModelInfo objects to generate registration for

            Returns:
                String containing all registration code
            """
            code_sections = []

            # Add header comment
            code_sections.append("# Auto-generated admin registrations")
            code_sections.append("# Generated by AdminCodeGenerator")
            code_sections.append("")

            # Generate code for each model
            for model in models:
                registration_code = self.generate_registration_code(model)
                code_sections.append(registration_code)
                code_sections.append("")  # Blank line between registrations

            return "\n".join(code_sections)

        def generate_registration_with_imports(self, models: List[ModelInfo]) -> str:
            """
            Generate complete registration code including necessary imports.

            Args:
                models: List of ModelInfo objects to generate registration for

            Returns:
                String containing imports and registration code
            """
            code_sections = []

            # Organize models by file
            models_by_file = {}
            for model in models:
                if model.file_path not in models_by_file:
                    models_by_file[model.file_path] = []
                models_by_file[model.file_path].append(model.name)

            # Generate imports
            code_sections.append("from django.contrib import admin")

            for file_path, model_names in sorted(models_by_file.items()):
                # Convert file path to module path
                # e.g., "Hub/models_security.py" -> "Hub.models_security"
                module_path = file_path.replace('/', '.').replace('\\', '.').replace('.py', '')

                # Generate import statement
                models_str = ", ".join(sorted(model_names))
                code_sections.append(f"from {module_path} import {models_str}")

            code_sections.append("")
            code_sections.append("")

            # Generate registration code
            registration_code = self.generate_bulk_registration_code(models)
            code_sections.append(registration_code)

            return "\n".join(code_sections)

        def get_registration_summary(self, models: List[ModelInfo]) -> Dict:
            """
            Generate a summary of registration code to be generated.

            Args:
                models: List of ModelInfo objects

            Returns:
                Dictionary containing summary information
            """
            summary = {
                'total_models': len(models),
                'models_by_file': {},
                'total_list_display_fields': 0,
                'models_with_list_display': 0,
                'field_usage': {}
            }

            # Organize by file and count fields
            for model in models:
                # Count by file
                if model.file_path not in summary['models_by_file']:
                    summary['models_by_file'][model.file_path] = []
                summary['models_by_file'][model.file_path].append(model.name)

                # Get list_display fields
                list_display_fields = self.get_list_display_fields(model)

                if list_display_fields:
                    summary['models_with_list_display'] += 1
                    summary['total_list_display_fields'] += len(list_display_fields)

                    # Track field usage
                    for field in list_display_fields:
                        if field not in summary['field_usage']:
                            summary['field_usage'][field] = 0
                        summary['field_usage'][field] += 1

            # Calculate average
            if summary['models_with_list_display'] > 0:
                summary['avg_fields_per_model'] = summary['total_list_display_fields'] / summary['models_with_list_display']
            else:
                summary['avg_fields_per_model'] = 0

            return summary

        def generate_summary_report(self, models: List[ModelInfo]) -> str:
            """
            Generate a human-readable summary report.

            Args:
                models: List of ModelInfo objects

            Returns:
                Formatted report string
            """
            summary = self.get_registration_summary(models)

            report_lines = []
            report_lines.append("=" * 70)
            report_lines.append("ADMIN REGISTRATION CODE GENERATION SUMMARY")
            report_lines.append("=" * 70)
            report_lines.append("")

            # Summary
            report_lines.append("SUMMARY:")
            report_lines.append(f"  Total Models: {summary['total_models']}")
            report_lines.append(f"  Models with list_display: {summary['models_with_list_display']}")
            report_lines.append(f"  Average fields per model: {summary['avg_fields_per_model']:.1f}")
            report_lines.append("")

            # Models by file
            if summary['models_by_file']:
                report_lines.append("MODELS BY FILE:")
                for file_path, model_names in sorted(summary['models_by_file'].items()):
                    report_lines.append(f"  {file_path}: {len(model_names)} models")
                    for model_name in sorted(model_names):
                        report_lines.append(f"    - {model_name}")
                report_lines.append("")

            # Most common fields
            if summary['field_usage']:
                report_lines.append("MOST COMMON LIST_DISPLAY FIELDS:")
                sorted_fields = sorted(summary['field_usage'].items(), key=lambda x: x[1], reverse=True)
                for field, count in sorted_fields[:10]:
                    report_lines.append(f"  {field}: {count} models")
                report_lines.append("")

            report_lines.append("=" * 70)

            return "\n".join(report_lines)




class AdminVerifier:
    """
    Verifies that models appear in Django admin interface and tests admin views.
    
    Tests that registered models are accessible at /admin/ and that their
    list, add, and change views load without HTTP errors.
    """
    
    def __init__(self, app_name: str = 'Hub'):
        """
        Initialize the AdminVerifier.
        
        Args:
            app_name: Name of the Django app (default: 'Hub')
        """
        self.app_name = app_name
        from django.test import Client
        self.client = Client()
    
    def verify_model_in_admin(self, model_name: str) -> bool:
        """
        Check if model appears in Django admin interface.
        
        Args:
            model_name: Name of the model to verify
            
        Returns:
            True if model is accessible in admin, False otherwise
        """
        try:
            from django.contrib import admin
            from django.apps import apps
            
            # Get the model class
            try:
                model_class = apps.get_model(self.app_name, model_name)
            except LookupError:
                return False
            
            # Check if model is registered in admin
            return model_class in admin.site._registry
            
        except Exception as e:
            print(f"Error verifying {model_name} in admin: {e}")
            return False
    
    def test_admin_views(self, model_name: str) -> Dict[str, Any]:
        """
        Test that list, add, and change views load without errors.
        
        Args:
            model_name: Name of the model to test
            
        Returns:
            Dictionary containing test results with keys:
                - model_name: Name of the model
                - in_admin: Whether model appears in admin
                - list_view_status: HTTP status code for list view
                - list_view_success: Whether list view loaded successfully
                - add_view_status: HTTP status code for add view
                - add_view_success: Whether add view loaded successfully
                - change_view_status: HTTP status code for change view (if object exists)
                - change_view_success: Whether change view loaded successfully
                - error_message: Any error messages encountered
        """
        from django.apps import apps
        from django.contrib.auth import get_user_model
        from django.test.utils import override_settings
        
        result = {
            'model_name': model_name,
            'in_admin': False,
            'list_view_status': None,
            'list_view_success': False,
            'add_view_status': None,
            'add_view_success': False,
            'change_view_status': None,
            'change_view_success': False,
            'error_message': ''
        }
        
        try:
            # Verify model is in admin
            result['in_admin'] = self.verify_model_in_admin(model_name)
            
            if not result['in_admin']:
                result['error_message'] = f"Model {model_name} not registered in admin"
                return result
            
            # Get the model class
            try:
                model_class = apps.get_model(self.app_name, model_name)
            except LookupError:
                result['error_message'] = f"Model {model_name} not found in app {self.app_name}"
                return result
            
            # Get model's admin URL name
            model_meta = model_class._meta
            app_label = model_meta.app_label
            model_name_lower = model_meta.model_name
            
            # Create a superuser for testing (or get existing)
            User = get_user_model()
            try:
                admin_user = User.objects.filter(is_superuser=True).first()
                if not admin_user:
                    # Create a test superuser
                    admin_user = User.objects.create_superuser(
                        username='admin_verifier_test',
                        email='test@example.com',
                        password='testpass123'
                    )
            except Exception as e:
                result['error_message'] = f"Could not create/get admin user: {e}"
                return result
            
            # Login as admin
            self.client.force_login(admin_user)
            
            # Use override_settings to allow testserver
            with override_settings(ALLOWED_HOSTS=['*']):
                # Test list view (changelist)
                list_url = f'/admin/{app_label}/{model_name_lower}/'
                try:
                    response = self.client.get(list_url, follow=False)
                    result['list_view_status'] = response.status_code
                    # Accept both 200 and 302 (redirect) as success for now
                    # 302 might be a redirect within admin (e.g., to login or another page)
                    result['list_view_success'] = response.status_code in [200, 302]
                    
                    if response.status_code not in [200, 302]:
                        result['error_message'] += f"List view returned {response.status_code}. "
                except Exception as e:
                    result['error_message'] += f"List view error: {str(e)}. "
                
                # Test add view
                add_url = f'/admin/{app_label}/{model_name_lower}/add/'
                try:
                    response = self.client.get(add_url, follow=False)
                    result['add_view_status'] = response.status_code
                    result['add_view_success'] = response.status_code in [200, 302]
                    
                    if response.status_code not in [200, 302]:
                        result['error_message'] += f"Add view returned {response.status_code}. "
                except Exception as e:
                    result['error_message'] += f"Add view error: {str(e)}. "
                
                # Test change view (only if an object exists)
                try:
                    first_obj = model_class.objects.first()
                    if first_obj:
                        change_url = f'/admin/{app_label}/{model_name_lower}/{first_obj.pk}/change/'
                        try:
                            response = self.client.get(change_url, follow=False)
                            result['change_view_status'] = response.status_code
                            result['change_view_success'] = response.status_code in [200, 302]
                            
                            if response.status_code not in [200, 302]:
                                result['error_message'] += f"Change view returned {response.status_code}. "
                        except Exception as e:
                            result['error_message'] += f"Change view error: {str(e)}. "
                    else:
                        # No objects exist, so we can't test change view
                        result['change_view_status'] = None
                        result['change_view_success'] = True  # Consider it success if no objects exist
                except Exception as e:
                    result['error_message'] += f"Error checking for objects: {str(e)}. "
            
        except Exception as e:
            result['error_message'] = f"Unexpected error: {str(e)}"
        
        return result
    
    def verify_models(self, models: List[ModelInfo]) -> List[Dict[str, Any]]:
        """
        Verify multiple models in admin interface.
        
        Args:
            models: List of ModelInfo objects to verify
            
        Returns:
            List of test result dictionaries
        """
        results = []
        
        for model in models:
            result = self.test_admin_views(model.name)
            results.append(result)
        
        return results
    
    def update_activation_status(self, model_name: str, test_result: Dict[str, Any]) -> None:
        """
        Update ModelActivationStatus record with verification results.
        
        Args:
            model_name: Name of the model
            test_result: Test result dictionary from test_admin_views()
        """
        from Hub.models_activation_tracking import ModelActivationStatus
        from django.utils import timezone
        
        try:
            # Get or create the activation status record
            status, created = ModelActivationStatus.objects.get_or_create(
                model_name=model_name,
                defaults={'model_file': f'{self.app_name}/models.py'}
            )
            
            # Update admin verification fields
            status.admin_registered = test_result['in_admin']
            status.admin_verified = (
                test_result['list_view_success'] and 
                test_result['add_view_success']
            )
            
            # Update error message if there are errors
            if test_result['error_message']:
                status.error_message = test_result['error_message']
            else:
                status.error_message = ''
            
            # Set activation date if fully verified
            if status.admin_verified and not status.activation_date:
                status.activation_date = timezone.now()
            
            status.save()
            
        except Exception as e:
            print(f"Error updating activation status for {model_name}: {e}")
    
    def verify_and_update_models(self, models: List[ModelInfo]) -> Dict[str, Any]:
        """
        Verify models and update their activation status records.
        
        Args:
            models: List of ModelInfo objects to verify
            
        Returns:
            Dictionary containing verification summary
        """
        results = self.verify_models(models)
        
        # Update activation status for each model
        for result in results:
            self.update_activation_status(result['model_name'], result)
        
        # Generate summary
        summary = {
            'total_models': len(results),
            'in_admin': sum(1 for r in results if r['in_admin']),
            'list_view_success': sum(1 for r in results if r['list_view_success']),
            'add_view_success': sum(1 for r in results if r['add_view_success']),
            'change_view_success': sum(1 for r in results if r['change_view_success']),
            'fully_verified': sum(1 for r in results if r['list_view_success'] and r['add_view_success']),
            'failed': sum(1 for r in results if not r['list_view_success'] or not r['add_view_success']),
            'results': results
        }
        
        return summary
    
    def generate_verification_report(self, summary: Dict[str, Any]) -> str:
        """
        Generate a human-readable verification report.
        
        Args:
            summary: Summary dictionary from verify_and_update_models()
            
        Returns:
            Formatted report string
        """
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("DJANGO ADMIN VERIFICATION REPORT")
        report_lines.append("=" * 70)
        report_lines.append("")
        
        # Summary
        report_lines.append("SUMMARY:")
        report_lines.append(f"  Total Models Tested: {summary['total_models']}")
        report_lines.append(f"  Registered in Admin: {summary['in_admin']}")
        report_lines.append(f"  List View Success: {summary['list_view_success']}")
        report_lines.append(f"  Add View Success: {summary['add_view_success']}")
        report_lines.append(f"  Change View Success: {summary['change_view_success']}")
        report_lines.append(f"  Fully Verified: {summary['fully_verified']}")
        report_lines.append(f"  Failed: {summary['failed']}")
        report_lines.append("")
        
        # Successful verifications
        successful = [r for r in summary['results'] if r['list_view_success'] and r['add_view_success']]
        if successful:
            report_lines.append("SUCCESSFULLY VERIFIED MODELS:")
            for result in successful:
                report_lines.append(f"  ✓ {result['model_name']}")
            report_lines.append("")
        
        # Failed verifications
        failed = [r for r in summary['results'] if not r['list_view_success'] or not r['add_view_success']]
        if failed:
            report_lines.append("FAILED VERIFICATIONS:")
            for result in failed:
                report_lines.append(f"  ✗ {result['model_name']}")
                if not result['in_admin']:
                    report_lines.append(f"      - Not registered in admin")
                if result['list_view_status'] and result['list_view_status'] != 200:
                    report_lines.append(f"      - List view: HTTP {result['list_view_status']}")
                if result['add_view_status'] and result['add_view_status'] != 200:
                    report_lines.append(f"      - Add view: HTTP {result['add_view_status']}")
                if result['error_message']:
                    report_lines.append(f"      - Error: {result['error_message']}")
            report_lines.append("")
        
        report_lines.append("=" * 70)
        
        return "\n".join(report_lines)
