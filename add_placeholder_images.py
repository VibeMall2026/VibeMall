#!/usr/bin/env python
import os
import django
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.core.files.base import ContentFile

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import Product

def create_placeholder_image(product_name, color):
    """Create a simple placeholder image for a product"""
    # Create image
    img = Image.new('RGB', (400, 400), color=color)
    draw = ImageDraw.Draw(img)
    
    # Add text
    text = product_name[:20]  # Limit text length
    try:
        # Try to use a larger font, fall back to default
        draw.text((200, 200), text, fill='white', anchor='mm')
    except:
        draw.text((200, 200), text, fill='white')
    
    # Convert to bytes
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes

# Color mapping for categories
colors = {
    'MOBILES': (0, 102, 204),       # Blue
    'FOOD_HEALTH': (51, 153, 51),   # Green
    'HOME_KITCHEN': (204, 102, 0),  # Orange
    'AUTO_ACC': (153, 0, 0),        # Dark Red
    'FURNITURE': (102, 51, 0),      # Brown
    'SPORTS': (255, 0, 0),          # Red
    'GENZ_TRENDS': (255, 0, 255),   # Magenta
    'NEXT_GEN': (0, 204, 204),      # Cyan
    'TOP_DEALS': (255, 255, 0),     # Yellow
    'TOP_SELLING': (255, 165, 0),   # Orange-Yellow
    'TOP_FEATURED': (128, 0, 128),  # Purple
    'RECOMMENDED': (0, 128, 128),   # Teal
}

print("Creating placeholder images for products...")
updated = 0

for product in Product.objects.all():
    if not product.image:
        category = product.category
        color = colors.get(category, (128, 128, 128))  # Gray as default
        
        # Create placeholder image
        img_bytes = create_placeholder_image(product.name, color)
        
        # Save to product
        filename = f"{product.name.lower().replace(' ', '_')}.jpg"
        product.image.save(filename, ContentFile(img_bytes.read()), save=True)
        updated += 1
        
        if updated % 10 == 0:
            print(f"  Updated {updated} products...")

print(f"\n✅ Completed! Updated {updated} products with placeholder images")

# Verify
with_images = Product.objects.exclude(image='').count()
print(f"Products with images: {with_images}/{Product.objects.count()}")
