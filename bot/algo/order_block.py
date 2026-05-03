"""
Order Block + Fair Value Gap (FVG) Algorithmic Strategy
========================================================

STRATEGY SUMMARY:
-----------------
Based on ICT/Smart Money Concepts:

1. FAIR VALUE GAP (FVG):
   - 3-candle pattern: candle[1] is explosive (large body)
   - Gap exists between candle[0].high and candle[2].low (bullish FVG)
   - Gap exists between candle[0].low and candle[2].high (bearish FVG)

2. ORDER BLOCK (OB):
   - The candle BEFORE the explosive move (candle[0] in the 3-candle pattern)
   - Bullish OB: high/low of candle[0] when followed by bullish FVG
   - Bearish OB: high/low of candle[0] when followed by bearish FVG
   - Key level = 50% of the order block (midpoint)

3. ENTRY RULES:
   - BUY: Price retraces into bullish OB zone (between OB low and OB 50%)
          AND closes above OB 50% level
   - SELL: Price retraces into bearish OB zone (between OB high and OB 50%)
           AND closes below OB 50% level

4. EXIT RULES:
   - Stop Loss: Below OB low (bullish) / Above OB high (bearish)
   - Take Profit: 1:2 or 1:3 risk-reward ratio
   - Trailing stop after 1:1 R:R reached

5. FILTERS:
   - Trend filter: Only trade in direction of higher timeframe trend (EMA 50)
   - Volatility filter: ATR must be above minimum threshold
   - Max 1 trade per OB zone (zone invalidated after touch)

TIMEFRAME: 15-minute analysis, 5-minute execution
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from loguru import logger

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

from bot import mt5_bridge
from bot.state import state


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class AlgoConfig:
    symbol: str = "XAUUSD"
    analysis_timeframe: int = 15        # minutes — for OB/FVG detection
    execution_timeframe: int = 5        # minutes — for entry confirmation
    risk_reward_ratio: float = 2.0      # minimum R:R (1:2)
    risk_percent: float = 1.0           # % of balance per trade
    fvg_min_body_ratio: float = 0.6     # explosive candle body/range ratio
    ob_lookback: int = 50               # candles to scan for OBs
    trend_ema_period: int = 50          # EMA period for trend filter
    atr_period: int = 14                # ATR period for volatility filter
    atr_min_multiplier: float = 0.5     # min ATR as fraction of avg ATR
    max_active_obs: int = 5             # max order blocks tracked at once
    scan_interval_seconds: int = 60     # how often to scan for new setups
    enabled: bool = True               # True = live trading on by default


# Global config instance
algo_config = AlgoConfig()


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body_ratio(self) -> float:
        return self.body / self.range if self.range > 0 else 0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


@dataclass
class FairValueGap:
    direction: str          # "bullish" | "bearish"
    top: float              # upper boundary of gap
    bottom: float           # lower boundary of gap
    time: datetime
    filled: bool = False

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class OrderBlock:
    id: str
    direction: str          # "bullish" | "bearish"
    high: float             # OB high
    low: float              # OB low
    midpoint: float         # 50% level — key entry zone
    time: datetime
    fvg: FairValueGap
    active: bool = True     # False once price enters zone
    trade_taken: bool = False
    ticket: Optional[int] = None

    @property
    def sl_level(self) -> float:
        """Stop loss level — just beyond OB boundary."""
        if self.direction == "bullish":
            return self.low - (self.high - self.low) * 0.1
        else:
            return self.high + (self.high - self.low) * 0.1

    def tp_level(self, entry: float, rr: float) -> float:
        """Take profit based on R:R ratio."""
        sl_distance = abs(entry - self.sl_level)
        if self.direction == "bullish":
            return entry + sl_distance * rr
        else:
            return entry - sl_distance * rr


# Active order blocks being tracked
_active_obs: list[OrderBlock] = []
_obs_lock = threading.Lock()

# Algo thread
_algo_thread: Optional[threading.Thread] = None
_algo_running = False


# ── MT5 helpers ───────────────────────────────────────────────────────────────

def _get_candles(symbol: str, timeframe_minutes: int, count: int) -> list[Candle]:
    """Fetch OHLCV candles from MT5."""
    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return []

    tf_map = {
        1: mt5.TIMEFRAME_M1,
        5: mt5.TIMEFRAME_M5,
        15: mt5.TIMEFRAME_M15,
        30: mt5.TIMEFRAME_M30,
        60: mt5.TIMEFRAME_H1,
        240: mt5.TIMEFRAME_H4,
        1440: mt5.TIMEFRAME_D1,
    }
    tf = tf_map.get(timeframe_minutes, mt5.TIMEFRAME_M15)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        return []

    candles = []
    for r in rates:
        candles.append(Candle(
            time=datetime.fromtimestamp(r['time']),
            open=float(r['open']),
            high=float(r['high']),
            low=float(r['low']),
            close=float(r['close']),
            volume=float(r['tick_volume']),
        ))
    return candles


def _get_current_price(symbol: str) -> Optional[float]:
    """Get current bid price."""
    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return None
    tick = mt5.symbol_info_tick(symbol)
    return tick.bid if tick else None


# ── Strategy logic ────────────────────────────────────────────────────────────

def _detect_fvg(c1: Candle, c2: Candle, c3: Candle) -> Optional[FairValueGap]:
    """
    Detect Fair Value Gap in 3-candle pattern.

    Bullish FVG: c2 is explosive bullish, gap between c1.high and c3.low
    Bearish FVG: c2 is explosive bearish, gap between c1.low and c3.high
    """
    # Check if c2 is explosive
    if c2.body_ratio < algo_config.fvg_min_body_ratio:
        return None

    if c2.is_bullish:
        # Bullish FVG: gap between c1 high and c3 low
        gap_bottom = c1.high
        gap_top = c3.low
        if gap_top > gap_bottom:
            return FairValueGap(
                direction="bullish",
                top=gap_top,
                bottom=gap_bottom,
                time=c2.time,
            )
    elif c2.is_bearish:
        # Bearish FVG: gap between c1 low and c3 high
        gap_top = c1.low
        gap_bottom = c3.high
        if gap_top > gap_bottom:
            return FairValueGap(
                direction="bearish",
                top=gap_top,
                bottom=gap_bottom,
                time=c2.time,
            )
    return None


def _detect_order_blocks(candles: list[Candle]) -> list[OrderBlock]:
    """
    Scan candles for Order Block + FVG patterns.
    Returns list of new OrderBlock objects.
    """
    obs = []
    if len(candles) < 3:
        return obs

    for i in range(len(candles) - 3):
        c1 = candles[i]
        c2 = candles[i + 1]
        c3 = candles[i + 2]

        fvg = _detect_fvg(c1, c2, c3)
        if not fvg:
            continue

        # Order block is c1 (the candle before the explosive move)
        ob_high = c1.high
        ob_low = c1.low
        ob_mid = (ob_high + ob_low) / 2

        ob_id = f"{fvg.direction}_{c1.time.strftime('%Y%m%d%H%M')}"

        ob = OrderBlock(
            id=ob_id,
            direction=fvg.direction,
            high=ob_high,
            low=ob_low,
            midpoint=ob_mid,
            time=c1.time,
            fvg=fvg,
        )
        obs.append(ob)

    return obs


def _calculate_ema(candles: list[Candle], period: int) -> Optional[float]:
    """Calculate EMA of close prices."""
    if len(candles) < period:
        return None
    closes = [c.close for c in candles]
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return ema


def _calculate_atr(candles: list[Candle], period: int) -> Optional[float]:
    """Calculate Average True Range."""
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        c = candles[i]
        prev_c = candles[i - 1]
        tr = max(
            c.high - c.low,
            abs(c.high - prev_c.close),
            abs(c.low - prev_c.close),
        )
        trs.append(tr)
    return sum(trs[-period:]) / period


def _is_trend_aligned(candles: list[Candle], direction: str) -> bool:
    """
    Trend filter: only trade in direction of EMA trend.
    Bullish OB requires price above EMA50.
    Bearish OB requires price below EMA50.
    """
    ema = _calculate_ema(candles, algo_config.trend_ema_period)
    if ema is None:
        return True  # no filter if not enough data
    current_price = candles[-1].close
    if direction == "bullish":
        return current_price > ema
    else:
        return current_price < ema


def _is_volatility_sufficient(candles: list[Candle]) -> bool:
    """
    Volatility filter: ATR must be above minimum threshold.
    Avoids trading in dead/choppy markets.
    """
    atr = _calculate_atr(candles, algo_config.atr_period)
    if atr is None:
        return True
    avg_atr = _calculate_atr(candles[:-algo_config.atr_period], algo_config.atr_period)
    if avg_atr is None:
        return True
    return atr >= avg_atr * algo_config.atr_min_multiplier


def _check_entry_signal(ob: OrderBlock, candles_exec: list[Candle]) -> Optional[float]:
    """
    Check if current price action gives entry signal on execution timeframe.

    Bullish entry: price retraces into OB zone (between OB low and OB midpoint)
                   AND last candle closes above OB midpoint
    Bearish entry: price retraces into OB zone (between OB midpoint and OB high)
                   AND last candle closes below OB midpoint

    Returns entry price if signal confirmed, None otherwise.
    """
    if len(candles_exec) < 2:
        return None

    last = candles_exec[-1]
    prev = candles_exec[-2]

    if ob.direction == "bullish":
        # Price must have touched the OB zone
        touched_zone = last.low <= ob.midpoint and last.low >= ob.low
        # Confirmation: close above midpoint
        confirmed = last.close > ob.midpoint and prev.close <= ob.midpoint
        if touched_zone and confirmed:
            return last.close

    elif ob.direction == "bearish":
        # Price must have touched the OB zone
        touched_zone = last.high >= ob.midpoint and last.high <= ob.high
        # Confirmation: close below midpoint
        confirmed = last.close < ob.midpoint and prev.close >= ob.midpoint
        if touched_zone and confirmed:
            return last.close

    return None


# ── Trade execution ───────────────────────────────────────────────────────────

def _execute_ob_trade(ob: OrderBlock, entry_price: float) -> bool:
    """Execute trade for confirmed Order Block setup."""
    sl = ob.sl_level
    tp = ob.tp_level(entry_price, algo_config.risk_reward_ratio)
    side = "buy" if ob.direction == "bullish" else "sell"

    logger.info(
        f"[ALGO] Order Block trade | {algo_config.symbol} {side.upper()} | "
        f"Entry: {entry_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f} | "
        f"OB zone: {ob.low:.5f}-{ob.high:.5f} | 50%: {ob.midpoint:.5f}"
    )

    result = mt5_bridge.open_trade(
        symbol=algo_config.symbol,
        side=side,
        sl=sl,
        tp=tp,
        entry=entry_price,
        comment=f"ALGO:OB:{ob.id[:8]}",
    )

    if result.get("success"):
        ob.trade_taken = True
        ob.ticket = result.get("ticket")
        ob.active = False  # deactivate after trade
        logger.success(
            f"[ALGO] Trade opened | Ticket: {ob.ticket} | "
            f"R:R 1:{algo_config.risk_reward_ratio}"
        )
        # Log to state
        state.signal_log.insert(0, {
            "time": datetime.now().isoformat(),
            "symbol": algo_config.symbol,
            "side": side,
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "status": "executed",
            "source": "ALGO:OrderBlock",
            "ob_id": ob.id,
        })
        return True
    else:
        logger.error(f"[ALGO] Trade failed: {result.get('message')}")
        return False


# ── Main scan loop ────────────────────────────────────────────────────────────

def _scan_and_trade() -> None:
    """
    Main algo loop:
    1. Fetch candles on analysis timeframe
    2. Detect new Order Blocks
    3. Apply trend + volatility filters
    4. Check entry signals on execution timeframe
    5. Execute trades
    """
    global _active_obs

    symbol = algo_config.symbol

    # Fetch analysis timeframe candles
    candles_analysis = _get_candles(symbol, algo_config.analysis_timeframe, algo_config.ob_lookback + 10)
    if len(candles_analysis) < algo_config.ob_lookback:
        logger.debug(f"[ALGO] Not enough candles for {symbol}")
        return

    # Detect new order blocks
    new_obs = _detect_order_blocks(candles_analysis)

    with _obs_lock:
        # Add new OBs (avoid duplicates)
        existing_ids = {ob.id for ob in _active_obs}
        for ob in new_obs:
            if ob.id not in existing_ids:
                # Apply trend filter
                if not _is_trend_aligned(candles_analysis, ob.direction):
                    logger.debug(f"[ALGO] OB {ob.id} filtered out — against trend")
                    continue
                # Apply volatility filter
                if not _is_volatility_sufficient(candles_analysis):
                    logger.debug(f"[ALGO] OB {ob.id} filtered out — low volatility")
                    continue
                _active_obs.append(ob)
                logger.info(
                    f"[ALGO] New {ob.direction} Order Block detected | "
                    f"Zone: {ob.low:.5f}-{ob.high:.5f} | 50%: {ob.midpoint:.5f} | "
                    f"Time: {ob.time}"
                )

        # Trim to max active OBs (keep most recent)
        _active_obs = sorted(_active_obs, key=lambda x: x.time, reverse=True)
        _active_obs = _active_obs[:algo_config.max_active_obs]

    # Check if bot is allowed to trade
    if not state.running:
        return

    # Check open positions — don't stack too many algo trades
    open_positions = mt5_bridge.get_open_positions()
    algo_positions = [p for p in open_positions if "ALGO:OB" in p.get("comment", "")]
    if len(algo_positions) >= 2:
        logger.debug(f"[ALGO] Max algo positions reached ({len(algo_positions)})")
        return

    # Fetch execution timeframe candles
    candles_exec = _get_candles(symbol, algo_config.execution_timeframe, 20)
    if len(candles_exec) < 5:
        return

    # Check each active OB for entry signal
    with _obs_lock:
        for ob in _active_obs:
            if not ob.active or ob.trade_taken:
                continue

            # Invalidate OB if price has blown through it
            current_price = _get_current_price(symbol)
            if current_price is None:
                continue

            if ob.direction == "bullish" and current_price < ob.low:
                ob.active = False
                logger.debug(f"[ALGO] Bullish OB {ob.id} invalidated — price below OB low")
                continue
            if ob.direction == "bearish" and current_price > ob.high:
                ob.active = False
                logger.debug(f"[ALGO] Bearish OB {ob.id} invalidated — price above OB high")
                continue

            # Check entry signal
            entry = _check_entry_signal(ob, candles_exec)
            if entry:
                logger.info(f"[ALGO] Entry signal confirmed for OB {ob.id} at {entry:.5f}")
                _execute_ob_trade(ob, entry)
                break  # one trade per scan


def _algo_loop() -> None:
    """Background thread that runs the algo scan loop."""
    global _algo_running
    logger.info(f"[ALGO] Order Block strategy started | Symbol: {algo_config.symbol} | "
                f"Analysis TF: {algo_config.analysis_timeframe}m | "
                f"Execution TF: {algo_config.execution_timeframe}m")

    while _algo_running:
        try:
            if algo_config.enabled and mt5_bridge.is_connected():
                _scan_and_trade()
        except Exception as e:
            logger.error(f"[ALGO] Scan error: {e}")

        time.sleep(algo_config.scan_interval_seconds)

    logger.info("[ALGO] Order Block strategy stopped.")


# ── Public API ────────────────────────────────────────────────────────────────

def start_algo() -> bool:
    """Start the algo trading thread."""
    global _algo_thread, _algo_running

    if _algo_running:
        logger.warning("[ALGO] Already running")
        return False

    algo_config.enabled = True   # always enable trading when started
    _algo_running = True
    _algo_thread = threading.Thread(target=_algo_loop, daemon=True, name="AlgoThread")
    _algo_thread.start()
    logger.success("[ALGO] Order Block strategy thread started (trading ENABLED)")
    return True


def stop_algo() -> bool:
    """Stop the algo trading thread."""
    global _algo_running

    if not _algo_running:
        return False

    _algo_running = False
    logger.info("[ALGO] Stopping Order Block strategy...")
    return True


def get_algo_status() -> dict:
    """Return current algo status and active order blocks."""
    with _obs_lock:
        obs_data = [
            {
                "id": ob.id,
                "direction": ob.direction,
                "high": ob.high,
                "low": ob.low,
                "midpoint": ob.midpoint,
                "time": ob.time.isoformat(),
                "active": ob.active,
                "trade_taken": ob.trade_taken,
                "ticket": ob.ticket,
            }
            for ob in _active_obs
        ]

    return {
        "running": _algo_running,
        "enabled": algo_config.enabled,
        "symbol": algo_config.symbol,
        "analysis_timeframe": algo_config.analysis_timeframe,
        "execution_timeframe": algo_config.execution_timeframe,
        "risk_reward": algo_config.risk_reward_ratio,
        "risk_percent": algo_config.risk_percent,
        "active_order_blocks": obs_data,
        "total_obs_tracked": len(_active_obs),
    }


def update_algo_config(
    symbol: Optional[str] = None,
    enabled: Optional[bool] = None,
    risk_reward: Optional[float] = None,
    risk_percent: Optional[float] = None,
    analysis_tf: Optional[int] = None,
    execution_tf: Optional[int] = None,
) -> dict:
    """Update algo configuration at runtime."""
    if symbol is not None:
        algo_config.symbol = symbol
    if enabled is not None:
        algo_config.enabled = enabled
    if risk_reward is not None:
        algo_config.risk_reward_ratio = risk_reward
    if risk_percent is not None:
        algo_config.risk_percent = risk_percent
    if analysis_tf is not None:
        algo_config.analysis_timeframe = analysis_tf
    if execution_tf is not None:
        algo_config.execution_timeframe = execution_tf

    logger.info(f"[ALGO] Config updated: {algo_config}")
    return get_algo_status()
