#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.contrib.auth.models import User

print("=" * 70)
print("ADMIN USERS IN DATABASE")
print("=" * 70)

users = User.objects.all()
if users.count() == 0:
    print("No users found in database!")
else:
    for user in users:
        admin_badge = "✓ ADMIN" if user.is_staff else "  User "
        print(f"{admin_badge} | {user.username:20} | {user.email:35} | Active: {user.is_active}")

print("=" * 70)
print(f"Total Users: {users.count()}")
