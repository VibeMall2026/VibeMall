"""
Enhanced Reel Generator V2 - With Animations, Watermarks & End Screen
"""

from moviepy.editor import (
    ImageClip, concatenate_videoclips, AudioFileClip, 
    CompositeVideoClip, TextClip, ColorClip
)
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
from django.conf import settings
from django.core.files import File
import tempfile
import numpy as np


class EnhancedReelGenerator:
    """Generate professional video reels with animations and branding"""
    
    def __init__(self, reel_instance):
        self.reel = reel_instance
        self.temp_files = []
        self.width = 1080
        self.height = 1920
    
    def generate_video(self):
        """Generate video with animations and branding"""
        try:
            # Mark as processing
            self.reel.is_processing = True
            self.reel.save(update_fields=['is_processing'])
            
            # Check FFmpeg
            import subprocess
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("❌ FFmpeg not found! Please install FFmpeg.")
                self.reel.is_processing = False
                self.reel.save(update_fields=['is_processing'])
                return False
            
            # Get images
            reel_images = self.reel.images.all().order_by('order')
            if not reel_images.exists():
                print("❌ No images found")
                self.reel.is_processing = False
                self.reel.save(update_fields=['is_processing'])
                return False
            
            clips = []
            
            # Create animated clips from images
            print(f"🎬 Creating {reel_images.count()} animated clips...")
            for idx, reel_image in enumerate(reel_images, 1):
                print(f"   Processing image {idx}/{reel_images.count()}...")
                clip = self._create_animated_clip(reel_image)
                if clip:
                    clips.append(clip)
            
            if not clips:
                print("❌ No valid clips created")
                self.reel.is_processing = False
                self.reel.save(update_fields=['is_processing'])
                return False
            
            # Add end screen if enabled
            if self.reel.add_end_screen:
                print("🎨 Creating branded end screen...")
                end_clip = self._create_end_screen()
                if end_clip:
                    clips.append(end_clip)
            
            # Concatenate clips
            print("🔗 Combining clips...")
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # Add watermark logo throughout video
            if self.reel.watermark_logo:
                print("💧 Adding watermark...")
                final_clip = self._add_watermark(final_clip)
            
            # Add background music
            if self.reel.background_music:
                print("🎵 Adding background music...")
                final_clip = self._add_audio(final_clip)
            
            # Generate output
            output_path = self._get_output_path()
            print(f"💾 Rendering video... (this may take 1-2 minutes)")
            
            final_clip.write_videofile(
                output_path,
                fps=30,
                codec='libx264',
                audio_codec='aac',
                preset='medium',
                threads=4,
                logger=None  # Suppress moviepy progress
            )
            
            # Save to model
            with open(output_path, 'rb') as f:
                self.reel.video_file.save(f'reel_{self.reel.id}.mp4', File(f), save=False)
            
            # Generate thumbnail
            self._generate_thumbnail(final_clip)
            
            # Update duration
            self.reel.duration = int(final_clip.duration)
            self.reel.is_processing = False
            self.reel.save()
            
            # Cleanup
            self._cleanup()
            if os.path.exists(output_path):
                os.remove(output_path)
            
            print(f"✅ Reel generated successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            self.reel.is_processing = False
            self.reel.save(update_fields=['is_processing'])
            self._cleanup()
            return False
    
    def _create_animated_clip(self, reel_image):
        """Create animated clip with effects"""
        try:
            # Pre-process image
            temp_img_path = self._preprocess_image(reel_image.image.path)
            
            # Create base clip
            clip = ImageClip(temp_img_path)
            clip = clip.set_duration(self.reel.duration_per_image)
            
            # Apply animation based on transition type
            if self.reel.transition_type == 'zoom':
                clip = self._apply_zoom_effect(clip)
            elif self.reel.transition_type == 'slide':
                clip = self._apply_slide_effect(clip)
            elif self.reel.transition_type == 'fade':
                clip = clip.crossfadein(0.5).crossfadeout(0.5)
            
            # Add text overlay
            if reel_image.text_overlay:
                clip = self._add_text_overlay(clip, reel_image)
            
            return clip
            
        except Exception as e:
            print(f"⚠️ Error creating clip: {e}")
            return None
    
    def _preprocess_image(self, image_path):
        """Pre-process and resize image"""
        img = Image.open(image_path)
        
        # Convert to RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Calculate dimensions
        img_ratio = img.width / img.height
        target_ratio = self.width / self.height
        
        if img_ratio > target_ratio:
            new_height = self.height
            new_width = int(new_height * img_ratio)
        else:
            new_width = self.width
            new_height = int(new_width / img_ratio)
        
        # Resize
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create canvas
        canvas = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        paste_x = (self.width - new_width) // 2
        paste_y = (self.height - new_height) // 2
        canvas.paste(img, (paste_x, paste_y))
        
        # Save to temp
        temp_img = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        canvas.save(temp_img.name, 'JPEG', quality=95)
        temp_img.close()
        self.temp_files.append(temp_img.name)
        
        return temp_img.name
    
    def _apply_zoom_effect(self, clip):
        """Apply smooth zoom-in effect"""
        def zoom(t):
            # Zoom from 1.0 to 1.2 over duration
            zoom_factor = 1 + 0.2 * (t / clip.duration)
            return zoom_factor
        
        return clip.resize(lambda t: zoom(t))
    
    def _apply_slide_effect(self, clip):
        """Apply slide effect"""
        def slide(t):
            # Slide from right to center
            progress = t / clip.duration
            x_offset = int(200 * (1 - progress))
            return ('center', 'center')
        
        return clip.set_position(slide)
    
    def _add_text_overlay(self, clip, reel_image):
        """Add animated text overlay"""
        try:
            # Create text clip with shadow effect
            txt_clip = TextClip(
                reel_image.text_overlay,
                fontsize=reel_image.text_size,
                color=reel_image.text_color,
                font='Arial-Bold',
                stroke_color='black',
                stroke_width=3,
                method='caption',
                size=(self.width - 100, None)
            )
            
            # Position text
            position_map = {
                'center': 'center',
                'top': ('center', 150),
                'bottom': ('center', self.height - 250)
            }
            
            txt_clip = txt_clip.set_position(
                position_map.get(reel_image.text_position, 'center')
            )
            txt_clip = txt_clip.set_duration(clip.duration)
            
            # Add fade in/out animation
            txt_clip = txt_clip.crossfadein(0.3).crossfadeout(0.3)
            
            return CompositeVideoClip([clip, txt_clip])
            
        except Exception as e:
            print(f"⚠️ Could not add text: {e}")
            return clip
    
    def _create_end_screen(self):
        """Create branded end screen with logo"""
        try:
            duration = self.reel.end_screen_duration
            
            # Create gradient background
            bg_img = self._create_gradient_background()
            bg_clip = ImageClip(bg_img).set_duration(duration)
            
            layers = [bg_clip]
            
            # Add logo if available
            if self.reel.watermark_logo and os.path.exists(self.reel.watermark_logo.path):
                logo_clip = self._create_logo_clip(duration, center=True, size=400)
                if logo_clip:
                    layers.append(logo_clip)
            
            # Add "VibeMall" text
            try:
                brand_text = TextClip(
                    "VibeMall",
                    fontsize=120,
                    color='white',
                    font='Arial-Bold',
                    stroke_color='#696cff',
                    stroke_width=3
                )
                brand_text = brand_text.set_position(('center', self.height - 400))
                brand_text = brand_text.set_duration(duration)
                brand_text = brand_text.crossfadein(0.5)
                layers.append(brand_text)
                
                # Add tagline
                tagline = TextClip(
                    "Shop the Latest Trends",
                    fontsize=40,
                    color='white',
                    font='Arial'
                )
                tagline = tagline.set_position(('center', self.height - 300))
                tagline = tagline.set_duration(duration)
                tagline = tagline.crossfadein(0.8)
                layers.append(tagline)
            except:
                pass
            
            return CompositeVideoClip(layers)
            
        except Exception as e:
            print(f"⚠️ Could not create end screen: {e}")
            return None
    
    def _create_gradient_background(self):
        """Create beautiful gradient background"""
        img = Image.new('RGB', (self.width, self.height))
        draw = ImageDraw.Draw(img)
        
        # Create gradient from purple to blue
        for y in range(self.height):
            progress = y / self.height
            r = int(102 + (68 - 102) * progress)  # 102 to 68
            g = int(108 + (138 - 108) * progress)  # 108 to 138
            b = int(255 + (255 - 255) * progress)  # 255 to 255
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        
        # Save to temp
        temp_bg = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        img.save(temp_bg.name, 'JPEG', quality=95)
        temp_bg.close()
        self.temp_files.append(temp_bg.name)
        
        return temp_bg.name
    
    def _add_watermark(self, video_clip):
        """Add watermark logo to video"""
        try:
            if not os.path.exists(self.reel.watermark_logo.path):
                return video_clip
            
            logo_clip = self._create_logo_clip(
                video_clip.duration, 
                center=False,
                size=120
            )
            
            if logo_clip:
                return CompositeVideoClip([video_clip, logo_clip])
            
            return video_clip
            
        except Exception as e:
            print(f"⚠️ Could not add watermark: {e}")
            return video_clip
    
    def _create_logo_clip(self, duration, center=False, size=120):
        """Create logo clip"""
        try:
            # Open and process logo
            logo = Image.open(self.reel.watermark_logo.path)
            
            # Convert to RGBA
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')
            
            # Resize logo
            logo.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Apply opacity
            if not center:
                alpha = logo.split()[3]
                alpha = alpha.point(lambda p: int(p * self.reel.watermark_opacity))
                logo.putalpha(alpha)
            
            # Save to temp
            temp_logo = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            logo.save(temp_logo.name, 'PNG')
            temp_logo.close()
            self.temp_files.append(temp_logo.name)
            
            # Create clip
            logo_clip = ImageClip(temp_logo.name)
            logo_clip = logo_clip.set_duration(duration)
            
            # Position
            if center:
                logo_clip = logo_clip.set_position('center')
            else:
                position_map = {
                    'top-left': (30, 30),
                    'top-right': (self.width - size - 30, 30),
                    'bottom-left': (30, self.height - size - 30),
                    'bottom-right': (self.width - size - 30, self.height - size - 30)
                }
                logo_clip = logo_clip.set_position(
                    position_map.get(self.reel.watermark_position, (self.width - size - 30, 30))
                )
            
            return logo_clip
            
        except Exception as e:
            print(f"⚠️ Logo error: {e}")
            return None
    
    def _add_audio(self, video_clip):
        """Add background music"""
        try:
            audio_path = self.reel.background_music.path
            if os.path.exists(audio_path):
                audio = AudioFileClip(audio_path)
                
                if audio.duration < video_clip.duration:
                    audio = audio.audio_loop(duration=video_clip.duration)
                else:
                    audio = audio.subclip(0, video_clip.duration)
                
                # Reduce volume slightly
                audio = audio.volumex(0.7)
                
                return video_clip.set_audio(audio)
        except Exception as e:
            print(f"⚠️ Audio error: {e}")
        
        return video_clip
    
    def _generate_thumbnail(self, video_clip):
        """Generate thumbnail"""
        try:
            frame = video_clip.get_frame(1)
            img = Image.fromarray(frame.astype('uint8'), 'RGB')
            img.thumbnail((540, 960), Image.Resampling.LANCZOS)
            
            temp_thumb = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            img.save(temp_thumb.name, 'JPEG', quality=85)
            temp_thumb.close()
            
            with open(temp_thumb.name, 'rb') as f:
                self.reel.thumbnail.save(f'thumb_{self.reel.id}.jpg', File(f), save=False)
            
            os.remove(temp_thumb.name)
        except Exception as e:
            print(f"⚠️ Thumbnail error: {e}")
    
    def _get_output_path(self):
        """Get output path"""
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f'reel_{self.reel.id}_{os.getpid()}.mp4')
        self.temp_files.append(output_path)
        return output_path
    
    def _cleanup(self):
        """Cleanup temp files"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        self.temp_files = []
