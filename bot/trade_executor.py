"""
Trade executor — takes a parsed signal, checks risk, and sends to MT5.

On Ubuntu VPS: calls Windows MT5 Bridge via HTTP (MT5_BRIDGE_URL in .env).
On Windows PC: calls mt5_bridge directly.
"""
import os
import asyncio
from datetime import datetime
from loguru import logger

from bot import config
from bot.state import state
from bot.signal_parser import ParsedSignal
from bot import mt5_bridge
from bot.risk_manager import can_trade

# Windows MT5 Bridge URL — set this in bot/.env on VPS
# e.g. MT5_BRIDGE_URL=http://YOUR_WINDOWS_PC_IP:8001
MT5_BRIDGE_URL = os.environ.get("MT5_BRIDGE_URL", "").rstrip("/")


async def _execute_via_bridge(sig: ParsedSignal, channel: str) -> dict:
    """Call Windows MT5 Bridge HTTP API to execute trade."""
    import httpx
    tp = sig.tp[0] if sig.tp else 0.0
    payload = {
        "symbol": sig.symbol,
        "side": sig.side,
        "sl": sig.sl,
        "tp": tp,
        "entry": sig.entry,
        "comment": f"VPS:{channel}",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{MT5_BRIDGE_URL}/trade", json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


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

    # Use Windows bridge if configured, else direct MT5
    if MT5_BRIDGE_URL:
        logger.info(f"Executing via Windows MT5 Bridge: {MT5_BRIDGE_URL}")
        result = await _execute_via_bridge(sig, channel)
    else:
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
