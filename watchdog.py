"""
watchdog.py — Process monitor for the trading bot API server.

Launches bot/main.py --api via the project venv, polls GET /health every 15 s,
and restarts the process on 3 consecutive failures or unexpected exit.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).parent.resolve()
PYTHON_EXE: Path = PROJECT_ROOT / ".ci_probe_0306" / "Scripts" / "python.exe"
BOT_MODULE: list[str] = [str(PYTHON_EXE), "-m", "bot.main"]
HEALTH_URL: str = "http://localhost:8001/health"
POLL_INTERVAL: int = 15        # seconds between health checks
FAIL_THRESHOLD: int = 3        # consecutive failures before restart
HEALTH_TIMEOUT: int = 10       # seconds before a health request times out
LOG_FILE: Path = PROJECT_ROOT / "watchdog.log"
LOG_MAX_BYTES: int = 10 * 1024 * 1024   # 10 MB
LOG_BACKUP_COUNT: int = 3


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class WatchdogState:
    process: subprocess.Popen | None = None
    consecutive_failures: int = 0
    restart_count: int = 0


# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------

def setup_logger() -> logging.Logger:
    """Configure a rotating-file logger for the watchdog component."""
    logger = logging.getLogger("watchdog")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger  # already configured (e.g. during tests)

    formatter = logging.Formatter(
        fmt="%(asctime)s UTC | watchdog | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Rotating file handler
    file_handler = RotatingFileHandler(
        filename=str(LOG_FILE),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Also echo to stdout so Task Scheduler captures it
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def kill_port(port: int) -> None:
    """Terminate any process currently bound to *port* on Windows."""
    logger = logging.getLogger("watchdog")
    try:
        # Find PID(s) listening on the port
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        pids: set[str] = set()
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    pids.add(parts[-1])

        for pid in pids:
            if pid and pid != "0":
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    capture_output=True,
                    timeout=10,
                )
                logger.debug("Killed PID %s that was holding port %d", pid, port)

        if not pids:
            logger.debug("No process found holding port %d", port)

    except Exception as exc:  # noqa: BLE001
        logger.debug("kill_port(%d) encountered an error (non-fatal): %s", port, exc)


def check_health(url: str = HEALTH_URL, timeout: int = HEALTH_TIMEOUT) -> bool:
    """Return True if the health endpoint responds with a 2xx status code."""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code < 300
    except requests.Timeout:
        return False
    except requests.ConnectionError:
        return False
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Main watchdog loop
# ---------------------------------------------------------------------------

def run_watchdog() -> None:
    """Launch the bot and keep it alive indefinitely."""
    logger = setup_logger()
    state = WatchdogState()

    def _launch() -> subprocess.Popen:
        logger.info("Launching bot: %s", " ".join(BOT_MODULE))
        return subprocess.Popen(
            BOT_MODULE,
            cwd=str(PROJECT_ROOT),
        )

    def _restart(reason: str) -> None:
        state.restart_count += 1
        logger.error(
            "Restarting bot (attempt %d) — reason: %s",
            state.restart_count,
            reason,
        )
        if state.process is not None:
            try:
                state.process.terminate()
                state.process.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass
        kill_port(8001)
        state.consecutive_failures = 0
        state.process = _launch()

    def _shutdown(signum=None, frame=None) -> None:  # noqa: ANN001
        logger.info("Watchdog shutting down (signal %s)", signum)
        if state.process is not None:
            try:
                state.process.terminate()
                state.process.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)

    # Initial launch
    try:
        state.process = _launch()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to launch bot: %s — retrying in %d s", exc, POLL_INTERVAL)
        time.sleep(POLL_INTERVAL)
        try:
            state.process = _launch()
        except Exception as exc2:  # noqa: BLE001
            logger.error("Second launch attempt failed: %s — exiting", exc2)
            sys.exit(1)

    logger.info("Watchdog started. Polling %s every %d s.", HEALTH_URL, POLL_INTERVAL)

    try:
        while True:
            time.sleep(POLL_INTERVAL)

            # Check if subprocess exited unexpectedly
            if state.process is not None and state.process.poll() is not None:
                exit_code = state.process.returncode
                logger.warning("Bot process exited unexpectedly (code %d)", exit_code)
                _restart(f"subprocess exited with code {exit_code}")
                continue

            # Health check
            healthy = check_health()
            if healthy:
                if state.consecutive_failures > 0:
                    logger.info(
                        "Health check recovered after %d failure(s)",
                        state.consecutive_failures,
                    )
                state.consecutive_failures = 0
            else:
                state.consecutive_failures += 1
                logger.warning(
                    "Health check failed (attempt %d/%d)",
                    state.consecutive_failures,
                    FAIL_THRESHOLD,
                )
                if state.consecutive_failures >= FAIL_THRESHOLD:
                    _restart(f"{FAIL_THRESHOLD} consecutive health failures")

    except KeyboardInterrupt:
        _shutdown()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_watchdog()
