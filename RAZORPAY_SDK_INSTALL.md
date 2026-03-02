# 🔧 Razorpay SDK Installation & Verification

## Current Status

**Error**: "Razorpay SDK is not installed. Please contact administrator."

**Cause**: The `razorpay` Python package is not installed in the current environment.

**Solution**: Install the razorpay package from PyPI.

---

## Installation Steps

### Method 1: Using pip (Recommended)

```bash
pip install razorpay
```

### Method 2: Install from requirements.txt

```bash
pip install -r requirements.txt
```

This will install ALL required packages including razorpay.

### Method 3: Specific to your environment

If using a virtual environment, activate it first:

```bash
# On Windows
venv\Scripts\activate
# Then install
pip install razorpay
```

---

## Verification

After installation, verify razorpay is installed:

```bash
# Check if installed
pip show razorpay

# Test import in Python
python -c "import razorpay; print('✓ razorpay installed')"

# In Django shell
python manage.py shell
>>> import razorpay
>>> print(razorpay.__version__)
```

---

## What Gets Installed

The `razorpay==1.4.1` package provides:

- `razorpay.Client` - Main API client
- Methods for payment, refund, transfer operations
- Support for test and production credentials
- Exception handling for API errors

---

## Required for VibeMall

Razorpay is critical for:
- ✅ Processing online payments (Razorpay payment gateway)
- ✅ Creating refunds for orders
- ✅ Processing cancellation refunds
- ✅ Handling return refunds
- ✅ Payment verification

**Without it**: All refund operations will fail with "SDK not installed" error.

---

## Package Details

| Property | Value |
|----------|-------|
| Package | razorpay |
| Version | 1.4.1 |
| Required by | VibeMall payment system |
| Installation method | pip |
| Size | ~5 MB |
| Dependencies | requests, httpretty (for testing) |

---

## After Installation

1. The error "Razorpay SDK is not installed" will disappear
2. Refund button will work properly
3. Specific error messages will appear (as per previous fix)
4. Admin can process Razorpay refunds normally

---

## Troubleshooting

### Still Getting "Not Installed" Error?

1. **Check Python version**:
   ```bash
   python --version  # Should be 3.8+
   ```

2. **Check if using venv/virtualenv**:
   - If yes, make sure it's activated before installing
   - Install packages while venv is active

3. **Check pip installation location**:
   ```bash
   pip install razorpay --upgrade
   ```

4. **Force reinstall**:
   ```bash
   pip uninstall razorpay -y
   pip install razorpay==1.4.1
   ```

### Alternative: Install All Requirements

```bash
pip install -r requirements.txt --upgrade
```

This ensures all packages from the requirements file are installed correctly.

---

## Next Steps

1. ✅ Run: `pip install razorpay`
2. ✅ Verify: `python -c "import razorpay; print('OK')"`
3. ✅ Test refund: Try refunding an order in admin panel
4. ✅ Confirm: Should see specific error messages (not "SDK not installed")

---

## Quick Command

Run this in the VibeMall directory to install everything:

```bash
pip install -r requirements.txt
```

Done! Now refunds will work.
