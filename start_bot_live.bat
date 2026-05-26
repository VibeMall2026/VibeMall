@echo off
setlocal
REM Run trading bot in foreground so logs are visible in this window.
REM Use this instead of start_server.bat when you want live console logs.

cd /d "%~dp0"
chcp 65001 >nul
set "PY_EXE=C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe"

echo ============================================================
echo Trading Bot Live Console
echo Working Dir: %CD%
echo Python: %PY_EXE%
echo Start Time: %DATE% %TIME%
echo Press Ctrl+C to stop.
echo ============================================================
echo.

if not exist "%PY_EXE%" (
  echo [ERROR] Python executable not found at:
  echo         %PY_EXE%
  echo.
  echo Bot process not started. Press any key to close this window.
  pause >nul
  exit /b 1
)

"%PY_EXE%" -X utf8 -u -m bot.main
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo Bot process exited with code %EXIT_CODE%.
echo Press any key to close this window.
pause >nul
exit /b %EXIT_CODE%
