"""
Volume Bubbles strategy (QuantAlgo-inspired) for MT5 bot runtime.

Notes:
- This mirrors the Pine indicator's cluster detection/classification logic.
- It is implemented as a scanner strategy (logs cluster events); no auto-order placement.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from loguru import logger

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

from bot import mt5_bridge


@dataclass
class _Cfg:
    symbol: str = "XAUUSD"
    analysis_timeframe: int = 15
    delta_timeframe: int = 1
    scan_interval_seconds: int = 10

    detect_method: str = "Volume OR Delta"  # Volume Only | Delta Only | Volume + Delta | Volume OR Delta
    classify_mode: str = "Both"             # Candle Direction | Delta Direction | Both
    consensus_mode: str = "Majority (2 of 3)"  # Any Window | Majority (2 of 3) | All Windows (strictest)

    short_len: int = 20
    mid_len: int = 50
    long_len: int = 100

    small_pct: float = 75.0
    medium_pct: float = 90.0
    big_pct: float = 97.0

    show_small: bool = True
    show_medium: bool = True
    show_big: bool = True


_cfg = _Cfg()
_running = False
_thread: Optional[threading.Thread] = None
_last_scan_at: Optional[str] = None
_last_scan_summary: dict[str, object] = {}
_last_signal_key: Optional[str] = None
_lock = threading.Lock()


def _tf_to_mt5(minutes: int):
    mp = {
        1: mt5.TIMEFRAME_M1,
        5: mt5.TIMEFRAME_M5,
        15: mt5.TIMEFRAME_M15,
        30: mt5.TIMEFRAME_M30,
        60: mt5.TIMEFRAME_H1,
        240: mt5.TIMEFRAME_H4,
        1440: mt5.TIMEFRAME_D1,
    }
    return mp.get(int(minutes), mt5.TIMEFRAME_M15)


def _fetch_candles(symbol: str, timeframe_min: int, count: int) -> list[dict]:
    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return []
    rates = mt5.copy_rates_from_pos(symbol, _tf_to_mt5(timeframe_min), 0, count)
    if rates is None or len(rates) == 0:
        return []
    out: list[dict] = []
    for r in rates:
        out.append(
            {
                "time": datetime.fromtimestamp(int(r["time"])),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["tick_volume"]),
            }
        )
    return out


def _percentile_linear(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    arr = sorted(float(v) for v in values)
    if len(arr) == 1:
        return arr[0]
    p = max(0.0, min(100.0, float(pct))) / 100.0
    idx = p * (len(arr) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(arr) - 1)
    frac = idx - lo
    return arr[lo] * (1.0 - frac) + arr[hi] * frac


def _consensus(p_short: bool, p_mid: bool, p_long: bool, mode: str) -> bool:
    hits = int(p_short) + int(p_mid) + int(p_long)
    if mode == "Any Window":
        return hits >= 1
    if mode == "All Windows (strictest)":
        return hits >= 3
    return hits >= 2


def _detect(v_hit: bool, d_hit: bool, method: str) -> bool:
    if method == "Volume Only":
        return v_hit
    if method == "Delta Only":
        return d_hit
    if method == "Volume + Delta":
        return v_hit and d_hit
    return v_hit or d_hit


def _estimate_bar_delta(symbol: str, bar_time: datetime, bar_close: datetime) -> tuple[float, bool]:
    """
    Approximate requestVolumeDelta(): sum signed lower-timeframe tick_volume by candle direction.
    """
    ltf = max(1, int(_cfg.delta_timeframe))
    bars = _fetch_candles(symbol, ltf, 500)
    if not bars:
        return 0.0, False
    d = 0.0
    found = False
    for c in bars:
        t = c["time"]
        if t < bar_time or t >= bar_close:
            continue
        found = True
        if c["close"] > c["open"]:
            d += c["volume"]
        elif c["close"] < c["open"]:
            d -= c["volume"]
    return d, found


def _scan_once() -> None:
    global _last_scan_at, _last_scan_summary, _last_signal_key

    need = max(_cfg.long_len, _cfg.mid_len, _cfg.short_len) + 5
    candles = _fetch_candles(_cfg.symbol, _cfg.analysis_timeframe, need)
    if len(candles) < need:
        _last_scan_summary = {"error": "not_enough_candles", "count": len(candles)}
        return

    cur = candles[-1]
    prev = candles[:-1]
    vols = [c["volume"] for c in prev]

    # Delta approximation for current analysis bar from lower timeframe candles.
    tf_sec = int(_cfg.analysis_timeframe) * 60
    cur_open = cur["time"]
    cur_close = datetime.fromtimestamp(int(cur_open.timestamp()) + tf_sec)
    net_delta, delta_available = _estimate_bar_delta(_cfg.symbol, cur_open, cur_close)
    abs_delta = abs(net_delta)

    def pwin(src: list[float], ln: int, pct: float) -> float:
        return _percentile_linear(src[-ln:], pct) if len(src) >= ln else _percentile_linear(src, pct)

    # Volume thresholds
    v_small_s = pwin(vols, _cfg.short_len, _cfg.small_pct)
    v_small_m = pwin(vols, _cfg.mid_len, _cfg.small_pct)
    v_small_l = pwin(vols, _cfg.long_len, _cfg.small_pct)
    v_med_s = pwin(vols, _cfg.short_len, _cfg.medium_pct)
    v_med_m = pwin(vols, _cfg.mid_len, _cfg.medium_pct)
    v_med_l = pwin(vols, _cfg.long_len, _cfg.medium_pct)
    v_big_s = pwin(vols, _cfg.short_len, _cfg.big_pct)
    v_big_m = pwin(vols, _cfg.mid_len, _cfg.big_pct)
    v_big_l = pwin(vols, _cfg.long_len, _cfg.big_pct)

    # Delta thresholds (from historical proxy deltas)
    delta_hist: list[float] = []
    for c in prev[-max(_cfg.long_len, 120):]:
        c_open = c["time"]
        c_close = datetime.fromtimestamp(int(c_open.timestamp()) + tf_sec)
        nd, ok = _estimate_bar_delta(_cfg.symbol, c_open, c_close)
        if ok:
            delta_hist.append(abs(nd))
    if not delta_hist:
        delta_hist = [0.0]

    d_small_s = pwin(delta_hist, _cfg.short_len, _cfg.small_pct)
    d_small_m = pwin(delta_hist, _cfg.mid_len, _cfg.small_pct)
    d_small_l = pwin(delta_hist, _cfg.long_len, _cfg.small_pct)
    d_med_s = pwin(delta_hist, _cfg.short_len, _cfg.medium_pct)
    d_med_m = pwin(delta_hist, _cfg.mid_len, _cfg.medium_pct)
    d_med_l = pwin(delta_hist, _cfg.long_len, _cfg.medium_pct)
    d_big_s = pwin(delta_hist, _cfg.short_len, _cfg.big_pct)
    d_big_m = pwin(delta_hist, _cfg.mid_len, _cfg.big_pct)
    d_big_l = pwin(delta_hist, _cfg.long_len, _cfg.big_pct)

    vol_big = _consensus(cur["volume"] >= v_big_s, cur["volume"] >= v_big_m, cur["volume"] >= v_big_l, _cfg.consensus_mode)
    vol_med = (not vol_big) and _consensus(cur["volume"] >= v_med_s, cur["volume"] >= v_med_m, cur["volume"] >= v_med_l, _cfg.consensus_mode)
    vol_small = (not vol_big) and (not vol_med) and _consensus(cur["volume"] >= v_small_s, cur["volume"] >= v_small_m, cur["volume"] >= v_small_l, _cfg.consensus_mode)

    delta_big = _consensus(abs_delta >= d_big_s, abs_delta >= d_big_m, abs_delta >= d_big_l, _cfg.consensus_mode)
    delta_med = (not delta_big) and _consensus(abs_delta >= d_med_s, abs_delta >= d_med_m, abs_delta >= d_med_l, _cfg.consensus_mode)
    delta_small = (not delta_big) and (not delta_med) and _consensus(abs_delta >= d_small_s, abs_delta >= d_small_m, abs_delta >= d_small_l, _cfg.consensus_mode)

    method = _cfg.detect_method if delta_available else "Volume Only"
    is_big = _detect(vol_big, delta_big, method)
    is_med = (not is_big) and _detect(vol_med or vol_big, delta_med or delta_big, method)
    is_small = (not is_big) and (not is_med) and _detect(vol_small or vol_med or vol_big, delta_small or delta_med or delta_big, method)

    candle_buy = cur["close"] >= cur["open"]
    candle_sell = cur["close"] < cur["open"]

    if _cfg.classify_mode == "Candle Direction":
        is_buy = candle_buy
        is_sell = candle_sell
    elif _cfg.classify_mode == "Delta Direction":
        is_buy = (net_delta > 0) if delta_available else candle_buy
        is_sell = (net_delta < 0) if delta_available else candle_sell
    else:
        is_buy = (candle_buy and net_delta > 0) if delta_available else candle_buy
        is_sell = (candle_sell and net_delta < 0) if delta_available else candle_sell

    visible = (_cfg.show_big and is_big) or (_cfg.show_medium and is_med) or (_cfg.show_small and is_small)
    level = "BIG" if is_big else ("MEDIUM" if is_med else ("SMALL" if is_small else "NONE"))
    side = "BUY" if is_buy else ("SELL" if is_sell else "MIXED")
    ratio = (cur["volume"] / (_percentile_linear(vols[-_cfg.mid_len:], 50) or 1.0)) if vols else 0.0

    _last_scan_at = datetime.utcnow().isoformat()
    _last_scan_summary = {
        "symbol": _cfg.symbol,
        "time": str(cur["time"]),
        "detect_method": method,
        "delta_available": delta_available,
        "volume": cur["volume"],
        "delta": net_delta,
        "ratio": ratio,
        "level": level,
        "side": side,
        "visible": visible,
    }

    if visible:
        signal_key = f"{cur['time'].isoformat()}|{level}|{side}"
        if signal_key != _last_signal_key:
            _last_signal_key = signal_key
            logger.info(
                f"[VOL_BUBBLES] {level} {side} | {_cfg.symbol} | vol={cur['volume']:.0f} "
                f"| delta={net_delta:.0f} | ratio={ratio:.2f}x | method={method}"
            )


def _loop() -> None:
    global _running
    logger.info(f"[VOL_BUBBLES] Started | symbol={_cfg.symbol} tf={_cfg.analysis_timeframe}m")
    while _running:
        try:
            if mt5_bridge.ensure_connected():
                _scan_once()
        except Exception as exc:
            logger.error(f"[VOL_BUBBLES] Loop error: {exc}")
        time.sleep(max(2, int(_cfg.scan_interval_seconds)))
    logger.info("[VOL_BUBBLES] Stopped.")


def start_algo() -> bool:
    global _running, _thread
    if _running:
        return True
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True, name="VolumeBubblesAlgo")
    _thread.start()
    return True


def stop_algo() -> None:
    global _running
    _running = False


def get_algo_status() -> dict:
    with _lock:
        return {
            "running": _running,
            "config": {
                "symbol": _cfg.symbol,
                "analysis_timeframe": _cfg.analysis_timeframe,
                "delta_timeframe": _cfg.delta_timeframe,
                "detect_method": _cfg.detect_method,
                "classify_mode": _cfg.classify_mode,
                "consensus_mode": _cfg.consensus_mode,
            },
            "last_scan_at": _last_scan_at,
            "last_scan_summary": dict(_last_scan_summary),
        }

