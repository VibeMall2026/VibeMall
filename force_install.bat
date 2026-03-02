@echo off
setlocal enabledelayedexpansion

cd /d "d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall"

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
