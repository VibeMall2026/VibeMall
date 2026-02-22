# 🎬 Reel Creator - Quick Reference Card

## 🚀 Installation (One Time)
```bash
pip install moviepy==1.0.3 numpy==1.24.3
```

## 📝 Create Reel (5 Steps)

### 1️⃣ Login Admin
```
http://localhost:8000/admin/
```

### 2️⃣ Go to Reels
```
Admin Panel → Reels → Add Reel
```

### 3️⃣ Fill Details
- **Title**: "My First Reel"
- **Duration per image**: 3 seconds
- **Transition**: fade

### 4️⃣ Add Images
Scroll down to "Reel Images":
- Upload image 1 → Order: 0 → Text: "Hello"
- Upload image 2 → Order: 1 → Text: "World"
- Upload image 3 → Order: 2 → Text: "VibeMall"

### 5️⃣ Generate
- Click "Save"
- Go to Reels list
- Click "🎬 Generate Reel"
- Wait 30 seconds
- Done! ✅

## 🎨 Text Overlay Options

| Setting | Options | Example |
|---------|---------|---------|
| **text_overlay** | Any text | "50% OFF" |
| **text_position** | center, top, bottom | center |
| **text_color** | white, black, #FF0000 | white |
| **text_size** | 30-150 | 70 |

## 📱 Output Format

- **Resolution**: 1080 x 1920 (vertical)
- **Format**: MP4
- **Perfect for**: Instagram Reels, YouTube Shorts

## ⚡ Quick Tips

✅ Use high-quality images (1080px+)
✅ Set proper order (0, 1, 2, 3...)
✅ White text on dark images
✅ 3-5 images = best results
✅ Preview before publishing

## 🔧 Common Issues

### MoviePy not installed?
```bash
pip install moviepy==1.0.3
```

### Video not generating?
- Check images are uploaded
- Check order is set (0, 1, 2...)
- Wait 30-60 seconds
- Refresh page

### Text not showing?
- Check text_overlay is filled
- Try different text_color
- Increase text_size

## 📊 Processing Time

| Images | Time |
|--------|------|
| 2-3 | ~20 sec |
| 4-5 | ~30 sec |
| 6-10 | ~60 sec |

## 🎯 Example Use Cases

### Product Promo
```
Image 1: Product photo → "New Arrival"
Image 2: Product detail → "Premium Quality"
Image 3: Price tag → "₹999 Only"
Image 4: CTA → "Shop Now"
```

### Flash Sale
```
Image 1: Banner → "Flash Sale"
Image 2: Products → "Up to 70% OFF"
Image 3: Timer → "Limited Time"
Image 4: Logo → "VibeMall.com"
```

## 📖 Full Documentation

- **Complete Guide**: `REEL_CREATOR_GUIDE.md`
- **Installation**: `INSTALL_REEL_FEATURE.md`
- **Summary**: `REEL_FEATURE_SUMMARY.md`

---

**Quick Start**: Install MoviePy → Add Reel → Upload Images → Generate → Share! 🎉
