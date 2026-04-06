"""
Reel Creator Utility for Admin Panel
Images ને video/reel માં convert કરે છે
Standardized video size: 1080x1920 (vertical/portrait)
"""

try:
    from moviepy.editor import (
        ImageClip, concatenate_videoclips, AudioFileClip, 
        CompositeVideoClip, TextClip, VideoFileClip
    )
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("⚠️ MoviePy not installed. Run: pip install moviepy==1.0.3")

try:
    import subprocess
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False

from PIL import Image
import os
from django.conf import settings

# Standard reel dimensions (Instagram/TikTok format)
STANDARD_WIDTH = 1080
STANDARD_HEIGHT = 1920
STANDARD_RESOLUTION = (STANDARD_WIDTH, STANDARD_HEIGHT)

class ReelCreator:
    def __init__(self, config=None):
        """Initialize reel creator with config"""
        self.config = config or self.get_default_config()
        # Force standard resolution
        self.config['resolution'] = list(STANDARD_RESOLUTION)
        
    def get_default_config(self):
        """Default configuration"""
        return {
            "duration_per_image": 3,
            "fps": 30,
            "resolution": list(STANDARD_RESOLUTION),
            "transition": "fade",
        }
    
    def resize_image_to_standard(self, img_path):
        """Resize image to standard reel dimensions (1080x1920) with proper aspect ratio"""
        img = Image.open(img_path)
        
        # Calculate aspect ratio
        img_aspect = img.width / img.height
        standard_aspect = STANDARD_WIDTH / STANDARD_HEIGHT
        
        if img_aspect > standard_aspect:
            # Image is wider than standard
            new_height = STANDARD_HEIGHT
            new_width = int(STANDARD_HEIGHT * img_aspect)
        else:
            # Image is taller or equal aspect ratio
            new_width = STANDARD_WIDTH
            new_height = int(STANDARD_WIDTH / img_aspect)
        
        # Resize
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create new image with standard size and paste resized image centered
        background = Image.new('RGB', STANDARD_RESOLUTION, color=(0, 0, 0))
        offset = ((STANDARD_WIDTH - new_width) // 2, (STANDARD_HEIGHT - new_height) // 2)
        background.paste(img, offset)
        
        return background
    
    def resize_video_to_standard(self, video_path, output_path):
        """Resize uploaded video to standard reel dimensions using ffmpeg"""
        if not FFMPEG_AVAILABLE:
            raise RuntimeError("FFmpeg is not available. Please install FFmpeg.")
        
        try:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vf', f'scale={STANDARD_WIDTH}:{STANDARD_HEIGHT}:force_original_aspect_ratio=decrease,pad={STANDARD_WIDTH}:{STANDARD_HEIGHT}:(ow-iw)/2:(oh-ih)/2',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',  # Overwrite output file
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
            return output_path
        except subprocess.TimeoutExpired:
            raise RuntimeError("Video resizing timed out. File may be too large.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg error: {e.stderr.decode()}")
    
    def create_reel(self, image_paths, output_path, background_music=None, text_overlays=None):
        """Create video from images with standardized size"""
        if not MOVIEPY_AVAILABLE:
            raise ImportError("MoviePy is not installed. Run: pip install moviepy==1.0.3")
        
        clips = []
        
        for img_path in image_paths:
            try:
                # Resize image to standard dimensions
                resized_img = self.resize_image_to_standard(img_path)
                
                # Save resized image temporarily
                temp_img_path = img_path.replace('.jpg', '_temp.jpg').replace('.png', '_temp.png')
                resized_img.save(temp_img_path, quality=95)
                
                # Create video clip
                clip = ImageClip(temp_img_path)
                clip = clip.set_duration(self.config['duration_per_image'])
                
                # Add fade transition
                if self.config['transition'] == 'fade':
                    clip = clip.crossfadein(0.3).crossfadeout(0.3)
                
                clips.append(clip)
                
            except Exception as e:
                print(f"⚠️ Error processing image {img_path}: {str(e)}")
                continue
        
        if not clips:
            raise ValueError("No valid images could be processed for reel creation.")
        
        # Concatenate all clips
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # Ensure final video is standard size
        final_clip = final_clip.resize(height=STANDARD_HEIGHT, width=STANDARD_WIDTH)
        
        # Add background music if provided
        if background_music and os.path.exists(background_music):
            try:
                audio = AudioFileClip(background_music)
                audio = audio.subclip(0, min(audio.duration, final_clip.duration))
                final_clip = final_clip.set_audio(audio)
            except Exception as e:
                print(f"⚠️ Error adding music: {str(e)}")
        
        # Add text overlays
        if text_overlays:
            final_clip = self.add_text_overlays(final_clip, text_overlays)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Write output file with standard settings
        final_clip.write_videofile(
            output_path,
            fps=self.config['fps'],
            codec='libx264',
            audio_codec='aac',
            verbose=False,
            logger=None
        )
        
        return output_path
    
    def add_text_overlays(self, video_clip, text_overlays):
        """Add text overlays to video"""
        text_clips = []
        
        for text_config in text_overlays:
            try:
                txt_clip = TextClip(
                    text_config['text'],
                    fontsize=text_config.get('fontsize', 70),
                    color=text_config.get('color', 'white'),
                    font=text_config.get('font', 'Arial-Bold')
                )
                txt_clip = txt_clip.set_position(text_config.get('position', 'center'))
                txt_clip = txt_clip.set_start(text_config.get('start', 0))
                txt_clip = txt_clip.set_duration(text_config.get('duration', 3))
                text_clips.append(txt_clip)
            except Exception as e:
                print(f"⚠️ Error adding text overlay: {str(e)}")
                continue
        
        if text_clips:
            return CompositeVideoClip([video_clip] + text_clips)
        return video_clip
