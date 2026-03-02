#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.contrib.auth.models import User

print("=" * 70)
print("FIXING ADMIN LOGIN")
print("=" * 70)

try:
    # Reset admin password
    user = User.objects.get(username='admin')
    user.set_password('vibemall@admin123')
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()

    print(f"\n✅ Password reset successfully!")
    print(f"\nLogin Credentials:")
    print(f"  Username: {user.username}")
    print(f"  Email: {user.email}")
    print(f"  Password: vibemall@admin123")
    print(f"  Staff: {user.is_staff}")
    print(f"  Superuser: {user.is_superuser}")
    print(f"  Active: {user.is_active}")
    
    print(f"\n📌 Access Admin Panel:")
    print(f"  URL: https://vibemall.in/admin-panel/")
    print("=" * 70)

except User.DoesNotExist:
    print("❌ User 'admin' not found!")
    print("\nCreating new admin user...")
    user = User.objects.create_superuser(
        username='admin',
        email='info.vibemall@gmail.com',
        password='vibemall@admin123'
    )
    print(f"✅ Created new admin user: admin")
    print(f"\nLogin Credentials:")
    print(f"  Username: admin")
    print(f"  Email: info.vibemall@gmail.com")
    print(f"  Password: vibemall@admin123")
    print("=" * 70)
