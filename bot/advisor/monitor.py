"""Background engine for the XAUUSD Trade Intelligence System.

Two things run continuously here, independent of whether anyone has the
dashboard open:

  Mode 1 (a trade is open) - re-checks every tracked algo position, updates
  the live price/PnL/SL-TP numbers on a fast cadence, and redoes the full
  candle-based health check on a slower, connection-safe cadence. Sends a
  Telegram alert the moment the exit decision turns risky.

  Mode 2 (no trade open) - scans the market for a BUY/SELL setup on a
  connection-safe cadence and alerts when a high-quality opportunity appears.

Connection safety: MT5's Python API holds one connection per process, shared
with the live trading logic in bot/accounts.py. Nothing here polls anywhere
near "every second" against MT5 itself - see FAST_TICK_SECONDS vs
FULL_RECOMPUTE_SECONDS below. The dashboard can still poll the API every
second; it's just reading the latest cached result, which is cheap.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from loguru import logger

# How often the background loop wakes up to at least refresh the live price
# (cheap: a single tick read, no candle fetch).
FAST_TICK_SECONDS = 3
# How often a full candle-based recompute (indicators, health score, exit
# decision / market scan) actually runs - this is the number that matters
# for MT5 connection load.
FULL_RECOMPUTE_SECONDS = 20
MODE2_SCAN_SECONDS = 15

ALERT_COOLDOWN_SECONDS = 10 * 60
EMERGENCY_ALERT_COOLDOWN_SECONDS = 2 * 60

_tracked: dict[int, dict] = {}
_tracked_lock = threading.Lock()
_mode2_state: dict = {}
_started = False


def register_open_trade(*, ticket: int, login: int, direction: str, entry: float, sl: float | None, tp: float | None) -> None:
    """Called by bot.accounts right after an algo trade opens successfully."""
    from bot.advisor import data as advisor_data
    from bot.advisor import health_score as hs

    entry_snapshot = None
    try:
        candles = advisor_data.get_candles(timeframe_min=15, count=250)
        if candles:
            entry_snapshot = hs.analyze_entry(candles, direction, entry)
    except Exception:
        logger.exception("[ADVISOR_MONITOR] Could not snapshot entry quality")

    with _tracked_lock:
        _tracked[int(ticket)] = {
            "login": int(login), "direction": direction.lower(), "entry": float(entry),
            "sl": float(sl) if sl else None, "tp": float(tp) if tp else None,
            "peak_price": float(entry),
            "entry_snapshot": entry_snapshot,
            "last_alert_ts": 0.0, "last_decision": None,
            "last_full_compute_ts": 0.0, "last_result": None,
            "tp_alert_70_sent": False, "tp_alert_90_sent": False,
        }
    logger.info(f"[ADVISOR_MONITOR] Now tracking ticket={ticket} login={login} direction={direction}")


def get_active_trade_result() -> dict | None:
    """Returns the latest cached Mode 1 result for the first tracked
    position, or None if nothing is open. Used by the API endpoint."""
    with _tracked_lock:
        for ticket, pos in _tracked.items():
            if pos.get("last_result"):
                result = dict(pos["last_result"])
                result["ticket"] = ticket
                return result
    return None


def get_scanner_result() -> dict | None:
    return _mode2_state.get("last_result")


def has_open_trade() -> bool:
    with _tracked_lock:
        return len(_tracked) > 0


def _untrack(ticket: int, reason: str) -> None:
    with _tracked_lock:
        _tracked.pop(ticket, None)
    logger.info(f"[ADVISOR_MONITOR] Stopped tracking ticket={ticket} ({reason})")


def _refresh_one(ticket: int, pos: dict) -> None:
    import MetaTrader5 as mt5

    from bot import accounts as accounts_module
    from bot.advisor import data as advisor_data
    from bot.advisor import health_score as hs

    lock = accounts_module.get_mt5_lock()
    now_monotonic = time.monotonic()
    do_full = (now_monotonic - pos.get("last_full_compute_ts", 0.0)) >= FULL_RECOMPUTE_SECONDS or pos.get("last_result") is None

    with lock:
        if not accounts_module.connect_account_by_login(pos["login"]):
            return

        live_positions = mt5.positions_get(ticket=ticket)
        if not live_positions:
            _untrack(ticket, "position closed")
            return

        current_price = advisor_data.get_live_price()
        if current_price is None:
            return

        result = None
        if do_full:
            candles = advisor_data.get_candles(timeframe_min=15, count=250)
            if candles:
                try:
                    result = hs.analyze_active_trade(
                        candles=candles, direction=pos["direction"], entry=pos["entry"],
                        current_price=current_price, stop_loss=pos["sl"], target=pos["tp"],
                        peak_price=pos.get("peak_price"), entry_snapshot=pos.get("entry_snapshot"),
                    )
                except Exception:
                    logger.exception(f"[ADVISOR_MONITOR] Full analysis failed for ticket={ticket}")

    if result is not None:
        with _tracked_lock:
            if ticket not in _tracked:
                return
            _tracked[ticket]["last_result"] = result
            _tracked[ticket]["peak_price"] = result["peak_price"]
            _tracked[ticket]["last_full_compute_ts"] = now_monotonic
        pos = _tracked[ticket]
    elif pos.get("last_result"):
        # Fast path: just refresh the price-dependent numbers between full
        # recomputes, using the cached indicator/momentum snapshot.
        from bot.advisor import health_score as hs
        cached = pos["last_result"]
        sl_r = hs.analyze_sl(pos["direction"], pos["entry"], pos["sl"], current_price)
        tp_r = hs.analyze_tp(pos["direction"], pos["entry"], pos["tp"], current_price)
        pnl_r = hs.pnl_tracker(pos["direction"], pos["entry"], current_price, pos.get("peak_price"))
        merged = dict(cached)
        merged["trade"] = {**cached["trade"], "current_price": current_price}
        merged["sl_analysis"], merged["tp_analysis"], merged["pnl"] = sl_r, tp_r, pnl_r
        merged["peak_price"] = pnl_r["peak_price"]
        # Safety override: if price is suddenly critical on SL, don't wait
        # for the next full recompute to reflect it.
        if sl_r.get("available") and sl_r["status"] == "CRITICAL" and cached["decision"]["decision"] != "EMERGENCY_EXIT":
            merged["decision"] = {
                "decision": "EMERGENCY_EXIT", "icon": "🚨", "label": "EMERGENCY EXIT — CLOSE IMMEDIATELY",
                "confidence": 10, "message": "Price within 10% of stop-loss — close now",
                "reasons": ["Price within 10% of stop-loss (live price update)"], "telegram": "urgent", "sound": True,
            }
        with _tracked_lock:
            if ticket not in _tracked:
                return
            _tracked[ticket]["last_result"] = merged
            _tracked[ticket]["peak_price"] = pnl_r["peak_price"]
        pos = _tracked[ticket]
        result = merged
    else:
        return

    _maybe_alert_mode1(ticket, pos, result)


def _maybe_alert_mode1(ticket: int, pos: dict, result: dict) -> None:
    from bot.telegram_notifier import send_mode1_alert

    decision = result["decision"]["decision"]
    now = time.monotonic()

    with _tracked_lock:
        entry = _tracked.get(ticket)
        if entry is None:
            return
        cooldown = EMERGENCY_ALERT_COOLDOWN_SECONDS if decision == "EMERGENCY_EXIT" else ALERT_COOLDOWN_SECONDS
        cooled_down = (now - entry["last_alert_ts"]) >= cooldown
        escalated = entry["last_decision"] not in ("EMERGENCY_EXIT", "EXIT_NOW") and decision in ("EMERGENCY_EXIT", "EXIT_NOW")
        should_alert = decision in ("EMERGENCY_EXIT", "EXIT_NOW") and (cooled_down or escalated)

        tp = result.get("tp_analysis") or {}
        tp_alert = None
        if tp.get("available"):
            if tp["pct_captured"] >= 90 and not entry["tp_alert_90_sent"]:
                tp_alert = "full"
                entry["tp_alert_90_sent"] = True
            elif tp["pct_captured"] >= 70 and not entry["tp_alert_70_sent"]:
                tp_alert = "partial"
                entry["tp_alert_70_sent"] = True

        if should_alert:
            entry["last_alert_ts"] = now
        entry["last_decision"] = decision

    if should_alert:
        try:
            send_mode1_alert(result)
        except Exception:
            logger.exception(f"[ADVISOR_MONITOR] Failed to send Mode 1 alert for ticket={ticket}")
    if tp_alert:
        try:
            send_mode1_alert(result, tp_note=tp_alert)
        except Exception:
            logger.exception(f"[ADVISOR_MONITOR] Failed to send TP alert for ticket={ticket}")


def _run_mode2_scan() -> None:
    """Keeps scanning and caching the result for the dashboard even when no
    trade is open. Does NOT send Telegram alerts - those only fire for real
    trades (Mode 1, tracked via register_open_trade after an actual algo
    execution). A "here's a setup" scan hit is not a trade, so it stays
    on-screen only, per explicit user instruction."""
    from bot import accounts as accounts_module
    from bot.advisor import data as advisor_data
    from bot.advisor import scanner as advisor_scanner

    lock = accounts_module.get_mt5_lock()
    with lock:
        candles = advisor_data.get_candles(timeframe_min=15, count=250)

    if not candles:
        return

    try:
        result = advisor_scanner.scan_market(candles)
    except Exception:
        logger.exception("[ADVISOR_MONITOR] Mode 2 scan failed")
        return

    _mode2_state["last_result"] = result


def _loop() -> None:
    logger.info(
        f"[ADVISOR_MONITOR] Started | fast tick={FAST_TICK_SECONDS}s | "
        f"full recompute={FULL_RECOMPUTE_SECONDS}s | mode2 scan={MODE2_SCAN_SECONDS}s"
    )
    last_mode2_scan = 0.0
    while True:
        time.sleep(FAST_TICK_SECONDS)
        try:
            with _tracked_lock:
                snapshot = list(_tracked.items())

            if snapshot:
                for ticket, pos in snapshot:
                    try:
                        _refresh_one(ticket, pos)
                    except Exception:
                        logger.exception(f"[ADVISOR_MONITOR] Unexpected error checking ticket={ticket}")
            else:
                now = time.monotonic()
                if (now - last_mode2_scan) >= MODE2_SCAN_SECONDS:
                    last_mode2_scan = now
                    try:
                        _run_mode2_scan()
                    except Exception:
                        logger.exception("[ADVISOR_MONITOR] Mode 2 scan cycle failed")
        except Exception:
            logger.exception("[ADVISOR_MONITOR] Top-level loop error")


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, daemon=True, name="AdvisorMonitor").start()
