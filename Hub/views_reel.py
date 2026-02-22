"""
Reel Generation Views for Admin Panel
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
import os
import threading
from .models import Reel, ReelImage
from .reel_creator import ReelCreator


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_generate_reel(request, reel_id):
    """Generate video from reel images"""
    reel = get_object_or_404(Reel, id=reel_id)
    
    # Check if already processing
    if reel.is_processing:
        messages.warning(request, 'Reel is already being processed. Please wait.')
        return redirect('/admin/Hub/reel/')
    
    # Check if images exist
    images = reel.images.all().order_by('order')
    if not images.exists():
        messages.error(request, 'Please add at least one image to generate the reel.')
        return redirect('/admin/Hub/reel/')
    
    # Mark as processing
    reel.is_processing = True
    reel.save()
    
    # Start generation in background thread
    thread = threading.Thread(target=generate_reel_video, args=(reel_id,))
    thread.daemon = True
    thread.start()
    
    messages.success(request, f'Reel generation started! Video will be ready in a few moments.')
    return redirect('/admin/Hub/reel/')


def generate_reel_video(reel_id):
    """Background task to generate reel video"""
    try:
        reel = Reel.objects.get(id=reel_id)
        images = reel.images.all().order_by('order')
        
        # Prepare image paths
        image_paths = []
        text_overlays = []
        
        for idx, img in enumerate(images):
            image_path = os.path.join(settings.MEDIA_ROOT, img.image.name)
            image_paths.append(image_path)
            
            # Add text overlay if exists
            if img.text_overlay:
                text_overlays.append({
                    'text': img.text_overlay,
                    'fontsize': img.text_size,
                    'color': img.text_color,
                    'position': img.text_position,
                    'start': idx * reel.duration_per_image,
                    'duration': reel.duration_per_image
                })
        
        # Create output path
        output_filename = f'reel_{reel.id}_{reel.created_at.strftime("%Y%m%d_%H%M%S")}.mp4'
        output_path = os.path.join(settings.MEDIA_ROOT, 'reels', output_filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Configure creator
        config = {
            'duration_per_image': reel.duration_per_image,
            'fps': 30,
            'resolution': [1080, 1920],  # Vertical format for reels
            'transition': reel.transition_type,
        }
        
        creator = ReelCreator(config)
        
        # Get background music path if exists
        music_path = None
        if reel.background_music:
            music_path = os.path.join(settings.MEDIA_ROOT, reel.background_music.name)
        
        # Generate video
        creator.create_reel(
            image_paths=image_paths,
            output_path=output_path,
            background_music=music_path,
            text_overlays=text_overlays if text_overlays else None
        )
        
        # Update reel with video file
        reel.video_file = f'reels/{output_filename}'
        
        # Generate thumbnail from first image
        if images.exists():
            first_image = images.first()
            reel.thumbnail = first_image.image
        
        # Calculate duration
        reel.duration = len(images) * reel.duration_per_image
        
        reel.is_processing = False
        reel.save()
        
        print(f"✅ Reel {reel.id} generated successfully!")
        
    except Exception as e:
        print(f"❌ Error generating reel {reel_id}: {str(e)}")
        try:
            reel = Reel.objects.get(id=reel_id)
            reel.is_processing = False
            reel.save()
        except:
            pass
