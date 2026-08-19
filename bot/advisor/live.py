"""Mode-switching orchestrator for the dashboard's single polling endpoint.

Decides Mode 1 (an algo trade is open) vs Mode 2 (no trade open, scanning
the market) by checking bot/advisor/monitor.py's tracked-position state, and
returns one unified JSON shape either way. Also detects and logs the
transition the first time each call sees the mode change, per the user's
"AUTO MODE SWITCHING RULES" (clear old data, show a switch notification, log
switch time and reason).
"""
from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from bot.advisor import monitor as advisor_monitor

_last_mode: int | None = None
_last_switch_at: str | None = None
_last_switch_reason: str | None = None
_switch_pending_display: bool = False


def _note_switch(new_mode: int, reason: str) -> bool:
    """Returns True exactly once, on the first call after the mode changed."""
    global _last_mode, _last_switch_at, _last_switch_reason, _switch_pending_display
    just_switched = False
    if _last_mode is not None and _last_mode != new_mode:
        _last_switch_at = datetime.now(timezone.utc).isoformat()
        _last_switch_reason = reason
        _switch_pending_display = True
        logger.info(f"[ADVISOR_LIVE] Mode switch: {_last_mode} -> {new_mode} ({reason})")
    _last_mode = new_mode
    if _switch_pending_display:
        just_switched = True
        _switch_pending_display = False
    return just_switched


def get_live_state() -> dict:
    """Single endpoint the dashboard polls. Returns whichever mode is
    currently active, plus switch metadata so the UI can show a banner."""
    has_trade = advisor_monitor.has_open_trade()

    if has_trade:
        result = advisor_monitor.get_active_trade_result()
        if result is None:
            # Trade just registered, first full analysis hasn't landed yet.
            return {
                "mode": 1, "status": "warming_up",
                "message": "Trade detected — running first analysis...",
                "switched": False, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        switched = _note_switch(1, "Algo opened a trade")
        result["status"] = "ok"
        result["switched"] = switched
        result["last_switch_at_utc"] = _last_switch_at
        result["last_switch_reason"] = _last_switch_reason
        return result

    result = advisor_monitor.get_scanner_result()
    if result is None:
        _note_switch(2, "No open trade — scanning market")
        return {
            "mode": 2, "status": "warming_up",
            "message": "Scanning market — first scan in progress...",
            "switched": False, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    switched = _note_switch(2, "No open trade — scanning market")
    result["status"] = "ok"
    result["switched"] = switched
    result["last_switch_at_utc"] = _last_switch_at
    result["last_switch_reason"] = _last_switch_reason
    return result
