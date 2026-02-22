"""
Test script to debug reel generation
Run: python test_reel_generation.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import Reel
from Hub.reel_generator import ReelGenerator

# Get the first reel
reels = Reel.objects.all().order_by('-id')

if not reels.exists():
    print("❌ No reels found in database!")
    print("Please create a reel from admin panel first.")
    exit()

reel = reels.first()
print(f"🎬 Testing reel: {reel.title} (ID: {reel.id})")
print(f"   Images: {reel.images.count()}")
print(f"   Duration per image: {reel.duration_per_image}s")
print(f"   Transition: {reel.transition_type}")
print()

# Check FFmpeg
print("🔍 Checking FFmpeg...")
import subprocess
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
    print("✅ FFmpeg is installed!")
    print(f"   Version: {result.stdout.split()[2]}")
except FileNotFoundError:
    print("❌ FFmpeg NOT found!")
    print("   Please install FFmpeg first:")
    print("   choco install ffmpeg")
    print()
    print("   Or see FFMPEG_INSTALLATION_GUIDE.md")
    exit()

print()

# Check images
print("🖼️ Checking images...")
for img in reel.images.all().order_by('order'):
    img_path = img.image.path
    exists = os.path.exists(img_path)
    status = "✅" if exists else "❌"
    print(f"   {status} Image {img.order}: {img_path}")
    if img.text_overlay:
        print(f"      Text: {img.text_overlay}")

print()

# Try to generate
print("🎥 Attempting to generate video...")
print("=" * 60)

try:
    generator = ReelGenerator(reel)
    success = generator.generate_video()
    
    print("=" * 60)
    if success:
        print("✅ SUCCESS! Video generated!")
        print(f"   Video: {reel.video_file.url if reel.video_file else 'Not saved'}")
        print(f"   Duration: {reel.duration}s")
    else:
        print("❌ FAILED! Check error messages above.")
        
except Exception as e:
    print("=" * 60)
    print(f"❌ EXCEPTION: {e}")
    print()
    import traceback
    traceback.print_exc()
