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
    scan_interval_seconds: int = 60     # how often to scan for new OB setups
    risk_check_interval_seconds: int = 1  # how often to check SL/profit lock on open trades
    max_trades_per_ob: int = 1          # max trades allowed per OB zone (1 = no re-entry after loss)
    enabled: bool = True                # True = trading enabled by default

    # ── Risk Management ───────────────────────────────────────────────────────
    daily_profit_limit: float = 50.0    # Stop trading if daily profit >= $50
    daily_loss_limit: float = 50.0      # Stop trading if daily loss >= $50
    max_drawdown_pct: float = 0.10      # Stop trading if drawdown >= 10%
    rr_breakeven: float = 1.0           # Move SL to breakeven at +1R
    rr_lock_profit: float = 2.0         # Lock +1R profit at +2R
    trail_atr_mult: float = 1.0         # ATR multiplier for trailing stop beyond +2R

    # ── Dollar-Based Profit Lock ──────────────────────────────────────────────
    dollar_profit_trigger: float = 15.0  # When floating profit >= $15...
    dollar_profit_lock: float = 10.0     # ...move SL to lock in $10 profit
    dollar_lock_enabled: bool = True     # Enable/disable dollar profit lock


# Global config instance
algo_config = AlgoConfig()

# ── Daily Risk Tracking ───────────────────────────────────────────────────────
from datetime import date as _date

_daily_pnl: float = 0.0
_daily_date: _date = _date.today()
_peak_equity: float = 0.0
_dd_halted: bool = False          # permanent halt on max drawdown
_daily_halted: bool = False       # daily halt on profit/loss limit


def _reset_daily_if_needed() -> None:
    """Reset daily counters at start of new day."""
    global _daily_pnl, _daily_date, _daily_halted
    today = _date.today()
    if _daily_date != today:
        _daily_date = today
        _daily_pnl = 0.0
        _daily_halted = False
        logger.info("[ALGO] Daily counters reset for new day")


def record_trade_pnl(pnl: float) -> None:
    """Call this after each trade closes to update daily PnL tracking."""
    global _daily_pnl, _daily_halted
    _reset_daily_if_needed()
    _daily_pnl += pnl
    logger.info(f"[ALGO] Daily PnL updated: {_daily_pnl:.2f}")

    if _daily_pnl >= algo_config.daily_profit_limit:
        _daily_halted = True
        logger.warning(f"[ALGO] ✅ Daily profit limit ${algo_config.daily_profit_limit} reached — halting for today")
    elif _daily_pnl <= -algo_config.daily_loss_limit:
        _daily_halted = True
        logger.warning(f"[ALGO] ⛔ Daily loss limit ${algo_config.daily_loss_limit} reached — halting for today")


def check_drawdown() -> bool:
    """Check if max drawdown exceeded. Returns True if trading should halt."""
    global _peak_equity, _dd_halted
    if _dd_halted:
        return True
    account = mt5_bridge.get_account_info()
    equity = account.get('equity', 0)
    if equity <= 0:
        return False
    if equity > _peak_equity:
        _peak_equity = equity
    if _peak_equity > 0:
        drawdown = (_peak_equity - equity) / _peak_equity
        if drawdown >= algo_config.max_drawdown_pct:
            _dd_halted = True
            logger.error(f"[ALGO] ⛔ Max drawdown {drawdown:.1%} exceeded — trading halted permanently")
            return True
    return False


def can_trade() -> bool:
    """Return True if risk rules allow a new trade."""
    _reset_daily_if_needed()
    if _dd_halted:
        logger.debug("[ALGO] Trading halted: max drawdown exceeded")
        return False
    if _daily_halted:
        logger.debug("[ALGO] Trading halted: daily profit/loss limit reached")
        return False
    return True


def get_risk_status() -> dict:
    """Return current risk management status."""
    _reset_daily_if_needed()
    account = mt5_bridge.get_account_info()
    equity = account.get('equity', 0)
    drawdown = (_peak_equity - equity) / _peak_equity if _peak_equity > 0 else 0.0
    return {
        "daily_pnl": round(_daily_pnl, 2),
        "daily_profit_limit": algo_config.daily_profit_limit,
        "daily_loss_limit": algo_config.daily_loss_limit,
        "daily_halted": _daily_halted,
        "dd_halted": _dd_halted,
        "current_drawdown_pct": round(drawdown * 100, 2),
        "max_drawdown_pct": algo_config.max_drawdown_pct * 100,
        "peak_equity": round(_peak_equity, 2),
        "can_trade": can_trade(),
    }



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
    trade_count: int = 0            # how many trades taken on this OB zone
    # R-multiple tracking fields
    entry_price: float = 0.0
    initial_sl: float = 0.0
    one_r: float = 0.0
    r_stage: int = 0        # 0=initial, 1=breakeven, 2=locked, 3=trailing
    # Dollar-based profit lock
    dollar_lock_applied: bool = False   # True once $-based SL lock is applied

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

# Algo threads
_algo_thread: Optional[threading.Thread] = None
_risk_thread: Optional[threading.Thread] = None
_algo_running = False


# ── MT5 helpers ───────────────────────────────────────────────────────────────

def _get_candles(symbol: str, timeframe_minutes: int, count: int) -> list[Candle]:
    """Fetch OHLCV candles from MT5 or via Windows bridge."""
    from bot import mt5_bridge as _bridge

    # Bridge mode (Ubuntu VPS → Windows PC)
    if _bridge.USE_BRIDGE:
        try:
            response = _bridge._call_bridge(
                f"/candles?symbol={symbol}&timeframe={timeframe_minutes}&count={count}"
            )
            if response and isinstance(response, list):
                candles = []
                for r in response:
                    candles.append(Candle(
                        time=datetime.fromisoformat(r['time']) if isinstance(r['time'], str) else datetime.fromtimestamp(r['time']),
                        open=float(r['open']),
                        high=float(r['high']),
                        low=float(r['low']),
                        close=float(r['close']),
                        volume=float(r.get('volume', r.get('tick_volume', 0))),
                    ))
                return candles
        except Exception as e:
            logger.warning(f"[ALGO] Bridge candles fetch failed: {e}")
        return []

    # Direct MT5 mode (Windows only)
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
    """Get current bid price from MT5 or via Windows bridge."""
    from bot import mt5_bridge as _bridge

    # Bridge mode
    if _bridge.USE_BRIDGE:
        try:
            response = _bridge._call_bridge(f"/price?symbol={symbol}")
            if response and "bid" in response:
                return float(response["bid"])
        except Exception as e:
            logger.warning(f"[ALGO] Bridge price fetch failed: {e}")
        return None

    # Direct MT5 mode
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
    """Execute trade for confirmed Order Block setup with full risk management."""

    # ── Risk management gate ──────────────────────────────────────────────────
    if not can_trade():
        logger.info("[ALGO] Trade blocked by risk management rules")
        return False

    if check_drawdown():
        logger.info("[ALGO] Trade blocked: max drawdown exceeded")
        return False

    sl = ob.sl_level
    tp = ob.tp_level(entry_price, algo_config.risk_reward_ratio)
    side = "buy" if ob.direction == "bullish" else "sell"

    # 1R = distance between entry and stop loss
    one_r = abs(entry_price - sl)

    logger.info(
        f"[ALGO] Order Block trade | {algo_config.symbol} {side.upper()} | "
        f"Entry: {entry_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f} | "
        f"1R: {one_r:.5f} | OB zone: {ob.low:.5f}-{ob.high:.5f} | 50%: {ob.midpoint:.5f}"
    )

    result = mt5_bridge.open_trade(
        symbol=algo_config.symbol,
        side=side,
        sl=sl,
        tp=tp,
        entry=entry_price,
        order_type="market",
        risk_percent=algo_config.risk_percent,
        comment=f"ALGO:OB:{ob.id[:8]}",
    )

    if result.get("success"):
        ob.trade_taken = True
        ob.ticket = result.get("ticket")
        ob.active = False
        ob.trade_count += 1
        ob.entry_price = entry_price
        ob.initial_sl = sl
        ob.one_r = one_r
        ob.r_stage = 0  # 0=initial, 1=breakeven, 2=locked, 3=trailing
        logger.success(
            f"[ALGO] Trade opened | Ticket: {ob.ticket} | "
            f"R:R 1:{algo_config.risk_reward_ratio} | 1R=${one_r:.5f}"
        )
        state.signal_log.insert(0, {
            "time": datetime.now().isoformat(),
            "symbol": algo_config.symbol,
            "side": side,
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "one_r": one_r,
            "status": "executed",
            "source": "ALGO:OrderBlock",
            "ob_id": ob.id,
        })
        return True
    else:
        logger.error(f"[ALGO] Trade failed: {result.get('message')}")
        return False


def _manage_open_trade_risk(ob: OrderBlock) -> None:
    """
    R-Multiple trailing stop management for open trades.

    Stage 0 → 1: At +1R → move SL to breakeven
    Stage 1 → 2: At +2R → lock in +1R profit
    Stage 2 → 3: Beyond +2R → trail by ATR × trail_atr_mult

    Dollar-based profit lock (independent of R stages):
    When floating profit >= dollar_profit_trigger ($15) → move SL to lock
    dollar_profit_lock ($10) profit, if not already applied.
    """
    if not ob.ticket or not hasattr(ob, 'one_r') or ob.one_r <= 0:
        return

    # Get current price
    current_price = _get_current_price(algo_config.symbol)
    if current_price is None:
        return

    side = "buy" if ob.direction == "bullish" else "sell"
    entry = ob.entry_price
    one_r = ob.one_r

    if side == "buy":
        profit_r = (current_price - entry) / one_r
    else:
        profit_r = (entry - current_price) / one_r

    new_sl = None

    # ── Dollar-based profit lock (checked first, independent of R stages) ────
    if (
        algo_config.dollar_lock_enabled
        and not ob.dollar_lock_applied
    ):
        # Fetch live floating profit from open positions
        try:
            open_positions = mt5_bridge.get_open_positions()
            for pos in open_positions:
                if pos.get("id") == ob.ticket or pos.get("position_id") == ob.ticket:
                    floating_pnl = float(pos.get("pnl", 0))
                    if floating_pnl >= algo_config.dollar_profit_trigger:
                        # Calculate the price at which $dollar_profit_lock is locked
                        # profit = (price - entry) * volume * contract_size  ← MT5 handles this
                        # We need: new_sl such that if price hits new_sl, profit = $lock_amount
                        # Approximation: price_offset = lock_amount / (floating_pnl / price_offset_current)
                        # Simpler: lock_sl_offset = (entry_to_current_offset) * (lock_amount / floating_pnl)
                        current_offset = abs(current_price - entry)
                        if current_offset > 0 and floating_pnl > 0:
                            lock_offset = current_offset * (algo_config.dollar_profit_lock / floating_pnl)
                            if side == "buy":
                                dollar_lock_sl = entry + lock_offset
                            else:
                                dollar_lock_sl = entry - lock_offset

                            # Only apply if this SL is better than current SL
                            current_sl = ob.initial_sl
                            is_better = (side == "buy" and dollar_lock_sl > current_sl) or \
                                        (side == "sell" and dollar_lock_sl < current_sl)
                            if is_better:
                                new_sl = dollar_lock_sl
                                ob.dollar_lock_applied = True
                                logger.info(
                                    f"[ALGO] 💰 Dollar profit lock triggered | "
                                    f"Floating P&L=${floating_pnl:.2f} >= ${algo_config.dollar_profit_trigger} | "
                                    f"Locking ${algo_config.dollar_profit_lock} profit @ SL={dollar_lock_sl:.5f}"
                                )
                    break
        except Exception as e:
            logger.warning(f"[ALGO] Dollar profit lock check failed: {e}")

    # ── R-Multiple stages ─────────────────────────────────────────────────────
    if profit_r >= algo_config.rr_lock_profit and ob.r_stage < 2:
        # +2R reached → lock in +1R profit
        if side == "buy":
            r_sl = entry + one_r
        else:
            r_sl = entry - one_r
        ob.r_stage = 2
        logger.info(f"[ALGO] +2R reached — locking +1R profit @ SL={r_sl:.5f}")
        # Take the better of dollar lock and R lock
        if new_sl is None:
            new_sl = r_sl
        else:
            new_sl = max(new_sl, r_sl) if side == "buy" else min(new_sl, r_sl)

    elif profit_r >= algo_config.rr_breakeven and ob.r_stage < 1:
        # +1R reached → move to breakeven
        r_sl = entry
        ob.r_stage = 1
        logger.info(f"[ALGO] +1R reached — moving SL to breakeven @ {r_sl:.5f}")
        if new_sl is None:
            new_sl = r_sl
        else:
            new_sl = max(new_sl, r_sl) if side == "buy" else min(new_sl, r_sl)

    if ob.r_stage >= 2:
        # Beyond +2R → trail by ATR
        candles = _get_candles(algo_config.symbol, algo_config.execution_timeframe, 20)
        atr = _calculate_atr(candles, algo_config.atr_period) if candles else None
        if atr:
            if side == "buy":
                trail_sl = current_price - atr * algo_config.trail_atr_mult
                if new_sl is None or trail_sl > new_sl:
                    new_sl = trail_sl
                    ob.r_stage = 3
            else:
                trail_sl = current_price + atr * algo_config.trail_atr_mult
                if new_sl is None or trail_sl < new_sl:
                    new_sl = trail_sl
                    ob.r_stage = 3

    # Apply new SL if it improves position
    if new_sl is not None:
        current_sl = ob.initial_sl
        should_update = (side == "buy" and new_sl > current_sl) or \
                        (side == "sell" and new_sl < current_sl)
        if should_update:
            result = mt5_bridge.modify_position(ob.ticket, sl=new_sl)
            if result.get("success"):
                ob.initial_sl = new_sl
                logger.info(f"[ALGO] SL updated to {new_sl:.5f} (stage={ob.r_stage})")




# ── Main scan loop ────────────────────────────────────────────────────────────

def _scan_and_trade() -> None:
    """
    Main algo loop:
    1. Check risk management gates (drawdown, daily limits)
    2. Check for closed trades and record PnL
    3. Fetch candles on analysis timeframe
    4. Detect new Order Blocks
    5. Apply trend + volatility filters
    6. Check entry signals on execution timeframe
    7. Execute trades

    Note: Open trade SL/profit-lock management runs in _risk_check_loop (1s).
    """
    global _active_obs

    symbol = algo_config.symbol

    # ── Risk management checks ────────────────────────────────────────────────
    check_drawdown()

    # ── Check for closed trades and record PnL ────────────────────────────────
    open_positions = mt5_bridge.get_open_positions()
    open_tickets = {p.get("id") for p in open_positions}

    with _obs_lock:
        for ob in _active_obs:
            if ob.trade_taken and ob.ticket and ob.ticket not in open_tickets:
                # Reset OB for potential re-entry ONLY if trade was profitable
                # (avoid re-entering same losing zone repeatedly)
                pnl_val = 0.0
                try:
                    history = mt5_bridge.get_trade_history(limit=10)
                    for t in history:
                        if t.get("ticket") == ob.ticket or t.get("position_id") == ob.ticket:
                            pnl_val = float(t.get("pnl", 0))
                            record_trade_pnl(pnl_val)
                            logger.info(f"[ALGO] Trade {ob.ticket} closed | PnL={pnl_val:.2f}")
                            break
                except Exception as e:
                    logger.warning(f"[ALGO] Could not fetch PnL for ticket {ob.ticket}: {e}")

                if pnl_val >= 0:
                    # Profitable/breakeven — allow re-entry on this OB
                    logger.info(f"[ALGO] OB {ob.id} closed with profit — resetting for re-entry")
                    ob.trade_taken = False
                    ob.active = True
                else:
                    # Loss — permanently deactivate this OB zone
                    logger.info(f"[ALGO] OB {ob.id} closed at loss (${pnl_val:.2f}) — deactivating zone")
                    ob.trade_taken = False
                    ob.active = False  # do NOT re-enter a losing OB zone
                ob.ticket = None
                ob.r_stage = 0
                ob.dollar_lock_applied = False

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

        # Trim to max active OBs (keep most recent) — remove traded/inactive first
        _active_obs = [o for o in _active_obs if o.active or o.trade_taken]
        _active_obs = sorted(_active_obs, key=lambda x: x.time, reverse=True)
        _active_obs = _active_obs[:algo_config.max_active_obs]

    # Check if bot is allowed to trade
    if not state.running:
        return

    # Check risk management rules before entering new trades
    if not algo_config.enabled:
        return
    if not can_trade():
        return

    # Check open positions — don't stack too many algo trades
    open_positions = mt5_bridge.get_open_positions()
    open_tickets = {p.get("id") for p in open_positions}
    algo_positions = [p for p in open_positions if "ALGO:OB" in p.get("comment", "")]

    # If a traded OB's position was manually closed, allow re-trading
    with _obs_lock:
        for ob in _active_obs:
            if ob.trade_taken and ob.ticket and ob.ticket not in open_tickets:
                # Position was manually closed — reset OB to allow new trade
                logger.info(f"[ALGO] OB {ob.id} position manually closed — resetting for re-entry")
                ob.trade_taken = False
                ob.active = True
                ob.ticket = None
                ob.dollar_lock_applied = False
                ob.r_stage = 0

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

            # Skip OB if max trades already taken on this zone
            if ob.trade_count >= algo_config.max_trades_per_ob:
                ob.active = False
                logger.debug(f"[ALGO] OB {ob.id} max trades reached ({ob.trade_count}) — deactivating")
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


def _risk_check_loop() -> None:
    """
    High-frequency loop (every 1 second) for open trade risk management:
    - Dollar-based profit lock ($15 → lock $10)
    - R-multiple trailing stop updates (breakeven, lock, trail)

    Kept separate from OB scan loop to avoid heavy candle fetches every second.
    """
    global _algo_running
    logger.info("[ALGO] Risk check loop started (1s interval)")

    while _algo_running:
        try:
            if mt5_bridge.is_connected():
                open_positions = mt5_bridge.get_open_positions()
                open_tickets = {p.get("id") for p in open_positions}

                with _obs_lock:
                    for ob in _active_obs:
                        if ob.ticket and ob.ticket in open_tickets and ob.trade_taken:
                            _manage_open_trade_risk(ob)
        except Exception as e:
            logger.error(f"[ALGO] Risk check error: {e}")

        time.sleep(algo_config.risk_check_interval_seconds)

    logger.info("[ALGO] Risk check loop stopped.")


def _algo_loop() -> None:
    """
    Main algo loop (every 60 seconds) for OB detection and new trade entries:
    1. Check risk management gates (drawdown, daily limits)
    2. Check for closed trades and record PnL
    3. Fetch candles on analysis timeframe
    4. Detect new Order Blocks
    5. Apply trend + volatility filters
    6. Check entry signals on execution timeframe
    7. Execute trades

    Note: Open trade risk management (SL/profit lock) runs in _risk_check_loop
    at 1-second intervals for faster response.
    """
    global _algo_running
    logger.info(f"[ALGO] Order Block strategy started | Symbol: {algo_config.symbol} | "
                f"Analysis TF: {algo_config.analysis_timeframe}m | "
                f"Execution TF: {algo_config.execution_timeframe}m")

    while _algo_running:
        try:
            if mt5_bridge.is_connected():
                _scan_and_trade()
        except Exception as e:
            logger.error(f"[ALGO] Scan error: {e}")

        time.sleep(algo_config.scan_interval_seconds)

    logger.info("[ALGO] Order Block strategy stopped.")


# ── Public API ────────────────────────────────────────────────────────────────

def start_algo() -> bool:
    """Start the algo trading thread."""
    global _algo_thread, _risk_thread, _algo_running

    if _algo_running:
        logger.warning("[ALGO] Already running")
        return False

    _algo_running = True

    # OB scan thread — runs every 60s for candle analysis and new entries
    _algo_thread = threading.Thread(target=_algo_loop, daemon=True, name="AlgoThread")
    _algo_thread.start()

    # Risk check thread — runs every 1s for SL/profit-lock management
    _risk_thread = threading.Thread(target=_risk_check_loop, daemon=True, name="AlgoRiskThread")
    _risk_thread.start()

    logger.success(
        f"[ALGO] Order Block strategy started | "
        f"OB scan: {algo_config.scan_interval_seconds}s | "
        f"Risk check: {algo_config.risk_check_interval_seconds}s | "
        f"{'trading ENABLED' if algo_config.enabled else 'scan-only mode'}"
    )
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
