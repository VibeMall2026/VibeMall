@echo off
REM stop_server.bat — Terminate all trading bot Python processes.

echo Stopping trading bot processes...

REM List matching processes before killing them
echo.
echo Processes to be terminated:
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE 2>nul
echo.

REM Kill python.exe processes associated with the bot
REM First try to kill by window title (startup_manager launched with "TradingBot" title)
taskkill /F /FI "WINDOWTITLE eq TradingBot*" /IM python.exe 2>nul

REM Also kill any remaining python.exe processes running from the project venv
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2^>nul') do (
    taskkill /F /PID %%~i 2>nul
)

echo.
echo Done. All bot python.exe processes terminated.
