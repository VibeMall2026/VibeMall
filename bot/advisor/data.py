"""Live XAUUSD candle data for the advisor - reuses the same MT5 connection
the trading bot already keeps open, no separate data feed needed."""
from __future__ import annotations

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

from bot import mt5_bridge

SYMBOL = "XAUUSD"


def get_candles(timeframe_min: int = 15, count: int = 250) -> list[dict] | None:
    """Live OHLC candles, oldest first. None if MT5 isn't connected right now."""
    if not MT5_AVAILABLE or not mt5_bridge.ensure_connected():
        return None

    tf_map = {1: mt5.TIMEFRAME_M1, 5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15,
              30: mt5.TIMEFRAME_M30, 60: mt5.TIMEFRAME_H1, 240: mt5.TIMEFRAME_H4}
    tf = tf_map.get(timeframe_min, mt5.TIMEFRAME_M15)

    try:
        info = mt5.symbol_info(SYMBOL)
        if info is not None and not info.visible:
            mt5.symbol_select(SYMBOL, True)
    except Exception:
        pass

    rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, count)
    if rates is None or len(rates) == 0:
        return None

    return [
        {
            "time": int(r["time"]), "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
            "tick_volume": float(r["tick_volume"]),
        }
        for r in rates
    ]


def get_live_price() -> float | None:
    if not MT5_AVAILABLE or not mt5_bridge.ensure_connected():
        return None
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return None
    return float((tick.bid + tick.ask) / 2.0)
