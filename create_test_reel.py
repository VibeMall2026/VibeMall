"""
Create a test reel in database
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import Reel, ReelImage, User
from django.core.files.base import ContentFile
from PIL import Image
import io

# Get admin user
try:
    admin_user = User.objects.filter(is_staff=True).first()
    if not admin_user:
        admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        print("❌ No admin user found! Please create an admin user first.")
        exit()
except Exception as e:
    print(f"❌ Error finding admin user: {e}")
    exit()

print("Creating test reel...")

# Create reel
reel = Reel.objects.create(
    title="Test Reel - Sample",
    description="This is a test reel created automatically",
    duration_per_image=3,
    transition_type='fade',
    created_by=admin_user,
    is_published=False
)

print(f"✅ Reel created with ID: {reel.id}")

# Create sample images
colors = [
    (255, 0, 0),    # Red
    (0, 255, 0),    # Green
    (0, 0, 255),    # Blue
    (255, 255, 0),  # Yellow
    (255, 0, 255),  # Magenta
]

texts = [
    "Welcome",
    "To Our",
    "Test",
    "Reel",
    "Demo"
]

for idx, (color, text) in enumerate(zip(colors, texts)):
    # Create a simple colored image
    img = Image.new('RGB', (1080, 1920), color=color)
    
    # Save to bytes
    img_io = io.BytesIO()
    img.save(img_io, format='JPEG', quality=85)
    img_io.seek(0)
    
    # Create ReelImage
    reel_image = ReelImage.objects.create(
        reel=reel,
        order=idx,
        text_overlay=text,
        text_position='center',
        text_color='white',
        text_size=70
    )
    
    # Save image file
    reel_image.image.save(
        f'test_reel_image_{idx}.jpg',
        ContentFile(img_io.read()),
        save=True
    )
    
    print(f"✅ Image {idx + 1} created: {text}")

print("\n" + "=" * 50)
print("TEST REEL CREATED SUCCESSFULLY!")
print("=" * 50)
print(f"\nReel ID: {reel.id}")
print(f"Title: {reel.title}")
print(f"Images: {reel.images.count()}")
print(f"\nAccess URLs:")
print(f"Edit: http://localhost:8000/admin-panel/reels/{reel.id}/edit/")
print(f"Generate: http://localhost:8000/admin-panel/reels/{reel.id}/generate/")
print(f"List: http://localhost:8000/admin-panel/reels/")
print("=" * 50)
