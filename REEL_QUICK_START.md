# 🚀 Reel Feature - Quick Start Guide (ગુજરાતી)

## 📦 Step 1: Dependencies Install કરો

```bash
pip install moviepy==1.0.3 Pillow==10.2.0
```

**Note**: FFmpeg પણ install હોવું જોઈએ. Check કરો:
```bash
ffmpeg -version
```

જો install નથી તો:
- **Windows**: https://ffmpeg.org/download.html થી download કરો
- **Linux**: `sudo apt install ffmpeg`
- **Mac**: `brew install ffmpeg`

## 🎬 Step 2: Admin Panel માં Reel બનાવો

### 2.1 Admin Panel Open કરો
```
http://localhost:8000/admin/
અથવા
http://your-domain.com/admin/
```

### 2.2 "Reels" Section માં જાઓ
- Left sidebar માં "REELS" section શોધો
- "Reels" પર click કરો
- "ADD REEL" button click કરો

### 2.3 Reel Details Fill કરો

**Basic Info:**
- **Title**: "My First Reel" (example)
- **Description**: "Test reel for products" (optional)

**Video Settings:**
- **Duration per image**: 3 (seconds)
- **Transition type**: fade
- **Background music**: (optional - MP3 file upload કરો)

**Status:**
- **Is published**: ❌ (હમણાં unchecked રાખો)
- **Is processing**: ❌ (automatic)

**Save** button click કરો

## 📸 Step 3: Images Add કરો

Reel save થયા પછી, same page પર નીચે "Reel Images" section દેખાશે:

### 3.1 First Image Add કરો
- "Add another Reel Image" click કરો
- **Image**: તમારી પહેલી image upload કરો
- **Order**: 0 (પહેલી image)
- **Text overlay**: "Welcome to Our Store!" (optional)
- **Text position**: center
- **Text color**: white
- **Text size**: 70

### 3.2 More Images Add કરો
Same process repeat કરો:
- Image 2: Order = 1, Text = "Best Products"
- Image 3: Order = 2, Text = "Shop Now"
- Image 4: Order = 3, Text = "Limited Offer"
- Image 5: Order = 4, Text = "Visit Us Today"

**Save** button click કરો

## 🎥 Step 4: Video Generate કરો

### 4.1 Reel List માં જાઓ
- "Reels" list page પર back જાઓ
- તમારા reel ની entry દેખાશે

### 4.2 Generate Button Click કરો
- તમારા reel ની સામે "🎬 Generate Reel" button દેખાશે
- Button click કરો
- "⏳ Processing..." message show થશે

### 4.3 Wait કરો
- Processing time: 30-60 seconds (5 images માટે)
- Page refresh કરો જો status update ન થાય

### 4.4 Check Generated Video
- Processing complete થયા પછી:
  - Video preview દેખાશે
  - Thumbnail generate થશે
  - Duration update થશે

## ✅ Step 5: Publish કરો

### 5.1 Video Check કરો
- Reel edit કરો
- Video preview play કરો
- Check કરો કે બધું correct છે

### 5.2 Publish કરો
- **Is published** checkbox ✅ enable કરો
- **Save** button click કરો

## 🎉 Done! તમારી પહેલી Reel Ready છે!

## 📱 Example: Product Showcase Reel

```
Image 1: Product photo 1 + "New Arrivals"
Image 2: Product photo 2 + "Premium Quality"
Image 3: Product photo 3 + "Best Prices"
Image 4: Product photo 4 + "Shop Now"
Image 5: Store logo + "Visit Us Today"

Duration: 3 seconds each = 15 seconds total
Transition: Fade
Music: Upbeat background track (optional)
```

## 🔧 Troubleshooting

### Problem: "No images found" error
**Solution**: 
- Reel edit કરો
- "Reel Images" section માં images add કરો
- Save કરો અને retry કરો

### Problem: "Generate Reel" button નથી દેખાતું
**Solution**:
- Reel save કરો પહેલા
- Page refresh કરો
- Check કરો કે તમે staff user છો

### Problem: Video generate નથી થતો
**Solution**:
1. Check FFmpeg installation: `ffmpeg -version`
2. Check server logs for errors
3. Verify images are uploaded correctly
4. Check file permissions on media folder

### Problem: Text overlay નથી દેખાતો
**Solution**:
- Text color change કરો (white → black અથવા vice versa)
- Text size increase કરો (70 → 90)
- Text position change કરો

## 💡 Tips & Best Practices

### Image Selection:
- ✅ High quality images use કરો (minimum 1080px width)
- ✅ Similar aspect ratio ની images use કરો
- ✅ Bright, clear images select કરો
- ❌ Blurry અથવા low quality images avoid કરો

### Text Overlays:
- ✅ Short, impactful text લખો (5-10 words)
- ✅ Contrasting colors use કરો (white on dark, black on light)
- ✅ Center position સૌથી સારું work કરે છે
- ❌ Long paragraphs avoid કરો

### Duration:
- ✅ 2-4 seconds per image ideal છે
- ✅ Total 15-30 seconds best છે social media માટે
- ❌ Too fast (< 2 sec) અથવા too slow (> 5 sec) avoid કરો

### Music:
- ✅ Upbeat, energetic music use કરો
- ✅ Copyright-free music use કરો
- ✅ Volume moderate રાખો
- ❌ Copyrighted music avoid કરો

## 📊 Quick Reference

| Setting | Recommended Value | Range |
|---------|------------------|-------|
| Duration per image | 3 seconds | 2-5 sec |
| Text size | 70 | 50-100 |
| Total images | 5-10 | 3-20 |
| Total duration | 15-30 sec | 10-60 sec |
| Image resolution | 1080px+ | 800px+ |
| Music volume | Medium | - |

## 🎯 Common Use Cases

### 1. Product Launch
```
Image 1: Product teaser + "Coming Soon"
Image 2: Product features + "Premium Quality"
Image 3: Product in use + "Easy to Use"
Image 4: Pricing + "Special Offer"
Image 5: CTA + "Order Now"
```

### 2. Sale Announcement
```
Image 1: Sale banner + "Big Sale"
Image 2: Discount % + "Up to 50% Off"
Image 3: Products + "Limited Time"
Image 4: Dates + "This Weekend Only"
Image 5: Store info + "Visit Us"
```

### 3. Brand Story
```
Image 1: Logo + "Our Story"
Image 2: Team photo + "Passionate Team"
Image 3: Products + "Quality Products"
Image 4: Customers + "Happy Customers"
Image 5: Contact + "Join Us"
```

## 📞 Need Help?

1. Check **REEL_FEATURE_GUIDE.md** for detailed documentation
2. Check **REEL_IMPLEMENTATION_SUMMARY.md** for technical details
3. Review Django admin logs for errors
4. Check server error logs

---

**Happy Reel Creating! 🎬✨**
