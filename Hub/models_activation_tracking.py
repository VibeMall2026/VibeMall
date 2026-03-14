"""
Models for tracking admin panel feature activation status.

These models track the activation process for existing admin panel features,
including migration status, admin registration, and connection verification.
"""

from django.db import models


class ModelActivationStatus(models.Model):
    """Track activation status for each model."""
    
    model_name = models.CharField(max_length=100, unique=True)
    model_file = models.CharField(max_length=200)
    has_migration = models.BooleanField(default=False)
    migration_applied = models.BooleanField(default=False)
    table_created = models.BooleanField(default=False)
    admin_registered = models.BooleanField(default=False)
    admin_verified = models.BooleanField(default=False)
    activation_date = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Model Activation Status"
        verbose_name_plural = "Model Activation Statuses"
        ordering = ['model_name']
    
    def __str__(self):
        return f"{self.model_name} - {'Active' if self.table_created else 'Inactive'}"


class FeatureActivationStatus(models.Model):
    """Track activation status for each feature."""
    
    feature_name = models.CharField(max_length=200)
    url_name = models.CharField(max_length=100)
    url_pattern = models.CharField(max_length=200)
    view_name = models.CharField(max_length=100)
    template_path = models.CharField(max_length=200)
    url_exists = models.BooleanField(default=False)
    view_exists = models.BooleanField(default=False)
    template_exists = models.BooleanField(default=False)
    loads_successfully = models.BooleanField(default=False)
    http_status = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    last_tested = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Feature Activation Status"
        verbose_name_plural = "Feature Activation Statuses"
        ordering = ['feature_name']
    
    def __str__(self):
        return f"{self.feature_name} - {'Operational' if self.loads_successfully else 'Non-operational'}"
    
    @property
    def status(self):
        """Return the current status of the feature."""
        if self.loads_successfully:
            return 'operational'
        elif not self.url_exists:
            return 'broken_url'
        elif not self.view_exists:
            return 'broken_view'
        elif not self.template_exists:
            return 'broken_template'
        else:
            return 'error'


class MigrationExecutionLog(models.Model):
    """Log migration execution results."""
    
    model_name = models.CharField(max_length=100)
    migration_file = models.CharField(max_length=200)
    execution_order = models.IntegerField()
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Migration Execution Log"
        verbose_name_plural = "Migration Execution Logs"
        ordering = ['execution_order', 'executed_at']
    
    def __str__(self):
        status = 'Success' if self.success else 'Failed'
        return f"{self.model_name} - {self.migration_file} ({status})"
