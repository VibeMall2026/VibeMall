"""
Reel Creator Utility for Admin Panel
Images ને video/reel માં convert કરે છે
"""

from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip, TextClip
from PIL import Image
import os
from django.conf import settings

class ReelCreator:
    def __init__(self, config=None):
        """Initialize reel creator with config"""
        self.config = config or self.get_default_config()
        
    def get_default_config(self):
        """Default configuration"""
        return {
            "duration_per_image": 3,
            "fps": 30,
            "resolution": [1080, 1920],
            "transition": "fade",
        }
    
    def create_reel(self, image_paths, output_path, background_music=None, text_overlays=None):
        """Create video from images"""
        clips = []
        
        for img_path in image_paths:
            # Load and resize image
            clip = ImageClip(img_path)
            clip = clip.resize(height=self.config['resolution'][1])
            clip = clip.set_duration(self.config['duration_per_image'])
            
            # Add fade transition
            if self.config['transition'] == 'fade':
                clip = clip.crossfadein(0.5).crossfadeout(0.5)
            
            clips.append(clip)
        
        # Concatenate all clips
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # Add background music if provided
        if background_music and os.path.exists(background_music):
            audio = AudioFileClip(background_music)
            audio = audio.subclip(0, min(audio.duration, final_clip.duration))
            final_clip = final_clip.set_audio(audio)
        
        # Add text overlays
        if text_overlays:
            final_clip = self.add_text_overlays(final_clip, text_overlays)
        
        # Write output file
        final_clip.write_videofile(
            output_path,
            fps=self.config['fps'],
            codec='libx264',
            audio_codec='aac'
        )
        
        return output_path
    
    def add_text_overlays(self, video_clip, text_overlays):
        """Add text overlays to video"""
        text_clips = []
        
        for text_config in text_overlays:
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
        
        return CompositeVideoClip([video_clip] + text_clips)
