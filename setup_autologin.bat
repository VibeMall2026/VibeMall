@echo off
REM setup_autologin.bat — Configure Windows automatic login via registry.
REM
REM Usage: setup_autologin.bat USERNAME PASSWORD
REM
REM WARNING: This writes the password in plaintext to the Windows registry.
REM          Use only on a physically secured machine.

if "%~1"=="" (
    echo Usage: setup_autologin.bat USERNAME PASSWORD
    echo.
    echo  USERNAME  — Windows account username to log in automatically
    echo  PASSWORD  — Password for that account
    exit /b 1
)
if "%~2"=="" (
    echo Usage: setup_autologin.bat USERNAME PASSWORD
    echo.
    echo  USERNAME  — Windows account username to log in automatically
    echo  PASSWORD  — Password for that account
    exit /b 1
)

set KEY=HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon

echo Configuring auto-login for user: %~1
echo.

reg add "%KEY%" /v AutoAdminLogon  /t REG_SZ /d 1     /f
reg add "%KEY%" /v DefaultUserName /t REG_SZ /d "%~1" /f
reg add "%KEY%" /v DefaultPassword /t REG_SZ /d "%~2" /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Auto-login configured for user: %~1
    echo      Registry key: %KEY%
    echo.
    echo Please reboot to verify that Windows logs in automatically.
) else (
    echo.
    echo [ERROR] Failed to write registry values. Run this script as Administrator.
    exit /b 1
)
