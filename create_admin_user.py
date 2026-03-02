import os
import django
from django.utils import timezone
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

# Create superuser
username = 'admin'
email = 'admin@vibemall.com'
password = 'Admin@2026VibeMall'

if User.objects.filter(username=username).exists():
    print(f"User '{username}' already exists!")
else:
    # Use raw SQL to insert with last_login set
    hashed_password = make_password(password)
    now = timezone.now()
    
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO auth_user 
            (password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [hashed_password, now, True, username, '', '', email, True, True, now])
    
    print(f"✓ Superuser '{username}' created successfully!")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    print(f"\nYou can now login at: https://your-railway-url.railway.app/admin/")
