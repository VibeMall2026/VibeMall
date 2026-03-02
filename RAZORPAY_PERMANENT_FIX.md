# 🔴 RAZORPAY "SDK NOT FOUND" - ROOT CAUSE & PERMANENT FIX

## The Problem (Why This Error Keeps Happening)

```
Refund failed: Razorpay SDK not found. Run: pip install razorpay
```

**Root Cause:** Django is running with **SYSTEM Python** instead of **venv Python**

When you run `python manage.py runserver`, Windows finds the SYSTEM Python (not the one with razorpay installed). Razorpay IS installed in the venv, but the running Python can't see it.

---

## The Solution (3 Methods - Pick One)

### ✅ METHOD 1: Use the Startup Script (EASIEST) ⭐

1. **Find this file:** `run_django.bat` (in project root)
2. **Double-click it** instead of running manage.py manually
3. **Done!** It will:
   - Activate the venv automatically
   - Verify razorpay is available
   - Start Django with the correct Python
   - Show which Python is running

**File Location:** 
```
d:\Iu University\...\VibeMall\run_django.bat
```

---

### ✅ METHOD 2: Manually Activate venv (RECOMMENDED)

**Step-by-step:**

1. **Open Command Prompt (cmd.exe)**

2. **Navigate to project:**
   ```
   cd "d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall"
   ```

3. **Activate venv:**
   ```
   venv\Scripts\activate.bat
   ```
   
   You should see `(venv)` at the beginning of your prompt:
   ```
   (venv) d:\...\VibeMall>
   ```

4. **Verify razorpay:**
   ```
   python -c "import razorpay; print('Razorpay OK')"
   ```

5. **Start Django:**
   ```
   python manage.py runserver
   ```

6. **Test refund:** Admin Panel → Orders → PAID order → Refund

---

### ✅ METHOD 3: Use Explicit venv Python (QUICKEST)

Run this single command (copy-paste exactly):

```bash
venv\Scripts\python.exe manage.py runserver
```

This **forces** the use of venv Python, bypassing any PATH issues.

---

## How to Verify It's Fixed

### Quick Check (Before Testing Refund)

Run this in Command Prompt:
```bash
python -c "import sys; print('Python:', sys.executable); import razorpay; print('Razorpay: OK')"
```

**Expected output:**
```
Python: d:\...\VibeMall\venv\Scripts\python.exe
Razorpay: OK
```

If you see system Python path (like `C:\Users\ADMIN\AppData\...`), you're using the wrong Python.

### Full Test (Test Refund)

1. Start Django with one of the methods above
2. Go to **Admin Panel → Orders**
3. **Select any order with PAID status** (green badge)
4. Click **Refund button**
5. Try processing a refund
6. Should now work! 

**Expected results:**
- ✅ Success: "Payment refunded successfully"
- ✅ Specific error: "Payment already refunded" OR "Invalid payment ID"
- ❌ Wrong: "SDK not found" (means venv still not activated)

---

## Understanding the Environment

### Current Setup

```
Project Root/
├── venv/                         ← Virtual Environment with razorpay
│   ├── Scripts/
│   │   ├── python.exe           ← THE CORRECT PYTHON
│   │   └── activate.bat         ← Activates venv
│   └── Lib/site-packages/
│       └── razorpay/            ← Package is HERE
├── manage.py                    ← Django starter
├── run_django.bat               ← Use this to start!
└── requirements.txt             ← Lists razorpay==1.4.1
```

### Why It Fails

```
❌ WRONG WAY (what's probably happening):
   You type: python manage.py runserver
   Windows finds: C:\Users\ADMIN\AppData\Local\Programs\Python311\python.exe (SYSTEM)
   Result: Can't find razorpay → "SDK not found" error

✅ CORRECT WAY (what we're fixing):
   You type: venv\Scripts\python.exe manage.py runserver
   Django uses: d:\...\VibeMall\venv\Scripts\python.exe
   Result: Finds razorpay in venv\Lib\site-packages → Works!
```

---

## Permanent Fix (For Team/Production)

If you don't want to worry about this every time:

### Option A: Create Shortcut
1. Right-click desktop → New → Shortcut
2. Command:
   ```
   cmd.exe /k "cd /d d:\Iu University\...\VibeMall && venv\Scripts\activate.bat && python manage.py runserver"
   ```
3. Name: "Start VibeMall Django"
4. Click it whenever you want to run Django

### Option B: Edit VSCode Settings
If using VSCode to run Django:

In `.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/Scripts/python.exe"
}
```

### Option C: Use the provided run_django.bat
Just double-click `run_django.bat` every time.

---

## Troubleshooting

### "Still getting SDK not found error"

**Check 1: Is venv activated?**
```bash
python -c "import sys; print(sys.prefix)"
```
Should show venv path, NOT system path

**Check 2: Is razorpay actually in venv?**
```bash
dir venv\Lib\site-packages\razorpay
```
Should list `__init__.py` and other files

**Check 3: Can you import it?**
```bash
python -c "import razorpay; print(razorpay.__file__)"
```
Should show path in venv

**Fix if not found:**
```bash
venv\Scripts\python.exe -m pip install razorpay --upgrade
```

### "Command not found: venv\Scripts\activate.bat"

This means you're in wrong directory. Make sure you're in project root:
```bash
cd "d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall"
```

Then try again:
```bash
venv\Scripts\activate.bat
```

### "Permission denied"

Run Command Prompt as Administrator:
1. Press `Win + X`
2. Choose "Command Prompt (Admin)" or "PowerShell (Admin)"
3. Try again

---

## What Changed in Code

We improved the error message to help debug:

**File:** `Hub/views.py` (lines 8303-8325)

```python
except ImportError as ie:
    import sys, logging, os, site
    logger = logging.getLogger(__name__)
    
    # Log detailed environment info
    logger.error(f'Razorpay import failed')
    logger.error(f'Python: {sys.executable}')
    logger.error(f'venv: {sys.prefix}')
    
    # More helpful error message
    return False, f'Razorpay SDK not found. Python: {sys.executable[:30]}... Run: pip install razorpay'
```

This helps us debug which Python Django is using.

---

## Summary

| Issue | Solution |
|-------|----------|
| "SDK not found" error repeats | Django using wrong Python |
| How to fix | Use `run_django.bat` OR activate venv before running |
| Permanent fix | Add to startup shortcut or VSCode settings |
| Test it | Admin → Orders → PAID order → Refund |

---

## Need Help?

1. **Run diagnostic:**
   ```bash
   python WHY_RAZORPAY_FAILS.py
   ```

2. **Try the fix:**
   - Use Method 1 (run_django.bat) - Easiest
   - Or Method 2 (activate venv) - Most common
   - Or Method 3 (explicit path) - Most reliable

3. **Test:**
   - Admin Panel → Orders → Refund on PAID order
   - Should now work ✅

---

**Last Updated:** March 2, 2026  
**Status:** PERMANENT FIX - Follow one of the three methods above
