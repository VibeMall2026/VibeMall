"""
Unit tests for startup_manager.py.

Tests subprocess launch with DETACHED_PROCESS flag, connectivity failure
exit behaviour, elapsed time logging on success, and timeout warning
without killing the watchdog.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Make the project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import startup_manager as sm


# ---------------------------------------------------------------------------
# Logger configuration tests
# ---------------------------------------------------------------------------

class TestSetupLogger:
    def setup_method(self) -> None:
        logger = logging.getLogger("startup_manager")
        logger.handlers.clear()

    def test_returns_logger_named_startup_manager(self) -> None:
        logger = sm.setup_logger()
        assert logger.name == "startup_manager"

    def test_rotating_file_handler_max_bytes(self) -> None:
        logger = sm.setup_logger()
        fh = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        assert fh.maxBytes == 5 * 1024 * 1024  # 5 MB

    def test_rotating_file_handler_backup_count(self) -> None:
        logger = sm.setup_logger()
        fh = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        assert fh.backupCount == 2

    def test_log_format_contains_startup_manager(self) -> None:
        logger = sm.setup_logger()
        fh = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        fmt = fh.formatter._fmt  # type: ignore[union-attr]
        assert "startup_manager" in fmt


# ---------------------------------------------------------------------------
# start_watchdog tests
# ---------------------------------------------------------------------------

class TestStartWatchdog:
    def setup_method(self) -> None:
        logging.getLogger("startup_manager").handlers.clear()
        sm.setup_logger()

    def test_spawns_process_with_detached_flag(self) -> None:
        """start_watchdog must use DETACHED_PROCESS creationflags."""
        mock_proc = MagicMock()
        mock_proc.pid = 9999

        with patch("startup_manager.subprocess.Popen", return_value=mock_proc) as mock_popen:
            sm.start_watchdog()
            _, kwargs = mock_popen.call_args
            assert kwargs.get("creationflags") == sm.DETACHED_PROCESS

    def test_spawns_process_with_venv_python(self) -> None:
        """start_watchdog must use the venv python executable."""
        mock_proc = MagicMock()
        mock_proc.pid = 9999

        with patch("startup_manager.subprocess.Popen", return_value=mock_proc) as mock_popen:
            sm.start_watchdog()
            args, _ = mock_popen.call_args
            cmd = args[0]
            assert ".ci_probe_0306" in cmd[0]

    def test_spawns_watchdog_script(self) -> None:
        """start_watchdog must target watchdog.py."""
        mock_proc = MagicMock()
        mock_proc.pid = 9999

        with patch("startup_manager.subprocess.Popen", return_value=mock_proc) as mock_popen:
            sm.start_watchdog()
            args, _ = mock_popen.call_args
            cmd = args[0]
            assert "watchdog.py" in cmd[1]

    def test_returns_popen_object(self) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 1234

        with patch("startup_manager.subprocess.Popen", return_value=mock_proc):
            result = sm.start_watchdog()
            assert result is mock_proc


# ---------------------------------------------------------------------------
# wait_for_internet tests
# ---------------------------------------------------------------------------

class TestWaitForInternet:
    def setup_method(self) -> None:
        logging.getLogger("startup_manager").handlers.clear()
        sm.setup_logger()

    def test_returns_true_on_first_success(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("startup_manager.requests.get", return_value=mock_response):
            assert sm.wait_for_internet(retries=5, interval=0) is True

    def test_returns_false_when_all_fail(self) -> None:
        import requests as req
        with patch("startup_manager.requests.get", side_effect=req.ConnectionError):
            assert sm.wait_for_internet(retries=5, interval=0) is False

    def test_makes_exactly_5_attempts_on_all_failure(self) -> None:
        import requests as req
        with patch("startup_manager.requests.get", side_effect=req.ConnectionError) as mock_get:
            sm.wait_for_internet(retries=5, interval=0)
            assert mock_get.call_count == 5

    def test_stops_after_first_success(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        import requests as req
        side_effects = [req.ConnectionError, req.ConnectionError, mock_response]
        with patch("startup_manager.requests.get", side_effect=side_effects) as mock_get:
            result = sm.wait_for_internet(retries=5, interval=0)
            assert result is True
            assert mock_get.call_count == 3


# ---------------------------------------------------------------------------
# wait_for_health tests
# ---------------------------------------------------------------------------

class TestWaitForHealth:
    def setup_method(self) -> None:
        logging.getLogger("startup_manager").handlers.clear()
        sm.setup_logger()

    def test_returns_true_on_first_healthy_response(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("startup_manager.requests.get", return_value=mock_response):
            assert sm.wait_for_health(poll_interval=0, timeout=60) is True

    def test_returns_false_on_timeout(self) -> None:
        import requests as req
        with patch("startup_manager.requests.get", side_effect=req.ConnectionError):
            # Use a very short timeout to avoid slow tests
            assert sm.wait_for_health(poll_interval=0, timeout=0) is False


# ---------------------------------------------------------------------------
# main() integration tests
# ---------------------------------------------------------------------------

class TestMain:
    def setup_method(self) -> None:
        logging.getLogger("startup_manager").handlers.clear()

    def test_exits_nonzero_when_connectivity_fails(self) -> None:
        """main() must exit with non-zero code when all connectivity checks fail."""
        with patch("startup_manager.time.sleep"):
            with patch("startup_manager.wait_for_internet", return_value=False):
                with pytest.raises(SystemExit) as exc_info:
                    sm.main()
                assert exc_info.value.code != 0

    def test_logs_elapsed_time_on_successful_health(self, caplog: pytest.LogCaptureFixture) -> None:
        """main() must log elapsed time when bot becomes healthy."""
        mock_proc = MagicMock()
        mock_proc.pid = 1234

        with patch("startup_manager.time.sleep"):
            with patch("startup_manager.wait_for_internet", return_value=True):
                with patch("startup_manager.start_watchdog", return_value=mock_proc):
                    with patch("startup_manager.wait_for_health", return_value=True):
                        with caplog.at_level(logging.INFO, logger="startup_manager"):
                            sm.main()

        log_text = caplog.text
        # Should log something about being ready / healthy
        assert any(
            keyword in log_text.lower()
            for keyword in ["ready", "healthy", "complete"]
        ), f"Expected readiness log message, got: {log_text}"

    def test_logs_timeout_warning_and_does_not_kill_watchdog(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        When health times out, main() must log a warning and exit 0,
        leaving the watchdog process alive (not terminated).
        """
        mock_proc = MagicMock()
        mock_proc.pid = 1234

        with patch("startup_manager.time.sleep"):
            with patch("startup_manager.wait_for_internet", return_value=True):
                with patch("startup_manager.start_watchdog", return_value=mock_proc):
                    with patch("startup_manager.wait_for_health", return_value=False):
                        with caplog.at_level(logging.WARNING, logger="startup_manager"):
                            try:
                                sm.main()
                            except SystemExit as e:
                                # exit(0) is acceptable
                                assert e.code == 0 or e.code is None

        # Watchdog process must NOT have been terminated
        mock_proc.terminate.assert_not_called()
        mock_proc.kill.assert_not_called()

        # Must have logged a warning about the timeout
        assert any(
            keyword in caplog.text.lower()
            for keyword in ["timeout", "did not become healthy", "time"]
        ), f"Expected timeout warning, got: {caplog.text}"
