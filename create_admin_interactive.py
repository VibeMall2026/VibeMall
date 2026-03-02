#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.contrib.auth.models import User

print("=" * 70)
print("CREATE ADMIN SUPERUSER")
print("=" * 70)

# Get admin details
admin_username = input("\nEnter admin username (default: admin): ").strip() or "admin"
admin_email = input("Enter admin email: ").strip()
admin_password = input("Enter admin password: ").strip()

if not admin_email or not admin_password:
    print("❌ Email and password are required!")
    exit(1)

# Check if user already exists
if User.objects.filter(username=admin_username).exists():
    print(f"\n⚠️  Username '{admin_username}' already exists!")
    update = input("Update password for existing user? (y/n): ").strip().lower()
    
    if update == 'y':
        user = User.objects.get(username=admin_username)
        user.email = admin_email
        user.set_password(admin_password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        print(f"✅ Updated existing user '{admin_username}'")
else:
    # Create new superuser
    user = User.objects.create_superuser(
        username=admin_username,
        email=admin_email,
        password=admin_password
    )
    print(f"\n✅ Created new admin superuser: {admin_username}")

print("\n" + "=" * 70)
print("ADMIN LOGIN DETAILS:")
print("=" * 70)
print(f"URL:      https://vibemall.in/admin/")
print(f"Username: {admin_username}")
print(f"Email:    {admin_email}")
print(f"Staff:    Yes")
print(f"Superuser: Yes")
print("\nOr access custom panel at: https://vibemall.in/admin-panel/")
print("=" * 70)
