#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.contrib.auth.models import User

print("=" * 70)
print("CREATING ADMIN SUPERUSER")
print("=" * 70)

# Create/Update admin user
admin_username = "admin"
admin_email = "info.vibemall@gmail.com"
admin_password = "vibemall@admin123"

try:
    if User.objects.filter(username=admin_username).exists():
        user = User.objects.get(username=admin_username)
        user.email = admin_email
        user.set_password(admin_password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        print(f"✅ Updated existing user: {admin_username}")
    else:
        user = User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password
        )
        print(f"✅ Created new superuser: {admin_username}")

    print("\n" + "=" * 70)
    print("ADMIN ACCOUNT CREATED!")
    print("=" * 70)
    print(f"Username: {admin_username}")
    print(f"Email:    {admin_email}")
    print(f"Password: {admin_password}")
    print("\nAccess URLs:")
    print(f"  Django Admin:  https://vibemall.in/admin/")
    print(f"  Admin Panel:   https://vibemall.in/admin-panel/")
    print("=" * 70)

except Exception as e:
    print(f"❌ Error: {e}")
