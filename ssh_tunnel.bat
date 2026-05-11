@echo off
REM ssh_tunnel.bat — Persistent SSH reverse tunnel with auto-reconnect.
REM Runs hidden in background. Forwards VPS port 2222 -> localhost:8001

set VPS_USER=root
set VPS_HOST=187.124.98.177
set VPS_PORT=22
set TUNNEL_PORT=2222
set LOCAL_PORT=8001
set KEY_FILE=%USERPROFILE%\.ssh\id_rsa

echo Starting SSH tunnel in background...
echo   Tunnel: remote %TUNNEL_PORT% -^> localhost:%LOCAL_PORT%

:loop
ssh -4 -N -R 127.0.0.1:%TUNNEL_PORT%:127.0.0.1:%LOCAL_PORT% ^
    -o ServerAliveInterval=30 ^
    -o ServerAliveCountMax=3 ^
    -o ExitOnForwardFailure=yes ^
    -o StrictHostKeyChecking=no ^
    -i "%KEY_FILE%" ^
    -p %VPS_PORT% ^
    %VPS_USER%@%VPS_HOST%

echo SSH tunnel exited. Reconnecting in 10 seconds...
timeout /t 10 /nobreak >nul
goto :loop
