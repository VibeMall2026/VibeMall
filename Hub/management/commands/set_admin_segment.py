"""
Management command to set admin/staff users' customer segment to ADMIN
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Hub.models import UserProfile


class Command(BaseCommand):
    help = 'Set all admin/staff users customer segment to ADMIN'

    def handle(self, *args, **kwargs):
        # Get all staff/superuser accounts
        admin_users = User.objects.filter(is_staff=True) | User.objects.filter(is_superuser=True)
        
        updated_count = 0
        created_count = 0
        
        for user in admin_users:
            # Create UserProfile if doesn't exist
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created profile for {user.username}'))
            
            # Update segment to ADMIN
            if profile.customer_segment != 'ADMIN':
                profile.customer_segment = 'ADMIN'
                profile.save()
                updated_count += 1
                self.stdout.write(self.style.SUCCESS(f'Updated {user.username} to ADMIN segment'))
        
        self.stdout.write(self.style.SUCCESS(
            f'\nCompleted! Created {created_count} profiles, Updated {updated_count} users to ADMIN segment'
        ))
