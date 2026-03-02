@echo off
REM Run Django with the correct venv Python
REM This ensures razorpay and all packages are available

setlocal enabledelayedexpansion

cd /d "d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall"

REM Activate venv
call venv\Scripts\activate.bat

REM Verify razorpay is available
echo.
echo ====================================================
echo Verifying razorpay installation...
echo ====================================================
python -c "import razorpay; print('OK: Razorpay is available')" || (
    echo ERROR: Razorpay not found. Installing...
    pip install razorpay
)
echo.

REM Start Django
echo ====================================================
echo Starting Django with correct Python environment...
echo ====================================================
echo Python: %VIRTUAL_ENV%\Scripts\python.exe
echo.

python manage.py runserver

pause
