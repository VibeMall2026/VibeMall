@echo off
REM =================================================================
REM VIBEMALL DJANGO STARTUP WITH RAZORPAY VERIFICATION
REM This script ensures razorpay is installed before starting Django
REM =================================================================

setlocal enabledelayedexpansion

cd /d "d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall"

title VibeMall Django Server

echo.
echo =================================================================
echo VIBEMALL DJANGO STARTUP
echo =================================================================
echo Time: %date% %time%
echo Directory: %CD%
echo.

REM Step 1: Activate venv
echo Step 1: Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate venv
    pause
    exit /b 1
)
echo OK - venv activated
echo.

REM Step 2: Verify Python
echo Step 2: Verifying Python...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not working
    pause
    exit /b 1
)
echo OK - Python working
echo.

REM Step 3: Check razorpay
echo Step 3: Checking razorpay installation...
python -c "import razorpay; print('[OK] Razorpay found'); exit(0)" >nul 2>&1

if %errorlevel% neq 0 (
    echo WARNING: Razorpay not found, installing now...
    pip install razorpay --upgrade --quiet
    
    python -c "import razorpay; print('[OK] Razorpay installed')"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install razorpay
        pause
        exit /b 1
    )
) else (
    echo OK - Razorpay is available
)
echo.

REM Step 4: Run Django
echo Step 4: Starting Django server...
echo =================================================================
echo Django will start on: http://localhost:8000
echo Admin panel: http://localhost:8000/admin
echo.
echo To stop server: Press Ctrl+C
echo =================================================================
echo.

python manage.py runserver

pause
