"""
Main entry point for the Trading Bot.

Usage:
  python -m bot.main          # Start bot + API server
  python -m bot.main --api    # Start API server only (no Telegram)
"""
import asyncio
import os
import subprocess
import sys
import threading
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uvicorn
from loguru import logger

# Ensure loguru is configured (console + logs/bot.log).
# Without importing bot.logger, loguru may keep default handlers and file logs won't be created.
import bot.logger  # noqa: F401

from bot import config
from bot.state import state
from bot import mt5_bridge
from bot.api_server import app


def _should_terminate_port_owner(pid: str) -> bool:
    if not pid or not pid.isdigit():
        return False
    if int(pid) == os.getpid():
        return False
    if os.name != "nt":
        return True
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\"; if ($p) {{ $p.CommandLine }}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        cmdline = (proc.stdout or "").strip().lower()
        if not cmdline:
            return False
        return ("-m bot.main" in cmdline) or ("uvicorn" in cmdline and "bot.api_server:app" in cmdline)
    except Exception:
        return False


def start_api_server() -> None:
    """Run FastAPI in a background thread."""
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level=config.LOG_LEVEL.lower(),
    )


def _mt5_reconnect_loop() -> None:
    """
    Background thread that monitors MT5 connection and auto-reconnects.
    Uses account_info() as health check (safer than terminal_info() cross-thread).
    """
    import time
    monitor_interval_seconds = max(1, int(getattr(config, "MT5_RECONNECT_MONITOR_SECONDS", 5) or 5))
    hb_every_seconds = max(1, int(getattr(config, "MT5_HEARTBEAT_SECONDS", 5) or 5))
    logger.info(f"[MT5] Auto-reconnect monitor started ({monitor_interval_seconds}s interval)")
    last_hb_ts = 0.0
    consecutive_misses = 0
    while True:
        try:
            # Use non-reconnecting account peek as health check so the monitor
            # itself does not trigger duplicate reconnect attempts.
            account = mt5_bridge.get_account_info(attempt_reconnect=False)
            if account and account.get("balance") is not None:
                # Connected and returning data
                if not state.mt5_connected:
                    logger.success("[MT5] Connection confirmed - marking online")
                state.mt5_connected = True
                try:
                    from bot.accounts import sync_account_runtime

                    sync_account_runtime(
                        login=int(account.get("login") or 0),
                        connected=True,
                        balance=account.get("balance"),
                        equity=account.get("equity"),
                        currency=account.get("currency"),
                    )
                except Exception:
                    pass
            else:
                # No data - try reconnect, but don't spam logs while backoff is active.
                try:
                    from bot.accounts import get_accounts_runtime_status

                    statuses = get_accounts_runtime_status()
                    any_trade_allowed = any(
                        s.get("enabled") and s.get("trade_allowed")
                        for s in statuses
                    )
                except Exception:
                    any_trade_allowed = True

                if not any_trade_allowed:
                    logger.debug("[MT5] Trading is halted; skipping MT5 reconnect until schedule resumes.")
                    try:
                        from bot import config as _cfg
                        from bot.accounts import sync_account_runtime

                        sync_account_runtime(
                            login=int(getattr(_cfg, "MT5_LOGIN", 0) or 0),
                            connected=False,
                            error="",
                        )
                    except Exception:
                        pass
                    state.mt5_connected = False
                    consecutive_misses = 0
                else:
                    consecutive_misses += 1
                    if mt5_bridge.reconnect_backoff_active():
                        logger.debug("[MT5] Reconnect backoff active; waiting before retry...")
                    else:
                        logger.warning("[MT5] No account data - attempting reconnect...")
                    if mt5_bridge.ensure_connected():
                        consecutive_misses = 0
                        state.mt5_connected = True
                        logger.success("[MT5] Reconnected successfully.")
                    else:
                        if consecutive_misses >= 3:
                            logger.error("[MT5] Reconnect failed - keeping last known online state")
                            try:
                                from bot import config as _cfg
                                from bot.accounts import sync_account_runtime

                                sync_account_runtime(
                                    login=int(getattr(_cfg, "MT5_LOGIN", 0) or 0),
                                    connected=True,
                                    error="mt5_disconnected",
                                )
                            except Exception:
                                pass
                        else:
                            logger.debug(
                                f"[MT5] Reconnect miss {consecutive_misses}/3; keeping last known connection state"
                            )

            # Per-account heartbeat for clear ON/OFF visibility in logs.
            now_ts = time.monotonic()
            if (now_ts - last_hb_ts) >= hb_every_seconds:
                try:
                    from bot.accounts import get_accounts_runtime_status

                    statuses = get_accounts_runtime_status()
                    enabled_count = sum(1 for s in statuses if s.get("enabled"))
                    connected_count = sum(1 for s in statuses if s.get("enabled") and s.get("connected"))
                    parts = []
                    for s in statuses:
                        mode = "HALT" if (s.get("enabled") and not s.get("trade_allowed")) else "RUN"
                        conn = "ON" if s.get("connected") else "OFF"
                        reason = s.get("halt_reason") or s.get("error") or ""
                        if reason:
                            parts.append(f"{s['label']}({s['login']}):{conn}/{mode}:{reason}")
                        else:
                            parts.append(f"{s['label']}({s['login']}):{conn}/{mode}")
                    logger.info(
                        f"[HEARTBEAT] Accounts {connected_count}/{enabled_count} connected | "
                        + " | ".join(parts)
                    )
                except Exception as hb_exc:
                    logger.warning(f"[HEARTBEAT] status log failed: {hb_exc}")
                last_hb_ts = now_ts
        except Exception as e:
            logger.error(f"[MT5] Reconnect monitor error: {e}")
        time.sleep(monitor_interval_seconds)


def _daily_schedule_loop() -> None:
    """
    Auto start/stop the bot around the IST trading window and send a summary.
    Morning: start at/after 09:00 IST once per day.
    Night: stop at/after 22:00 IST once per day.
    """
    import time

    ist = ZoneInfo("Asia/Kolkata")
    last_sent: dict[str, str] = {"morning": "", "night": ""}

    logger.info("[SCHEDULE] Auto start/stop scheduler started (IST 09:00/22:00)")
    while True:
        try:
            now_ist = datetime.now(timezone.utc).astimezone(ist)
            today = now_ist.date().isoformat()

            if 9 <= now_ist.hour < 10:
                if last_sent.get("morning") != today:
                    last_sent["morning"] = today
                    from bot.algo.runner import start_all_strategies

                    # Called unconditionally. state.running is a bot-wide flag
                    # and says nothing about whether the strategy threads are
                    # alive: on 29 Jul it was True while every strategy had been
                    # stopped by the night halt, so this branch logged "already
                    # running", started nothing, and the account sat idle for
                    # the whole session. start_all_strategies skips whatever is
                    # genuinely running, so it is the only honest check.
                    state.running = True
                    started = start_all_strategies()
                    logger.info(f"[SCHEDULE] Morning auto-start | strategies={started or 'none new'}")

                    from bot.telegram_listener import build_schedule_notice_text
                    from bot.telegram_notifier import send_text_alert

                    send_text_alert(build_schedule_notice_text("start"))

            if now_ist.hour >= 22:
                if last_sent.get("night") != today:
                    last_sent["night"] = today
                    from bot.algo.runner import stop_all_strategies

                    # Unconditional for the same reason as the morning branch:
                    # a stale state.running of False would otherwise leave live
                    # strategies scanning right through the night.
                    state.running = False
                    stop_all_strategies()
                    logger.info("[SCHEDULE] Night auto-stop")

                    from bot.telegram_listener import build_schedule_notice_text
                    from bot.telegram_notifier import send_text_alert

                    send_text_alert(build_schedule_notice_text("stop"))
        except Exception as exc:
            logger.warning(f"[SCHEDULE] Auto start/stop loop error: {exc}")

        time.sleep(60)


async def start_bot() -> None:
    """Connect MT5 and start Telegram listener."""
    try:
        from bot.accounts import get_accounts_runtime_status, refresh_account_info

        statuses = get_accounts_runtime_status()
        any_trade_allowed = any(
            s.get("enabled") and s.get("trade_allowed")
            for s in statuses
        )
    except Exception:
        any_trade_allowed = True

    # During the night window we keep every account OFF and avoid bringing MT5
    # up at startup so the dashboard stays aligned with the trade gate.
    if not any_trade_allowed:
        logger.info("Night window active - starting without MT5 connection.")
        state.mt5_connected = False
        try:
            mt5_bridge.disconnect()
        except Exception:
            pass
        try:
            refresh_account_info()
        except Exception as exc:
            logger.debug(f"Night refresh skipped: {exc}")
    # Connect MT5 only when trading is allowed.
    elif not mt5_bridge.is_connected():
        logger.info("Connecting to MT5...")
        if mt5_bridge.ensure_connected():
            state.mt5_connected = True
            logger.success("MT5 connected.")
        else:
            logger.warning("MT5 not connected - running without trade execution.")
    else:
        state.mt5_connected = True
        logger.info("MT5 already connected.")

    # Telegram disabled mode (keep MT5 strategies running without Telegram).
    if not config.TG_ENABLED:
        logger.warning("Telegram listener is disabled via TG_ENABLED=false.")
        state.running = True
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            state.running = False
            state.telegram_connected = False
            mt5_bridge.disconnect()
        return

    # Start Telegram listener with retry loop so the bot keeps running
    # even if Telegram auth/session is temporarily unavailable.
    logger.info("Starting Telegram listener...")
    from bot.telegram_listener import start_listener
    state.running = True
    try:
        while True:
            try:
                await start_listener()
                logger.warning(
                    "Telegram listener stopped. Retrying in %ss...",
                    config.TG_RECONNECT_DELAY,
                )
                retry_delay = max(3, int(config.TG_RECONNECT_DELAY))
            except Exception as e:
                msg = str(e)
                # Telethon FloodWait-like message:
                # "A wait of 82759 seconds is required (caused by SendCodeRequest)"
                m = re.search(r"wait of\s+(\d+)\s+seconds", msg, re.IGNORECASE)
                if m:
                    wait_s = max(30, int(m.group(1)))
                    retry_delay = wait_s + 5
                    logger.error(
                        "Telegram listener flood-wait detected. Sleeping %ss before retry.",
                        retry_delay,
                    )
                else:
                    retry_delay = max(3, int(config.TG_RECONNECT_DELAY))
                    logger.error(f"Telegram listener error: {e}")
            state.telegram_connected = False
            await asyncio.sleep(retry_delay)
    finally:
        state.running = False
        state.telegram_connected = False
        mt5_bridge.disconnect()


def main() -> None:
    api_only = "--api" in sys.argv

    logger.info("=" * 60)
    logger.info("  Trading Bot Starting")
    logger.info(f"  API: http://{config.API_HOST}:{config.API_PORT}")
    if config.MT5_LOGIN > 0 and config.MT5_PASSWORD and config.MT5_SERVER:
        logger.info(f"  MT5 Login: {config.MT5_LOGIN} @ {config.MT5_SERVER}")
    else:
        logger.info("  MT5 Login: none (using account registry only)")
    logger.info(f"  Channels: {', '.join(config.TG_CHANNELS) or 'none'}")
    logger.info(f"  Execution Alerts: {config.TG_EXECUTION_ALERT_CHAT or config.ADMIN_CHAT_ID or 'disabled'}")
    logger.info("=" * 60)

    # Kill any process holding the port before starting
    import time
    try:
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if f":{config.API_PORT}" in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if _should_terminate_port_owner(pid):
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                    logger.info(f"Freed port {config.API_PORT} (killed PID {pid})")
                    time.sleep(2)  # Wait longer for OS to release the port
    except Exception:
        pass

    # Initialize state channels from config
    from bot.state import state as _state
    if not _state.channels:
        _state.channels = list(config.TG_CHANNELS)

    # Start API server in background thread
    api_thread = threading.Thread(target=start_api_server, daemon=True, name="APIServer")
    api_thread.start()
    time.sleep(1)  # Give uvicorn time to bind before proceeding
    logger.info(f"API server started on port {config.API_PORT}")

    if api_only:
        logger.info("Running in API-only mode (no strategies, no Telegram listener).")
        api_thread.join()
        return

    # Mark the bot running BEFORE the strategy threads start.
    #
    # Strategy threads scan immediately on start, but execute_on_all_accounts()
    # rejects algo trades while state.running is False. state.running was only
    # set once start_bot() reached its Telegram loop below, so a signal landing
    # in that gap was dropped with "Algo execution blocked: bot is stopped".
    # start_bot() sets the same flag, so this only closes the window - the
    # night window is enforced per-account via trade_allowed, not this flag.
    _state.running = True

    # Start ALL algo strategies assigned to accounts (parallel execution)
    from bot.algo.runner import start_all_strategies
    started = start_all_strategies()
    logger.info(f"[RUNNER] Started strategies: {started}")

    # Start MT5 auto-reconnect monitor
    reconnect_thread = threading.Thread(
        target=_mt5_reconnect_loop, daemon=True, name="MT5ReconnectMonitor"
    )
    reconnect_thread.start()

    schedule_thread = threading.Thread(
        target=_daily_schedule_loop, daemon=True, name="ISTScheduleManager"
    )
    schedule_thread.start()

    # Run bot (blocking)
    asyncio.run(start_bot())


if __name__ == "__main__":
    main()
