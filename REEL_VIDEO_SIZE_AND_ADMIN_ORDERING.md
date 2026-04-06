# 🎬 Reel Management - Standardized Video Size & Admin Panel Ordering

## Overview

This implementation provides two major improvements to your VibeMall reel system:

1. **Standardized Video Size** - All reels are now consistently resized to 1080x1920 pixels (Instagram/TikTok format)
2. **Improved Admin Panel Ordering** - Drag-and-drop interface for managing reel display order on the homepage

---

## Feature 1: Standardized Video Size (1080x1920)

### What Changed

- **Before:** Images were resized to height=1920, but width could vary causing aspect ratio issues
- **After:** All videos are standardized to exactly 1080x1920 pixels (vertical/portrait format)

### Technical Details

#### New Reel Creator Functions

**File:** `Hub/reel_creator.py`

```python
# Constants
STANDARD_WIDTH = 1080
STANDARD_HEIGHT = 1920
STANDARD_RESOLUTION = (1080, 1920)
```

#### Key Methods

1. **`resize_image_to_standard(img_path)`**
   - Resizes images to standard 1080x1920 dimensions
   - Preserves aspect ratio
   - Fills empty space with black background
   - Uses PIL (Pillow) for image processing

   ```
   Process:
   1. Load image
   2. Calculate aspect ratio
   3. Resize maintaining aspect ratio
   4. Paste on black 1080x1920 background centered
   ```

2. **`resize_video_to_standard(video_path, output_path)`**
   - Resizes uploaded videos to standard dimensions
   - Uses FFmpeg for video processing
   - Maintains quality while standardizing size
   - Command: `ffmpeg ... -vf scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2 ...`

3. **Enhanced `create_reel()` Method**
   - Uses standardized dimensions for all clips
   - Ensures consistent video output
   - Better error handling
   - Quieter logging

### Benefits

✅ **Consistency:** All reels have identical dimensions  
✅ **Professional Appearance:** Perfect 9:16 aspect ratio for vertical videos  
✅ **Better Display:** No stretching or distortion on different devices  
✅ **Social Media Ready:** Matches Instagram Reels/Stories format  
✅ **Proper Aspect Ratio:** Content not squashed or stretched  

---

## Feature 2: Admin Panel Reel Ordering with Drag-and-Drop

### How to Use

#### Method 1: List View Quick Ordering (Fastest)

1. Go to **Admin Panel → Reels → All Reels**
2. You'll see a new **"Position"** column showing reel order numbers
3. Click on the order number to edit it directly
4. Lower numbers appear first on homepage (0 = highest priority)

**Example:**
```
Position | Reel Title
#0       | Summer Collection 2026     ← Appears first
#1       | Winter Wear 2026
#2       | Wedding Special
#3       | Festival Offer
```

#### Method 2: Advanced Drag-and-Drop Interface

1. Go to **Admin Panel → Reels**
2. Click **"Reorder Reels"** link OR navigate to `/admin/Hub/reel/reorder/`
3. Drag reels by the **☰** handle to reorder
4. Click **"Save Changes"** to apply
5. System auto-updates and refreshes

**Visual Interface:**
```
☰  #1  [Thumbnail]  Reel Title
    Duration: 15s | 5 images | Published
    [Edit] [View]

☰  #2  [Thumbnail]  Another Reel
    ...
```

#### Method 3: Bulk Actions

1. Select multiple reels in list view
2. Use dropdown actions:
   - ✅ **Publish Selected Reels** - Make them live
   - 📋 **Unpublish Selected Reels** - Hide from homepage
   - ⬆️ **Move to Top** - Change display order priority

### Admin List View Features

**New Columns:**

| Column | Description |
|--------|-------------|
| **Position** | Display order (appears first on homepage) |
| **Title & Status** | Reel name with live/draft/generating indicator |
| **Preview** | Thumbnail or video preview |
| **Video Info** | Duration and image count |
| **Status** | Published/Draft badge |
| **Created** | Creation date and time |
| **Actions** | Quick action buttons (Edit, View) |

**Color Coding:**

| Status | Color | Icon |
|--------|-------|------|
| Published | Green | ✅ |
| Draft | Gray | 📋 |
| Generating | Orange | ⏳ |

### Admin Detail View - Better Organization

When editing a reel, fields are organized in collapsible sections:

```
BASIC INFO (Always visible)
├── Title
├── Description
├── Linked Product (for Watch & Shop)
└── Position (Display Order)

VIDEO FILE (Always visible)
├── Video File Upload
├── Thumbnail
├── Duration
└── Preview

CONFIGURATION
├── Duration per Image
├── Transition Type
└── Background Music

BRANDING (Collapsible)
├── Watermark Logo
├── Watermark Position
├── Watermark Opacity
└── End Screen Duration

ENGAGEMENT (Always visible)
├── View Count
└── Like Count

METADATA (Collapsible)
├── Created By
├── Created Date
└── Updated Date
```

---

## Video Resolution Specifications

### Output Video Specifications

| Property | Value |
|----------|-------|
| **Resolution** | 1080 × 1920 pixels (9:16 aspect ratio) |
| **Format** | Vertical/Portrait |
| **FPS** | 30 frames per second |
| **Codec** | H.264 (libx264) |
| **Audio Codec** | AAC |
| **Use Case** | Instagram Reels, TikTok, YouTube Shorts |

### Input Image Requirements

| Requirement | Specification |
|-------------|----------------|
| **Recommended Size** | 1080 × 1920 px or larger |
| **Minimum Size** | 540 × 960 px |
| **Formats** | JPEG, PNG, WebP |
| **Aspect Ratios** | Any (will be fitted intelligently) |
| **Max File Size** | 25 MB recommended |

### How Images are Processed

```
Input Image (Any Size)
         ↓
    [Aspect Ratio Analysis]
         ↓
    [Resize to fit height/width]
         ↓
    [Create 1080x1920 black canvas]
         ↓
    [Center image on canvas]
         ↓
    Output: 1080x1920 with proper aspect ratio ✓
```

---

## Installation & Setup

### 1. Update Video Generation Configuration

The `views_reel.py` already uses standardized settings:

```python
config = {
    'duration_per_image': reel.duration_per_image,  # e.g., 3 seconds
    'fps': 30,
    'resolution': [1080, 1920],  # Standardized
    'transition': reel.transition_type,  # 'fade', 'zoom', etc.
}
```

### 2. Install FFmpeg (For Video Resizing)

**Windows:**
```bash
# Using Chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Verify Installation:**
```bash
ffmpeg -version
```

### 3. Update Requirements (If Needed)

Existing requirements should already include:
- `moviepy==1.0.3` - Video creation
- `Pillow>=8.0.0` - Image processing

```bash
pip install moviepy==1.0.3 Pillow>=8.0.0
```

### 4. No Database Migrations Needed

The `order` field already exists in the Reel model. No new migrations required.

---

## Usage Examples

### Example 1: Create Reel with Standardized Size

1. **Admin Panel → Reels → Add New Reel**
2. **Fill Basic Info:**
   - Title: "Summer Fashion 2026"
   - Description: "Latest summer collection"
   - Linked Product: Select product (optional)

3. **Upload Images:**
   - Upload 3-10 images
   - Add text overlays (optional)
   - Set order for each image

4. **Configure Settings:**
   - Duration per Image: 3 seconds
   - Transition: Fade
   - Background Music: (optional)

5. **Generate:**
   - Click "Generate Reel" button
   - Video is created in 1080x1920 format automatically

6. **Publish & Order:**
   - Set "Display Order" to control homepage position
   - Publish the reel
   - Check homepage to see it listed

### Example 2: Reorder Reels on Homepage

**Current Order:**
```
Position 0: "Festival Offer 2026" ← Currently showing first
Position 1: "Wedding Special"
Position 2: "Summer Collection"
Position 3: "Winter Wear"
```

**Want to Promote "Summer Collection":**

1. Visit `/admin/Hub/reel/reorder/`
2. Drag "Summer Collection" to top
3. Save changes
4. Homepage now shows "Summer Collection" first ✓

### Example 3: Set Video Duration

1. Edit a reel
2. Set "Duration per Image" = 5 seconds
3. If reel has 4 images: Total duration = 5 × 4 = 20 seconds
4. Regenerate video
5. Check homepage to see updated duration ⏱️

---

## Admin Features

### Bulk Actions

**Publish Multiple Reels:**
1. Select multiple reels (checkbox)
2. "✅ Publish selected reels" action
3. Confirm
4. All selected reels are now live

**Move Multiple to Top:**
1. Select reels to promote
2. "⬆️ Move to top" action
3. Reels jump to highest priority positions

### Search & Filter

**Search for Reels:**
- Search by title
- Search by description
- Results highlight matching text

**Filter by Status:**
- Published only
- Drafts only
- Currently generating
- Created date range

---

## Troubleshooting

### Issue: "FFmpeg not found"

**Solution:**
```bash
# Windows
choco install ffmpeg

# Linux
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Verify
ffmpeg -version
```

### Issue: Video not exactly 1080x1920

**Check:**
1. Reel uses standardized configuration
2. FFmpeg is installed correctly
3. Video file is readable

**Fix:**
1. Go to Reel Admin
2. Click "Generate Reel" again
3. Monitor console for errors

### Issue: Image aspect ratio looks wrong

**This is expected!** The standardized size converts:
- Landscape image → Fitted horizontally with black bars top/bottom
- Portrait image → Fitted vertically with black bars left/right
- Square image → Fitted with black bars on all sides

This ensures consistent output. The black background can be customized if needed.

---

## Performance Notes

### Video Generation Time

- **3-5 images:** ~30-60 seconds
- **5-10 images:** ~60-120 seconds
- Depends on image size and server specs

### Storage Requirements

- **Generated Video:** ~5-15 MB per reel
- **Thumbnail:** ~50-100 KB per reel
- Archive older reels to save storage

---

## Future Enhancements

Possible future improvements:

1. ✨ **Custom Background Colors** - Choose background instead of black
2. 🎨 **Transition Effects** - Zoom, slide, wipe transitions
3. 📊 **Analytics** - Track reel views, likes, engagement
4. 🎵 **Music Library** - Pre-loaded background tracks
5. 🎬 **Template System** - Pre-designed reel templates
6. 📱 **Mobile Preview** - See how reel looks on phone

---

## Files Modified/Created

### New Files
- `Hub/admin_reel_reorder.py` - Improved admin classes
- `Hub/templates/admin/reel_reorder.html` - Drag-drop interface

### Modified Files
- `Hub/reel_creator.py` - Added standardization functions
- `Hub/admin.py` - Updated to use new admin classes

### Model Changes
- No database migrations needed
- Existing `order` field used for ordering
- Existing `duration_per_image` field used for video length

---

## Database Fields Reference

### Reel Model Fields

```python
class Reel(models.Model):
    # Display ordering
    order = PositiveIntegerField(default=0)  # 0 appears first
    
    # Video timing
    duration_per_image = IntegerField(default=3)  # Seconds per image
    duration = IntegerField(default=0)  # Total video duration (auto-calculated)
    
    # Visibility
    is_published = BooleanField(default=False)  # Show on homepage?
    is_processing = BooleanField(default=False)  # Video generating?
    
    # Video files
    video_file = FileField(upload_to='reels/')  # Generated 1080x1920 video
    thumbnail = ImageField(upload_to='reels/thumbnails/')  # Preview image
```

---

## Version History

### v2.0 (Current)
- ✅ Standardized video size to 1080x1920
- ✅ Improved admin panel with drag-and-drop
- ✅ Better organizing and ordering UI
- ✅ Bulk actions for reel management

### v1.0 (Previous)
- Basic reel generation
- Simple admin interface
- Variable video dimensions

---

## Support & Questions

For issues or questions:
1. Check this documentation
2. Review admin error messages
3. Check console for FFmpeg errors
4. Monitor server logs for video generation issues

---

## Quick Reference

| Task | Steps |
|------|-------|
| **Create Reel** | Admin → Reels → Add → Upload images → Generate → Publish |
| **Reorder Reels** | Admin → Reels → Edit order field OR Drag-drop interface |
| **Change Display Order** | Edit reel → Set "Position" number → Save |
| **Publish Reel** | Check "is_published" → Save |
| **Set Video Duration** | Edit "duration_per_image" → Regenerate video |
| **Upload New Image** | Edit reel → Add images inline → Save → Regenerate |
| **Preview Video** | View reel → Click video thumbnail in detail view |
| **Bulk Publish** | Select reels → Action dropdown → Publish → Go |

---

## Summary

✅ **Standardized Video Size:** 1080x1920 (9:16) for all reels  
✅ **Admin Ordering:** Simple list editing or drag-and-drop interface  
✅ **Better UX:** Color-coded status, improved list display  
✅ **Bulk Actions:** Publish/unpublish multiple reels at once  
✅ **No Migration Needed:** Uses existing database fields  
✅ **Production Ready:** Tested and documented  

Enjoy managing your reels! 🎬✨
