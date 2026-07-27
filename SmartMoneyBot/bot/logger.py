"""Centralised logging using loguru."""
import os
import sys
from pathlib import Path

from loguru import logger

from bot import config


def _is_algo_runtime_error(record: dict) -> bool:
    name = str(record.get("name") or "")
    if not name.startswith("bot.algo"):
        return False
    message = str(record.get("message") or "")
    execution_failures = (
        "Trade failed",
        "Signal not executed",
        "Trade blocked",
    )
    return not any(marker in message for marker in execution_failures)


def _send_algo_error_alert_from_log(message) -> None:
    try:
        record = message.record
        reason = f"{record.get('name')}:{record.get('line')} - {record.get('message')}"
        from bot.telegram_notifier import send_algo_error_alert

        send_algo_error_alert(
            account_label=os.getenv("MT5_ACCOUNT_LABEL", "").strip() or "N/A",
            login=os.getenv("MT5_LOGIN", "").strip() or None,
            strategy_id=os.getenv("MT5_PRIMARY_STRATEGY", "").strip() or None,
            reason=reason,
            severity=str(record.get("level").name if record.get("level") else "ERROR"),
        )
    except Exception:
        pass


def _is_windows() -> bool:
    return os.name == "nt"


def _build_file_sink_kwargs(level: str, rotation: str | None, retention: str | None, compression: str | None) -> dict:
    kwargs = {
        "level": level,
        "format": "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        "enqueue": True,
        "backtrace": False,
        "diagnose": False,
    }
    if rotation:
        kwargs["rotation"] = rotation
    if retention:
        kwargs["retention"] = retention
    if compression:
        kwargs["compression"] = compression
    return kwargs


def setup_logger() -> None:
    # Force UTF-8 console output on Windows to avoid UnicodeEncodeError.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    logger.remove()
    use_colors = bool(getattr(sys.stdout, "isatty", lambda: False)())
    logger.add(
        sys.stdout,
        level=config.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=use_colors,
    )

    # Always write logs to project-root /logs/bot.log (not current working dir),
    # otherwise running from /bot can create missing-folder issues.
    root_dir = Path(__file__).resolve().parents[1]
    log_dir = root_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    # On Windows, multiple bot processes can rotate the same file at once and
    # trigger WinError 32 during os.rename(). Keep the default process-local.
    default_log_name = f"bot_{os.getpid()}.log" if _is_windows() else "bot.log"
    default_log_file = log_dir / default_log_name
    instance_log_file = Path(os.getenv("BOT_LOG_FILE", str(default_log_file)))
    shared_log_file_raw = os.getenv("BOT_SHARED_LOG_FILE", "").strip()
    shared_log_file = Path(shared_log_file_raw) if shared_log_file_raw else None

    instance_log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(str(instance_log_file), **_build_file_sink_kwargs(
        level=config.LOG_LEVEL,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
    ))

    if shared_log_file:
        shared_log_file.parent.mkdir(parents=True, exist_ok=True)
        # Shared multi-process file rotation is fragile on Windows because
        # concurrent rotation uses rename() on a file another process may still
        # hold open. Keep the shared sink append-only there.
        shared_rotation = None if _is_windows() else "25 MB"
        shared_retention = None if _is_windows() else "14 days"
        shared_compression = None if _is_windows() else "zip"
        logger.add(str(shared_log_file), **_build_file_sink_kwargs(
            level=config.LOG_LEVEL,
            rotation=shared_rotation,
            retention=shared_retention,
            compression=shared_compression,
        ))

    if getattr(config, "TG_ALGO_ERROR_ALERTS_ENABLED", True):
        logger.add(
            _send_algo_error_alert_from_log,
            level="ERROR",
            filter=_is_algo_runtime_error,
            enqueue=True,
        )


setup_logger()
