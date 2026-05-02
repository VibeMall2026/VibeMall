@echo off
REM ssh_tunnel.bat — Persistent SSH reverse tunnel with auto-reconnect.
REM Forwards VPS_PORT on the remote VPS to localhost:LOCAL_PORT on this machine.
REM Uses key-based authentication for unattended reconnection.
REM
REM Edit the variables below to match your VPS configuration before running.

set VPS_USER=root
set VPS_HOST=187.124.98.177
set VPS_PORT=22
set TUNNEL_PORT=2222
set LOCAL_PORT=8001
set KEY_FILE=%USERPROFILE%\.ssh\id_rsa

echo SSH reverse tunnel starting...
echo   VPS:  %VPS_USER%@%VPS_HOST%:%VPS_PORT%
echo   Tunnel: remote %TUNNEL_PORT% -> localhost:%LOCAL_PORT%
echo   Key:  %KEY_FILE%
echo.

:loop
ssh -4 -N -R 127.0.0.1:%TUNNEL_PORT%:127.0.0.1:%LOCAL_PORT% ^
    -o ServerAliveInterval=30 ^
    -o ServerAliveCountMax=3 ^
    -o ExitOnForwardFailure=yes ^
    -i "%KEY_FILE%" ^
    -p %VPS_PORT% ^
    %VPS_USER%@%VPS_HOST%

echo SSH tunnel exited. Reconnecting in 10 seconds...
timeout /t 10 /nobreak >nul
goto :loop
