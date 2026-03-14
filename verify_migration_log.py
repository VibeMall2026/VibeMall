"""
Verify that MigrationExecutionLog entries were created.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models_activation_tracking import MigrationExecutionLog

# Query the logs
logs = MigrationExecutionLog.objects.all().order_by('-executed_at')[:10]

print("=" * 80)
print("Recent Migration Execution Logs")
print("=" * 80)

if logs:
    for log in logs:
        status = "✓ SUCCESS" if log.success else "✗ FAILED"
        print(f"\n{status}")
        print(f"  Model: {log.model_name}")
        print(f"  Migration: {log.migration_file}")
        print(f"  Order: {log.execution_order}")
        print(f"  Executed: {log.executed_at}")
        if log.error_message:
            print(f"  Error: {log.error_message[:100]}...")
else:
    print("\nNo migration execution logs found.")

print("\n" + "=" * 80)
print(f"Total logs in database: {MigrationExecutionLog.objects.count()}")
print("=" * 80)
