"""
Quick FFmpeg check script
"""
import subprocess
import sys

print("🔍 Checking FFmpeg installation...\n")

try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
    
    if result.returncode == 0:
        print("✅ FFmpeg is installed and working!")
        print("\nVersion info:")
        print(result.stdout.split('\n')[0])
        print("\n✅ You can now generate reels!")
    else:
        print("❌ FFmpeg found but returned error")
        print(result.stderr)
        
except FileNotFoundError:
    print("❌ FFmpeg NOT found!")
    print("\n📥 Installation instructions:")
    print("\n1. Using Chocolatey (easiest):")
    print("   choco install ffmpeg")
    print("\n2. Manual installation:")
    print("   - Download from: https://www.gyan.dev/ffmpeg/builds/")
    print("   - Extract to C:\\ffmpeg")
    print("   - Add C:\\ffmpeg\\bin to System PATH")
    print("\n3. Restart terminal after installation")
    print("\nSee FFMPEG_INSTALLATION_GUIDE.md for detailed steps")
    sys.exit(1)
    
except subprocess.TimeoutExpired:
    print("⚠️ FFmpeg command timed out")
    sys.exit(1)

print("\n" + "="*60)
print("Next steps:")
print("1. Run: python manage.py fix_stuck_reels")
print("2. Go to admin panel and click 'Generate' on a reel")
print("3. Watch the server console for detailed output")
print("="*60)
