"""Check published status of reels"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import Reel

print("🔍 Checking Reel Published Status...\n")

reels = Reel.objects.all().order_by('-id')[:5]

for reel in reels:
    status = "✅ Published" if reel.is_published else "📝 Draft"
    processing = " (⏳ Processing)" if reel.is_processing else ""
    
    print(f"ID {reel.id}: {reel.title}")
    print(f"   Status: {status}{processing}")
    print(f"   is_published: {reel.is_published}")
    print(f"   Video: {'Yes' if reel.video_file else 'No'}")
    print()
