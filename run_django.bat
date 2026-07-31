@echo off
REM Run Django with the correct venv Python
REM This ensures razorpay and all packages are available

setlocal enabledelayedexpansion

REM Always work from the folder this script lives in, so the project can be
REM moved or cloned anywhere without editing a hardcoded path again.
cd /d "%~dp0"

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
