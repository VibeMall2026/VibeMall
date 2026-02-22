"""
Management command to fix stuck reels that are stuck in processing state
"""
from django.core.management.base import BaseCommand
from Hub.models import Reel


class Command(BaseCommand):
    help = 'Fix reels stuck in processing state'

    def handle(self, *args, **options):
        # Find all reels stuck in processing
        stuck_reels = Reel.objects.filter(is_processing=True)
        
        count = stuck_reels.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('✅ No stuck reels found!'))
            return
        
        self.stdout.write(f'Found {count} stuck reel(s)')
        
        # Reset processing flag
        for reel in stuck_reels:
            self.stdout.write(f'  Fixing: {reel.title} (ID: {reel.id})')
            reel.is_processing = False
            reel.save(update_fields=['is_processing'])
        
        self.stdout.write(self.style.SUCCESS(f'✅ Fixed {count} stuck reel(s)!'))
        self.stdout.write('')
        self.stdout.write('You can now try generating them again.')
