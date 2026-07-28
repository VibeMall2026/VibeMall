"""
Smart Money Structure strategy.

Python port of the Pine v5 indicator "Smart Money Structure | GainzAlgo".
Every input, threshold and filter below maps 1:1 to the Pine source; the
mapping is called out in comments wherever the translation is non-obvious.

Two deliberate departures from Pine, both required to trade this live:

1. Signals are evaluated on the last CLOSED bar. Pine re-evaluates the
   in-progress bar on every tick (and repaints until it closes). A live
   executor cannot do that: the forming bar has only a few seconds of
   volume in it, so `volume > sma(volume, 50)` can never be true and the
   strategy never fires. The forming bar is dropped for signal logic.

   Higher-timeframe trend context still uses the latest (developing) HTF
   bar, which is what Pine's `request.security` returns in real time and
   carries no look-ahead.

2. TP/SL are validated against the broker's minimum stop distance and
   rounded to the symbol's digits before the order is sent. Pine draws
   levels on a chart and has no broker to satisfy.

Note on units: Pine adds `tp_points` directly to price (`high + tp_points`),
so these are PRICE UNITS, not MT5 "points". On XAUUSD the default of 10
means $10, not $0.10.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from loguru import logger

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

from bot import config as runtime_config
from bot import mt5_bridge
from bot.accounts import execute_on_all_accounts, get_accounts_for_strategy, get_mt5_lock


@dataclass
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


# Pine timeframe strings -> minutes. Matches the `options=[...]` list on the
# higher_tf / lower_tf / restrict_trend_tf inputs.
_TF_MINUTES: dict[str, int] = {
    "1M": 1,
    "5M": 5,
    "15M": 15,
    "30M": 30,
    "1H": 60,
    "4H": 240,
    "D": 1440,
}

# How many bars to pull per timeframe. Sized so a full trading session fits,
# because ta.vwap() resets at session start and needs the whole session.
_TF_BARS: dict[int, int] = {
    1: 1500,
    5: 400,
    15: 220,
    30: 160,
    60: 140,
    240: 120,
    1440: 120,
}


@dataclass
class AlgoConfig:
    """Mirrors the Pine `input.*` declarations, same names, same defaults."""

    symbol: str = "XAUUSD"
    symbols: list[str] | None = None

    # Chart timeframe the indicator is applied to.
    analysis_timeframe: int = 5
    scan_interval_seconds: int = 15

    # --- Pine: main inputs ---
    pivot_length: int = 5
    momentum_threshold_base: float = 0.01
    tp_points: int = 10          # price units, added straight to price
    sl_points: int = 10          # price units, subtracted straight from price
    min_signal_distance: int = 5
    pre_momentum_factor_base: float = 0.5
    short_trend_period: int = 30
    long_trend_period: int = 100

    # --- Pine: group "Signal Filters" ---
    use_momentum_filter: bool = True
    use_trend_filter: bool = True
    higher_tf_choice: str = "5M"
    use_lower_tf_filter: bool = True
    lower_tf_choice: str = "5M"
    use_volume_filter: bool = True
    use_breakout_filter: bool = True
    show_get_ready: bool = False
    restrict_repeated_signals: bool = True
    restrict_trend_tf_choice: str = "5M"

    # --- Pine: group "Volume Filter Settings" / "Breakout Filter Settings" ---
    volume_long_period: int = 50
    volume_short_period: int = 5
    breakout_period: int = 5

    # --- Bot-side only (no Pine equivalent) ---
    enabled: bool = True
    risk_percent: float = field(default_factory=lambda: runtime_config.RISK_PERCENT)

    def get_symbols(self) -> list[str]:
        if self.symbols:
            return list(self.symbols)
        assigned = get_accounts_for_strategy("smart_money")
        resolved: list[str] = []
        for account in assigned:
            for sym in list(getattr(account, "allowed_symbols", None) or []):
                sym = str(sym or "").strip().upper()
                if sym and sym not in resolved:
                    resolved.append(sym)
        return resolved or [self.symbol]


algo_config = AlgoConfig()
_running = False
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()

# Per-symbol state. Mirrors the Pine `var` declarations, which persist across
# bars and reset when the script reloads.
_last_closed_bar: dict[str, datetime] = {}
_last_signal_bar_time: dict[str, datetime] = {}
_last_signal_direction: dict[str, str] = {}
_last_restrict_trend: dict[str, int] = {}

_last_scan_at: Optional[str] = None
_last_scan_summary: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Repeat-signal state persistence
#
# restrict_repeated_signals is enforced from _last_signal_direction /
# _last_restrict_trend, which used to live only in memory. A process restart
# wiped them, silently lifting the restriction: after a SELL the rule blocks
# further SELLs until the trend leaves bearish, but a restarted process has no
# "after a SELL" to remember and takes the duplicate. That is a risk change,
# not a strategy change, so the state is persisted here.
#
# Scoped to one IST trading day. The bot's own window is 09:00-22:00 IST, so
# midnight IST falls inside the idle window and never splits a session. A
# stale file from a previous day is ignored rather than blocking the first
# trade of a new day.
# ---------------------------------------------------------------------------
_IST = ZoneInfo("Asia/Kolkata")
_STATE_PATH = Path(__file__).resolve().parent.parent / "sessions" / "smart_money_state.json"
_state_file_lock = threading.Lock()


def _trading_day() -> str:
    return datetime.now(timezone.utc).astimezone(_IST).date().isoformat()


def _load_signal_state() -> None:
    """Best-effort restore of repeat-signal state for the current trading day."""
    try:
        if not _STATE_PATH.exists():
            return
        raw = _STATE_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return
        data = json.loads(raw)
        if not isinstance(data, dict):
            return

        saved_day = str(data.get("trading_day") or "")
        today = _trading_day()
        if saved_day != today:
            logger.info(
                f"[SMART_MONEY] Ignoring repeat-signal state from {saved_day or 'unknown day'} "
                f"(today is {today}) - starting fresh"
            )
            return

        symbols = data.get("symbols")
        if not isinstance(symbols, dict):
            return

        restored = 0
        for symbol, entry in symbols.items():
            if not isinstance(entry, dict):
                continue
            direction = str(entry.get("last_signal") or "").strip()
            if direction in ("Buy", "Sell"):
                _last_signal_direction[symbol] = direction
            trend = entry.get("last_restrict_trend")
            if isinstance(trend, int):
                _last_restrict_trend[symbol] = trend
            bar_time = str(entry.get("last_signal_bar_time") or "").strip()
            if bar_time:
                try:
                    _last_signal_bar_time[symbol] = datetime.fromisoformat(bar_time)
                except ValueError:
                    pass
            restored += 1

        if restored:
            summary = ", ".join(
                f"{sym}={_last_signal_direction.get(sym, 'Neutral')}"
                f"@trend{_last_restrict_trend.get(sym, 0)}"
                for sym in symbols
            )
            logger.info(f"[SMART_MONEY] Restored repeat-signal state for {today} | {summary}")
    except Exception as exc:
        logger.warning(f"[SMART_MONEY] Could not load repeat-signal state: {exc}")


def _save_signal_state() -> None:
    """Best-effort persist of repeat-signal state. Never raises into the scan loop."""
    try:
        with _state_file_lock:
            symbols: dict[str, dict] = {}
            for symbol, direction in _last_signal_direction.items():
                bar_time = _last_signal_bar_time.get(symbol)
                symbols[symbol] = {
                    "last_signal": direction,
                    "last_restrict_trend": int(_last_restrict_trend.get(symbol, 0)),
                    "last_signal_bar_time": bar_time.isoformat() if bar_time else None,
                }
            payload = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "trading_day": _trading_day(),
                "symbols": symbols,
            }
            _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[SMART_MONEY] Could not persist repeat-signal state: {exc}")


# ---------------------------------------------------------------------------
# MT5 data access
# ---------------------------------------------------------------------------

def _tf_to_mt5(timeframe_minutes: int):
    mapping = {
        1: mt5.TIMEFRAME_M1,
        5: mt5.TIMEFRAME_M5,
        15: mt5.TIMEFRAME_M15,
        30: mt5.TIMEFRAME_M30,
        60: mt5.TIMEFRAME_H1,
        240: mt5.TIMEFRAME_H4,
        1440: mt5.TIMEFRAME_D1,
    }
    return mapping.get(int(timeframe_minutes), mt5.TIMEFRAME_M5)


def _get_candles(symbol: str, timeframe_minutes: int, count: int) -> list[Candle]:
    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return []

    with get_mt5_lock():
        try:
            mt5.symbol_select(symbol, True)
        except Exception:
            pass

        rates = mt5.copy_rates_from_pos(symbol, _tf_to_mt5(timeframe_minutes), 0, count)
        if rates is None or len(rates) == 0:
            try:
                lookback_days = max(3, int((count * max(1, timeframe_minutes)) / 1440) + 3)
                start = datetime.now(timezone.utc) - timedelta(days=lookback_days)
                rates = mt5.copy_rates_from(symbol, _tf_to_mt5(timeframe_minutes), start, count)
            except Exception as exc:
                logger.warning(f"[SMART_MONEY] copy_rates_from fallback failed for {symbol}: {exc}")
                rates = None

    if rates is None or len(rates) == 0:
        return []

    return [
        Candle(
            time=datetime.fromtimestamp(row["time"], tz=timezone.utc),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["tick_volume"]),
        )
        for row in rates
    ]


def _get_tick_price(symbol: str, side: str) -> Optional[float]:
    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return None
    with get_mt5_lock():
        tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return None
    return float(tick.ask if side == "buy" else tick.bid)


# ---------------------------------------------------------------------------
# Pine built-in equivalents
#
# Each of these evaluates at an explicit bar index rather than "the last bar",
# so the caller controls whether the forming bar is included.
# ---------------------------------------------------------------------------

def _sma_at(values: list[float], period: int, index: int) -> Optional[float]:
    """Pine ta.sma(series, period) evaluated at `index`."""
    if index < 0 or index >= len(values) or index + 1 < period or period <= 0:
        return None
    return sum(values[index + 1 - period : index + 1]) / float(period)


def _ema_at(values: list[float], period: int, index: int) -> Optional[float]:
    """Pine ta.ema(series, period) evaluated at `index` (SMA-seeded)."""
    if index < 0 or index >= len(values) or index + 1 < period or period <= 0:
        return None
    ema = sum(values[:period]) / float(period)
    multiplier = 2.0 / (period + 1.0)
    for value in values[period : index + 1]:
        ema = (value - ema) * multiplier + ema
    return float(ema)


def _atr_at(candles: list[Candle], period: int, index: int) -> Optional[float]:
    """Pine ta.atr(period) — Wilder's RMA of true range, evaluated at `index`."""
    if index < 1 or index >= len(candles):
        return None
    trs: list[float] = []
    for i in range(1, index + 1):
        current = candles[i]
        previous = candles[i - 1]
        trs.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    if len(trs) < period:
        return None
    rma = sum(trs[:period]) / float(period)
    multiplier = 1.0 / float(period)
    for tr in trs[period:]:
        rma = (tr - rma) * multiplier + rma
    return float(rma)


def _session_vwap_at(candles: list[Candle], index: int) -> Optional[float]:
    """
    Pine ta.vwap(hlc3) evaluated at `index`.

    Pine's VWAP is session-anchored: it resets when a new session starts, not
    a rolling window. Session boundary here is a change of date in the bar's
    server timestamp, which is how MT5 delimits a broker day.
    """
    if index < 0 or index >= len(candles):
        return None
    session_day = candles[index].time.date()
    pv = 0.0
    total_volume = 0.0
    i = index
    while i >= 0 and candles[i].time.date() == session_day:
        candle = candles[i]
        typical = (candle.high + candle.low + candle.close) / 3.0
        volume = max(1.0, float(candle.volume or 0.0))
        pv += typical * volume
        total_volume += volume
        i -= 1
    return pv / total_volume if total_volume > 0 else None


def _confirmed_pivots(
    candles: list[Candle], length: int, upto_index: int
) -> tuple[Optional[float], Optional[float]]:
    """
    Pine ta.pivothigh(high, length, length) / ta.pivotlow(low, length, length),
    returning the most recent pivot confirmed at or before `upto_index`.

    A pivot at bar i is only confirmed once bar i+length exists, so the scan
    stops `length` bars short of `upto_index` — this is what makes the levels
    non-repainting.

    The centre bar must be STRICTLY higher (lower) than every neighbour, as in
    Pine: a tie is not a pivot. Using >= instead would mark every bar of a flat
    stretch as a pivot and drag the level along with price.
    """
    last_high: Optional[float] = None
    last_low: Optional[float] = None
    for i in range(length, upto_index - length + 1):
        candidate = candles[i]
        neighbours = candles[i - length : i] + candles[i + 1 : i + length + 1]
        if all(candidate.high > c.high for c in neighbours):
            last_high = candidate.high
        if all(candidate.low < c.low for c in neighbours):
            last_low = candidate.low
    return last_high, last_low


def _cvd_at(candles: list[Candle], index: int) -> float:
    """
    Pine's cumulative volume delta:
        close > close[1] -> +volume, close < close[1] -> -volume.

    Pine accumulates from the first bar the script ever sees; here it
    accumulates over the fetched window, so treat the absolute value as
    relative rather than comparable to a TradingView reading.
    """
    total = 0.0
    for i in range(1, min(index, len(candles) - 1) + 1):
        if candles[i].close > candles[i - 1].close:
            total += candles[i].volume
        elif candles[i].close < candles[i - 1].close:
            total -= candles[i].volume
    return total


# ---------------------------------------------------------------------------
# Multi-timeframe trend engine
# ---------------------------------------------------------------------------

def _trend_for_timeframe(symbol: str, timeframe_minutes: int, reference_close: float) -> int:
    """
    Pine:
        [emaTF, vwapTF] = request.security(tickerid, TF, [ta.ema(close,20), ta.vwap(hlc3)])
        trendTF = close > emaTF and close > vwapTF ? 1 : close < emaTF and close < vwapTF ? -1 : 0

    Note the operand on the comparison is the CHART's close, not the higher
    timeframe's close — so `reference_close` is passed in from the analysis
    timeframe, matching Pine exactly.

    Returns 0 whenever price sits between EMA and VWAP. With use_trend_filter
    on that blocks BOTH directions, which is the single most common reason
    this strategy sits flat in a ranging market.
    """
    bars = _TF_BARS.get(timeframe_minutes, 300)
    candles = _get_candles(symbol, timeframe_minutes, bars)
    if len(candles) < 25:
        return 0

    index = len(candles) - 1  # developing bar, as request.security returns live
    ema = _ema_at([c.close for c in candles], 20, index)
    vwap = _session_vwap_at(candles, index)
    if ema is None or vwap is None:
        return 0
    if reference_close > ema and reference_close > vwap:
        return 1
    if reference_close < ema and reference_close < vwap:
        return -1
    return 0


def _all_trends(symbol: str, reference_close: float) -> dict[str, int]:
    """Pine computes all seven timeframes every bar; so do we."""
    return {
        name: _trend_for_timeframe(symbol, minutes, reference_close)
        for name, minutes in _TF_MINUTES.items()
    }


def _system_confidence(trend_strength_raw: int) -> float:
    """Pine's confidence ladder, verbatim."""
    magnitude = abs(trend_strength_raw)
    if magnitude == 7:
        return 90.0
    if magnitude >= 4:
        return 75.0
    if magnitude >= 2:
        return 60.0
    return 50.0


# ---------------------------------------------------------------------------
# Signal construction
# ---------------------------------------------------------------------------

def _build_signal(symbol: str) -> Optional[dict]:
    timeframe = int(algo_config.analysis_timeframe)
    needed = max(
        algo_config.volume_long_period,
        algo_config.breakout_period,
        algo_config.pivot_length * 2,
        30,
    ) + 40
    candles = _get_candles(symbol, timeframe, max(400, needed))
    if len(candles) < needed:
        logger.debug(f"[SMART_MONEY] Not enough candles for {symbol} (got {len(candles)})")
        return None

    # index -1 is the bar currently forming. Everything below evaluates the
    # last CLOSED bar so the volume and breakout comparisons are like-for-like.
    idx = len(candles) - 2
    signal_bar = candles[idx]
    bar_time = signal_bar.time

    if _last_closed_bar.get(symbol) == bar_time:
        return None
    _last_closed_bar[symbol] = bar_time

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.volume for c in candles]

    close = closes[idx]
    prev_close = closes[idx - 1]

    # --- adaptive momentum (Pine) ---
    atr = _atr_at(candles, 14, idx)
    if atr is None or atr <= 0:
        atr = max(1e-9, signal_bar.high - signal_bar.low)
    volatility_factor = (atr / close) if close else 0.0
    price_change = ((close - prev_close) / prev_close) * 100.0 if prev_close else 0.0
    momentum_threshold = algo_config.momentum_threshold_base * (1 + volatility_factor * 2)
    pre_momentum_factor = algo_config.pre_momentum_factor_base * (1 - volatility_factor * 0.5)
    pre_momentum_threshold = momentum_threshold * pre_momentum_factor

    # --- multi-timeframe trend ---
    trends = _all_trends(symbol, close)
    trend_strength_raw = sum(trends.values())
    trend_strength = (trend_strength_raw / 7.0) * 100.0
    confidence = _system_confidence(trend_strength_raw)

    higher_tf_trend = trends.get(algo_config.higher_tf_choice, 0)
    lower_tf_trend = trends.get(algo_config.lower_tf_choice, 0)
    restrict_tf_trend = trends.get(algo_config.restrict_trend_tf_choice, 0)

    bullish_trend_ok = higher_tf_trend == 1
    bearish_trend_ok = higher_tf_trend == -1
    lower_tf_bullish = lower_tf_trend == 1
    lower_tf_bearish = lower_tf_trend == -1
    lower_tf_not_neutral = lower_tf_trend != 0

    # --- volume filter (Pine) ---
    #   volAvg50   = ta.sma(volume, volumeLongPeriod)
    #   volShort   = ta.sma(volume, volumeShortPeriod)
    #   volCondition = volume > volAvg50 and ta.change(volShort) > 0
    vol_avg_long = _sma_at(volumes, algo_config.volume_long_period, idx)
    vol_short_now = _sma_at(volumes, algo_config.volume_short_period, idx)
    vol_short_prev = _sma_at(volumes, algo_config.volume_short_period, idx - 1)
    if vol_avg_long is None or vol_short_now is None or vol_short_prev is None:
        vol_condition = False
    else:
        vol_condition = volumes[idx] > vol_avg_long and (vol_short_now - vol_short_prev) > 0

    # --- breakout filter (Pine) ---
    #   highestBreakout[1] == highest high over the `breakoutPeriod` bars that
    #   ended on the PREVIOUS bar, hence the slice stopping at idx.
    period = algo_config.breakout_period
    highest_prev = max(highs[idx - period : idx]) if idx - period >= 0 else None
    lowest_prev = min(lows[idx - period : idx]) if idx - period >= 0 else None
    raw_buy_breakout = highest_prev is not None and close > highest_prev
    raw_sell_breakout = lowest_prev is not None and close < lowest_prev

    # --- filter application (Pine ternaries) ---
    early_buy_signal = (price_change > momentum_threshold) if algo_config.use_momentum_filter else True
    early_sell_signal = (price_change < -momentum_threshold) if algo_config.use_momentum_filter else True

    buy_trend_ok = bullish_trend_ok if algo_config.use_trend_filter else True
    sell_trend_ok = bearish_trend_ok if algo_config.use_trend_filter else True

    buy_lower_tf_ok = (
        (not lower_tf_bearish and lower_tf_not_neutral) if algo_config.use_lower_tf_filter else True
    )
    sell_lower_tf_ok = (
        (not lower_tf_bullish and lower_tf_not_neutral) if algo_config.use_lower_tf_filter else True
    )

    buy_volume_ok = vol_condition if algo_config.use_volume_filter else True
    sell_volume_ok = vol_condition if algo_config.use_volume_filter else True

    buy_breakout_ok = raw_buy_breakout if algo_config.use_breakout_filter else True
    sell_breakout_ok = raw_sell_breakout if algo_config.use_breakout_filter else True

    # --- repeated-signal restriction (Pine) ---
    last_signal = _last_signal_direction.get(symbol, "Neutral")
    last_trend = _last_restrict_trend.get(symbol, 0)
    buy_allowed = (not algo_config.restrict_repeated_signals) or (
        last_signal != "Buy" or (restrict_tf_trend != last_trend and restrict_tf_trend != 1)
    )
    sell_allowed = (not algo_config.restrict_repeated_signals) or (
        last_signal != "Sell" or (restrict_tf_trend != last_trend and restrict_tf_trend != -1)
    )

    # --- min signal distance (Pine: bar_index - last_signal_bar) ---
    # Tracked by bar timestamp rather than bar index, because the fetch window
    # slides and an index would not survive between scans.
    last_sig_time = _last_signal_bar_time.get(symbol)
    if last_sig_time is None:
        enough_distance = True
        bars_since_signal = None
    else:
        bars_since_signal = (bar_time - last_sig_time).total_seconds() / 60.0 / max(1, timeframe)
        enough_distance = bars_since_signal >= algo_config.min_signal_distance

    # --- final conditions, exactly the six Pine layers ---
    buy_signal = (
        early_buy_signal
        and enough_distance
        and buy_trend_ok
        and buy_lower_tf_ok
        and buy_volume_ok
        and buy_breakout_ok
        and buy_allowed
    )
    sell_signal = (
        early_sell_signal
        and enough_distance
        and sell_trend_ok
        and sell_lower_tf_ok
        and sell_volume_ok
        and sell_breakout_ok
        and sell_allowed
    )

    # --- "Get Ready" (Pine: display only, never trades) ---
    get_ready_buy = get_ready_sell = False
    if algo_config.use_momentum_filter:
        get_ready_buy = (
            pre_momentum_threshold < price_change < momentum_threshold
            and enough_distance
            and buy_trend_ok
            and buy_lower_tf_ok
            and buy_volume_ok
            and buy_breakout_ok
        )
        get_ready_sell = (
            -momentum_threshold < price_change < -pre_momentum_threshold
            and enough_distance
            and sell_trend_ok
            and sell_lower_tf_ok
            and sell_volume_ok
            and sell_breakout_ok
        )

    # --- market structure (Pine: drawn on the chart, NOT part of entry) ---
    last_high, last_low = _confirmed_pivots(candles, algo_config.pivot_length, idx)
    bos_buy = bool(last_high is not None and signal_bar.high > last_high and signal_bar.is_bullish)
    bos_sell = bool(last_low is not None and signal_bar.low < last_low and signal_bar.is_bearish)
    choch_buy = bool(last_low is not None and signal_bar.high > last_low and signal_bar.is_bullish)
    choch_sell = bool(last_high is not None and signal_bar.low < last_high and signal_bar.is_bearish)

    # --- blocker diagnostics ---
    buy_blockers: list[str] = []
    sell_blockers: list[str] = []
    if not enough_distance:
        detail = (
            f"enough_distance=False (bars_since_signal={bars_since_signal:.1f}, "
            f"min={algo_config.min_signal_distance})"
        )
        buy_blockers.append(detail)
        sell_blockers.append(detail)
    if algo_config.use_momentum_filter and not early_buy_signal:
        buy_blockers.append(
            f"momentum=False (price_change={price_change:.5f} <= threshold={momentum_threshold:.5f})"
        )
    if algo_config.use_momentum_filter and not early_sell_signal:
        sell_blockers.append(
            f"momentum=False (price_change={price_change:.5f} >= -threshold={-momentum_threshold:.5f})"
        )
    if algo_config.use_trend_filter and not buy_trend_ok:
        buy_blockers.append(
            f"trend=False ({algo_config.higher_tf_choice} trend={higher_tf_trend}, need 1)"
        )
    if algo_config.use_trend_filter and not sell_trend_ok:
        sell_blockers.append(
            f"trend=False ({algo_config.higher_tf_choice} trend={higher_tf_trend}, need -1)"
        )
    if algo_config.use_lower_tf_filter and not buy_lower_tf_ok:
        buy_blockers.append(
            f"lower_tf=False ({algo_config.lower_tf_choice} trend={lower_tf_trend})"
        )
    if algo_config.use_lower_tf_filter and not sell_lower_tf_ok:
        sell_blockers.append(
            f"lower_tf=False ({algo_config.lower_tf_choice} trend={lower_tf_trend})"
        )
    if algo_config.use_volume_filter and not vol_condition:
        detail = (
            f"volume=False (vol={volumes[idx]:.0f}, sma{algo_config.volume_long_period}="
            f"{vol_avg_long if vol_avg_long is None else round(vol_avg_long)}, "
            f"sma{algo_config.volume_short_period}_rising="
            f"{None if vol_short_now is None else (vol_short_now - vol_short_prev) > 0})"
        )
        buy_blockers.append(detail)
        sell_blockers.append(detail)
    if algo_config.use_breakout_filter and not raw_buy_breakout:
        buy_blockers.append(f"breakout=False (close={close:.5f} <= prev {period}-bar high {highest_prev})")
    if algo_config.use_breakout_filter and not raw_sell_breakout:
        sell_blockers.append(f"breakout=False (close={close:.5f} >= prev {period}-bar low {lowest_prev})")
    if not buy_allowed:
        buy_blockers.append(
            f"repeat_blocked (last_signal={last_signal}, restrict_trend={restrict_tf_trend}, prev={last_trend})"
        )
    if not sell_allowed:
        sell_blockers.append(
            f"repeat_blocked (last_signal={last_signal}, restrict_trend={restrict_tf_trend}, prev={last_trend})"
        )

    return {
        "time": bar_time,
        "open": signal_bar.open,
        "high": signal_bar.high,
        "low": signal_bar.low,
        "close": close,
        "prev_close": prev_close,
        "atr": atr,
        "price_change": price_change,
        "momentum_threshold": momentum_threshold,
        "pre_momentum_threshold": pre_momentum_threshold,
        "trends": trends,
        "trend_strength_raw": trend_strength_raw,
        "trend_strength": trend_strength,
        "confidence": confidence,
        "cvd": _cvd_at(candles, idx),
        "higher_tf_trend": higher_tf_trend,
        "lower_tf_trend": lower_tf_trend,
        "restrict_tf_trend": restrict_tf_trend,
        "last_high": last_high,
        "last_low": last_low,
        "bos_buy": bos_buy,
        "bos_sell": bos_sell,
        "choch_buy": choch_buy,
        "choch_sell": choch_sell,
        "buy_signal": buy_signal,
        "sell_signal": sell_signal,
        "get_ready_buy": get_ready_buy,
        "get_ready_sell": get_ready_sell,
        "buy_blockers": buy_blockers,
        "sell_blockers": sell_blockers,
    }


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _symbol_trade_spec(symbol: str) -> tuple[int, float, float]:
    """Return (digits, point, min_stop_distance_in_price) for the symbol."""
    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return 2, 0.01, 0.0
    with get_mt5_lock():
        info = mt5.symbol_info(symbol)
    if not info:
        return 2, 0.01, 0.0
    digits = int(getattr(info, "digits", 2) or 2)
    point = float(getattr(info, "point", 0.01) or 0.01)
    stops_level = int(getattr(info, "trade_stops_level", 0) or 0)
    return digits, point, stops_level * point


def _execute_signal(symbol: str, side: str, entry: float, signal: dict) -> None:
    """
    Pine places its levels off the signal bar's own high/low:
        buy  -> tp = high + tp_points, sl = low  - sl_points
        sell -> tp = low  - tp_points, sl = high + sl_points

    tp_points/sl_points are price units, not MT5 points — `high + tp_points`
    in Pine on XAUUSD means ten dollars, not ten ticks.
    """
    digits, _point, min_distance = _symbol_trade_spec(symbol)
    bar_high = float(signal["high"])
    bar_low = float(signal["low"])
    tp_offset = float(algo_config.tp_points)
    sl_offset = float(algo_config.sl_points)

    if side == "buy":
        tp = bar_high + tp_offset
        sl = bar_low - sl_offset
    else:
        tp = bar_low - tp_offset
        sl = bar_high + sl_offset

    # The bar's high/low straddle the entry, but a fast move between bar close
    # and fill can leave a level on the wrong side. Reject rather than send an
    # order that would be instantly invalid.
    if side == "buy" and not (sl < entry < tp):
        logger.warning(
            f"[SMART_MONEY] {symbol} BUY skipped — levels inverted after fill "
            f"(sl={sl:.{digits}f} entry={entry:.{digits}f} tp={tp:.{digits}f})"
        )
        return
    if side == "sell" and not (tp < entry < sl):
        logger.warning(
            f"[SMART_MONEY] {symbol} SELL skipped — levels inverted after fill "
            f"(tp={tp:.{digits}f} entry={entry:.{digits}f} sl={sl:.{digits}f})"
        )
        return

    # Broker minimum stop distance. Widening SL does not increase risk — lot
    # size is derived from the SL distance downstream — so it is safe to push
    # the level out to the minimum rather than drop the trade.
    if min_distance > 0:
        if side == "buy":
            if entry - sl < min_distance:
                sl = entry - min_distance
                logger.warning(f"[SMART_MONEY] {symbol} SL widened to broker minimum ({min_distance})")
            if tp - entry < min_distance:
                tp = entry + min_distance
                logger.warning(f"[SMART_MONEY] {symbol} TP widened to broker minimum ({min_distance})")
        else:
            if sl - entry < min_distance:
                sl = entry + min_distance
                logger.warning(f"[SMART_MONEY] {symbol} SL widened to broker minimum ({min_distance})")
            if entry - tp < min_distance:
                tp = entry - min_distance
                logger.warning(f"[SMART_MONEY] {symbol} TP widened to broker minimum ({min_distance})")

    sl = round(sl, digits)
    tp = round(tp, digits)

    results = execute_on_all_accounts(
        symbol=symbol,
        side=side,
        sl=float(sl),
        tp=float(tp),
        entry=float(entry),
        order_type="market",
        risk_percent=float(algo_config.risk_percent),
        comment="ALGO:SMR",
        strategy_id="smart_money",
    )

    succeeded = [row for row in results or [] if row.get("success")]
    if succeeded:
        for row in succeeded:
            logger.success(
                f"[SMART_MONEY] Trade on {row.get('account_label')} ({row.get('login')}) "
                f"{symbol} {side.upper()} ticket={row.get('ticket')} "
                f"entry={entry:.{digits}f} sl={sl:.{digits}f} tp={tp:.{digits}f}"
            )
    else:
        logger.warning(
            f"[SMART_MONEY] Signal not executed on mapped accounts | {symbol} {side.upper()} | {results}"
        )


# ---------------------------------------------------------------------------
# Scan loop
# ---------------------------------------------------------------------------

def _scan_symbol(symbol: str) -> None:
    global _last_scan_at

    signal = _build_signal(symbol)
    if not signal:
        return

    _last_scan_at = datetime.now(timezone.utc).isoformat()
    _last_scan_summary[symbol] = {
        "time": signal["time"].isoformat(),
        "close": signal["close"],
        "buy_signal": signal["buy_signal"],
        "sell_signal": signal["sell_signal"],
        "get_ready_buy": signal["get_ready_buy"],
        "get_ready_sell": signal["get_ready_sell"],
        "trends": signal["trends"],
        "trend_strength": round(signal["trend_strength"], 1),
        "confidence": signal["confidence"],
        "cvd": round(signal["cvd"]),
        "last_high": signal["last_high"],
        "last_low": signal["last_low"],
        "bos_buy": signal["bos_buy"],
        "bos_sell": signal["bos_sell"],
        "choch_buy": signal["choch_buy"],
        "choch_sell": signal["choch_sell"],
    }

    trend_map = " ".join(f"{name}:{value:+d}" for name, value in signal["trends"].items())
    logger.info(
        f"[SMART_MONEY] {symbol} bar={signal['time']} close={signal['close']:.5f} "
        f"buy={signal['buy_signal']} sell={signal['sell_signal']} "
        f"strength={signal['trend_strength']:.0f} conf={signal['confidence']:.0f}% | {trend_map}"
    )
    if not signal["buy_signal"] and not signal["sell_signal"]:
        logger.info(
            f"[SMART_MONEY] {symbol} blocked | "
            f"BUY blockers: {signal['buy_blockers'] or ['none']} | "
            f"SELL blockers: {signal['sell_blockers'] or ['none']}"
        )
    if algo_config.show_get_ready and (signal["get_ready_buy"] or signal["get_ready_sell"]):
        direction = "BUY" if signal["get_ready_buy"] else "SELL"
        logger.info(f"[SMART_MONEY] {symbol} GET READY {direction} (momentum building)")

    if not algo_config.enabled:
        return

    # Pine draws both labels if both fire; a trader cannot take both sides, so
    # an ambiguous bar is skipped.
    if signal["buy_signal"] and not signal["sell_signal"]:
        side = "buy"
    elif signal["sell_signal"] and not signal["buy_signal"]:
        side = "sell"
    else:
        return

    price = _get_tick_price(symbol, side)
    if price is None:
        logger.warning(f"[SMART_MONEY] {symbol} {side.upper()} skipped — no tick price available")
        return

    _last_signal_bar_time[symbol] = signal["time"]
    _last_signal_direction[symbol] = "Buy" if side == "buy" else "Sell"
    _last_restrict_trend[symbol] = int(signal["restrict_tf_trend"])
    # Persist before executing: if the order send crashes the process, the
    # restriction must still be in force on the way back up.
    _save_signal_state()
    _execute_signal(symbol, side, float(price), signal)


def _loop() -> None:
    global _running
    logger.info(
        f"[SMART_MONEY] Started | symbols={algo_config.get_symbols()} "
        f"tf={algo_config.analysis_timeframe}m pivot_length={algo_config.pivot_length} "
        f"htf={algo_config.higher_tf_choice} ltf={algo_config.lower_tf_choice} "
        f"tp={algo_config.tp_points} sl={algo_config.sl_points} (price units)"
    )
    while _running:
        try:
            if not mt5_bridge.ensure_connected():
                logger.debug("[SMART_MONEY] MT5 not connected; skipping scan")
            else:
                for symbol in algo_config.get_symbols():
                    _scan_symbol(symbol)
        except Exception as exc:
            logger.error(f"[SMART_MONEY] Loop error: {exc}")
        time.sleep(max(3, int(algo_config.scan_interval_seconds)))
    logger.info("[SMART_MONEY] Stopped.")


# ---------------------------------------------------------------------------
# Module contract used by bot.algo.runner / bot.algo.manager / api_server
# ---------------------------------------------------------------------------

def start_algo() -> bool:
    global _running, _thread
    if _running:
        return True
    _load_signal_state()
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True, name="SmartMoneyAlgo")
    _thread.start()
    return True


def stop_algo() -> bool:
    global _running
    if not _running:
        return False
    _running = False
    return True


def update_algo_config(
    enabled: Optional[bool] = None,
    symbol: Optional[str] = None,
    symbols: Optional[list[str]] = None,
    analysis_timeframe: Optional[int] = None,
    scan_interval_seconds: Optional[int] = None,
    pivot_length: Optional[int] = None,
    momentum_threshold_base: Optional[float] = None,
    tp_points: Optional[int] = None,
    sl_points: Optional[int] = None,
    min_signal_distance: Optional[int] = None,
    pre_momentum_factor_base: Optional[float] = None,
    use_momentum_filter: Optional[bool] = None,
    use_trend_filter: Optional[bool] = None,
    higher_tf_choice: Optional[str] = None,
    use_lower_tf_filter: Optional[bool] = None,
    lower_tf_choice: Optional[str] = None,
    use_volume_filter: Optional[bool] = None,
    use_breakout_filter: Optional[bool] = None,
    show_get_ready: Optional[bool] = None,
    restrict_repeated_signals: Optional[bool] = None,
    restrict_trend_tf_choice: Optional[str] = None,
    volume_long_period: Optional[int] = None,
    volume_short_period: Optional[int] = None,
    breakout_period: Optional[int] = None,
    risk_percent: Optional[float] = None,
) -> dict:
    """
    Update live config. Called via bot.algo.manager.update_algo_config, which
    filters kwargs by this signature — every Pine input is exposed here so the
    dashboard can tune the strategy without a restart.
    """
    updates = {k: v for k, v in locals().items() if v is not None}
    with _lock:
        for key, value in updates.items():
            if key in ("higher_tf_choice", "lower_tf_choice", "restrict_trend_tf_choice"):
                value = str(value).strip().upper()
                if value not in _TF_MINUTES:
                    raise ValueError(f"{key} must be one of {list(_TF_MINUTES)}")
            setattr(algo_config, key, value)
        # Timeframe or filter changes invalidate the "already seen this bar"
        # guard; clearing it makes the next scan re-evaluate immediately.
        _last_closed_bar.clear()
    logger.info(f"[SMART_MONEY] Config updated: {updates}")
    return get_algo_status()


def get_algo_status() -> dict:
    with _lock:
        assigned = [
            {"label": a.label, "login": a.login}
            for a in get_accounts_for_strategy("smart_money")
            if a.enabled
        ]
        return {
            "running": _running,
            "enabled": algo_config.enabled,
            "strategy": "smart_money",
            "symbols": algo_config.get_symbols(),
            "analysis_timeframe": algo_config.analysis_timeframe,
            "risk_percent": algo_config.risk_percent,
            "managed_trades": 0,
            "assigned_accounts": assigned,
            "last_scan_at": _last_scan_at,
            "scan_summary": dict(_last_scan_summary),
            "filters": {
                "momentum": algo_config.use_momentum_filter,
                "trend": algo_config.use_trend_filter,
                "higher_tf": algo_config.higher_tf_choice,
                "lower_tf_filter": algo_config.use_lower_tf_filter,
                "lower_tf": algo_config.lower_tf_choice,
                "volume": algo_config.use_volume_filter,
                "breakout": algo_config.use_breakout_filter,
                "restrict_repeated": algo_config.restrict_repeated_signals,
                "restrict_trend_tf": algo_config.restrict_trend_tf_choice,
            },
            "levels": {
                "tp_points": algo_config.tp_points,
                "sl_points": algo_config.sl_points,
                "units": "price",
            },
        }
