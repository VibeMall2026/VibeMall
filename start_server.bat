@echo off
setlocal
REM start_server.bat - launch startup_manager in always-visible console mode.
REM WATCHDOG_VISIBLE=1 keeps watchdog and bot logs visible in this same window.

cd /d "%~dp0"
chcp 65001 >nul
echo Starting trading bot server (visible mode)...
set "WATCHDOG_VISIBLE=1"
python -X utf8 -u startup_manager.py

echo.
echo Startup complete. Opening live shared logs...
echo Press Ctrl+C to stop log tracking.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p='.\logs\bot_shared.log'; " ^
  "while(-not (Test-Path $p)){ Start-Sleep -Seconds 2 }; " ^
  "Get-Content -LiteralPath $p -Tail 120 -Wait"
