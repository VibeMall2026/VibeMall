"""
Unit tests for watchdog.py.

Tests subprocess launch arguments, kill_port behaviour, logger configuration,
and check_health return values.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make the project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import watchdog as wd


# ---------------------------------------------------------------------------
# Logger configuration tests
# ---------------------------------------------------------------------------

class TestSetupLogger:
    def setup_method(self) -> None:
        """Remove any existing handlers before each test."""
        logger = logging.getLogger("watchdog")
        logger.handlers.clear()

    def test_returns_logger_named_watchdog(self) -> None:
        logger = wd.setup_logger()
        assert logger.name == "watchdog"

    def test_rotating_file_handler_present(self) -> None:
        logger = wd.setup_logger()
        file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1

    def test_rotating_file_handler_max_bytes(self) -> None:
        logger = wd.setup_logger()
        fh = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        assert fh.maxBytes == 10 * 1024 * 1024  # 10 MB

    def test_rotating_file_handler_backup_count(self) -> None:
        logger = wd.setup_logger()
        fh = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        assert fh.backupCount == 3

    def test_log_format_contains_required_fields(self) -> None:
        logger = wd.setup_logger()
        fh = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        fmt = fh.formatter._fmt  # type: ignore[union-attr]
        assert "UTC" in fmt
        assert "watchdog" in fmt
        assert "%(levelname)s" in fmt
        assert "%(message)s" in fmt

    def test_idempotent_when_called_twice(self) -> None:
        logger1 = wd.setup_logger()
        handler_count = len(logger1.handlers)
        logger2 = wd.setup_logger()
        assert len(logger2.handlers) == handler_count


# ---------------------------------------------------------------------------
# check_health tests
# ---------------------------------------------------------------------------

class TestCheckHealth:
    def test_returns_true_on_200(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("watchdog.requests.get", return_value=mock_response):
            assert wd.check_health("http://localhost:8001/health") is True

    def test_returns_true_on_201(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 201
        with patch("watchdog.requests.get", return_value=mock_response):
            assert wd.check_health("http://localhost:8001/health") is True

    def test_returns_false_on_500(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch("watchdog.requests.get", return_value=mock_response):
            assert wd.check_health("http://localhost:8001/health") is False

    def test_returns_false_on_404(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch("watchdog.requests.get", return_value=mock_response):
            assert wd.check_health("http://localhost:8001/health") is False

    def test_returns_false_on_timeout(self) -> None:
        import requests as req
        with patch("watchdog.requests.get", side_effect=req.Timeout):
            assert wd.check_health("http://localhost:8001/health") is False

    def test_returns_false_on_connection_error(self) -> None:
        import requests as req
        with patch("watchdog.requests.get", side_effect=req.ConnectionError):
            assert wd.check_health("http://localhost:8001/health") is False


# ---------------------------------------------------------------------------
# kill_port tests
# ---------------------------------------------------------------------------

class TestKillPort:
    def test_calls_netstat_to_find_pid(self) -> None:
        """kill_port should run netstat -ano to discover listening PIDs."""
        netstat_output = (
            "  TCP    0.0.0.0:8001           0.0.0.0:0              LISTENING       1234\n"
        )
        mock_result = MagicMock()
        mock_result.stdout = netstat_output

        with patch("watchdog.subprocess.run", return_value=mock_result) as mock_run:
            wd.kill_port(8001)
            # First call should be netstat
            first_call_args = mock_run.call_args_list[0][0][0]
            assert "netstat" in first_call_args

    def test_calls_taskkill_with_found_pid(self) -> None:
        """kill_port should call taskkill /F /PID <pid> for each found PID."""
        netstat_output = (
            "  TCP    0.0.0.0:8001           0.0.0.0:0              LISTENING       5678\n"
        )
        mock_result = MagicMock()
        mock_result.stdout = netstat_output

        with patch("watchdog.subprocess.run", return_value=mock_result) as mock_run:
            wd.kill_port(8001)
            # Find the taskkill call
            taskkill_calls = [
                c for c in mock_run.call_args_list
                if "taskkill" in c[0][0]
            ]
            assert len(taskkill_calls) >= 1
            taskkill_args = taskkill_calls[0][0][0]
            assert "5678" in taskkill_args

    def test_does_not_raise_when_no_process_on_port(self) -> None:
        """kill_port should not raise if no process is listening on the port."""
        mock_result = MagicMock()
        mock_result.stdout = "  TCP    0.0.0.0:9999    0.0.0.0:0    LISTENING    9999\n"

        with patch("watchdog.subprocess.run", return_value=mock_result):
            # Should not raise
            wd.kill_port(8001)

    def test_does_not_raise_on_subprocess_exception(self) -> None:
        """kill_port should swallow exceptions and log them as DEBUG."""
        with patch("watchdog.subprocess.run", side_effect=OSError("netstat not found")):
            # Should not raise
            wd.kill_port(8001)


# ---------------------------------------------------------------------------
# Bot launch argument tests
# ---------------------------------------------------------------------------

class TestBotLaunchArguments:
    def test_bot_module_uses_venv_python(self) -> None:
        """BOT_MODULE must use the venv python executable."""
        assert ".ci_probe_0306" in wd.BOT_MODULE[0]
        assert "python" in wd.BOT_MODULE[0].lower()

    def test_bot_module_uses_module_flag(self) -> None:
        """BOT_MODULE must include -m flag for module execution."""
        assert "-m" in wd.BOT_MODULE

    def test_bot_module_targets_bot_main(self) -> None:
        """BOT_MODULE must target bot.main."""
        assert "bot.main" in wd.BOT_MODULE

    def test_bot_module_includes_api_flag(self) -> None:
        """BOT_MODULE must include --api flag."""
        assert "--api" in wd.BOT_MODULE
