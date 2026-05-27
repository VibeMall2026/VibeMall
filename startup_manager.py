"""
startup_manager.py — Boot sequence orchestrator for the trading bot.

Waits for Windows services to settle, verifies internet connectivity,
spawns watchdog.py as a detached background process, then confirms the
bot API is healthy before exiting.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).parent.resolve()
PYTHON_EXE: Path = Path(r"C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe")
WATCHDOG_SCRIPT: Path = PROJECT_ROOT / "watchdog.py"

STARTUP_DELAY: int = 60          # seconds to wait after login before doing anything
MAX_RETRIES: int = 5
RETRY_INTERVAL: int = 10         # seconds between connectivity retries
HEALTH_URL: str = "http://localhost:8001/health"
HEALTH_POLL_INTERVAL: int = 5    # seconds between readiness polls
HEALTH_TIMEOUT_SECS: int = 60    # max seconds to wait for bot to become healthy

LOG_FILE: Path = PROJECT_ROOT / "startup_manager.log"
LOG_MAX_BYTES: int = 5 * 1024 * 1024   # 5 MB
LOG_BACKUP_COUNT: int = 2

# Windows process creation flag — start process detached from the current console
DETACHED_PROCESS: int = 0x00000008
VISIBLE_MODE: bool = str(os.environ.get("WATCHDOG_VISIBLE", "0")).lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------

def setup_logger() -> logging.Logger:
    """Configure a rotating-file logger for the startup_manager component."""
    logger = logging.getLogger("startup_manager")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger  # already configured (e.g. during tests)

    formatter = logging.Formatter(
        fmt="%(asctime)s UTC | startup_manager | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        filename=str(LOG_FILE),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_internet(
    retries: int = MAX_RETRIES,
    interval: int = RETRY_INTERVAL,
) -> bool:
    """
    Attempt a direct TCP connect up to *retries* times.

    We avoid DNS/SSL checks here because they can hang on some boot sequences.
    Returns True on the first successful socket connection, False otherwise.
    """
    logger = logging.getLogger("startup_manager")
    for attempt in range(1, retries + 1):
        try:
            with socket.create_connection(("1.1.1.1", 53), timeout=5):
                logger.info("Internet connectivity confirmed on attempt %d/%d", attempt, retries)
                return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Connectivity check %d/%d failed: %s",
                attempt,
                retries,
                exc,
            )
        if attempt < retries:
            time.sleep(interval)

    logger.error(
        "Internet connectivity not confirmed after %d attempts",
        retries,
    )
    return False


def start_watchdog() -> subprocess.Popen:
    """
    Spawn watchdog.py as a detached background process.

    Uses DETACHED_PROCESS on Windows so the watchdog survives after
    startup_manager exits.
    """
    logger = logging.getLogger("startup_manager")
    cmd = [str(PYTHON_EXE), "-u", str(WATCHDOG_SCRIPT)]
    logger.info("Starting watchdog: %s", " ".join(cmd))
    if VISIBLE_MODE:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            close_fds=True,
        )
    else:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            creationflags=DETACHED_PROCESS,
            close_fds=True,
        )
    logger.info("Watchdog started with PID %d", proc.pid)
    return proc


def wait_for_health(
    url: str = HEALTH_URL,
    poll_interval: int = HEALTH_POLL_INTERVAL,
    timeout: int = HEALTH_TIMEOUT_SECS,
) -> bool:
    """
    Poll *url* every *poll_interval* seconds for up to *timeout* seconds.

    Returns True on the first 2xx response, False if the timeout is reached.
    """
    logger = logging.getLogger("startup_manager")
    deadline = time.monotonic() + timeout
    poll_index = 0

    while time.monotonic() < deadline:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code < 300:
                elapsed = poll_index * poll_interval
                logger.info(
                    "Bot API is ready (elapsed ~%d s)",
                    elapsed,
                )
                return True
        except Exception:  # noqa: BLE001
            pass

        poll_index += 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(poll_interval, remaining))

    return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logger = setup_logger()
    logger.info("Startup manager beginning. Waiting %d s for Windows services…", STARTUP_DELAY)

    try:
        time.sleep(STARTUP_DELAY)
    except KeyboardInterrupt:
        logger.info("Startup manager interrupted during initial delay — exiting cleanly")
        sys.exit(0)

    logger.info("Checking internet connectivity…")
    if not wait_for_internet():
        logger.error("Cannot reach internet. Aborting startup.")
        sys.exit(1)

    logger.info("Spawning watchdog…")
    try:
        start_watchdog()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to start watchdog: %s — aborting", exc)
        sys.exit(1)

    logger.info("Waiting for bot API to become healthy (up to %d s)…", HEALTH_TIMEOUT_SECS)
    if wait_for_health():
        logger.info("Startup complete — bot API is healthy.")
    else:
        logger.warning(
            "Bot did not become healthy within %d s. "
            "Watchdog is still running and will continue retrying.",
            HEALTH_TIMEOUT_SECS,
        )
        # Exit 0: watchdog is alive and will keep retrying
        sys.exit(0)


if __name__ == "__main__":
    main()
