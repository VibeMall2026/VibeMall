# 🔧 Reel 404 Error - Fix Guide

## 🐛 Error

```
Page not found (404)
No Reel matches the given query.
```

## 🔍 Cause

The reel with ID 7 doesn't exist in your database. This happens when:
1. Database was reset/cleared
2. Reel was deleted
3. Wrong ID in URL
4. No reels created yet

## ✅ Solution

You need to create a reel first! Here are 3 ways:

---

## Method 1: Create via Admin Panel (Recommended)

### Step 1: Go to Create Reel Page
```
http://localhost:8000/admin-panel/reels/add/
```

### Step 2: Fill the Form
- **Title**: "My First Reel"
- **Description**: "Test reel"
- **Duration**: 3 seconds
- **Transition**: Fade

### Step 3: Upload Images
- Click upload area
- Select 3-5 images from your computer
- Add text overlays (optional)

### Step 4: Submit
- Click "Generate Reel" button
- Wait for processing
- Reel will be created!

### Step 5: Access Edit Page
After creation, you'll be redirected to the edit page automatically.

---

## Method 2: Create Test Reel via Script

### Step 1: Run Check Script
```bash
python check_reels.py
```

This will show you all existing reels in database.

### Step 2: Create Test Reel
```bash
python create_test_reel.py
```

This will:
- ✅ Create a test reel
- ✅ Add 5 sample images (colored backgrounds)
- ✅ Add text overlays
- ✅ Show you the reel ID and URLs

### Step 3: Access the Reel
The script will output URLs like:
```
Edit: http://localhost:8000/admin-panel/reels/1/edit/
Generate: http://localhost:8000/admin-panel/reels/1/generate/
```

---

## Method 3: Create via Django Shell

### Step 1: Open Django Shell
```bash
python manage.py shell
```

### Step 2: Create Reel
```python
from Hub.models import Reel, User

# Get admin user
admin = User.objects.filter(is_staff=True).first()

# Create reel
reel = Reel.objects.create(
    title="Test Reel",
    description="Created via shell",
    duration_per_image=3,
    transition_type='fade',
    created_by=admin
)

print(f"Reel created with ID: {reel.id}")
```

### Step 3: Exit Shell
```python
exit()
```

### Step 4: Access Reel
```
http://localhost:8000/admin-panel/reels/<ID>/edit/
```

---

## 🎯 Quick Fix Steps

### If you just want to test the feature:

```bash
# 1. Create test reel
python create_test_reel.py

# 2. Note the reel ID from output

# 3. Go to edit page
http://localhost:8000/admin-panel/reels/<ID>/edit/

# 4. Or go to list page
http://localhost:8000/admin-panel/reels/
```

---

## 📊 Check Database Status

### Check if any reels exist:
```bash
python check_reels.py
```

### Output will show:
```
EXISTING REELS IN DATABASE
==================================================

ID: 1
Title: Test Reel
Created: 2026-02-22 10:30:00
Images: 5
Video: No
Published: False
--------------------------------------------------

Total Reels: 1
==================================================
```

---

## 🚀 Recommended Workflow

### For Testing:
```
1. Run: python create_test_reel.py
   ↓
2. Go to: /admin-panel/reels/
   ↓
3. Click "Edit" on test reel
   ↓
4. Click "Generate Video"
   ↓
5. Test complete! ✅
```

### For Production:
```
1. Go to: /admin-panel/reels/add/
   ↓
2. Upload real product images
   ↓
3. Add text overlays
   ↓
4. Generate reel
   ↓
5. Publish! ✅
```

---

## 🔍 Troubleshooting

### Problem: "No admin user found"
**Solution:**
```bash
python manage.py createsuperuser
```

### Problem: "Permission denied"
**Solution:**
Login as admin user first:
```
http://localhost:8000/admin-panel/
```

### Problem: "Image upload fails"
**Solution:**
Check media folder permissions:
```bash
# Windows
mkdir media\reels\images

# Linux/Mac
mkdir -p media/reels/images
chmod 755 media/reels/images
```

### Problem: "Reel list is empty"
**Solution:**
Create a reel first using any of the 3 methods above.

---

## 📱 Access Points

### Main Pages:
```
Reel List:   /admin-panel/reels/
Create Reel: /admin-panel/reels/add/
Edit Reel:   /admin-panel/reels/<ID>/edit/
Generate:    /admin-panel/reels/<ID>/generate/
```

### Sidebar Menu:
```
Admin Panel → 🎬 Reels → All Reels
Admin Panel → 🎬 Reels → Create New Reel
```

---

## ✅ Verification

### After creating a reel, verify:

1. **Check database:**
   ```bash
   python check_reels.py
   ```

2. **Check reel list:**
   ```
   http://localhost:8000/admin-panel/reels/
   ```

3. **Check edit page:**
   ```
   http://localhost:8000/admin-panel/reels/<ID>/edit/
   ```

All should work without 404 errors! ✅

---

## 🎉 Summary

**Problem**: Reel ID 7 doesn't exist  
**Solution**: Create a reel first  
**Methods**: Admin panel, Script, or Django shell  
**Recommended**: Use `create_test_reel.py` for quick testing  

---

## 🚀 Quick Start

```bash
# Create test reel
python create_test_reel.py

# Check it was created
python check_reels.py

# Access reel list
# Go to: http://localhost:8000/admin-panel/reels/
```

**Done! No more 404 errors! 🎬✨**
