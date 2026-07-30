@echo off
REM ollama_tunnel.bat - Exposes this PC's Ollama to the VibeMall server.
REM
REM The product-automation worker on the VPS calls OLLAMA_BASE_URL. This
REM reverse tunnel makes the VPS's own 127.0.0.1:11434 reach the Ollama
REM running here, so the server needs no public port and this PC needs no
REM port forwarding or firewall change.
REM
REM Keep this window open while the bot is running. It reconnects on its own
REM if the connection drops; if this PC sleeps, drafts simply fall back to
REM rule-based extraction until it comes back.
REM
REM Requires: ollama serve running locally, and the SSH key already used for
REM this VPS.

set VPS_USER=root
set VPS_HOST=187.124.98.177
set VPS_PORT=22
set REMOTE_PORT=11434
set LOCAL_PORT=11434
set KEY_FILE=%USERPROFILE%\.ssh\id_rsa

echo Ollama reverse tunnel starting...
echo   VPS:    %VPS_USER%@%VPS_HOST%:%VPS_PORT%
echo   Tunnel: VPS 127.0.0.1:%REMOTE_PORT% -^> this PC 127.0.0.1:%LOCAL_PORT%
echo.
echo Leave this window open. Press Ctrl+C to stop.
echo.

:loop
ssh -4 -N -R 127.0.0.1:%REMOTE_PORT%:127.0.0.1:%LOCAL_PORT% ^
    -o ServerAliveInterval=30 ^
    -o ServerAliveCountMax=3 ^
    -o ExitOnForwardFailure=yes ^
    -i "%KEY_FILE%" ^
    -p %VPS_PORT% ^
    %VPS_USER%@%VPS_HOST%

echo Tunnel exited. Reconnecting in 10 seconds...
timeout /t 10 /nobreak >nul
goto :loop
