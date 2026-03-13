#!/usr/bin/env python3
"""
VPS Django Model Conflict Fix Script
Run this on the VPS to fix related_name conflicts
"""

import os
import sys

def fix_model_conflicts():
    """Fix Django model related_name conflicts"""
    
    print("🔧 Fixing Django Model Conflicts on VPS")
    print("=" * 50)
    
    # Fix Hub/models_new_features.py
    new_features_file = "Hub/models_new_features.py"
    if os.path.exists(new_features_file):
        print(f"📝 Fixing {new_features_file}...")
        
        with open(new_features_file, 'r') as f:
            content = f.read()
        
        # Fix AdminUserRole.assigned_by conflict
        content = content.replace(
            "related_name='assigned_roles'",
            "related_name='admin_roles_assigned'"
        )
        
        with open(new_features_file, 'w') as f:
            f.write(content)
        
        print("✅ Fixed AdminUserRole.assigned_by conflict")
    else:
        print(f"⚠️ {new_features_file} not found")
    
    # Fix Hub/models_security_access.py
    security_file = "Hub/models_security_access.py"
    if os.path.exists(security_file):
        print(f"📝 Fixing {security_file}...")
        
        with open(security_file, 'r') as f:
            content = f.read()
        
        # Fix UserRoleAssignment.assigned_by conflict
        content = content.replace(
            "assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_roles')",
            "assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='security_roles_assigned')"
        )
        
        # Fix IPWhitelist conflicts
        content = content.replace(
            "allowed_users = models.ManyToManyField(User, blank=True, help_text=\"Specific users allowed from this IP\")",
            "allowed_users = models.ManyToManyField(User, blank=True, related_name='allowed_ip_whitelist', help_text=\"Specific users allowed from this IP\")"
        )
        
        content = content.replace(
            "created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)",
            "created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_ip_whitelist')"
        )
        
        with open(security_file, 'w') as f:
            f.write(content)
        
        print("✅ Fixed UserRoleAssignment and IPWhitelist conflicts")
    else:
        print(f"⚠️ {security_file} not found")
    
    # Fix migration file if it exists
    migration_file = "Hub/migrations/0035_new_features_models.py"
    if os.path.exists(migration_file):
        print(f"📝 Fixing {migration_file}...")
        
        with open(migration_file, 'r') as f:
            content = f.read()
        
        content = content.replace(
            "related_name='assigned_roles'",
            "related_name='admin_roles_assigned'"
        )
        
        with open(migration_file, 'w') as f:
            f.write(content)
        
        print("✅ Fixed migration file")
    else:
        print(f"⚠️ {migration_file} not found")
    
    print("\n🎉 All conflicts fixed!")
    print("Now run: python manage.py makemigrations && python manage.py migrate")

if __name__ == "__main__":
    try:
        fix_model_conflicts()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)