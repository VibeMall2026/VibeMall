"""
Reel Generator - Create videos from images
Django integration for automatic reel creation
"""

from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip, TextClip
from PIL import Image
import os
from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
import tempfile


class ReelGenerator:
    """Generate video reels from images"""
    
    def __init__(self, reel_instance):
        """
        Initialize with a Reel model instance
        
        Args:
            reel_instance: Hub.models.Reel instance
        """
        self.reel = reel_instance
        self.temp_files = []
    
    def generate_video(self):
        """
        Generate video from reel images
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Mark as processing
            self.reel.is_processing = True
            self.reel.save(update_fields=['is_processing'])
            
            # Check FFmpeg availability
            import subprocess
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("❌ FFmpeg not found! Please install FFmpeg to generate videos.")
                print("   Download from: https://ffmpeg.org/download.html")
                self.reel.is_processing = False
                self.reel.save(update_fields=['is_processing'])
                return False
            
            # Get all images ordered
            reel_images = self.reel.images.all().order_by('order')
            
            if not reel_images.exists():
                print("❌ No images found for reel")
                self.reel.is_processing = False
                self.reel.save(update_fields=['is_processing'])
                return False
            
            clips = []
            
            # Create clips from each image
            for reel_image in reel_images:
                clip = self._create_image_clip(reel_image)
                if clip:
                    clips.append(clip)
            
            if not clips:
                print("❌ No valid clips created")
                self.reel.is_processing = False
                self.reel.save(update_fields=['is_processing'])
                return False
            
            # Concatenate all clips
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # Add background music if provided
            if self.reel.background_music:
                try:
                    audio_path = self.reel.background_music.path
                    if os.path.exists(audio_path):
                        audio = AudioFileClip(audio_path)
                        # Loop or trim audio to match video duration
                        if audio.duration < final_clip.duration:
                            # Loop audio
                            audio = audio.audio_loop(duration=final_clip.duration)
                        else:
                            # Trim audio
                            audio = audio.subclip(0, final_clip.duration)
                        final_clip = final_clip.set_audio(audio)
                except Exception as e:
                    print(f"⚠️ Could not add audio: {e}")
            
            # Generate output file
            output_path = self._get_output_path()
            
            # Write video file
            final_clip.write_videofile(
                output_path,
                fps=30,
                codec='libx264',
                audio_codec='aac',
                preset='medium',
                threads=4
            )
            
            # Save video file to model
            with open(output_path, 'rb') as f:
                self.reel.video_file.save(
                    f'reel_{self.reel.id}.mp4',
                    File(f),
                    save=False
                )
            
            # Generate and save thumbnail
            self._generate_thumbnail(final_clip)
            
            # Update duration
            self.reel.duration = int(final_clip.duration)
            self.reel.is_processing = False
            self.reel.save()
            
            # Cleanup
            self._cleanup()
            if os.path.exists(output_path):
                os.remove(output_path)
            
            print(f"✅ Reel generated successfully: {self.reel.title}")
            return True
            
        except Exception as e:
            print(f"❌ Error generating reel: {e}")
            self.reel.is_processing = False
            self.reel.save(update_fields=['is_processing'])
            self._cleanup()
            return False
    
    def _create_image_clip(self, reel_image):
        """Create a video clip from a reel image"""
        try:
            image_path = reel_image.image.path
            
            # Pre-process image with Pillow to avoid MoviePy issues
            from PIL import Image as PILImage
            
            # Open and resize image first
            img = PILImage.open(image_path)
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Calculate dimensions for 1080x1920 (vertical)
            target_width = 1080
            target_height = 1920
            
            # Resize maintaining aspect ratio
            img_ratio = img.width / img.height
            target_ratio = target_width / target_height
            
            if img_ratio > target_ratio:
                # Image is wider - fit to height
                new_height = target_height
                new_width = int(new_height * img_ratio)
            else:
                # Image is taller - fit to width
                new_width = target_width
                new_height = int(new_width / img_ratio)
            
            # Resize using LANCZOS
            img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)
            
            # Create canvas and paste image centered
            canvas = PILImage.new('RGB', (target_width, target_height), (0, 0, 0))
            paste_x = (target_width - new_width) // 2
            paste_y = (target_height - new_height) // 2
            canvas.paste(img, (paste_x, paste_y))
            
            # Save to temp file
            temp_img = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            canvas.save(temp_img.name, 'JPEG', quality=95)
            temp_img.close()
            self.temp_files.append(temp_img.name)
            
            # Create image clip from processed image
            clip = ImageClip(temp_img.name)
            
            # Set duration
            clip = clip.set_duration(self.reel.duration_per_image)
            
            # Add transitions
            if self.reel.transition_type == 'fade':
                clip = clip.crossfadein(0.5).crossfadeout(0.5)
            
            # Add text overlay if provided
            if reel_image.text_overlay:
                clip = self._add_text_overlay(clip, reel_image)
            
            return clip
            
        except Exception as e:
            print(f"⚠️ Error creating clip for image {reel_image.id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _add_text_overlay(self, clip, reel_image):
        """Add text overlay to clip"""
        try:
            # Create text clip
            txt_clip = TextClip(
                reel_image.text_overlay,
                fontsize=reel_image.text_size,
                color=reel_image.text_color,
                font='Arial-Bold',
                stroke_color='black',
                stroke_width=2
            )
            
            # Position text
            position_map = {
                'center': 'center',
                'top': ('center', 100),
                'bottom': ('center', 1820 - txt_clip.h)
            }
            
            txt_clip = txt_clip.set_position(
                position_map.get(reel_image.text_position, 'center')
            )
            txt_clip = txt_clip.set_duration(clip.duration)
            
            # Composite video with text
            return CompositeVideoClip([clip, txt_clip])
            
        except Exception as e:
            print(f"⚠️ Could not add text overlay: {e}")
            return clip
    
    def _generate_thumbnail(self, video_clip):
        """Generate thumbnail from first frame"""
        try:
            # Get frame at 1 second
            frame = video_clip.get_frame(1)
            
            # Convert to PIL Image
            from PIL import Image
            import numpy as np
            img = Image.fromarray(frame.astype('uint8'), 'RGB')
            
            # Resize thumbnail (use LANCZOS instead of ANTIALIAS)
            img.thumbnail((540, 960), Image.Resampling.LANCZOS)
            
            # Save to temporary file
            temp_thumb = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            img.save(temp_thumb.name, 'JPEG', quality=85)
            temp_thumb.close()
            
            # Save to model
            with open(temp_thumb.name, 'rb') as f:
                self.reel.thumbnail.save(
                    f'thumb_{self.reel.id}.jpg',
                    File(f),
                    save=False
                )
            
            # Cleanup temp file
            os.remove(temp_thumb.name)
            
        except Exception as e:
            print(f"⚠️ Could not generate thumbnail: {e}")
    
    def _get_output_path(self):
        """Get temporary output path for video"""
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f'reel_{self.reel.id}_{os.getpid()}.mp4')
        self.temp_files.append(output_path)
        return output_path
    
    def _cleanup(self):
        """Cleanup temporary files"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"⚠️ Could not remove temp file {temp_file}: {e}")
        self.temp_files = []


def generate_reel_async(reel_id):
    """
    Generate reel asynchronously (can be called from Celery task)
    
    Args:
        reel_id: ID of the Reel model instance
    
    Returns:
        bool: True if successful
    """
    from Hub.models import Reel
    
    try:
        reel = Reel.objects.get(id=reel_id)
        generator = ReelGenerator(reel)
        return generator.generate_video()
    except Reel.DoesNotExist:
        print(f"❌ Reel with ID {reel_id} not found")
        return False
    except Exception as e:
        print(f"❌ Error in async reel generation: {e}")
        return False
