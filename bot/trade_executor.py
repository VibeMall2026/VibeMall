"""
Trade executor — takes a parsed signal, checks risk, and sends to MT5.
"""
import asyncio
from datetime import datetime
from loguru import logger

from bot import config
from bot.state import state
from bot.signal_parser import ParsedSignal
from bot import mt5_bridge
from bot.risk_manager import can_trade


# Track last trade time per symbol for duplicate/min-seconds check
_last_trade_time: dict[str, datetime] = {}


async def execute_signal(sig: ParsedSignal, channel: str = "") -> dict:
    """
    Execute a parsed signal. Returns result dict.
    """
    if not sig.valid:
        return {"success": False, "reason": sig.reason}

    symbol = sig.symbol
    side = sig.side

    # ── Duplicate window check ────────────────────────────────────────────────
    if state.duplicate_window_minutes > 0 and symbol in _last_trade_time:
        elapsed = (datetime.now() - _last_trade_time[symbol]).total_seconds() / 60
        if elapsed < state.duplicate_window_minutes:
            reason = f"Duplicate signal for {symbol} within {state.duplicate_window_minutes}min window"
            logger.warning(reason)
            _update_signal_log(symbol, "rejected", reason)
            return {"success": False, "reason": reason}

    # ── Min seconds between trades ────────────────────────────────────────────
    if state.min_seconds_between_trades > 0 and symbol in _last_trade_time:
        elapsed_sec = (datetime.now() - _last_trade_time[symbol]).total_seconds()
        if elapsed_sec < state.min_seconds_between_trades:
            reason = f"Too soon after last trade ({elapsed_sec:.0f}s < {state.min_seconds_between_trades}s)"
            logger.warning(reason)
            _update_signal_log(symbol, "rejected", reason)
            return {"success": False, "reason": reason}

    # ── Risk checks ───────────────────────────────────────────────────────────
    allowed, reason = can_trade(symbol)
    if not allowed:
        logger.warning(f"Trade blocked by risk manager: {reason}")
        _update_signal_log(symbol, "blocked", reason)
        return {"success": False, "reason": reason}

    # ── Execute on MT5 ────────────────────────────────────────────────────────
    tp = sig.tp[0] if sig.tp else 0.0
    comment = f"TG:{channel}"

    result = mt5_bridge.open_trade(
        symbol=symbol,
        side=side,
        sl=sig.sl,
        tp=tp,
        entry=sig.entry,
        comment=comment,
    )

    if result.get("success"):
        _last_trade_time[symbol] = datetime.now()
        _update_signal_log(symbol, "executed", "Trade opened successfully")
        logger.success(f"Trade executed: {symbol} {side.upper()} ticket={result.get('ticket')}")
    else:
        _update_signal_log(symbol, "failed", result.get("message", "Unknown error"))
        logger.error(f"Trade failed: {result.get('message')}")

    return result


def _update_signal_log(symbol: str, status: str, reason: str) -> None:
    """Update the most recent signal log entry for this symbol."""
    for entry in state.signal_log:
        if entry.get("symbol") == symbol and entry.get("status") in ("pending", ""):
            entry["status"] = status
            entry["reason"] = reason
            break
