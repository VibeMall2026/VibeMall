# Requirements Document

## Introduction

This feature implements a Windows Local Server Auto-Start & Always-On Setup for the trading bot project. The goal is to run the Python/FastAPI bot API server (port 8001) as a 24/7 local service on a Windows PC that automatically starts on boot, self-recovers from crashes, exposes the local API to a remote Ubuntu VPS via SSH reverse tunnel, and supports a safe Friday shutdown / Monday restart workflow.

The system consists of six components: a Watchdog script, a Startup Manager script, convenience batch files, an SSH reverse tunnel script, Windows Task Scheduler installation scripts, and Windows auto-login registry configuration.

## Glossary

- **Watchdog**: Python script (`watchdog.py`) that monitors the bot API process and restarts it on failure.
- **Startup_Manager**: Python script (`startup_manager.py`) that orchestrates the full startup sequence after Windows login.
- **Bot_API**: The FastAPI application (`bot/main.py`) running on port 8001 inside the Python venv.
- **Health_Endpoint**: The HTTP endpoint `GET /health` on the Bot_API used to verify liveness.
- **SSH_Tunnel**: A persistent SSH reverse tunnel that forwards a VPS port to the local Bot_API port.
- **Task_Scheduler**: Windows Task Scheduler service used to auto-start components on user logon.
- **Venv**: The Python virtual environment located at `.ci_probe_0306/` in the project root.
- **VPS**: The remote Ubuntu server that proxies public traffic to the SSH_Tunnel endpoint.
- **Nginx**: The reverse proxy on the VPS that routes HTTP requests to the SSH_Tunnel endpoint.
- **Install_Script**: The batch file (`install_tasks.bat`) that registers tasks in Task_Scheduler.

---

## Requirements

### Requirement 1: Watchdog Process Monitor

**User Story:** As a server operator, I want the bot API to automatically restart when it crashes or becomes unhealthy, so that the trading bot remains available without manual intervention.

#### Acceptance Criteria

1. WHEN the Watchdog starts, THE Watchdog SHALL launch the Bot_API as a subprocess using the Venv Python executable.
2. WHILE the Bot_API subprocess is running, THE Watchdog SHALL poll the Health_Endpoint every 15 seconds.
3. WHEN the Health_Endpoint returns a non-2xx response or times out for 3 consecutive checks, THE Watchdog SHALL terminate the Bot_API subprocess and restart it.
4. WHEN the Bot_API subprocess exits unexpectedly, THE Watchdog SHALL detect the exit within 15 seconds and restart the subprocess.
5. BEFORE restarting the Bot_API, THE Watchdog SHALL release port 8001 by terminating any process bound to that port.
6. WHEN a restart occurs, THE Watchdog SHALL log the timestamp, failure reason, and restart attempt number to a log file.
7. THE Watchdog SHALL reset the consecutive failure counter to zero after a successful Health_Endpoint response.

---

### Requirement 2: Startup Manager Sequence

**User Story:** As a server operator, I want the server components to start automatically and in the correct order after Windows login, so that the system is fully operational without manual steps.

#### Acceptance Criteria

1. WHEN the Startup_Manager is invoked, THE Startup_Manager SHALL wait a configurable delay (default 60 seconds) before beginning the startup sequence, to allow Windows services to initialize.
2. AFTER the initial delay, THE Startup_Manager SHALL verify internet connectivity by attempting an HTTP request to a known reliable endpoint, retrying up to 5 times with 10-second intervals.
3. IF internet connectivity is not confirmed after 5 retries, THEN THE Startup_Manager SHALL log the failure and exit with a non-zero status code.
4. WHEN internet connectivity is confirmed, THE Startup_Manager SHALL start the Watchdog as a background subprocess.
5. AFTER starting the Watchdog, THE Startup_Manager SHALL poll the Health_Endpoint every 5 seconds for up to 60 seconds to confirm the Bot_API is ready.
6. WHEN the Health_Endpoint returns a 2xx response, THE Startup_Manager SHALL log a "ready" message including the elapsed startup time.
7. IF the Bot_API does not become healthy within 60 seconds, THEN THE Startup_Manager SHALL log a timeout warning and exit, leaving the Watchdog running to continue retrying.

---

### Requirement 3: Convenience Batch Files

**User Story:** As a server operator, I want simple batch file commands to manually start, stop, and restart the server, so that I can perform maintenance without memorizing complex commands.

#### Acceptance Criteria

1. WHEN `start_server.bat` is executed, THE Startup_Manager SHALL be launched in a new background window using the Venv Python executable.
2. WHEN `stop_server.bat` is executed, THE stop script SHALL terminate all `python.exe` processes associated with the project and log the stop event.
3. WHEN `restart_server.bat` is executed, THE restart script SHALL execute `stop_server.bat` followed by `start_server.bat` in sequence.
4. THE `stop_server.bat` SHALL display a confirmation message listing the processes it terminated before exiting.

---

### Requirement 4: SSH Reverse Tunnel

**User Story:** As a server operator, I want the local Bot_API to be accessible from the remote VPS, so that the trading dashboard on the VPS can communicate with the bot running on the Windows PC.

#### Acceptance Criteria

1. WHEN `ssh_tunnel.bat` is executed, THE SSH_Tunnel SHALL establish a reverse tunnel forwarding a configured VPS port to `localhost:8001`.
2. THE SSH_Tunnel SHALL use `ServerAliveInterval=30` and `ServerAliveCountMax=3` SSH options to detect dropped connections.
3. THE SSH_Tunnel SHALL use `ExitOnForwardFailure=yes` so that the SSH process exits immediately if the port forward cannot be established.
4. WHEN the SSH connection drops or exits, THE SSH_Tunnel script SHALL wait 10 seconds and then re-establish the connection automatically.
5. THE SSH_Tunnel SHALL run in an infinite reconnect loop until the script is explicitly terminated.
6. THE SSH_Tunnel SHALL use key-based authentication (no password prompt) to allow unattended reconnection.

---

### Requirement 5: Windows Task Scheduler Auto-Start

**User Story:** As a server operator, I want the server and SSH tunnel to start automatically when the Windows PC boots and a user logs in, so that no manual action is required after a power cycle.

#### Acceptance Criteria

1. WHEN `install_tasks.bat` is executed, THE Install_Script SHALL register a Task_Scheduler task named `TradingBotServer` that triggers on user logon.
2. WHEN `install_tasks.bat` is executed, THE Install_Script SHALL register a Task_Scheduler task named `TradingBotSSHTunnel` that triggers on user logon.
3. THE `TradingBotServer` task SHALL run with highest available privileges and SHALL NOT require a user to be logged in interactively to execute.
4. THE `TradingBotSSHTunnel` task SHALL run with highest available privileges and SHALL NOT require a user to be logged in interactively to execute.
5. THE Install_Script SHALL provide sub-commands to enable, disable, and remove each registered task.
6. WHEN a task is successfully registered, THE Install_Script SHALL display a confirmation message including the task name and trigger type.
7. IF a task with the same name already exists, THEN THE Install_Script SHALL overwrite it with the new configuration.

---

### Requirement 6: Windows Auto-Login Configuration

**User Story:** As a server operator, I want the Windows PC to log in automatically after a reboot, so that the Task Scheduler logon triggers fire without requiring physical keyboard input.

#### Acceptance Criteria

1. WHEN the auto-login setup script is executed, THE setup script SHALL write the `AutoAdminLogon` registry value to `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon` with value `1`.
2. WHEN the auto-login setup script is executed, THE setup script SHALL write the `DefaultUserName` registry value to the configured Windows username.
3. WHEN the auto-login setup script is executed, THE setup script SHALL write the `DefaultPassword` registry value to the configured Windows password.
4. THE setup script SHALL require the operator to supply the username and password as script parameters rather than hardcoding credentials.
5. WHEN the registry values are written successfully, THE setup script SHALL display a confirmation message and instruct the operator to reboot to verify.

---

### Requirement 7: VPS Nginx Reverse Proxy Configuration

**User Story:** As a server operator, I want the VPS Nginx to forward incoming HTTP requests to the SSH tunnel endpoint, so that the trading dashboard is reachable via the VPS public domain.

#### Acceptance Criteria

1. THE Nginx configuration SHALL include a `location` block that proxies requests to `http://localhost:<tunnel_port>`.
2. THE Nginx configuration SHALL set `proxy_pass`, `proxy_set_header Host`, `proxy_set_header X-Real-IP`, and `proxy_set_header X-Forwarded-For` headers.
3. THE Nginx configuration SHALL set `proxy_read_timeout` to 300 seconds to accommodate long-running bot API responses.
4. WHEN the Nginx configuration is applied and Nginx is reloaded, THE VPS SHALL forward requests arriving at the configured location to the SSH_Tunnel endpoint without error.

---

### Requirement 8: Logging and Observability

**User Story:** As a server operator, I want all components to write structured logs, so that I can diagnose failures and verify the system is operating correctly.

#### Acceptance Criteria

1. THE Watchdog SHALL write log entries to a file named `watchdog.log` in the project root directory.
2. THE Startup_Manager SHALL write log entries to a file named `startup_manager.log` in the project root directory.
3. WHEN any component logs an event, THE component SHALL include the UTC timestamp, component name, log level, and message in each log entry.
4. THE Watchdog SHALL rotate log files when they exceed 10 MB, retaining the 3 most recent log files.
5. THE Startup_Manager SHALL rotate log files when they exceed 5 MB, retaining the 2 most recent log files.
