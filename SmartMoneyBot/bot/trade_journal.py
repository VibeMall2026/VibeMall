"""
Trade Journal — persists trade detail data to a JSON file.

Stores entry reason, initial SL/TP, SL trail log, exit reason, etc.
Survives bot restarts unlike in-memory signal_log.

File: bot/sessions/trade_journal.json
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

_JOURNAL_PATH = Path(__file__).parent / "sessions" / "trade_journal.json"
_lock = threading.Lock()
_journal: dict[str, dict] = {}  # key: str(ticket)


def _load() -> None:
    """Load journal from disk on startup."""
    global _journal
    try:
        if _JOURNAL_PATH.exists():
            with open(_JOURNAL_PATH, "r", encoding="utf-8") as f:
                _journal = json.load(f)
            logger.info(f"[JOURNAL] Loaded {len(_journal)} trade records from disk")
    except Exception as exc:
        logger.warning(f"[JOURNAL] Could not load journal: {exc}")
        _journal = {}


def _save() -> None:
    """Save journal to disk."""
    try:
        _JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_JOURNAL_PATH, "w", encoding="utf-8") as f:
            json.dump(_journal, f, indent=2, default=str)
    except Exception as exc:
        logger.warning(f"[JOURNAL] Could not save journal: {exc}")


def record_trade_open(
    ticket: int,
    symbol: str,
    side: str,
    entry_price: float,
    initial_sl: float,
    initial_tp: float,
    one_r: float,
    risk_reward: float,
    entry_reason: str,
    source: str,
    strategy: str = "",
) -> None:
    """Record a new trade opening."""
    key = str(ticket)
    with _lock:
        _journal[key] = {
            "ticket": ticket,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "initial_sl": initial_sl,
            "initial_tp": initial_tp,
            "one_r": one_r,
            "risk_reward": risk_reward,
            "entry_reason": entry_reason,
            "source": source,
            "strategy": strategy,
            "opened_at": datetime.now().isoformat(),
            "sl_trail_log": [],
            "exit_reason": None,
            "exit_price": None,
            "final_pnl": None,
            "closed_at": None,
        }
        _save()
    logger.debug(f"[JOURNAL] Recorded trade open: ticket={ticket} {symbol} {side}")


def record_sl_trail(ticket: int, old_sl: float, new_sl: float, stage: str) -> None:
    """Record an SL trail event."""
    key = str(ticket)
    with _lock:
        if key not in _journal:
            return
        _journal[key]["sl_trail_log"].append({
            "time": datetime.now().isoformat(),
            "old_sl": old_sl,
            "new_sl": new_sl,
            "stage": stage,
        })
        _save()
    logger.debug(f"[JOURNAL] SL trail: ticket={ticket} {old_sl} → {new_sl} ({stage})")


def record_trade_close(
    ticket: int,
    exit_price: float,
    final_pnl: float,
    exit_reason: str,
) -> None:
    """Record trade close."""
    key = str(ticket)
    with _lock:
        if key not in _journal:
            # Create minimal record if not found
            _journal[key] = {
                "ticket": ticket,
                "exit_reason": exit_reason,
                "exit_price": exit_price,
                "final_pnl": final_pnl,
                "closed_at": datetime.now().isoformat(),
                "sl_trail_log": [],
            }
        else:
            _journal[key]["exit_reason"] = exit_reason
            _journal[key]["exit_price"] = exit_price
            _journal[key]["final_pnl"] = final_pnl
            _journal[key]["closed_at"] = datetime.now().isoformat()
        _save()
    logger.debug(f"[JOURNAL] Recorded trade close: ticket={ticket} pnl={final_pnl}")


def get_trade(ticket: int) -> Optional[dict]:
    """Get trade detail by ticket."""
    with _lock:
        return _journal.get(str(ticket))


def get_all_trades() -> list[dict]:
    """Get all journal entries sorted by opened_at desc."""
    with _lock:
        trades = list(_journal.values())
    trades.sort(key=lambda t: t.get("opened_at", ""), reverse=True)
    return trades


def enrich_trade(trade: dict) -> dict:
    """Enrich a trade dict with journal data if available."""
    ticket = trade.get("ticket") or trade.get("position_id")
    if not ticket:
        return trade
    journal_entry = get_trade(int(ticket))
    if not journal_entry:
        return trade
    # Merge journal data into trade dict
    enriched = dict(trade)
    enriched["entry_reason"] = journal_entry.get("entry_reason") or trade.get("entry_reason")
    enriched["initial_sl"] = journal_entry.get("initial_sl") or trade.get("sl")
    enriched["initial_tp"] = journal_entry.get("initial_tp") or trade.get("tp")
    enriched["one_r"] = journal_entry.get("one_r") or trade.get("one_r")
    enriched["risk_reward"] = journal_entry.get("risk_reward") or trade.get("risk_reward")
    enriched["sl_trail_log"] = journal_entry.get("sl_trail_log", [])
    enriched["exit_reason"] = journal_entry.get("exit_reason") or trade.get("exit_reason")
    enriched["exit_price"] = journal_entry.get("exit_price") or trade.get("exit_price")
    enriched["final_pnl"] = journal_entry.get("final_pnl") or trade.get("pnl")
    enriched["strategy"] = journal_entry.get("strategy", "")
    enriched["source"] = journal_entry.get("source") or trade.get("source", "")
    return enriched


# Load on import
_load()
