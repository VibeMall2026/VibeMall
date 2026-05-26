@echo off
setlocal
cd /d "%~dp0"

echo ===========================================
echo Live Log Watch
echo 1) bot_process.log  (best for trade events)
echo 2) logs\bot.log     (app logger output)
echo 3) watchdog.log     (watchdog/restart events)
echo ===========================================
set /p CHOICE=Select log to watch [1-3]: 

if "%CHOICE%"=="1" set "LOGFILE=bot_process.log"
if "%CHOICE%"=="2" set "LOGFILE=logs\bot.log"
if "%CHOICE%"=="3" set "LOGFILE=watchdog.log"

if not defined LOGFILE (
  echo Invalid choice.
  exit /b 1
)

if not exist "%LOGFILE%" (
  echo File not found: %LOGFILE%
  exit /b 1
)

echo.
echo Watching: %LOGFILE%
echo Press Ctrl+C to stop.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -LiteralPath '%LOGFILE%' -Tail 80 -Wait"
