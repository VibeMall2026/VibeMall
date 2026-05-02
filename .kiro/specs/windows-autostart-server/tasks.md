# Implementation Plan: Windows Autostart Server

## Overview

Implement the full Windows Local Server Auto-Start & Always-On Setup for the trading bot. All Python files (`watchdog.py`, `startup_manager.py`) and batch files live in the project root alongside `bot/`. Tests live in `tests/`. The implementation language is Python (for scripts) and Windows Batch (for `.bat` files).

## Tasks

- [x] 1. Create watchdog.py — process monitor with health polling and restart logic
  - Create `watchdog.py` in the project root
  - Define all config constants: `PROJECT_ROOT`, `PYTHON_EXE`, `BOT_MODULE`, `HEALTH_URL`, `POLL_INTERVAL`, `FAIL_THRESHOLD`, `HEALTH_TIMEOUT`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`
  - Implement `setup_logger()` using `RotatingFileHandler` writing to `watchdog.log` (10 MB max, 3 backups)
  - Log format: `%(asctime)s UTC | watchdog | %(levelname)s | %(message)s`
  - Implement `kill_port(port: int) -> None` using `subprocess` to find and terminate any process bound to the given port (use `netstat` + `taskkill` on Windows)
  - Implement `check_health(url: str, timeout: int) -> bool` using `requests.get`; return `True` on 2xx, `False` on non-2xx, timeout, or connection error
  - Implement `WatchdogState` dataclass with fields: `process`, `consecutive_failures`, `restart_count`
  - Implement `run_watchdog()` main loop: launch bot via `subprocess.Popen`, poll health every 15 s, track consecutive failures, restart after 3 failures or subprocess exit, call `kill_port(8001)` before each restart, log every restart with UTC timestamp + reason + attempt number, reset failure counter to 0 on success
  - Handle `KeyboardInterrupt`/`SIGTERM`: log shutdown message, terminate child process, exit cleanly
  - Add `if __name__ == "__main__"` entry point
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 8.1, 8.3, 8.4_

  - [x]* 1.1 Write property test for restart trigger logic (Property 1)
    - File: `tests/test_watchdog_properties.py`
    - **Property 1: Restart triggers on exactly 3 consecutive failures**
    - Use `@given(st.lists(st.booleans(), min_size=1))` to feed health result sequences into the failure-counter logic
    - Assert restart fires if and only if the maximum consecutive `False` run ≥ 3
    - Tag: `# Feature: windows-autostart-server, Property 1`
    - **Validates: Requirements 1.3**

  - [x]* 1.2 Write property test for failure counter reset (Property 2)
    - File: `tests/test_watchdog_properties.py`
    - **Property 2: Failure counter resets to zero after any success**
    - Use `@given(st.lists(st.booleans(), min_size=1).filter(lambda s: True in s))` to feed sequences containing at least one `True`
    - Assert `consecutive_failures == 0` after processing the sequence
    - Tag: `# Feature: windows-autostart-server, Property 2`
    - **Validates: Requirements 1.7**

  - [x]* 1.3 Write property test for log entry format (Property 3)
    - File: `tests/test_watchdog_properties.py`
    - **Property 3: Log entries always contain all required fields**
    - Use `@given(st.text(), st.sampled_from(["DEBUG","INFO","WARNING","ERROR"]), st.integers(min_value=0))` to generate arbitrary log events
    - Assert each formatted log line contains: UTC timestamp substring, `"watchdog"`, the level name, and the message text
    - Tag: `# Feature: windows-autostart-server, Property 3`
    - **Validates: Requirements 1.6, 8.3**

  - [x]* 1.4 Write unit tests for watchdog
    - File: `tests/test_watchdog.py`
    - Test that `run_watchdog` launches bot with correct venv python path and `--api` flag (mock `subprocess.Popen`)
    - Test that `kill_port` calls the right system commands (mock `subprocess.run`)
    - Test that `setup_logger` configures `RotatingFileHandler` with `maxBytes=10*1024*1024` and `backupCount=3`
    - Test that `check_health` returns `True` on 2xx and `False` on non-2xx, timeout, and connection error
    - _Requirements: 1.1, 1.5, 8.1, 8.4_

- [x] 2. Checkpoint — verify watchdog tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Create startup_manager.py — boot sequence orchestrator
  - Create `startup_manager.py` in the project root
  - Define all config constants: `STARTUP_DELAY`, `CONNECTIVITY_URL`, `MAX_RETRIES`, `RETRY_INTERVAL`, `HEALTH_POLL_INTERVAL`, `HEALTH_TIMEOUT_SECS`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`
  - Implement `setup_logger()` using `RotatingFileHandler` writing to `startup_manager.log` (5 MB max, 2 backups)
  - Same log format as watchdog but with component name `"startup_manager"`
  - Implement `wait_for_internet(url, retries, interval) -> bool`: attempt `requests.get(url, timeout=10)` up to `retries` times with `interval`-second gaps; return `True` on first 2xx, `False` if all fail
  - Implement `start_watchdog() -> subprocess.Popen`: spawn `watchdog.py` as a detached background process using `subprocess.Popen` with `DETACHED_PROCESS` flag (Windows `creationflags`)
  - Implement `wait_for_health(url, poll_interval, timeout) -> bool`: poll `/health` every `poll_interval` seconds for up to `timeout` seconds; return `True` on first 2xx, `False` on timeout
  - Implement `main()`: sleep `STARTUP_DELAY`, call `wait_for_internet` (exit non-zero if fails), call `start_watchdog`, call `wait_for_health` (log elapsed time on success; log timeout warning and exit 0 on failure, leaving watchdog alive)
  - Handle `KeyboardInterrupt` during startup delay: log info and exit cleanly
  - Add `if __name__ == "__main__"` entry point
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 8.2, 8.3, 8.5_

  - [x]* 3.1 Write property test for connectivity retry logic (Property 4)
    - File: `tests/test_startup_manager_properties.py`
    - **Property 4: Startup manager retries connectivity up to 5 times**
    - Use `@given(st.integers(min_value=0, max_value=5))` to simulate N failures then a success (or N=5 all failures)
    - Assert attempt count equals `min(N+1, 5)` and exit behaviour matches spec (proceed on success, exit non-zero on all-fail)
    - Tag: `# Feature: windows-autostart-server, Property 4`
    - **Validates: Requirements 2.2, 2.3**

  - [x]* 3.2 Write property test for readiness polling timeout (Property 5)
    - File: `tests/test_startup_manager_properties.py`
    - **Property 5: Readiness polling respects the 60-second timeout**
    - Use `@given(st.integers(min_value=0, max_value=12))` to simulate success at poll index K
    - Assert logged elapsed time ≈ K × 5 seconds and no polls occur beyond index 12
    - Tag: `# Feature: windows-autostart-server, Property 5`
    - **Validates: Requirements 2.5, 2.6**

  - [x]* 3.3 Write unit tests for startup_manager
    - File: `tests/test_startup_manager.py`
    - Test that `start_watchdog` spawns process with `DETACHED_PROCESS` flag (mock `subprocess.Popen`)
    - Test that `main` exits non-zero when all 5 connectivity checks fail (mock `wait_for_internet` to return `False`)
    - Test that `main` logs elapsed time on successful health confirmation (mock `wait_for_health` to return `True`)
    - Test that `main` logs timeout warning and does NOT kill watchdog on health timeout (mock `wait_for_health` to return `False`)
    - _Requirements: 2.3, 2.4, 2.6, 2.7_

- [x] 4. Checkpoint — verify startup_manager tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Create convenience batch files
  - Create `start_server.bat` in the project root: use `start "TradingBot" /B` to launch `startup_manager.py` via the venv python executable in a background window
  - Create `stop_server.bat` in the project root: echo a stopping message, use `taskkill /F /IM python.exe` with appropriate filters to terminate project python processes, echo a confirmation listing terminated processes
  - Create `restart_server.bat` in the project root: call `stop_server.bat`, wait 3 seconds via `timeout /t 3 /nobreak`, then call `start_server.bat`
  - All batch files use `@echo off` at the top
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 6. Create ssh_tunnel.bat — persistent SSH reverse tunnel
  - Create `ssh_tunnel.bat` in the project root
  - Define variables at the top: `VPS_USER`, `VPS_HOST`, `VPS_PORT`, `TUNNEL_PORT` (2222), `LOCAL_PORT` (8001), `KEY_FILE` (`%USERPROFILE%\.ssh\id_rsa`)
  - Implement `:loop` label with `ssh -N -R %TUNNEL_PORT%:localhost:%LOCAL_PORT%` command
  - Include SSH options: `-o ServerAliveInterval=30`, `-o ServerAliveCountMax=3`, `-o ExitOnForwardFailure=yes`
  - Include `-i "%KEY_FILE%"` and `-p %VPS_PORT% %VPS_USER%@%VPS_HOST%`
  - After SSH exits: echo reconnect message, `timeout /t 10 /nobreak >nul`, `goto :loop`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 7. Create install_tasks.bat — Windows Task Scheduler registration
  - Create `install_tasks.bat` in the project root
  - Implement default (install) mode: register `TradingBotServer` task via `schtasks /create /F /TN TradingBotServer /TR "..." /SC ONLOGON /RL HIGHEST`; register `TradingBotSSHTunnel` task similarly
  - Use `/F` flag on `schtasks /create` to overwrite existing tasks
  - Implement sub-command dispatch: parse `%1` for `enable`, `disable`, `remove` and apply to `%2` (task name) via `schtasks /change` or `schtasks /delete`
  - Echo confirmation message including task name and trigger type after each successful registration
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [x] 8. Create setup_autologin.bat — Windows registry auto-login
  - Create `setup_autologin.bat` in the project root
  - Validate that both `%~1` (username) and `%~2` (password) are provided; if either is missing, echo usage instructions and `exit /b 1`
  - Write `AutoAdminLogon=1`, `DefaultUserName=%~1`, `DefaultPassword=%~2` to `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon` using `reg add ... /f`
  - Echo confirmation message with the configured username (not the password)
  - Echo instruction to reboot to verify
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 9. Create nginx_bot.conf — VPS Nginx reverse proxy snippet
  - Create `nginx_bot.conf` in the project root
  - Write a `location /bot/` block with `proxy_pass http://localhost:2222/`
  - Include all required headers: `proxy_set_header Host $host`, `proxy_set_header X-Real-IP $remote_addr`, `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`
  - Set `proxy_read_timeout 300s`
  - Add a comment at the top explaining this is a snippet to include inside an existing `server {}` block on the VPS
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 10. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The venv Python executable path is `.ci_probe_0306/Scripts/python.exe` relative to the project root
- The bot is launched as `python -m bot.main --api` (module mode, not direct file path)
- All batch files use `@echo off` and Windows-native commands only
- Property tests use Hypothesis with minimum 100 iterations each
- Each property test file includes a comment tag referencing the design property number
- `setup_autologin.bat` uses `%~1`/`%~2` (tilde-dequoted) to safely handle passwords with spaces
