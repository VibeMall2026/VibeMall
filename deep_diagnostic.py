#!/usr/bin/env python
"""
DEEP DIAGNOSTIC: Check all Python environments and razorpay locations
This will help identify WHY razorpay import is failing at runtime
"""

import os
import sys
import subprocess
import glob

print("\n" + "="*80)
print("DEEP DIAGNOSTIC: RAZORPAY IMPORT FAILURE ANALYSIS")
print("="*80 + "\n")

# 1. Current Python info
print("1. CURRENT PYTHON (running this script)")
print("-" * 80)
print(f"   Executable: {sys.executable}")
print(f"   Version: {sys.version}")
print(f"   In venv: {hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)}")
print(f"   Prefix: {sys.prefix}")
print()

# 2. Find all Python installations
print("2. ALL PYTHON INSTALLATIONS ON SYSTEM")
print("-" * 80)

python_locations = []

# Check common locations
search_paths = [
    r"C:\Users\ADMIN\AppData\Local\Programs\Python*\python.exe",
    r"D:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall\venv\Scripts\python.exe",
    r"C:\Python*\python.exe"
]

for pattern in search_paths:
    matches = glob.glob(pattern)
    python_locations.extend(matches)

if not python_locations:
    # Try finding via where command
    try:
        result = subprocess.run(["where", "python"], capture_output=True, text=True)
        if result.stdout:
            python_locations.extend(result.stdout.strip().split('\n'))
    except:
        pass

python_locations = list(set(python_locations))  # Remove duplicates

for i, python_exe in enumerate(python_locations[:5], 1):
    try:
        result = subprocess.run(
            [python_exe, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor} | venv={hasattr(sys, \"real_prefix\") or (hasattr(sys, \"base_prefix\") and sys.base_prefix != sys.prefix)}')"],
            capture_output=True,
            text=True,
            timeout=5
        )
        version_info = result.stdout.strip() if result.returncode == 0 else "ERROR"
        print(f"   {i}. {python_exe}")
        print(f"      Version: {version_info}")
    except Exception as e:
        print(f"   {i}. {python_exe}")
        print(f"      Error: {e}")

print()

# 3. Check razorpay installation in each Python
print("3. RAZORPAY INSTALLATION STATUS IN EACH PYTHON")
print("-" * 80)

for i, python_exe in enumerate(python_locations[:5], 1):
    try:
        result = subprocess.run(
            [python_exe, "-c", "import razorpay; import os; print(os.path.dirname(razorpay.__file__))"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            location = result.stdout.strip()
            print(f"   {i}. {python_exe}")
            print(f"      INSTALLED: {location}")
        else:
            print(f"   {i}. {python_exe}")
            print(f"      NOT INSTALLED")
    except Exception as e:
        print(f"   {i}. {python_exe}: ERROR - {e}")

print()

# 4. Django's Python path (simulate manage.py)
print("4. DJANGO'S PYTHON ENVIRONMENT (via manage.py)")
print("-" * 80)

try:
    # First find which python manage.py uses
    result = subprocess.run(
        ["which", "python"],
        cwd=r"d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall",
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode == 0:
        django_python = result.stdout.strip()
        print(f"   Python used by manage.py: {django_python}")
    else:
        print(f"   Could not determine (using current): {sys.executable}")
        django_python = sys.executable
    
    # Check if razorpay is available to that Python
    result = subprocess.run(
        [django_python, "-m", "pip", "show", "razorpay"],
        cwd=r"d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall",
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0:
        print(f"   Razorpay status: INSTALLED")
        for line in result.stdout.split('\n')[:5]:
            if line.strip():
                print(f"      {line}")
    else:
        print(f"   Razorpay status: NOT INSTALLED")
        print(f"   pip show output: {result.stderr[:200]}")
        
except Exception as e:
    print(f"   Error checking Django Python: {e}")

print()

# 5. Site packages in venv
print("5. VENV SITE-PACKAGES CHECK")
print("-" * 80)

venv_path = r"d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall\venv"
site_packages = os.path.join(venv_path, "Lib", "site-packages")

print(f"   VirtualEnv: {venv_path}")
print(f"   Exists: {os.path.exists(venv_path)}")

if os.path.exists(site_packages):
    print(f"   SitePackages: {site_packages}")
    print(f"   Exists: True")
    
    # Check if razorpay exists
    razorpay_path = os.path.join(site_packages, "razorpay")
    print(f"   Razorpay dir: {razorpay_path}")
    print(f"   Exists: {os.path.exists(razorpay_path)}")
    
    if os.path.exists(razorpay_path):
        contents = os.listdir(razorpay_path)
        print(f"   Contents: {contents[:5]}")
else:
    print(f"   SitePackages NOT FOUND: {site_packages}")

print()

# 6. RECOMMENDATION
print("6. RECOMMENDED FIX")
print("-" * 80)
print("""
Based on the analysis:

Option A (MOST LIKELY):
   1. Find the venv Python: .\\venv\\Scripts\\python.exe
   2. Install razorpay in that venv:
      .\\venv\\Scripts\\python.exe -m pip install razorpay
   3. Restart Django
   4. Test refund

Option B (if venv not found):
   1. Activate venv: .\\venv\\Scripts\\activate.bat
   2. Install razorpay: pip install razorpay
   3. Restart Django
   4. Test refund

Option C (NUCLEAR - fresh install):
   1. python -m pip install --upgrade razorpay
   2. python manage.py shell
   3. import razorpay (should work)
   4. exit()
   5. python manage.py runserver
   6. Test refund
""")

print("="*80 + "\n")
