@echo off
REM Run trading bot in foreground so logs are visible in this window.
REM Use this instead of start_server.bat when you want live console logs.

cd /d "%~dp0"
echo Starting trading bot with live logs...
echo Press Ctrl+C to stop.
echo.

python -u -m bot.main

echo.
echo Bot process exited. Press any key to close this window.
pause >nul
