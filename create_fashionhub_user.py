import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.contrib.auth.models import User

# Check if VibeMall user exists
if User.objects.filter(username='VibeMall').exists():
    print("User 'VibeMall' already exists")
else:
    # Create VibeMall superuser
    User.objects.create_superuser(
        username='VibeMall',
        email='vibemall@admin.com',
        password='VibeMall@123'
    )
    print("Created superuser 'VibeMall'")
    print("  Username: VibeMall")
    print("  Password: VibeMall@123")
    print("  Email: vibemall@admin.com")
