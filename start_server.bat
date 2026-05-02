@echo off
REM start_server.bat — Launch the trading bot startup manager in the background.
REM The startup manager waits 60 s, checks internet, then spawns watchdog.py.

echo Starting trading bot server...
start "TradingBot" /B python startup_manager.py
echo Startup manager launched. Check startup_manager.log for progress.
