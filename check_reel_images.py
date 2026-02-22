"""Check reel images in database"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import Reel, ReelImage

print("🔍 Checking Reels and Images...\n")

reels = Reel.objects.all().order_by('-id')

if not reels.exists():
    print("❌ No reels found!")
else:
    for reel in reels:
        image_count = reel.images.count()
        print(f"📹 Reel: {reel.title} (ID: {reel.id})")
        print(f"   Images: {image_count}")
        print(f"   Status: {'Processing' if reel.is_processing else 'Published' if reel.is_published else 'Draft'}")
        
        if image_count > 0:
            print(f"   Image details:")
            for img in reel.images.all():
                print(f"      - Order {img.order}: {img.image.name}")
                if img.text_overlay:
                    print(f"        Text: {img.text_overlay}")
        else:
            print(f"   ⚠️ No images found for this reel!")
        
        print()

print(f"\nTotal Reels: {reels.count()}")
print(f"Total Images: {ReelImage.objects.count()}")
