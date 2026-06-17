"""
Volume Bubbles strategy (QuantAlgo-inspired) for MT5 bot runtime.

Notes:
- This mirrors the Pine indicator's cluster detection/classification logic.
- Includes optional auto-order placement using detected clusters.
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

from bot import config as runtime_config
from bot import mt5_bridge
from bot.accounts import execute_on_all_accounts
from bot.algo.order_block import can_trade_with_reason


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
    trade_enabled: bool = True
    trade_levels: tuple[str, ...] = ("MEDIUM", "BIG")
    risk_percent: float = 0.35
    atr_period: int = 14
    sl_atr_mult: float = 1.2
    tp_rr: float = 2.0
    min_seconds_between_entries: int = 180
    partial_close_enabled: bool = runtime_config.PARTIAL_CLOSE_ENABLED
    partial_close_at_r: float = runtime_config.PARTIAL_CLOSE_TRIGGER_R
    partial_close_fraction: float = runtime_config.PARTIAL_CLOSE_FRACTION


@dataclass
class _ManagedTrade:
    ticket: int
    symbol: str
    side: str
    entry: float
    sl: float
    one_r: float
    partial_closed: bool = False


_cfg = _Cfg()
_running = False
_thread: Optional[threading.Thread] = None
_risk_thread: Optional[threading.Thread] = None
_last_scan_at: Optional[str] = None
_last_scan_summary: dict[str, object] = {}
_last_signal_key: Optional[str] = None
_last_trade_ts: float = 0.0
_managed_trades: dict[int, _ManagedTrade] = {}
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
    global _last_scan_at, _last_scan_summary, _last_signal_key, _last_trade_ts

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
            _try_execute_trade(
                symbol=_cfg.symbol,
                side=side,
                level=level,
                candles=candles,
            )


def _has_open_volume_bubble_position(symbol: str) -> bool:
    try:
        positions = mt5_bridge.get_open_positions() or []
        for p in positions:
            if str(p.get("symbol", "")).upper() != str(symbol).upper():
                continue
            c = str(p.get("comment", "") or "")
            if "ALGO:VBL:" in c:
                return True
    except Exception:
        return False
    return False


def _atr_from_candles(candles: list[dict], period: int) -> float:
    if len(candles) < max(3, period + 1):
        return 0.0
    trs: list[float] = []
    for i in range(1, len(candles)):
        h = float(candles[i]["high"])
        l = float(candles[i]["low"])
        pc = float(candles[i - 1]["close"])
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    if not trs:
        return 0.0
    window = trs[-period:] if len(trs) >= period else trs
    return sum(window) / float(len(window))


def _try_execute_trade(symbol: str, side: str, level: str, candles: list[dict]) -> None:
    global _last_trade_ts
    if not _cfg.trade_enabled:
        return
    if level not in _cfg.trade_levels:
        return
    if side not in {"BUY", "SELL"}:
        return
    now_ts = time.time()
    if now_ts - _last_trade_ts < max(5, int(_cfg.min_seconds_between_entries)):
        return
    if _has_open_volume_bubble_position(symbol):
        return

    allowed, reason = can_trade_with_reason()
    if not allowed:
        logger.info(f"[VOL_BUBBLES] Trade blocked | reason={reason}")
        return

    tick = mt5_bridge.get_current_price(symbol)
    if tick is None:
        return
    entry = float(tick)
    atr = _atr_from_candles(candles, max(5, int(_cfg.atr_period)))
    if atr <= 0:
        return
    sl_dist = atr * float(_cfg.sl_atr_mult)
    if sl_dist <= 0:
        return

    detected_side = str(side or "").upper()
    execution_side = "SELL" if detected_side == "BUY" else "BUY"

    if execution_side == "BUY":
        sl = entry - sl_dist
        tp = entry + (sl_dist * float(_cfg.tp_rr))
        s = "buy"
    else:
        sl = entry + sl_dist
        tp = entry - (sl_dist * float(_cfg.tp_rr))
        s = "sell"

    logger.info(
        f"[VOL_BUBBLES] Reverse execution active | detected={detected_side} -> execute={execution_side} | "
        f"{symbol} | level={level}"
    )

    results = execute_on_all_accounts(
        symbol=symbol,
        side=s,
        sl=sl,
        tp=tp,
        entry=entry,
        order_type="market",
        risk_percent=float(_cfg.risk_percent),
        comment=f"ALGO:VBL:{level}",
        strategy_id="volume_bubbles",
    )
    success = [r for r in results if r.get("success")]
    if success:
        _last_trade_ts = now_ts
        for r in success:
            ticket = int(r.get("ticket") or 0)
            if ticket:
                with _lock:
                    _managed_trades[ticket] = _ManagedTrade(
                        ticket=ticket,
                        symbol=symbol,
                        side=s,
                        entry=entry,
                        sl=sl,
                        one_r=abs(entry - sl),
                    )
            logger.success(
                f"[VOL_BUBBLES] Trade on {r.get('account_label')} ({r.get('login')}) "
                f"| detected={detected_side} execute={execution_side} | {symbol} | ticket={r.get('ticket')} | level={level}"
            )
    else:
        logger.warning(
            f"[VOL_BUBBLES] Signal not executed | detected={detected_side} execute={execution_side} | "
            f"{symbol} {level} | {results}"
        )


def _manage_trade(tr: _ManagedTrade, live_pos: dict) -> None:
    if not _cfg.partial_close_enabled or tr.partial_closed or tr.one_r <= 0:
        return

    current = mt5_bridge.get_current_price(tr.symbol, side=tr.side)
    if current is None:
        return

    profit_r = (current - tr.entry) / tr.one_r if tr.side == "buy" else (tr.entry - current) / tr.one_r
    if profit_r < float(_cfg.partial_close_at_r):
        return

    live_volume = float(live_pos.get("volume", 0.0) or 0.0)
    if live_volume <= 0:
        return

    try:
        from bot.algo.human_mind import execute_partial_close
        if execute_partial_close(
            tr.ticket,
            tr.symbol,
            live_volume,
            close_fraction=float(_cfg.partial_close_fraction),
        ):
            tr.partial_closed = True
            logger.info(
                f"[VOL_BUBBLES] Partial book done | ticket={tr.ticket} "
                f"at +{float(_cfg.partial_close_at_r):.2f}R "
                f"fraction={float(_cfg.partial_close_fraction):.2f}"
            )
    except Exception as exc:
        logger.warning(f"[VOL_BUBBLES] Partial book failed | ticket={tr.ticket} error={exc}")


def _risk_loop() -> None:
    while _running:
        try:
            positions = mt5_bridge.get_open_positions() or []
            positions_by_ticket = {
                int(p.get("id") or p.get("position_id") or 0): p
                for p in positions
                if int(p.get("id") or p.get("position_id") or 0)
            }

            with _lock:
                tracked = list(_managed_trades.items())

            for ticket, tr in tracked:
                live_pos = positions_by_ticket.get(int(ticket))
                if not live_pos:
                    with _lock:
                        _managed_trades.pop(int(ticket), None)
                    continue
                _manage_trade(tr, live_pos)
        except Exception as exc:
            logger.debug(f"[VOL_BUBBLES] Risk loop error: {exc}")
        time.sleep(1)


def _loop() -> None:
    global _running
    logger.info(
        f"[VOL_BUBBLES] Started | symbol={_cfg.symbol} tf={_cfg.analysis_timeframe}m "
        f"| trade_enabled={_cfg.trade_enabled} levels={list(_cfg.trade_levels)}"
    )
    while _running:
        try:
            if mt5_bridge.ensure_connected():
                _scan_once()
        except Exception as exc:
            logger.error(f"[VOL_BUBBLES] Loop error: {exc}")
        time.sleep(max(2, int(_cfg.scan_interval_seconds)))
    logger.info("[VOL_BUBBLES] Stopped.")


def start_algo() -> bool:
    global _running, _thread, _risk_thread
    if _running:
        return True
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True, name="VolumeBubblesAlgo")
    _risk_thread = threading.Thread(target=_risk_loop, daemon=True, name="VolumeBubblesRisk")
    _thread.start()
    _risk_thread.start()
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
                "partial_close_enabled": _cfg.partial_close_enabled,
                "partial_close_at_r": _cfg.partial_close_at_r,
                "partial_close_fraction": _cfg.partial_close_fraction,
            },
            "managed_trades": len(_managed_trades),
            "last_scan_at": _last_scan_at,
            "last_scan_summary": dict(_last_scan_summary),
        }
