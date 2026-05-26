@echo off
setlocal
cd /d "%~dp0"

echo ===========================================
echo Live Log Watch
echo 1) bot_process.log      (best for trade events)
echo 2) logs\bot.log         (app logger output)
echo 3) watchdog.log         (watchdog/restart events)
echo 4) startup_manager.log  (startup checks)
echo ===========================================
set /p CHOICE=Select log to watch [1-4]: 

if "%CHOICE%"=="1" set "LOGFILE=bot_process.log"
if "%CHOICE%"=="2" set "LOGFILE=logs\bot.log"
if "%CHOICE%"=="3" set "LOGFILE=watchdog.log"
if "%CHOICE%"=="4" set "LOGFILE=startup_manager.log"

if not defined LOGFILE (
  echo Invalid choice.
  exit /b 1
)

if not exist "%LOGFILE%" (
  echo File not found yet: %LOGFILE%
  echo.
  echo Available log files in this folder:
  dir /b *.log 2>nul
  if exist logs\*.log (
    echo.
    echo Available log files in logs\:
    dir /b logs\*.log
  )
  echo.
  echo Start bot first using start_server.bat or start_bot_live.bat, then run this watcher again.
  pause
  exit /b 1
)

echo.
echo Watching: %LOGFILE%
echo Press Ctrl+C to stop.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -LiteralPath '%LOGFILE%' -Tail 80 -Wait"
