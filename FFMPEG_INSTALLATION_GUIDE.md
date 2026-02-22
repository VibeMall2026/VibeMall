# FFmpeg Installation Guide for Windows

## What is FFmpeg?
FFmpeg is required for video generation in the Reel Creator feature. Without it, videos cannot be created from images.

## Installation Steps for Windows

### Method 1: Using Chocolatey (Recommended - Easiest)

1. Open PowerShell as Administrator
2. Install Chocolatey if not already installed:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

3. Install FFmpeg:
```powershell
choco install ffmpeg
```

4. Verify installation:
```bash
ffmpeg -version
```

### Method 2: Manual Installation

1. **Download FFmpeg:**
   - Visit: https://www.gyan.dev/ffmpeg/builds/
   - Download: `ffmpeg-release-essentials.zip`

2. **Extract Files:**
   - Extract the ZIP file to `C:\ffmpeg`
   - You should have: `C:\ffmpeg\bin\ffmpeg.exe`

3. **Add to System PATH:**
   - Press `Win + X` and select "System"
   - Click "Advanced system settings"
   - Click "Environment Variables"
   - Under "System variables", find and select "Path"
   - Click "Edit"
   - Click "New"
   - Add: `C:\ffmpeg\bin`
   - Click "OK" on all windows

4. **Verify Installation:**
   - Open a NEW Command Prompt or PowerShell
   - Run: `ffmpeg -version`
   - You should see FFmpeg version information

### Method 3: Using Scoop

1. Install Scoop if not already installed:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
irm get.scoop.sh | iex
```

2. Install FFmpeg:
```powershell
scoop install ffmpeg
```

3. Verify:
```bash
ffmpeg -version
```

## After Installation

1. **Restart your terminal/IDE** to load the new PATH
2. **Test in Django:**
   ```bash
   python manage.py shell
   ```
   ```python
   import subprocess
   subprocess.run(['ffmpeg', '-version'])
   ```

3. **Try generating a reel** from the admin panel

## Troubleshooting

### "ffmpeg is not recognized"
- Make sure you added FFmpeg to PATH correctly
- Restart your terminal/IDE after adding to PATH
- Try opening a NEW terminal window

### Video generation still fails
- Check server console for detailed error messages
- Ensure images are uploaded correctly
- Verify temp directory has write permissions

## Quick Test

After installation, run this in your project directory:
```bash
python manage.py fix_stuck_reels
```

Then try generating a reel from the admin panel!

---

**Need Help?** Check the server console output when generating reels for detailed error messages.
