@echo off
REM restart_server.bat — Stop then start the trading bot server.

echo Restarting trading bot server...
call stop_server.bat
echo Waiting 3 seconds before restart...
timeout /t 3 /nobreak >nul
call start_server.bat
