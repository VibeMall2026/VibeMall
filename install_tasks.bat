@echo off
REM install_tasks.bat — Register (or manage) Windows Task Scheduler tasks for the trading bot.
REM
REM Usage:
REM   install_tasks.bat                    — Install both tasks (default)
REM   install_tasks.bat enable  <taskname> — Enable a task
REM   install_tasks.bat disable <taskname> — Disable a task
REM   install_tasks.bat remove  <taskname> — Delete a task

setlocal EnableDelayedExpansion

set TASK_SERVER=TradingBotServer
set TASK_TUNNEL=TradingBotSSHTunnel
set PROJECT_DIR=C:\Users\ADMIN\VibeMall-77d8112a
set PYTHON_EXE=C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe
set STARTUP_SCRIPT=%PROJECT_DIR%\startup_manager.py
set TUNNEL_SCRIPT=%PROJECT_DIR%\ssh_tunnel.bat

REM ---- Sub-command dispatch ----
if /I "%~1"=="enable"  goto :subcmd_enable
if /I "%~1"=="disable" goto :subcmd_disable
if /I "%~1"=="remove"  goto :subcmd_remove

REM ---- Default: install both tasks ----
goto :install_all

:install_all
echo Installing Task Scheduler tasks...
echo.

REM Register TradingBotServer (runs startup_manager.py at logon, highest privileges)
schtasks /create /F ^
    /TN "%TASK_SERVER%" ^
    /TR "\"%PYTHON_EXE%\" \"%STARTUP_SCRIPT%\"" ^
    /SC ONLOGON ^
    /RL HIGHEST ^
    /DELAY 0000:05
if %ERRORLEVEL% EQU 0 (
    echo [OK] Task "%TASK_SERVER%" registered — trigger: ONLOGON, privilege: HIGHEST
) else (
    echo [ERROR] Failed to register task "%TASK_SERVER%"
)

echo.

REM Register TradingBotSSHTunnel (runs ssh_tunnel.bat at logon, highest privileges)
schtasks /create /F ^
    /TN "%TASK_TUNNEL%" ^
    /TR "\"%TUNNEL_SCRIPT%\"" ^
    /SC ONLOGON ^
    /RL HIGHEST ^
    /DELAY 0001:00
if %ERRORLEVEL% EQU 0 (
    echo [OK] Task "%TASK_TUNNEL%" registered — trigger: ONLOGON, privilege: HIGHEST
) else (
    echo [ERROR] Failed to register task "%TASK_TUNNEL%"
)

echo.
echo Done. Both tasks will run automatically on next logon.
echo To verify: schtasks /query /TN "%TASK_SERVER%"
echo            schtasks /query /TN "%TASK_TUNNEL%"
goto :eof

:subcmd_enable
if "%~2"=="" (
    echo Usage: install_tasks.bat enable ^<taskname^>
    exit /b 1
)
schtasks /change /TN "%~2" /ENABLE
if %ERRORLEVEL% EQU 0 (
    echo [OK] Task "%~2" enabled.
) else (
    echo [ERROR] Failed to enable task "%~2"
)
goto :eof

:subcmd_disable
if "%~2"=="" (
    echo Usage: install_tasks.bat disable ^<taskname^>
    exit /b 1
)
schtasks /change /TN "%~2" /DISABLE
if %ERRORLEVEL% EQU 0 (
    echo [OK] Task "%~2" disabled.
) else (
    echo [ERROR] Failed to disable task "%~2"
)
goto :eof

:subcmd_remove
if "%~2"=="" (
    echo Usage: install_tasks.bat remove ^<taskname^>
    exit /b 1
)
schtasks /delete /F /TN "%~2"
if %ERRORLEVEL% EQU 0 (
    echo [OK] Task "%~2" removed.
) else (
    echo [ERROR] Failed to remove task "%~2"
)
goto :eof
