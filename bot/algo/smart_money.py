"""
Smart Money Structure strategy.

Implements a compact live version of the supplied GainzAlgo-style smart money
indicator:
- volatility-adjusted momentum
- multi-timeframe EMA + VWAP trend alignment
- pivot-based structure breakout entries
- fixed TP/SL in symbol points
- strategy-scoped execution only
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

from bot import config as runtime_config
from bot import mt5_bridge
from bot.accounts import execute_on_all_accounts, get_accounts_for_strategy


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


@dataclass
class AlgoConfig:
    symbol: str = "XAUUSD"
    symbols: list[str] | None = None
    analysis_timeframe: int = 5
    scan_interval_seconds: int = 15
    pivot_length: int = 5
    tp_points: int = 10
    sl_points: int = 10
    min_signal_distance: int = 5
    momentum_threshold_base: float = 0.01
    pre_momentum_factor_base: float = 0.5
    use_momentum_filter: bool = True
    use_trend_filter: bool = True
    use_lower_tf_filter: bool = True
    use_volume_filter: bool = True
    use_breakout_filter: bool = True
    restrict_repeated_signals: bool = True
    higher_tf_choice: str = "15M"
    lower_tf_choice: str = "1M"
    restrict_trend_tf_choice: str = "5M"
    enabled: bool = True
    risk_percent: float = runtime_config.RISK_PERCENT

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
_last_bar_time: dict[str, datetime] = {}
_last_signal_bar: dict[str, int] = {}
_last_signal_direction: dict[str, str] = {}
_last_restrict_trend: dict[str, int] = {}
_last_scan_at: Optional[str] = None
_last_scan_summary: dict[str, dict] = {}


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
    from bot import mt5_bridge as _bridge

    bridge_url = str(getattr(_bridge, "BRIDGE_URL", "") or "").strip()
    if bridge_url:
        try:
            response = _bridge._call_bridge(
                f"/candles?symbol={symbol}&timeframe={timeframe_minutes}&count={count}"
            )
            if response and isinstance(response, list):
                candles: list[Candle] = []
                for row in response:
                    candles.append(
                        Candle(
                            time=datetime.fromisoformat(row["time"]) if isinstance(row["time"], str) else datetime.fromtimestamp(row["time"]),
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=float(row.get("volume", row.get("tick_volume", 0))),
                        )
                    )
                return candles
        except Exception as exc:
            logger.warning(f"[SMART_MONEY] Bridge candles fetch failed: {exc}")
        # Fall through to local MT5 if bridge is unavailable or empty.

    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return []

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

    candles: list[Candle] = []
    for row in rates:
        candles.append(
            Candle(
                time=datetime.fromtimestamp(row["time"], tz=timezone.utc),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["tick_volume"]),
            )
        )
    return candles


def _get_tick_price(symbol: str, side: str) -> Optional[float]:
    from bot import mt5_bridge as _bridge

    if _bridge.USE_BRIDGE:
        try:
            response = _bridge._call_bridge(f"/price?symbol={symbol}")
            if response and "bid" in response and "ask" in response:
                bid = float(response["bid"])
                ask = float(response["ask"])
                return ask if side == "buy" else bid
        except Exception as exc:
            logger.warning(f"[SMART_MONEY] Bridge price fetch failed: {exc}")
        return None

    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return None
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return None
    return float(tick.ask if side == "buy" else tick.bid)


def _symbol_point(symbol: str) -> float:
    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return 0.01
    info = mt5.symbol_info(symbol)
    if not info:
        return 0.01
    point = float(getattr(info, "point", 0.01) or 0.01)
    return point if point > 0 else 0.01


def _ema(values: list[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    multiplier = 2.0 / (period + 1.0)
    ema = sum(values[:period]) / period
    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
    return float(ema)


def _atr(candles: list[Candle], period: int = 14) -> Optional[float]:
    if len(candles) < period + 1:
        return None
    trs: list[float] = []
    for index in range(1, len(candles)):
        current = candles[index]
        previous = candles[index - 1]
        tr = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        trs.append(tr)
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def _vwap(candles: list[Candle]) -> Optional[float]:
    if not candles:
        return None
    pv = 0.0
    vol = 0.0
    for candle in candles:
        typical = (candle.high + candle.low + candle.close) / 3.0
        volume = max(1.0, float(candle.volume or 0.0))
        pv += typical * volume
        vol += volume
    return pv / vol if vol > 0 else None


def _trend_from_candles(candles: list[Candle]) -> int:
    if len(candles) < 25:
        return 0
    closes = [float(c.close) for c in candles]
    ema = _ema(closes, 20)
    vwap = _vwap(candles)
    close = closes[-1]
    if ema is None or vwap is None:
        return 0
    if close > ema and close > vwap:
        return 1
    if close < ema and close < vwap:
        return -1
    return 0


def _pick_trend(symbol: str, choice: str) -> int:
    choice_map = {
        "1M": 1,
        "5M": 5,
        "15M": 15,
        "30M": 30,
        "1H": 60,
        "4H": 240,
        "D": 1440,
    }
    timeframe = choice_map.get(str(choice or "").strip().upper(), 5)
    candles = _get_candles(symbol, timeframe, 80)
    return _trend_from_candles(candles)


def _latest_pivot_levels(candles: list[Candle], length: int) -> tuple[Optional[float], Optional[float]]:
    if len(candles) < (length * 2) + 5:
        return None, None
    last_high = None
    last_low = None
    for index in range(length, len(candles) - length):
        window = candles[index - length : index + length + 1]
        candidate = candles[index]
        if candidate.high >= max(c.high for c in window):
            last_high = candidate.high
        if candidate.low <= min(c.low for c in window):
            last_low = candidate.low
    return last_high, last_low


def _volume_ok(candles: list[Candle]) -> bool:
    if len(candles) < 25:
        return False
    recent = candles[-1].volume
    average = sum(c.volume for c in candles[-20:]) / 20.0
    return recent > average


def _breakout_ok(side: str, candles: list[Candle], breakout_period: int = 5) -> bool:
    if len(candles) < breakout_period + 2:
        return False
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    if side == "buy":
        return closes[-1] > max(highs[-(breakout_period + 1):-1])
    return closes[-1] < min(lows[-(breakout_period + 1):-1])


def _build_signal(symbol: str) -> Optional[dict]:
    candles = _get_candles(symbol, algo_config.analysis_timeframe, 300)
    if len(candles) < 40:
        logger.debug(f"[SMART_MONEY] Not enough candles for {symbol} (got {len(candles)})")
        return None

    bar_time = candles[-1].time
    if _last_bar_time.get(symbol) == bar_time:
        return None
    _last_bar_time[symbol] = bar_time

    closes = [float(c.close) for c in candles]
    close = closes[-1]
    prev_close = closes[-2]
    atr = _atr(candles, 14) or max(0.01, candles[-1].high - candles[-1].low)
    price_change = ((close - prev_close) / prev_close) * 100.0 if prev_close else 0.0
    momentum_threshold = algo_config.momentum_threshold_base * (1 + ((atr / close) * 2 if close else 0))
    pre_momentum_threshold = momentum_threshold * algo_config.pre_momentum_factor_base

    higher_tf_trend = _pick_trend(symbol, algo_config.higher_tf_choice)
    lower_tf_trend = _pick_trend(symbol, algo_config.lower_tf_choice)
    restrict_tf_trend = _pick_trend(symbol, algo_config.restrict_trend_tf_choice)

    bullish_trend_ok = higher_tf_trend == 1
    bearish_trend_ok = higher_tf_trend == -1
    lower_tf_bullish = lower_tf_trend == 1
    lower_tf_bearish = lower_tf_trend == -1
    lower_tf_not_neutral = lower_tf_trend != 0

    last_high, last_low = _latest_pivot_levels(candles, algo_config.pivot_length)
    buy_breakout_ok = _breakout_ok("buy", candles)
    sell_breakout_ok = _breakout_ok("sell", candles)
    volume_ok = _volume_ok(candles)

    long_cond = True
    short_cond = True
    if algo_config.use_momentum_filter:
        long_cond = price_change > momentum_threshold
        short_cond = price_change < -momentum_threshold

    buy_trend_ok = bullish_trend_ok if algo_config.use_trend_filter else True
    sell_trend_ok = bearish_trend_ok if algo_config.use_trend_filter else True
    buy_lower_tf_ok = (not lower_tf_bearish and lower_tf_not_neutral) if algo_config.use_lower_tf_filter else True
    sell_lower_tf_ok = (not lower_tf_bullish and lower_tf_not_neutral) if algo_config.use_lower_tf_filter else True
    buy_volume_ok = volume_ok if algo_config.use_volume_filter else True
    sell_volume_ok = volume_ok if algo_config.use_volume_filter else True
    buy_breakout = buy_breakout_ok if algo_config.use_breakout_filter else True
    sell_breakout = sell_breakout_ok if algo_config.use_breakout_filter else True

    last_signal = _last_signal_direction.get(symbol, "neutral")
    last_trend = _last_restrict_trend.get(symbol, 0)
    buy_allowed = not algo_config.restrict_repeated_signals or (
        last_signal != "buy" or (restrict_tf_trend != last_trend and restrict_tf_trend != 1)
    )
    sell_allowed = not algo_config.restrict_repeated_signals or (
        last_signal != "sell" or (restrict_tf_trend != last_trend and restrict_tf_trend != -1)
    )

    bar_index = len(candles) - 1
    last_signal_bar = _last_signal_bar.get(symbol, -10_000)
    enough_distance = bar_index - last_signal_bar >= algo_config.min_signal_distance

    buy_signal = (
        enough_distance
        and long_cond
        and buy_trend_ok
        and buy_lower_tf_ok
        and buy_volume_ok
        and buy_breakout
        and buy_allowed
        and last_high is not None
        and close > last_high
    )
    sell_signal = (
        enough_distance
        and short_cond
        and sell_trend_ok
        and sell_lower_tf_ok
        and sell_volume_ok
        and sell_breakout
        and sell_allowed
        and last_low is not None
        and close < last_low
    )

    return {
        "time": bar_time,
        "close": close,
        "prev_close": prev_close,
        "atr": atr,
        "price_change": price_change,
        "momentum_threshold": momentum_threshold,
        "pre_momentum_threshold": pre_momentum_threshold,
        "higher_tf_trend": higher_tf_trend,
        "lower_tf_trend": lower_tf_trend,
        "restrict_tf_trend": restrict_tf_trend,
        "last_high": last_high,
        "last_low": last_low,
        "buy_signal": buy_signal,
        "sell_signal": sell_signal,
        "candles": candles,
    }


def _execute_signal(symbol: str, side: str, price: float, atr: float) -> None:
    point = _symbol_point(symbol)
    sl = price - (algo_config.sl_points * point) if side == "buy" else price + (algo_config.sl_points * point)
    tp = price + (algo_config.tp_points * point) if side == "buy" else price - (algo_config.tp_points * point)
    comment = "ALGO:SMR"

    results = execute_on_all_accounts(
        symbol=symbol,
        side=side,
        sl=float(sl),
        tp=float(tp),
        entry=float(price),
        order_type="market",
        risk_percent=float(algo_config.risk_percent),
        comment=comment,
        strategy_id="smart_money",
    )

    succ = [row for row in results or [] if row.get("success")]
    if succ:
        for row in succ:
            logger.success(
                f"[SMART_MONEY] Trade on {row.get('account_label')} ({row.get('login')}) "
                f"{symbol} {side.upper()} ticket={row.get('ticket')} "
                f"entry={price:.5f} sl={sl:.5f} tp={tp:.5f}"
            )
    else:
        logger.warning(f"[SMART_MONEY] Signal not executed on mapped accounts | {symbol} {side.upper()} | {results}")


def _scan_symbol(symbol: str) -> None:
    global _last_scan_at
    signal = _build_signal(symbol)
    if not signal:
        return

    _last_scan_at = datetime.now(timezone.utc).isoformat()
    _last_scan_summary[symbol] = {
        "time": signal["time"].isoformat(),
        "close": signal["close"],
        "last_high": signal["last_high"],
        "last_low": signal["last_low"],
        "buy_signal": signal["buy_signal"],
        "sell_signal": signal["sell_signal"],
        "trend": signal["higher_tf_trend"],
    }
    logger.info(
        f"[SMART_MONEY] {symbol} bar={signal['time']} close={signal['close']:.5f} "
        f"buy={signal['buy_signal']} sell={signal['sell_signal']} "
        f"trend={signal['higher_tf_trend']} lower_tf={signal['lower_tf_trend']}"
    )

    if not algo_config.enabled:
        return
    if signal["buy_signal"] and not signal["sell_signal"]:
        price = _get_tick_price(symbol, "buy")
        if price is None:
            return
        _last_signal_bar[symbol] = len(signal["candles"]) - 1
        _last_signal_direction[symbol] = "buy"
        _last_restrict_trend[symbol] = int(signal["restrict_tf_trend"])
        _execute_signal(symbol, "buy", float(price), float(signal["atr"]))
    elif signal["sell_signal"] and not signal["buy_signal"]:
        price = _get_tick_price(symbol, "sell")
        if price is None:
            return
        _last_signal_bar[symbol] = len(signal["candles"]) - 1
        _last_signal_direction[symbol] = "sell"
        _last_restrict_trend[symbol] = int(signal["restrict_tf_trend"])
        _execute_signal(symbol, "sell", float(price), float(signal["atr"]))


def _loop() -> None:
    global _running
    logger.info(
        f"[SMART_MONEY] Started | symbols={algo_config.get_symbols()} tf={algo_config.analysis_timeframe}m "
        f"pivot_length={algo_config.pivot_length}"
    )
    while _running:
        try:
            if mt5_bridge.ensure_connected():
                for symbol in algo_config.get_symbols():
                    _scan_symbol(symbol)
        except Exception as exc:
            logger.error(f"[SMART_MONEY] Loop error: {exc}")
        time.sleep(max(3, int(algo_config.scan_interval_seconds)))
    logger.info("[SMART_MONEY] Stopped.")


def start_algo() -> bool:
    global _running, _thread
    if _running:
        return True
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
        }
