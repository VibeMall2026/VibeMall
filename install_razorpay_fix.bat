@echo off
REM Automatic Razorpay Install - Fixes the "SDK not found" error
REM This ensures razorpay is installed in the venv AND system Python

setlocal enabledelayedexpansion

echo.
echo ====================================================================
echo RAZORPAY AUTOMATIC INSTALLATION FIX
echo ====================================================================
echo.

REM Get project directory
cd /d "d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall"

echo Detected project directory: %CD%
echo.

REM Step 1: Install in venv
echo Step 1: Installing razorpay in venv...
echo ====================================================================

if exist "venv\Scripts\python.exe" (
    echo venv found. Installing razorpay...
    call venv\Scripts\python.exe -m pip install razorpay --upgrade
    if %errorlevel% equ 0 (
        echo.
        echo [OK] Razorpay installed in venv
        echo.
    ) else (
        echo [ERROR] Failed to install in venv
        pause
        exit /b 1
    )
) else (
    echo [WARNING] venv not found at venv\Scripts\python.exe
)

REM Step 2: Install in system Python (backup)
echo Step 2: Installing razorpay in system Python...
echo ====================================================================

python -m pip install razorpay --upgrade
if %errorlevel% equ 0 (
    echo.
    echo [OK] Razorpay installed in system Python
    echo.
) else (
    echo [WARNING] Failed to install in system Python
)

REM Step 3: Verify installation
echo Step 3: Verifying installation...
echo ====================================================================
echo.

echo Checking venv Python:
call venv\Scripts\python.exe -c "import razorpay; print('  [OK] Razorpay available in venv')" || echo "  [ERROR] Razorpay NOT available in venv"

echo.
echo Checking system Python:
python -c "import razorpay; print('  [OK] Razorpay available in system')" || echo "  [ERROR] Razorpay NOT available in system"

REM Step 4: Test import
echo.
echo Step 4: Testing razorpay import...
echo ====================================================================

call venv\Scripts\python.exe -c "import razorpay; client = razorpay.Client(auth=('test', 'test')); print('[OK] Razorpay client created')" && (
    echo.
    echo ====================================================================
    echo SUCCESS! Razorpay is ready to use!
    echo ====================================================================
    echo.
    echo Next steps:
    echo 1. Start Django: run_django.bat (or venv\Scripts\python.exe manage.py runserver)
    echo 2. Test refund: Admin Panel ^> Orders ^> PAID order ^> Refund
    echo.
) || (
    echo.
    echo ====================================================================
    echo ERROR: Razorpay still not working
    echo ====================================================================
    echo.
    echo Please run this script again or contact support
    echo.
)

pause
