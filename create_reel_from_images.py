"""
Image to Video/Reel Creator Script
તમારા images ને automatically video માં convert કરે છે
"""

from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip, TextClip
from PIL import Image
import os
import json

class ReelCreator:
    def __init__(self, config_file='reel_config.json'):
        """Initialize reel creator with config"""
        self.config = self.load_config(config_file)
        
    def load_config(self, config_file):
        """Load configuration from JSON file"""
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self.get_default_config()
    
    def get_default_config(self):
        """Default configuration"""
        return {
            "output_file": "output_reel.mp4",
            "duration_per_image": 3,  # seconds
            "fps": 30,
            "resolution": [1080, 1920],  # width, height (vertical for reels)
            "transition": "fade",
            "background_music": None,
            "text_overlays": []
        }
    
    def create_reel(self, image_paths):
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
        if self.config['background_music'] and os.path.exists(self.config['background_music']):
            audio = AudioFileClip(self.config['background_music'])
            audio = audio.subclip(0, min(audio.duration, final_clip.duration))
            final_clip = final_clip.set_audio(audio)
        
        # Add text overlays
        if self.config['text_overlays']:
            final_clip = self.add_text_overlays(final_clip)
        
        # Write output file
        final_clip.write_videofile(
            self.config['output_file'],
            fps=self.config['fps'],
            codec='libx264',
            audio_codec='aac'
        )
        
        print(f"✅ Reel created successfully: {self.config['output_file']}")
        return self.config['output_file']
    
    def add_text_overlays(self, video_clip):
        """Add text overlays to video"""
        text_clips = []
        
        for text_config in self.config['text_overlays']:
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


def main():
    """Main function to create reel"""
    # Example usage
    creator = ReelCreator('reel_config.json')
    
    # તમારા images ની list
    images = [
        'image1.jpg',
        'image2.jpg',
        'image3.jpg',
        'image4.jpg'
    ]
    
    # Check if images exist
    existing_images = [img for img in images if os.path.exists(img)]
    
    if not existing_images:
        print("❌ No images found! Please add images first.")
        return
    
    print(f"📸 Found {len(existing_images)} images")
    print("🎬 Creating reel...")
    
    creator.create_reel(existing_images)


if __name__ == "__main__":
    main()
