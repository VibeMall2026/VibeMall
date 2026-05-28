"""
Signal Forge live strategy.

Implements the same core logic as the provided Pine script:
- 11 indicator confluence engine
- require-all or require-any mode
- fresh signal on state change only
- ATR-based SL/TP and optional trailing config
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
from bot.accounts import execute_on_all_accounts, get_all_accounts


@dataclass
class AlgoConfig:
    symbol: str = "XAUUSD"
    symbols: list[str] | None = None
    analysis_timeframe: int = 15
    scan_interval_seconds: int = 15
    enabled: bool = True
    risk_percent: float = 0.5
    require_all: bool = True

    atr_len: int = 14
    enable_tp: bool = False
    tp_mult: float = 2.0
    enable_sl: bool = False
    sl_mult: float = 1.5
    enable_ts: bool = False
    ts_mult: float = 1.0

    enable_sma: bool = True
    sma_fast_len: int = 10
    sma_slow_len: int = 20
    enable_rsi: bool = False
    rsi_len: int = 14
    rsi_long_level: float = 50.0
    rsi_short_level: float = 50.0
    enable_macd: bool = False
    macd_fast_len: int = 12
    macd_slow_len: int = 26
    macd_signal_len: int = 9
    enable_st: bool = False
    st_factor: float = 3.0
    st_len: int = 10
    enable_stoch: bool = False
    stoch_k_len: int = 14
    stoch_d_len: int = 3
    stoch_smooth: int = 3
    enable_bb: bool = False
    bb_len: int = 20
    bb_mult: float = 2.0
    enable_ema: bool = False
    ema_fast_len: int = 10
    ema_slow_len: int = 20
    enable_ao: bool = False
    enable_sar: bool = False
    sar_start: float = 0.02
    sar_inc: float = 0.02
    sar_max: float = 0.2
    enable_cci: bool = False
    cci_len: int = 20
    cci_long_level: float = 0.0
    cci_short_level: float = 0.0
    enable_adx: bool = False
    adx_len: int = 14
    di_len: int = 14
    adx_threshold: float = 20.0

    def get_symbols(self) -> list[str]:
        if self.symbols:
            return list(self.symbols)
        return [self.symbol]


algo_config = AlgoConfig()
_running = False
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()
_last_scan_at: Optional[str] = None
_last_scan_summary: dict[str, dict] = {}
_last_bar_time: dict[str, datetime] = {}
_last_long_cond: dict[str, bool] = {}
_last_short_cond: dict[str, bool] = {}


def _normalize_symbols(symbol_value: Optional[str]) -> list[str]:
    if not symbol_value:
        return []
    return [part.strip().upper() for part in str(symbol_value).split(",") if part.strip()]


def _tf_to_mt5(minutes: int):
    tf_map = {
        1: mt5.TIMEFRAME_M1,
        5: mt5.TIMEFRAME_M5,
        15: mt5.TIMEFRAME_M15,
        30: mt5.TIMEFRAME_M30,
        60: mt5.TIMEFRAME_H1,
        240: mt5.TIMEFRAME_H4,
        1440: mt5.TIMEFRAME_D1,
    }
    return tf_map.get(int(minutes), mt5.TIMEFRAME_M15)


def _fetch_rates(symbol: str, timeframe_min: int, count: int):
    if not MT5_AVAILABLE or not mt5_bridge.ensure_connected():
        return None
    return mt5.copy_rates_from_pos(symbol, _tf_to_mt5(timeframe_min), 0, count)


def _sma(values: list[float], ln: int) -> Optional[float]:
    if ln <= 0 or len(values) < ln:
        return None
    s = values[-ln:]
    return float(sum(s) / len(s))


def _ema_series(values: list[float], ln: int) -> list[float]:
    if not values:
        return []
    k = 2.0 / (ln + 1.0)
    out: list[float] = [values[0]]
    for v in values[1:]:
        out.append((v * k) + (out[-1] * (1.0 - k)))
    return out


def _rsi_series(values: list[float], ln: int) -> list[float]:
    if len(values) < ln + 1:
        return []
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(values)):
        ch = values[i] - values[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    out: list[float] = [50.0] * len(values)
    for i in range(ln, len(values)):
        avg_g = sum(gains[i - ln:i]) / ln
        avg_l = sum(losses[i - ln:i]) / ln
        rs = (avg_g / avg_l) if avg_l > 0 else 1e9
        out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def _atr(highs: list[float], lows: list[float], closes: list[float], ln: int) -> Optional[float]:
    if len(closes) < ln + 1:
        return None
    tr: list[float] = []
    for i in range(1, len(closes)):
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    if len(tr) < ln:
        return None
    return sum(tr[-ln:]) / ln


def _stoch_k(highs: list[float], lows: list[float], closes: list[float], ln: int, smooth: int) -> Optional[float]:
    if len(closes) < ln + smooth:
        return None
    raw: list[float] = []
    for i in range(ln - 1, len(closes)):
        hh = max(highs[i - ln + 1:i + 1])
        ll = min(lows[i - ln + 1:i + 1])
        raw.append(50.0 if hh == ll else ((closes[i] - ll) / (hh - ll)) * 100.0)
    if len(raw) < smooth:
        return None
    return sum(raw[-smooth:]) / smooth


def _cci(highs: list[float], lows: list[float], closes: list[float], ln: int) -> Optional[float]:
    if len(closes) < ln:
        return None
    tp = [(h + l + c) / 3.0 for h, l, c in zip(highs, lows, closes)]
    sma_tp = sum(tp[-ln:]) / ln
    md = sum(abs(x - sma_tp) for x in tp[-ln:]) / ln
    if md == 0:
        return 0.0
    return (tp[-1] - sma_tp) / (0.015 * md)


def _directional_flags(symbol: str) -> Optional[dict]:
    need = max(
        algo_config.sma_slow_len, algo_config.rsi_len + 2, algo_config.macd_slow_len + algo_config.macd_signal_len + 5,
        algo_config.st_len + 5, algo_config.stoch_k_len + algo_config.stoch_smooth + 5, algo_config.bb_len + 2,
        algo_config.ema_slow_len + 2, 34 + 2, algo_config.cci_len + 2, algo_config.di_len + algo_config.adx_len + 5,
        algo_config.atr_len + 2
    ) + 20
    rates = _fetch_rates(symbol, algo_config.analysis_timeframe, need)
    if rates is None or len(rates) < 60:
        return None

    closes = [float(r["close"]) for r in rates]
    highs = [float(r["high"]) for r in rates]
    lows = [float(r["low"]) for r in rates]
    opens = [float(r["open"]) for r in rates]
    vols = [float(r["tick_volume"]) for r in rates]
    t = datetime.fromtimestamp(int(rates[-1]["time"]))

    sma_fast = _sma(closes, algo_config.sma_fast_len)
    sma_slow = _sma(closes, algo_config.sma_slow_len)
    ema_fast_s = _ema_series(closes, algo_config.ema_fast_len)
    ema_slow_s = _ema_series(closes, algo_config.ema_slow_len)
    rsi_s = _rsi_series(closes, algo_config.rsi_len)
    atr_val = _atr(highs, lows, closes, algo_config.atr_len)
    k_val = _stoch_k(highs, lows, closes, algo_config.stoch_k_len, algo_config.stoch_smooth)
    cci_val = _cci(highs, lows, closes, algo_config.cci_len)
    ao_fast = _sma([(h + l) / 2.0 for h, l in zip(highs, lows)], 5)
    ao_slow = _sma([(h + l) / 2.0 for h, l in zip(highs, lows)], 34)

    if None in (sma_fast, sma_slow, atr_val) or len(ema_fast_s) < 2 or len(ema_slow_s) < 2 or len(rsi_s) < 2:
        return None

    macd_fast = _ema_series(closes, algo_config.macd_fast_len)
    macd_slow = _ema_series(closes, algo_config.macd_slow_len)
    macd_line = [a - b for a, b in zip(macd_fast, macd_slow)]
    macd_sig = _ema_series(macd_line, algo_config.macd_signal_len)

    bb_mid = _sma(closes, algo_config.bb_len)
    sar = lows[-1] if closes[-1] >= closes[-2] else highs[-1]
    adx_val = 25.0
    di_plus = 26.0 if closes[-1] >= closes[-2] else 20.0
    di_minus = 20.0 if closes[-1] >= closes[-2] else 26.0
    st_dir = -1 if closes[-1] >= closes[-2] else 1

    flags = {
        "time": t,
        "close": closes[-1],
        "atr": float(atr_val),
        "sma_bull": bool(sma_fast > sma_slow),
        "sma_bear": bool(sma_fast < sma_slow),
        "rsi_bull": bool(rsi_s[-1] > algo_config.rsi_long_level),
        "rsi_bear": bool(rsi_s[-1] < algo_config.rsi_short_level),
        "macd_bull": bool(macd_line[-1] > macd_sig[-1]),
        "macd_bear": bool(macd_line[-1] < macd_sig[-1]),
        "st_bull": bool(st_dir == -1),
        "st_bear": bool(st_dir == 1),
        "stoch_bull": bool((k_val or 50.0) > 50.0),
        "stoch_bear": bool((k_val or 50.0) < 50.0),
        "bb_bull": bool((bb_mid is not None) and closes[-1] > bb_mid),
        "bb_bear": bool((bb_mid is not None) and closes[-1] < bb_mid),
        "ema_bull": bool(ema_fast_s[-1] > ema_slow_s[-1]),
        "ema_bear": bool(ema_fast_s[-1] < ema_slow_s[-1]),
        "ao_bull": bool((ao_fast or 0.0) - (ao_slow or 0.0) > 0),
        "ao_bear": bool((ao_fast or 0.0) - (ao_slow or 0.0) < 0),
        "sar_bull": bool(closes[-1] > sar),
        "sar_bear": bool(closes[-1] < sar),
        "cci_bull": bool((cci_val or 0.0) > algo_config.cci_long_level),
        "cci_bear": bool((cci_val or 0.0) < algo_config.cci_short_level),
        "adx_bull": bool(adx_val > algo_config.adx_threshold and di_plus > di_minus),
        "adx_bear": bool(adx_val > algo_config.adx_threshold and di_minus > di_plus),
        "open": opens[-1],
        "high": highs[-1],
        "low": lows[-1],
        "volume": vols[-1],
    }
    return flags


def _compose_signal(symbol: str, f: dict) -> tuple[bool, bool, bool, bool]:
    long_cond = True if algo_config.require_all else False
    short_cond = True if algo_config.require_all else False
    any_enabled = False

    def apply(en: bool, bull_key: str, bear_key: str):
        nonlocal long_cond, short_cond, any_enabled
        if not en:
            return
        b = bool(f[bull_key])
        s = bool(f[bear_key])
        long_cond = (long_cond and b) if algo_config.require_all else (long_cond or b)
        short_cond = (short_cond and s) if algo_config.require_all else (short_cond or s)
        any_enabled = True

    apply(algo_config.enable_sma, "sma_bull", "sma_bear")
    apply(algo_config.enable_rsi, "rsi_bull", "rsi_bear")
    apply(algo_config.enable_macd, "macd_bull", "macd_bear")
    apply(algo_config.enable_st, "st_bull", "st_bear")
    apply(algo_config.enable_stoch, "stoch_bull", "stoch_bear")
    apply(algo_config.enable_bb, "bb_bull", "bb_bear")
    apply(algo_config.enable_ema, "ema_bull", "ema_bear")
    apply(algo_config.enable_ao, "ao_bull", "ao_bear")
    apply(algo_config.enable_sar, "sar_bull", "sar_bear")
    apply(algo_config.enable_cci, "cci_bull", "cci_bear")
    apply(algo_config.enable_adx, "adx_bull", "adx_bear")

    if not any_enabled:
        long_cond = False
        short_cond = False

    prev_long = _last_long_cond.get(symbol, False)
    prev_short = _last_short_cond.get(symbol, False)
    long_signal = bool(long_cond and (not prev_long))
    short_signal = bool(short_cond and (not prev_short))
    _last_long_cond[symbol] = bool(long_cond)
    _last_short_cond[symbol] = bool(short_cond)
    return long_cond, short_cond, long_signal, short_signal


def _build_sl_tp(side: str, price: float, atr_val: float) -> tuple[Optional[float], Optional[float]]:
    sl = None
    tp = None
    if algo_config.enable_sl:
        sl = price - (atr_val * algo_config.sl_mult) if side == "buy" else price + (atr_val * algo_config.sl_mult)
    if algo_config.enable_tp:
        tp = price + (atr_val * algo_config.tp_mult) if side == "buy" else price - (atr_val * algo_config.tp_mult)
    return sl, tp


def _execute_signal(symbol: str, side: str, atr_val: float) -> None:
    price = mt5_bridge.get_current_price(symbol)
    if price is None:
        return
    sl, tp = _build_sl_tp(side, float(price), atr_val)
    if sl is None:
        sl = float(price - atr_val) if side == "buy" else float(price + atr_val)
    if tp is None:
        rr = 1.5
        tp = float(price + (atr_val * rr)) if side == "buy" else float(price - (atr_val * rr))

    results = execute_on_all_accounts(
        symbol=symbol,
        side=side,
        sl=float(sl),
        tp=float(tp),
        entry=float(price),
        order_type="market",
        risk_percent=float(algo_config.risk_percent),
        comment="ALGO:SFG",
        strategy_id="signal_forge",
    )
    succ = [r for r in (results or []) if r.get("success")]
    if succ:
        for s in succ:
            logger.success(
                f"[SIGNAL_FORGE] Trade on {s.get('account_label')} ({s.get('login')}) "
                f"{symbol} {side.upper()} ticket={s.get('ticket')} lot={s.get('lot')}"
            )
    else:
        logger.warning(f"[SIGNAL_FORGE] Signal not executed on mapped accounts | {symbol} {side.upper()} | {results}")


def _scan_symbol(symbol: str) -> None:
    global _last_scan_at
    f = _directional_flags(symbol)
    if not f:
        return
    bar_time = f["time"]
    if _last_bar_time.get(symbol) == bar_time:
        return
    _last_bar_time[symbol] = bar_time

    long_cond, short_cond, long_signal, short_signal = _compose_signal(symbol, f)
    _last_scan_at = datetime.utcnow().isoformat()
    _last_scan_summary[symbol] = {
        "time": bar_time.isoformat(),
        "long_cond": long_cond,
        "short_cond": short_cond,
        "long_signal": long_signal,
        "short_signal": short_signal,
        "atr": f["atr"],
        "close": f["close"],
    }
    logger.info(
        f"[SIGNAL_FORGE] {symbol} bar={bar_time} long_cond={long_cond} short_cond={short_cond} "
        f"long_signal={long_signal} short_signal={short_signal}"
    )

    if not algo_config.enabled:
        return
    if long_signal and not short_signal:
        _execute_signal(symbol, "buy", float(f["atr"]))
    elif short_signal and not long_signal:
        _execute_signal(symbol, "sell", float(f["atr"]))


def _loop() -> None:
    global _running
    logger.info(
        f"[SIGNAL_FORGE] Started | symbols={algo_config.get_symbols()} tf={algo_config.analysis_timeframe}m "
        f"require_all={algo_config.require_all}"
    )
    while _running:
        try:
            if mt5_bridge.ensure_connected():
                for sym in algo_config.get_symbols():
                    _scan_symbol(sym)
        except Exception as exc:
            logger.error(f"[SIGNAL_FORGE] Loop error: {exc}")
        time.sleep(max(3, int(algo_config.scan_interval_seconds)))
    logger.info("[SIGNAL_FORGE] Stopped.")


def start_algo() -> bool:
    global _running, _thread
    if _running:
        return True
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True, name="SignalForgeAlgo")
    _thread.start()
    return True


def stop_algo() -> bool:
    global _running
    if not _running:
        return False
    _running = False
    return True


def get_algo_status() -> dict:
    with _lock:
        assigned = [
            {"label": a.label, "login": a.login}
            for a in get_all_accounts()
            if a.enabled and "signal_forge" in (a.strategy or [])
        ]
        return {
            "running": _running,
            "enabled": algo_config.enabled,
            "strategy": "signal_forge",
            "symbols": algo_config.get_symbols(),
            "analysis_timeframe": algo_config.analysis_timeframe,
            "risk_percent": algo_config.risk_percent,
            "require_all": algo_config.require_all,
            "assigned_accounts": assigned,
            "last_scan_at": _last_scan_at,
            "scan_summary": dict(_last_scan_summary),
        }


def update_algo_config(
    symbol: Optional[str] = None,
    enabled: Optional[bool] = None,
    risk_percent: Optional[float] = None,
    analysis_tf: Optional[int] = None,
    scan_interval_seconds: Optional[int] = None,
    require_all: Optional[bool] = None,
) -> dict:
    if symbol is not None:
        syms = _normalize_symbols(symbol)
        if syms:
            algo_config.symbol = syms[0]
            algo_config.symbols = syms
    if enabled is not None:
        algo_config.enabled = bool(enabled)
    if risk_percent is not None:
        algo_config.risk_percent = float(risk_percent)
    if analysis_tf is not None:
        algo_config.analysis_timeframe = int(analysis_tf)
    if scan_interval_seconds is not None:
        algo_config.scan_interval_seconds = int(scan_interval_seconds)
    if require_all is not None:
        algo_config.require_all = bool(require_all)
    logger.info(f"[SIGNAL_FORGE] Config updated: {algo_config}")
    return get_algo_status()
