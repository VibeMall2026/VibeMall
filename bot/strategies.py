"""
Strategy Registry — defines all available trading strategies.

Each strategy has:
- id: unique identifier
- name: display name
- description: short description
- status: "available" | "coming_soon"
- module: Python module path (for available strategies)

To add a new strategy:
1. Create bot/algo/<strategy_name>.py with start/stop/get_status functions
2. Add entry to STRATEGIES list below
"""
from __future__ import annotations
from typing import Optional


STRATEGIES: list[dict] = [
    {
        "id": "breakout",
        "name": "Range Breakout Retest",
        "description": "Recent range breakout with trend, ATR, volume, and retest confirmation",
        "status": "available",
        "module": "bot.algo.breakout",
    },
    {
        "id": "signal_forge",
        "name": "Signal Forge",
        "description": "Modular 11-indicator signal engine with fresh-signal entries and ATR-based exits",
        "status": "available",
        "module": "bot.algo.signal_forge",
    },
    {
        "id": "smart_money",
        "name": "Smart Money Structure",
        "description": "Pivot breakout strategy with volatility, trend, and volume confirmation",
        "status": "available",
        "module": "bot.algo.smart_money",
    },
    {
        "id": "ema_crossover",
        "name": "EMA Crossover",
        "description": "Classic EMA 9/21 crossover strategy with trend filter",
        "status": "coming_soon",
        "module": None,
    },
    {
        "id": "rsi_reversal",
        "name": "RSI Reversal",
        "description": "RSI overbought/oversold reversal with confirmation candle",
        "status": "coming_soon",
        "module": None,
    },
    {
        "id": "bollinger_breakout",
        "name": "Bollinger Band Breakout",
        "description": "Breakout strategy using Bollinger Bands with volume confirmation",
        "status": "coming_soon",
        "module": None,
    },
    {
        "id": "telegram_signals",
        "name": "Telegram Signals Only",
        "description": "Execute trades only from Telegram channel signals (no algo)",
        "status": "available",
        "module": None,  # No algo module — just signal execution
    },
]


def get_all_strategies() -> list[dict]:
    return STRATEGIES


def get_strategy(strategy_id: str) -> Optional[dict]:
    for s in STRATEGIES:
        if s["id"] == strategy_id:
            return s
    return None


def get_available_strategies() -> list[dict]:
    return [s for s in STRATEGIES if s["status"] == "available"]
