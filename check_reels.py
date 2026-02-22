"""
Quick script to check existing reels in database
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import Reel, ReelImage

# Check reels
reels = Reel.objects.all()

print("=" * 50)
print("EXISTING REELS IN DATABASE")
print("=" * 50)

if reels.exists():
    for reel in reels:
        print(f"\nID: {reel.id}")
        print(f"Title: {reel.title}")
        print(f"Created: {reel.created_at}")
        print(f"Images: {reel.images.count()}")
        print(f"Video: {'Yes' if reel.video_file else 'No'}")
        print(f"Published: {reel.is_published}")
        print(f"Processing: {reel.is_processing}")
        print("-" * 50)
else:
    print("\n❌ No reels found in database!")
    print("\nTo create a reel:")
    print("1. Go to: http://localhost:8000/admin-panel/reels/add/")
    print("2. Fill in the form")
    print("3. Upload 3-5 images")
    print("4. Click 'Generate Reel'")

print("\n" + "=" * 50)
print(f"Total Reels: {reels.count()}")
print("=" * 50)
