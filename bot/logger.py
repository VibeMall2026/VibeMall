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
    default_log_file = log_dir / "bot.log"
    instance_log_file = Path(os.getenv("BOT_LOG_FILE", str(default_log_file)))
    shared_log_file_raw = os.getenv("BOT_SHARED_LOG_FILE", "").strip()
    shared_log_file = Path(shared_log_file_raw) if shared_log_file_raw else None

    instance_log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(instance_log_file),
        level=config.LOG_LEVEL,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    )

    if shared_log_file:
        shared_log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(shared_log_file),
            level=config.LOG_LEVEL,
            rotation="25 MB",
            retention="14 days",
            compression="zip",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        )

    if getattr(config, "TG_ALGO_ERROR_ALERTS_ENABLED", True):
        logger.add(
            _send_algo_error_alert_from_log,
            level="ERROR",
            filter=_is_algo_runtime_error,
            enqueue=True,
        )


setup_logger()
