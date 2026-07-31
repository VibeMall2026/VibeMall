@echo off
setlocal enabledelayedexpansion

REM Always work from the folder this script lives in, so the project can be
REM moved or cloned anywhere without editing a hardcoded path again.
cd /d "%~dp0"

echo.
echo ====================================================================
echo FORCE INSTALLING RAZORPAY IN VENV
echo ====================================================================
echo.

REM Use venv Python directly
call venv\Scripts\python.exe force_install_razorpay.py

if %errorlevel% equ 0 (
    echo.
    echo ====================================================================
    echo SUCCESS! Razorpay is now installed
    echo ====================================================================
    echo.
    echo NEXT: Restart Django and test refund
    echo.
) else (
    echo.
    echo ERROR DURING INSTALLATION
    echo.
)

pause
