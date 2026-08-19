"""Real-time risk monitor for algo-opened XAUUSD trades.

When bot.accounts.execute_on_all_accounts() opens an algo trade, it calls
register_open_trade() (right next to where it already sends the normal
execution alert). This module then re-runs the 12-indicator advisor
against that specific position every ~30 seconds and sends a Telegram
alert the moment it turns risky.

Connection safety: MT5's Python API only holds one live connection per
process, and the main bot already cycles through 4 accounts for its own
trading. This monitor does NOT run its own independent connection loop -
it shares bot.accounts.get_mt5_lock() with everything else, and only ever
connects to accounts that actually have a tracked open position (not all
4 blindly), keeping its footprint small and serialized with real trading
activity instead of competing with it.
"""
from __future__ import annotations

import threading
import time

from loguru import logger

CHECK_INTERVAL_SECONDS = 30
ALERT_COOLDOWN_SECONDS = 10 * 60  # don't re-alert the same position more than once per 10 min
RISK_CONFIDENCE_THRESHOLD = 50.0

_tracked: dict[int, dict] = {}
_tracked_lock = threading.Lock()
_started = False


def register_open_trade(*, ticket: int, login: int, direction: str, entry: float, sl: float | None, tp: float | None) -> None:
    """Called by bot.accounts right after an algo trade opens successfully."""
    with _tracked_lock:
        _tracked[int(ticket)] = {
            "login": int(login),
            "direction": direction.lower(),
            "entry": float(entry),
            "sl": float(sl) if sl else None,
            "tp": float(tp) if tp else None,
            "last_alert_ts": 0.0,
            "last_decision": None,
        }
    logger.info(f"[ADVISOR_MONITOR] Now tracking ticket={ticket} login={login} direction={direction}")


def _untrack(ticket: int, reason: str) -> None:
    with _tracked_lock:
        _tracked.pop(ticket, None)
    logger.info(f"[ADVISOR_MONITOR] Stopped tracking ticket={ticket} ({reason})")


def _check_one(ticket: int, pos: dict) -> None:
    import MetaTrader5 as mt5

    from bot import accounts as accounts_module
    from bot.advisor import data as advisor_data
    from bot.advisor import scoring as advisor_scoring

    lock = accounts_module.get_mt5_lock()
    with lock:
        if not accounts_module.connect_account_by_login(pos["login"]):
            logger.debug(f"[ADVISOR_MONITOR] Could not connect login={pos['login']} this cycle; will retry")
            return

        live_positions = mt5.positions_get(ticket=ticket)
        if not live_positions:
            _untrack(ticket, "position closed")
            return

        candles = advisor_data.get_candles(timeframe_min=15, count=250)
        if not candles:
            logger.debug(f"[ADVISOR_MONITOR] No candle data this cycle for ticket={ticket}")
            return
        current_price = advisor_data.get_live_price()
        if current_price is None:
            current_price = candles[-1]["close"]

        try:
            result = advisor_scoring.analyze_trade(
                candles=candles,
                direction=pos["direction"],
                entry=pos["entry"],
                current_price=current_price,
                stop_loss=pos["sl"],
                target=pos["tp"],
            )
        except Exception:
            logger.exception(f"[ADVISOR_MONITOR] analyze_trade failed for ticket={ticket}")
            return

    is_risky = result["decision"] == "CLOSE" or result["confidence_pct"] < RISK_CONFIDENCE_THRESHOLD
    if not is_risky:
        with _tracked_lock:
            if ticket in _tracked:
                _tracked[ticket]["last_decision"] = result["decision"]
        return

    now = time.monotonic()
    with _tracked_lock:
        entry = _tracked.get(ticket)
        if entry is None:
            return
        cooled_down = (now - entry["last_alert_ts"]) >= ALERT_COOLDOWN_SECONDS
        escalated = entry["last_decision"] != "CLOSE" and result["decision"] == "CLOSE"
        should_alert = cooled_down or escalated
        if should_alert:
            entry["last_alert_ts"] = now
        entry["last_decision"] = result["decision"]

    if should_alert:
        from bot.telegram_notifier import send_advisor_alert
        try:
            send_advisor_alert(result)
            logger.info(
                f"[ADVISOR_MONITOR] Alert sent | ticket={ticket} decision={result['decision']} "
                f"confidence={result['confidence_pct']}%"
            )
        except Exception:
            logger.exception(f"[ADVISOR_MONITOR] Failed to send alert for ticket={ticket}")


def _loop() -> None:
    logger.info(f"[ADVISOR_MONITOR] Started ({CHECK_INTERVAL_SECONDS}s interval)")
    while True:
        time.sleep(CHECK_INTERVAL_SECONDS)
        with _tracked_lock:
            snapshot = list(_tracked.items())
        for ticket, pos in snapshot:
            try:
                _check_one(ticket, pos)
            except Exception:
                logger.exception(f"[ADVISOR_MONITOR] Unexpected error checking ticket={ticket}")


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, daemon=True, name="AdvisorMonitor").start()
