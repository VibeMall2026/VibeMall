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
from bot import config as _config
from bot.state import state


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class AlgoConfig:
    symbol: str = "XAUUSD"
    symbols: list = None  # Multi-symbol list — if set, overrides symbol
    analysis_timeframe: int = 15        # minutes — for OB/FVG detection
    execution_timeframe: int = 5        # minutes — for entry confirmation
    risk_reward_ratio: float = 2.0      # minimum R:R (1:2)
    risk_percent: float = 1.0           # % of balance per trade
    fvg_min_body_ratio: float = 0.6     # explosive candle body/range ratio
    ob_lookback: int = 50               # candles to scan for OBs
    trend_ema_period: int = 50          # EMA period for trend filter
    trend_timeframe_minutes: int = 60   # higher timeframe for trend confirmation
    require_trend_alignment: bool = False
    atr_period: int = 14                # ATR period for volatility filter
    atr_min_multiplier: float = 0.5     # min ATR as fraction of avg ATR
    max_active_obs: int = 10            # max order blocks tracked at once (2 per symbol)
    scan_interval_seconds: int = 60     # how often to scan for new OB setups
    risk_check_interval_seconds: int = 1  # how often to check SL/profit lock on open trades
    max_trades_per_ob: int = 1          # max trades allowed per OB zone (1 = no re-entry after loss)
    enabled: bool = True                # True = trading enabled by default

    # ── Risk Management ───────────────────────────────────────────────────────
    daily_profit_limit: float = 50.0    # Stop trading if daily profit >= $50
    daily_loss_limit: float = 30.0      # Stop trading if daily loss >= $30
    max_drawdown_pct: float = 0.10      # Stop trading if drawdown >= 10%
    rr_breakeven: float = 1.0           # Move SL to breakeven at +1R
    rr_lock_profit: float = 1.5         # Lock +1R profit at +1.5R
    trail_atr_mult: float = 0.8         # ATR multiplier for trailing stop (tighter)
    entry_max_mid_distance_atr: float = 0.35  # reject entries too far from OB midpoint
    require_entry_momentum: bool = False
    require_entry_distance_check: bool = False

    # ── Strong Trailing Stop (recommended) ────────────────────────────────────
    # Tight "smart" trailing that follows recent swing highs/lows with a small ATR buffer.
    # Starts early to protect open profit, while still respecting a minimum step and cooldown.
    strong_trailing_enabled: bool = True
    strong_trailing_start_r: float = 0.30          # start trailing once trade is +0.3R
    strong_trailing_swing_lookback: int = 3        # candles to use for swing high/low
    strong_trailing_atr_buffer_mult: float = 0.15  # buffer = ATR * this
    strong_trailing_min_step_r: float = 0.05       # only update if SL improves by >= 0.05R
    strong_trailing_min_update_seconds: int = 5    # minimum seconds between SL updates
    # ── Dollar-Based Profit Lock ──────────────────────────────────────────────
    dollar_profit_trigger: float = 8.0   # When floating profit >= $8...
    dollar_profit_lock: float = 5.0      # ...move SL to lock in $5 profit
    dollar_lock_enabled: bool = True     # Enable/disable dollar profit lock


    def get_symbols(self) -> list:
        """Return list of symbols to trade."""
        if self.symbols:
            return self.symbols
        return [self.symbol]


# Global config instance
algo_config = AlgoConfig()
algo_config.symbols = ["XAUUSD", "EURUSD", "USDJPY", "GBPUSD", "USDCHF"]


def _normalize_symbols(symbol_value: Optional[str]) -> list[str]:
    """Normalize a single symbol or comma-separated symbol list."""
    if not symbol_value:
        return []
    return [part.strip().upper() for part in str(symbol_value).split(",") if part.strip()]

# ── Daily Risk Tracking ───────────────────────────────────────────────────────
from datetime import date as _date

_daily_pnl: float = 0.0
_daily_date: _date = _date.today()
_peak_equity: float = 0.0
_dd_halted: bool = False          # permanent halt on max drawdown
_peak_equity_by_account: dict[str, float] = {}
_dd_halted_by_account: dict[str, bool] = {}
_daily_halted: bool = False       # daily halt on profit/loss limit
_last_scan_at: Optional[str] = None
_last_scan_summary: dict[str, dict] = {}
_last_recovery_at: float = 0.0


def _ob_debug(event: str, **payload) -> None:
    """Structured debug logs gated by OB_DEBUG_MODE."""
    if not getattr(_config, "OB_DEBUG_MODE", False):
        return
    bits = [f"{k}={v}" for k, v in payload.items()]
    logger.info(f"[ALGO][{event}] " + " | ".join(bits))


def _recover_tracked_ob_positions() -> int:
    """
    Rebuild minimal tracked OB objects from currently open ALGO:OB positions.
    This allows risk/trailing management to continue after bot restart.
    """
    recovered = 0
    try:
        open_positions = mt5_bridge.get_open_positions()
    except Exception:
        return 0

    with _obs_lock:
        for pos in open_positions:
            comment = str(pos.get("comment", "") or "")
            if "ALGO:OB" not in comment:
                continue
            ticket = pos.get("id", pos.get("position_id"))
            symbol = str(pos.get("symbol", "") or "").upper()
            side = str(pos.get("side", "") or "").lower()
            entry_price = float(pos.get("entry", 0) or 0)
            sl = float(pos.get("sl", 0) or 0)
            if not ticket or not symbol or entry_price <= 0 or sl <= 0:
                continue

            # Already tracked?
            existing = _active_obs.get(symbol, [])
            if any(ob.ticket == ticket and ob.trade_taken for ob in existing):
                continue

            direction = "bullish" if side == "buy" else "bearish"
            one_r = abs(entry_price - sl)
            if one_r <= 0:
                continue

            # Minimal synthetic OB for risk-management continuity.
            fake = OrderBlock(
                id=f"recovered_{ticket}",
                direction=direction,
                high=entry_price,
                low=entry_price,
                midpoint=entry_price,
                time=datetime.utcnow(),
                fvg=FairValueGap(direction=direction, top=entry_price, bottom=entry_price, time=datetime.utcnow()),
                symbol=symbol,
                active=False,
                trade_taken=True,
                ticket=ticket,
            )
            fake.entry_price = entry_price
            fake.initial_sl = sl
            fake.one_r = one_r
            fake.r_stage = 0
            fake.dollar_lock_applied = False

            _active_obs.setdefault(symbol, []).append(fake)
            recovered += 1

    if recovered:
        logger.info(f"[ALGO] Recovered {recovered} open ALGO:OB position(s) after restart")
    return recovered


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
    account = mt5_bridge.get_account_info()
    account_key = str(account.get("login") or account.get("account") or "global")
    peak_equity = float(_peak_equity_by_account.get(account_key, 0.0) or 0.0)
    dd_halted = bool(_dd_halted_by_account.get(account_key, False))
    if dd_halted:
        _peak_equity = peak_equity
        _dd_halted = True
        return True

    equity = account.get('equity', 0)
    if equity <= 0:
        return False

    if equity > peak_equity:
        peak_equity = float(equity)
        _peak_equity_by_account[account_key] = peak_equity

    if peak_equity > 0:
        drawdown = (peak_equity - equity) / peak_equity
        if drawdown >= algo_config.max_drawdown_pct:
            _dd_halted_by_account[account_key] = True
            _peak_equity = peak_equity
            _dd_halted = True
            logger.error(f"[ALGO] Max drawdown {drawdown:.1%} exceeded on account={account_key} - trading halted")
            return True

    _peak_equity = peak_equity
    _dd_halted = bool(_dd_halted_by_account.get(account_key, False))
    return False

def check_daily_loss_realtime() -> bool:
    """
    Real-time daily loss check using live floating PnL.
    Returns True if daily loss limit exceeded (should halt trading).
    Checks: closed PnL + open floating PnL combined.
    """
    global _daily_halted
    _reset_daily_if_needed()
    if _daily_halted:
        return True

    # Get floating PnL from open positions
    try:
        open_positions = mt5_bridge.get_open_positions()
        floating_pnl = sum(float(p.get('pnl', 0)) for p in open_positions)
    except Exception:
        floating_pnl = 0.0

    total_pnl = _daily_pnl + floating_pnl

    if total_pnl <= -algo_config.daily_loss_limit:
        _daily_halted = True
        logger.warning(
            f"[ALGO] ⛔ Daily loss limit ${algo_config.daily_loss_limit} reached "
            f"(closed: ${_daily_pnl:.2f} + floating: ${floating_pnl:.2f} = ${total_pnl:.2f}) "
            f"— halting trading for today"
        )
        return True

    if total_pnl >= algo_config.daily_profit_limit:
        _daily_halted = True
        logger.warning(
            f"[ALGO] ✅ Daily profit target ${algo_config.daily_profit_limit} reached "
            f"(${total_pnl:.2f}) — halting trading for today"
        )
        return True

    return False


def can_trade() -> bool:
    """Return True if risk rules allow a new trade."""
    _reset_daily_if_needed()
    if check_drawdown():
        logger.debug("[ALGO] Trading halted: max drawdown exceeded")
        return False
    if _daily_halted:
        logger.debug("[ALGO] Trading halted: daily profit/loss limit reached")
        return False
    # Real-time check: floating + closed PnL
    if check_daily_loss_realtime():
        return False
    return True


def get_risk_status() -> dict:
    """Return current risk management status."""
    _reset_daily_if_needed()
    account = mt5_bridge.get_account_info()
    account_key = str(account.get("login") or account.get("account") or "global")
    equity = account.get('equity', 0)
    balance = account.get('balance', 0)
    peak_equity = float(_peak_equity_by_account.get(account_key, _peak_equity) or 0.0)
    dd_halted = bool(_dd_halted_by_account.get(account_key, _dd_halted))
    drawdown = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
    drawdown_amount = max(peak_equity - equity, 0.0) if peak_equity > 0 else 0.0
    max_dd_amount = (peak_equity * algo_config.max_drawdown_pct) if peak_equity > 0 else 0.0
    remaining_dd_amount = max(max_dd_amount - drawdown_amount, 0.0)
    remaining_dd_pct = max((algo_config.max_drawdown_pct - drawdown) * 100, 0.0)
    dd_used_pct_of_limit = min((drawdown / algo_config.max_drawdown_pct) * 100, 100.0) if algo_config.max_drawdown_pct > 0 else 0.0
    try:
        open_positions = mt5_bridge.get_open_positions()
        floating_pnl = sum(float(p.get('pnl', 0)) for p in open_positions)
    except Exception:
        floating_pnl = 0.0
    allowed = can_trade()
    return {
        "daily_pnl": round(_daily_pnl, 2),
        "floating_pnl": round(floating_pnl, 2),
        "total_daily_pnl": round(_daily_pnl + floating_pnl, 2),
        "daily_profit_limit": algo_config.daily_profit_limit,
        "daily_loss_limit": algo_config.daily_loss_limit,
        "daily_halted": _daily_halted,
        "dd_halted": dd_halted,
        "balance": round(balance, 2),
        "equity": round(equity, 2),
        "current_drawdown_pct": round(drawdown * 100, 2),
        "current_drawdown_amount": round(drawdown_amount, 2),
        "max_drawdown_pct": algo_config.max_drawdown_pct * 100,
        "max_drawdown_amount": round(max_dd_amount, 2),
        "remaining_drawdown_pct": round(remaining_dd_pct, 2),
        "remaining_drawdown_amount": round(remaining_dd_amount, 2),
        "drawdown_used_pct_of_limit": round(dd_used_pct_of_limit, 2),
        "peak_equity": round(peak_equity, 2),
        "account_key": account_key,
        "can_trade": bool(allowed),
    }


def reset_risk_halts(reset_peak_equity: bool = False) -> dict:
    """
    Manually clear risk halts so trading can resume.
    Use with care: this overrides automatic protections.
    """
    global _daily_halted, _dd_halted, _daily_pnl, _daily_date, _peak_equity
    _daily_halted = False
    _daily_pnl = 0.0
    _daily_date = _date.today()
    account = mt5_bridge.get_account_info()
    account_key = str(account.get("login") or account.get("account") or "global")
    _dd_halted_by_account[account_key] = False
    _dd_halted = False
    if reset_peak_equity:
        _peak_equity_by_account[account_key] = 0.0
        _peak_equity = 0.0
    logger.warning(
        "[ALGO] Manual risk reset applied | daily_halted=False dd_halted=False "
        f"reset_peak_equity={reset_peak_equity}"
    )
    return get_risk_status()



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
    direction: str
    high: float             # OB high
    low: float              # OB low
    midpoint: float         # 50% level — key entry zone
    time: datetime
    fvg: FairValueGap
    symbol: str = "XAUUSD"  # symbol this OB was detected on
    atr: float = 0.0        # ATR at time of detection — used for SL/TP
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
        """Stop loss level — ATR-based (1.5x ATR from OB boundary).
        Falls back to OB zone if ATR not available.
        """
        ob_size = self.high - self.low
        # Use ATR if available, else use OB size as proxy
        buffer = (self.atr * 1.5) if self.atr > 0 else (ob_size * 0.5)
        if self.direction == "bullish":
            return self.low - buffer
        else:
            return self.high + buffer

    def tp_level(self, entry: float, rr: float) -> float:
        """Take profit based on R:R ratio."""
        sl_distance = abs(entry - self.sl_level)
        if self.direction == "bullish":
            return entry + sl_distance * rr
        else:
            return entry - sl_distance * rr


# Active order blocks being tracked
_active_obs: dict[str, list] = {}  # keyed by symbol
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


def _get_current_price(symbol: str, side: Optional[str] = None) -> Optional[float]:
    """Get live price from MT5/bridge. side='buy' -> ask, side='sell' -> bid, else midpoint."""
    from bot import mt5_bridge as _bridge

    # Bridge mode
    if _bridge.USE_BRIDGE:
        try:
            response = _bridge._call_bridge(f"/price?symbol={symbol}")
            if response and "bid" in response and "ask" in response:
                bid = float(response["bid"])
                ask = float(response["ask"])
                if side == "buy":
                    return ask
                if side == "sell":
                    return bid
                return (bid + ask) / 2.0
            if response and "bid" in response:
                return float(response["bid"])
        except Exception as e:
            logger.warning(f"[ALGO] Bridge price fetch failed: {e}")
        return None

    # Direct MT5 mode
    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return None
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return None
    if side == "buy":
        return tick.ask
    if side == "sell":
        return tick.bid
    return (tick.bid + tick.ask) / 2.0


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

    # Need 3-candle windows: indices (i, i+1, i+2) => i in [0, len-3]
    for i in range(len(candles) - 2):
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
    atr_exec = _calculate_atr(candles_exec, min(algo_config.atr_period, max(2, len(candles_exec) - 1)))
    max_mid_distance = (atr_exec * algo_config.entry_max_mid_distance_atr) if atr_exec else None

    if ob.direction == "bullish":
        # Price must have touched the OB zone
        touched_zone = last.low <= ob.midpoint and last.low >= ob.low
        # Confirmation: close above midpoint
        confirmed = last.close > ob.midpoint and prev.close <= ob.midpoint
        momentum_ok = (last.close > last.open) if algo_config.require_entry_momentum else True
        distance_ok = (
            True
            if (not algo_config.require_entry_distance_check or max_mid_distance is None)
            else abs(last.close - ob.midpoint) <= max_mid_distance
        )
        logger.debug(
            f"[ALGO][ENTRY_CHECK] {ob.id} bullish | touched={touched_zone} confirmed={confirmed} "
            f"| last(o={last.open:.5f} h={last.high:.5f} l={last.low:.5f} c={last.close:.5f}) "
            f"| prev(c={prev.close:.5f}) | zone=({ob.low:.5f}-{ob.midpoint:.5f})"
        )
        if touched_zone and confirmed and momentum_ok and distance_ok:
            _ob_debug(
                "ENTRY_DECISION",
                symbol=ob.symbol,
                ob_id=ob.id,
                direction=ob.direction,
                trend_ok="n/a",
                touched=touched_zone,
                confirmed=confirmed,
                reject_reason="",
            )
            return last.close

    elif ob.direction == "bearish":
        # Price must have touched the OB zone
        touched_zone = last.high >= ob.midpoint and last.high <= ob.high
        # Confirmation: close below midpoint
        confirmed = last.close < ob.midpoint and prev.close >= ob.midpoint
        momentum_ok = (last.close < last.open) if algo_config.require_entry_momentum else True
        distance_ok = (
            True
            if (not algo_config.require_entry_distance_check or max_mid_distance is None)
            else abs(last.close - ob.midpoint) <= max_mid_distance
        )
        logger.debug(
            f"[ALGO][ENTRY_CHECK] {ob.id} bearish | touched={touched_zone} confirmed={confirmed} "
            f"| last(o={last.open:.5f} h={last.high:.5f} l={last.low:.5f} c={last.close:.5f}) "
            f"| prev(c={prev.close:.5f}) | zone=({ob.midpoint:.5f}-{ob.high:.5f})"
        )
        if touched_zone and confirmed and momentum_ok and distance_ok:
            _ob_debug(
                "ENTRY_DECISION",
                symbol=ob.symbol,
                ob_id=ob.id,
                direction=ob.direction,
                trend_ok="n/a",
                touched=touched_zone,
                confirmed=confirmed,
                reject_reason="",
            )
            return last.close

    _ob_debug(
        "ENTRY_DECISION",
        symbol=ob.symbol,
        ob_id=ob.id,
        direction=ob.direction,
        trend_ok="n/a",
        touched=touched_zone if "touched_zone" in locals() else False,
        confirmed=confirmed if "confirmed" in locals() else False,
        reject_reason="entry_condition_not_met",
    )
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

    # ── $10 SL / $10 TP hard cap ──────────────────────────────────────────────
    # Cap SL and TP so that max loss = $10 and max profit = $10 per trade.
    try:
        _cap_usd = 10.0
        _sl_dist = abs(entry_price - sl)
        _tp_dist = abs(tp - entry_price)
        _max_dist = None

        if MT5_AVAILABLE and mt5_bridge.is_connected():
            import MetaTrader5 as _mt5
            _sym = _mt5.symbol_info(ob.symbol)
            _tick = _mt5.symbol_info_tick(ob.symbol)
            if _sym and _tick:
                _price = _tick.ask if side == "buy" else _tick.bid
                _lot = max(_sym.volume_min, 0.01)
                _order_type = _mt5.ORDER_TYPE_BUY if side == "buy" else _mt5.ORDER_TYPE_SELL
                _dollar_per_unit = abs(_mt5.order_calc_profit(_order_type, ob.symbol, _lot, _price, _price + _sym.trade_tick_size) or 0)
                if _dollar_per_unit > 0:
                    _max_dist = _cap_usd * (_sym.trade_tick_size / _dollar_per_unit)
        elif mt5_bridge.USE_BRIDGE:
            # Bridge mode: use account balance + symbol tick info from bridge
            _price_resp = mt5_bridge._call_bridge(f"/price?symbol={ob.symbol}")
            if _price_resp:
                _mid = (_price_resp.get("bid", 0) + _price_resp.get("ask", 0)) / 2
                # Approximate: for XAUUSD $1 ≈ 0.01 price units at 0.01 lot
                # Use a conservative fixed ratio per symbol
                _symbol_dollar_per_point = {
                    "XAUUSD": 0.01,   # $1 per $0.01 move at 0.01 lot
                    "EURUSD": 0.1,    # $1 per 0.0001 move at 0.01 lot → 0.0001
                    "USDJPY": 0.1,
                    "GBPUSD": 0.1,
                    "USDCHF": 0.1,
                }
                _ratio = _symbol_dollar_per_point.get(ob.symbol, 0.1)
                _max_dist = _cap_usd * _ratio

        if _max_dist and _max_dist > 0:
            if _sl_dist > _max_dist:
                sl = entry_price - _max_dist if side == "buy" else entry_price + _max_dist
                logger.info(f"[ALGO] SL capped to ${_cap_usd}: {sl:.5f}")
            if _tp_dist > _max_dist:
                tp = entry_price + _max_dist if side == "buy" else entry_price - _max_dist
                logger.info(f"[ALGO] TP capped to ${_cap_usd}: {tp:.5f}")
    except Exception as _cap_exc:
        logger.warning(f"[ALGO] $10 cap calculation failed, using OB levels: {_cap_exc}")

    # 1R = distance between entry and stop loss
    one_r = abs(entry_price - sl)

    logger.info(
        f"[ALGO] Order Block trade | {ob.symbol} {side.upper()} | "
        f"Entry: {entry_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f} | "
        f"1R: {one_r:.5f} | OB zone: {ob.low:.5f}-{ob.high:.5f} | 50%: {ob.midpoint:.5f}"
    )
    live_price = _get_current_price(ob.symbol, side=side)
    logger.debug(
        f"[ALGO][ENTRY_EXEC] {ob.id} side={side} live_price={live_price} entry_price={entry_price:.5f} "
        f"direction={ob.direction} fvg={ob.fvg.direction}"
    )
    spread_points = "n/a"
    try:
        if MT5_AVAILABLE and mt5_bridge.is_connected():
            tick = mt5.symbol_info_tick(ob.symbol)
            sym = mt5.symbol_info(ob.symbol)
            if tick and sym and getattr(sym, "trade_tick_size", 0):
                spread_points = round((tick.ask - tick.bid) / sym.trade_tick_size, 2)
    except Exception:
        pass
    _ob_debug(
        "ENTRY_EXEC",
        symbol=ob.symbol,
        ob_id=ob.id,
        side=side,
        entry=round(entry_price, 5),
        sl=round(sl, 5),
        tp=round(tp, 5),
        live_price=live_price,
        spread=spread_points,
    )

    # Execute only on accounts that have 'order_block' strategy assigned
    from bot.accounts import get_all_accounts, execute_on_all_accounts

    ob_accounts = [
        acc for acc in get_all_accounts()
        if acc.enabled and "order_block" in (acc.strategy or [])
    ]

    ticket = None
    if not ob_accounts:
        # Fallback: use primary mt5_bridge connection
        logger.warning("[ALGO] No accounts with 'order_block' strategy — using primary connection")
        result = mt5_bridge.open_trade(
            symbol=ob.symbol,
            side=side,
            sl=sl,
            tp=tp,
            entry=entry_price,
            order_type="market",
            risk_percent=algo_config.risk_percent,
            comment=f"ALGO:OB:{ob.id[:8]}",
        )
        if not result.get("success"):
            logger.error(f"[ALGO] Trade failed: {result.get('message')}")
            return False
        ticket = result.get("ticket")
    else:
        from bot.accounts import _connect_account, _reconnect_primary
        import math as _math
        results = []
        for acc in ob_accounts:
            try:
                if _connect_account(acc):
                    from bot.accounts import _execute_single
                    r = _execute_single(
                        symbol=ob.symbol,
                        side=side,
                        sl=sl,
                        tp=tp,
                        entry=entry_price,
                        order_type="market",
                        risk_percent=algo_config.risk_percent,
                        comment=f"ALGO:OB:{ob.id[:8]}",
                    )
                    r["account_id"] = acc.id
                    r["account_label"] = acc.label
                    r["login"] = acc.login
                    results.append(r)
            except Exception as _e:
                logger.error(f"[ALGO] OB trade error on {acc.label}: {_e}")
                results.append({"success": False, "message": str(_e), "login": acc.login, "account_label": acc.label})
        _reconnect_primary()
        ob_logins = {acc.login for acc in ob_accounts}
        relevant = [r for r in results if r.get("login") in ob_logins]
        successes = [r for r in relevant if r.get("success")]

        if not successes:
            logger.error(f"[ALGO] Trade failed on all order_block accounts: {relevant}")
            return False

        ticket = successes[0].get("ticket")
        for r in successes:
            logger.success(
                f"[ALGO] Trade on {r.get('account_label')} ({r.get('login')}) | "
                f"Ticket: {r.get('ticket')} | {ob.symbol} {side.upper()}"
            )

    ob.trade_taken = True
    ob.ticket = ticket
    ob.active = False
    ob.trade_count += 1
    ob.entry_price = entry_price
    ob._opened_at = datetime.utcnow()
    ob._partial_closed = False
    ob.initial_sl = sl
    ob.one_r = one_r
    ob.r_stage = 0  # 0=initial, 1=breakeven, 2=locked, 3=trailing

    entry_reason = f"Order Block {ob.direction} | Zone: {ob.low:.5f}-{ob.high:.5f} | 50%: {ob.midpoint:.5f} | FVG: {ob.fvg.direction}"

    logger.success(
        f"[ALGO] Trade opened | Ticket: {ob.ticket} | "
        f"R:R 1:{algo_config.risk_reward_ratio} | 1R=${one_r:.5f}"
    )

    # Persist to trade journal (survives bot restarts)
    from bot.trade_journal import record_trade_open
    record_trade_open(
        ticket=ticket,
        symbol=ob.symbol,
        side=side,
        entry_price=entry_price,
        initial_sl=sl,
        initial_tp=tp,
        one_r=one_r,
        risk_reward=algo_config.risk_reward_ratio,
        entry_reason=entry_reason,
        source="ALGO:OrderBlock",
        strategy="order_block",
    )

    state.signal_log.insert(0, {
        "time": datetime.now().isoformat(),
        "symbol": ob.symbol,
        "side": side,
        "entry": entry_price,
        "sl": sl,
        "tp": tp,
        "one_r": one_r,
        "status": "executed",
        "source": "ALGO:OrderBlock",
        "ob_id": ob.id,
        "ticket": ticket,
        "entry_reason": entry_reason,
        "initial_sl": sl,
        "initial_tp": tp,
        "risk_reward": algo_config.risk_reward_ratio,
        "sl_trail_log": [],
        "exit_reason": None,
        "exit_price": None,
        "final_pnl": None,
    })
    return True


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

    side = "buy" if ob.direction == "bullish" else "sell"
    entry = ob.entry_price
    one_r = ob.one_r

    # Get current price
    current_price = _get_current_price(getattr(ob, 'symbol', algo_config.symbol), side=side)
    if current_price is None:
        return

    # ── Human Mind: partial close, early exit, time-based exit ───────────────
    from bot.algo.human_mind import (
        should_early_exit, should_time_exit, should_partial_close,
        execute_partial_close, close_trade,
    )
    _ob_symbol = getattr(ob, 'symbol', algo_config.symbol)
    candles_exec_hm = _get_candles(_ob_symbol, algo_config.execution_timeframe, 10)

    # Partial close at 1R (only once per trade)
    if not getattr(ob, '_partial_closed', False):
        if should_partial_close(entry, current_price, one_r, side, False):
            try:
                _positions = mt5_bridge.get_open_positions()
                for _pos in _positions:
                    if _pos.get("id") == ob.ticket or _pos.get("position_id") == ob.ticket:
                        _vol = float(_pos.get("volume", 0.01))
                        if execute_partial_close(ob.ticket, _ob_symbol, _vol):
                            ob._partial_closed = True
                            logger.info(f"[ALGO] Partial close done on ticket {ob.ticket} at 1R")
                        break
            except Exception as _exc:
                logger.warning(f"[ALGO] Partial close check failed: {_exc}")

    # Early exit on strong reversal candle
    if candles_exec_hm and should_early_exit(side, candles_exec_hm):
        if close_trade(ob.ticket, _ob_symbol, side, "ALGO:REVERSAL_EXIT"):
            ob.trade_taken = False
            ob.active = False
            ob.ticket = None
            return

    # Time-based exit — close stale trades with minimal profit
    _opened_at = getattr(ob, '_opened_at', None)
    if _opened_at and should_time_exit(_opened_at, entry, current_price, one_r, side):
        if close_trade(ob.ticket, _ob_symbol, side, "ALGO:TIME_EXIT"):
            ob.trade_taken = False
            ob.active = False
            ob.ticket = None
            return

    if side == "buy":
        profit_r = (current_price - entry) / one_r
    else:
        profit_r = (entry - current_price) / one_r

    new_sl = None
    logger.debug(
        f"[ALGO][RISK] ticket={ob.ticket} side={side} current={current_price:.5f} "
        f"entry={entry:.5f} one_r={one_r:.5f} profit_r={profit_r:.3f} "
        f"r_stage={ob.r_stage} sl={ob.initial_sl:.5f}"
    )
    r_stage_before = ob.r_stage

    # ── Dollar-based profit lock (independent safety net) ────────────────────
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

    # ── Strong trailing SL (swing-based + ATR buffer) ─────────────────────────
    if algo_config.strong_trailing_enabled and profit_r >= algo_config.strong_trailing_start_r:
        candles_trail = _get_candles(
            getattr(ob, 'symbol', algo_config.symbol),
            algo_config.execution_timeframe,
            max(20, algo_config.strong_trailing_swing_lookback + 5),
        )
        atr_trail = _calculate_atr(candles_trail, algo_config.atr_period) if candles_trail else None
        lookback = max(2, int(algo_config.strong_trailing_swing_lookback or 3))

        if candles_trail and len(candles_trail) >= lookback:
            recent = candles_trail[-lookback:]
            buffer = (atr_trail or 0.0) * float(algo_config.strong_trailing_atr_buffer_mult or 0.0)

            if side == "buy":
                swing = min(c.low for c in recent)
                candidate = swing - buffer
                # Safety: SL must remain below current price
                if atr_trail and candidate >= current_price:
                    candidate = current_price - (atr_trail * 0.10)
                if candidate > ob.initial_sl:
                    new_sl = candidate if new_sl is None else max(new_sl, candidate)
                    ob.r_stage = max(ob.r_stage, 3)
            else:
                swing = max(c.high for c in recent)
                candidate = swing + buffer
                # Safety: SL must remain above current price
                if atr_trail and candidate <= current_price:
                    candidate = current_price + (atr_trail * 0.10)
                if candidate < ob.initial_sl:
                    new_sl = candidate if new_sl is None else min(new_sl, candidate)
                    ob.r_stage = max(ob.r_stage, 3)

            if atr_trail:
                _ob_debug(
                    "STRONG_TRAIL",
                    ticket=ob.ticket,
                    side=side,
                    profit_r=round(profit_r, 3),
                    lookback=lookback,
                    atr=round(atr_trail, 5),
                    buffer_mult=algo_config.strong_trailing_atr_buffer_mult,
                    candidate_sl=round(new_sl, 5) if new_sl is not None else "none",
                )

    # Apply new SL if it improves position
    if new_sl is not None:
        current_sl = ob.initial_sl
        # Strong trailing: avoid spamming modify requests
        min_step = float(getattr(algo_config, "strong_trailing_min_step_r", 0.0) or 0.0) * one_r
        if min_step > 0 and abs(new_sl - current_sl) < min_step:
            new_sl = None
        else:
            last_update = float(getattr(ob, "_last_sl_update_ts", 0.0) or 0.0)
            if getattr(algo_config, "strong_trailing_min_update_seconds", 0) and last_update:
                if (time.time() - last_update) < int(algo_config.strong_trailing_min_update_seconds):
                    # Only skip if the improvement is not "big"
                    big_step = max(min_step * 2, min_step)
                    if big_step > 0 and abs(new_sl - current_sl) < big_step:
                        new_sl = None
        should_update = (side == "buy" and new_sl > current_sl) or \
                        (side == "sell" and new_sl < current_sl)
        if should_update:
            result = mt5_bridge.modify_position(ob.ticket, sl=new_sl)
            if result.get("success"):
                old_sl = ob.initial_sl
                ob.initial_sl = new_sl
                ob._last_sl_update_ts = time.time()
                stage_names = {0: "initial", 1: "breakeven", 2: "profit_lock", 3: "trailing"}
                stage_label = stage_names.get(ob.r_stage, str(ob.r_stage))
                logger.info(f"[ALGO] SL updated to {new_sl:.5f} (stage={stage_label})")
                # Log to persistent journal
                from bot.trade_journal import record_sl_trail
                record_sl_trail(ob.ticket, old_sl, new_sl, stage_label)
                # Also update in-memory signal_log
                for entry in state.signal_log:
                    if entry.get("ticket") == ob.ticket:
                        trail_log = entry.get("sl_trail_log", [])
                        trail_log.append({
                            "time": datetime.now().isoformat(),
                            "old_sl": round(old_sl, 5),
                            "new_sl": round(new_sl, 5),
                            "stage": stage_label,
                        })
                        entry["sl_trail_log"] = trail_log
                        break
                _ob_debug(
                    "RISK_STAGE",
                    ticket=ob.ticket,
                    profit_r=round(profit_r, 3),
                    r_stage_before=r_stage_before,
                    r_stage_after=ob.r_stage,
                    candidate_sl=round(new_sl, 5),
                    applied_sl=round(ob.initial_sl, 5),
                    modify_response="success",
                )
            else:
                logger.warning(
                    f"[ALGO][RISK] SL update failed | ticket={ob.ticket} "
                    f"requested_sl={new_sl:.5f} response={result}"
                )
                _ob_debug(
                    "RISK_STAGE",
                    ticket=ob.ticket,
                    profit_r=round(profit_r, 3),
                    r_stage_before=r_stage_before,
                    r_stage_after=ob.r_stage,
                    candidate_sl=round(new_sl, 5),
                    applied_sl=round(ob.initial_sl, 5),
                    modify_response=result,
                )
        else:
            logger.debug(
                f"[ALGO][RISK] SL skipped | ticket={ob.ticket} side={side} "
                f"current_sl={current_sl:.5f} candidate_sl={new_sl:.5f}"
            )
    else:
        logger.debug(
            f"[ALGO][RISK] No SL candidate | ticket={ob.ticket} profit_r={profit_r:.3f} r_stage={ob.r_stage}"
        )
        _ob_debug(
            "RISK_STAGE",
            ticket=ob.ticket,
            profit_r=round(profit_r, 3),
            r_stage_before=r_stage_before,
            r_stage_after=ob.r_stage,
            candidate_sl="none",
            applied_sl=round(ob.initial_sl, 5),
            modify_response="skipped",
        )




# ── Main scan loop ────────────────────────────────────────────────────────────

def _scan_and_trade(symbol: str = None) -> None:
    """
    Main algo loop for one symbol.
    """
    global _active_obs, _last_scan_at, _last_scan_summary

    if symbol is None:
        symbol = algo_config.symbol

    # Per-symbol OB list
    if symbol not in _active_obs:
        _active_obs[symbol] = []
    symbol_obs = _active_obs[symbol]

    # ── Risk management checks ────────────────────────────────────────────────
    check_drawdown()

    # ── Check for closed trades and record PnL ────────────────────────────────
    open_positions = mt5_bridge.get_open_positions()
    open_tickets = {str(p.get("id")) for p in open_positions if p.get("id") is not None}

    with _obs_lock:
        for ob in symbol_obs:
            if ob.trade_taken and ob.ticket and str(ob.ticket) not in open_tickets:
                closed_ticket = ob.ticket
                closed_r_stage = ob.r_stage
                # Reset OB for potential re-entry ONLY if trade was profitable
                # (avoid re-entering same losing zone repeatedly)
                pnl_val = 0.0
                try:
                    history = mt5_bridge.get_trade_history(limit=10)
                    for t in history:
                        if t.get("ticket") == closed_ticket or t.get("position_id") == closed_ticket:
                            pnl_val = float(t.get("pnl", 0))
                            record_trade_pnl(pnl_val)
                            # Human mind: record result for consecutive loss tracking
                            from bot.algo.human_mind import record_trade_result, record_sl_hit
                            record_trade_result(pnl_val)
                            if pnl_val < 0:
                                record_sl_hit(ob.id)
                            logger.info(f"[ALGO] Trade {closed_ticket} closed | PnL={pnl_val:.2f}")
                            break
                except Exception as e:
                    logger.warning(f"[ALGO] Could not fetch PnL for ticket {closed_ticket}: {e}")

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
                # Record exit reason in signal_log
                for entry in state.signal_log:
                    if entry.get("ticket") == closed_ticket or entry.get("ob_id") == ob.id:
                        entry["final_pnl"] = round(pnl_val, 2)
                        entry["exit_price"] = None  # fetched from history if available
                        if pnl_val > 0:
                            entry["exit_reason"] = "Trailing SL" if closed_r_stage >= 3 else "TP Hit"
                            entry["status"] = "win"
                        elif pnl_val < 0:
                            entry["exit_reason"] = "SL Hit"
                            entry["status"] = "loss"
                        else:
                            entry["exit_reason"] = "Breakeven"
                            entry["status"] = "breakeven"
                        break

                # Reset trade tracking fields last (after we log/annotate by ticket)
                ob.ticket = None
                ob.r_stage = 0
                ob.dollar_lock_applied = False

    # Fetch analysis timeframe candles
    candles_analysis = _get_candles(symbol, algo_config.analysis_timeframe, algo_config.ob_lookback + 10)
    candles_trend = _get_candles(symbol, algo_config.trend_timeframe_minutes, algo_config.trend_ema_period + 20)
    if len(candles_analysis) < algo_config.ob_lookback:
        logger.debug(f"[ALGO] Not enough candles for {symbol}")
        return

    # Detect new order blocks
    new_obs = _detect_order_blocks(candles_analysis)

    added_count = 0
    with _obs_lock:
        # Add new OBs (avoid duplicates)
        existing_ids = {ob.id for ob in symbol_obs}
        # Calculate current ATR for SL sizing
        current_atr = _calculate_atr(candles_analysis, algo_config.atr_period) or 0.0

        for ob in new_obs:
            if ob.id not in existing_ids:
                # Apply trend filter
                trend_candles = candles_trend if len(candles_trend) >= algo_config.trend_ema_period else candles_analysis
                if algo_config.require_trend_alignment and not _is_trend_aligned(trend_candles, ob.direction):
                    logger.debug(f"[ALGO] OB {ob.id} filtered out — against trend")
                    _ob_debug(
                        "ENTRY_DECISION",
                        symbol=symbol,
                        ob_id=ob.id,
                        direction=ob.direction,
                        trend_ok=False,
                        touched=False,
                        confirmed=False,
                        reject_reason="trend_filter_failed",
                    )
                    continue
                # Apply volatility filter
                if not _is_volatility_sufficient(candles_analysis):
                    logger.debug(f"[ALGO] OB {ob.id} filtered out — low volatility")
                    continue
                ob.symbol = symbol  # tag OB with its symbol
                ob.atr = current_atr  # store ATR for SL calculation
                symbol_obs.append(ob)
                added_count += 1
                logger.info(
                    f"[ALGO] New {ob.direction} Order Block detected | "
                    f"Zone: {ob.low:.5f}-{ob.high:.5f} | 50%: {ob.midpoint:.5f} | "
                    f"Time: {ob.time}"
                )

        # Trim to max active OBs (keep most recent) — remove traded/inactive first
        _active_obs[symbol] = [o for o in symbol_obs if o.active or o.trade_taken]
        symbol_obs = _active_obs[symbol]
        _active_obs[symbol] = sorted(symbol_obs, key=lambda x: x.time, reverse=True)[:algo_config.max_active_obs]
        symbol_obs = _active_obs[symbol]

    _last_scan_at = datetime.now().isoformat()
    _last_scan_summary[symbol] = {
        "symbol": symbol,
        "detected": len(new_obs),
        "added": added_count,
        "tracked": len(symbol_obs),
        "at": _last_scan_at,
    }

    # Check if bot is allowed to trade
    if not state.running:
        return

    # Check risk management rules before entering new trades
    if not algo_config.enabled:
        return
    if not can_trade():
        return

    # Check open positions — limit per symbol (not global across all symbols)
    open_positions = mt5_bridge.get_open_positions()
    open_tickets = {str(p.get("id")) for p in open_positions if p.get("id") is not None}
    algo_positions = [
        p for p in open_positions
        if "ALGO:OB" in str(p.get("comment", "")) and str(p.get("symbol", "")).upper() == symbol.upper()
    ]

    # If a traded OB's position was manually closed, allow re-trading
    with _obs_lock:
        for ob in symbol_obs:
            if ob.trade_taken and ob.ticket and str(ob.ticket) not in open_tickets:
                # Position was manually closed — reset OB to allow new trade
                logger.info(f"[ALGO] OB {ob.id} position manually closed — resetting for re-entry")
                ob.trade_taken = False
                ob.active = True
                ob.ticket = None
                ob.dollar_lock_applied = False
                ob.r_stage = 0

    if len(algo_positions) >= 2:
        logger.debug(f"[ALGO] Max algo positions reached for {symbol} ({len(algo_positions)})")
        return

    # Fetch execution timeframe candles
    candles_exec = _get_candles(symbol, algo_config.execution_timeframe, 20)
    if len(candles_exec) < 5:
        return

    # Check each active OB for entry signal
    with _obs_lock:
        for ob in symbol_obs:
            if not ob.active or ob.trade_taken:
                continue

            # Skip OB if max trades already taken on this zone
            if ob.trade_count >= algo_config.max_trades_per_ob:
                ob.active = False
                logger.debug(f"[ALGO] OB {ob.id} max trades reached ({ob.trade_count}) — deactivating")
                continue

            # Invalidate OB if price has blown through it
            current_price = _get_current_price(symbol, side="mid")
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
                # ── Human Mind gate ───────────────────────────────────────────
                from bot.algo.human_mind import can_enter_trade, get_lot_multiplier
                allowed, reason = can_enter_trade(
                    symbol=symbol,
                    direction=ob.direction,
                    candles=candles_exec,
                    open_positions=open_positions,
                )
                if not allowed:
                    logger.info(f"[ALGO] Trade blocked by human_mind: {reason} | OB {ob.id}")
                    continue
                logger.info(f"[ALGO] Entry signal confirmed for OB {ob.id} at {entry:.5f}")
                _ob_debug(
                    "ENTRY_DECISION",
                    symbol=symbol,
                    ob_id=ob.id,
                    direction=ob.direction,
                    trend_ok=True,
                    touched=True,
                    confirmed=True,
                    reject_reason="",
                )
                _execute_ob_trade(ob, entry)
                break  # one trade per scan


def _risk_check_loop() -> None:
    """
    High-frequency loop (every 1 second) for open trade risk management:
    - Total portfolio profit close (all trades close when combined profit >= $7)
    - Dollar-based profit lock ($15 → lock $10)
    - R-multiple trailing stop updates (breakeven, lock, trail)

    Kept separate from OB scan loop to avoid heavy candle fetches every second.
    """
    global _algo_running, _last_recovery_at
    logger.info("[ALGO] Risk check loop started (1s interval)")
    last_snapshot_at = 0.0
    snapshot_ttl_seconds = 3.0
    cached_ticket_owner: dict[str, object] = {}
    cached_ticket_raw: set = set()

    while _algo_running:
        try:
            if mt5_bridge.ensure_connected():
                from bot.accounts import get_all_accounts, _connect_account, _reconnect_primary

                # ── Total portfolio profit close check ────────────────────────
                try:
                    from bot.algo.human_mind import check_and_close_all_on_profit_target
                    _all_positions = mt5_bridge.get_open_positions()
                    if check_and_close_all_on_profit_target(_all_positions):
                        # All trades closed — reset all tracked OBs
                        with _obs_lock:
                            for _obs_list in _active_obs.values():
                                for _ob in _obs_list:
                                    if _ob.trade_taken:
                                        _ob.trade_taken = False
                                        _ob.active = False
                                        _ob.ticket = None
                        time.sleep(algo_config.risk_check_interval_seconds)
                        continue
                except Exception as _pte:
                    logger.warning(f"[ALGO] Profit target close check failed: {_pte}")

                with _obs_lock:
                    all_obs = [ob for obs in _active_obs.values() for ob in obs]
                    tracked_open_obs = [ob for ob in all_obs if ob.ticket and ob.trade_taken]

                # No active tracked OB tickets -> skip expensive account switching.
                if not tracked_open_obs:
                    now_recover = time.time()
                    if (now_recover - _last_recovery_at) >= 10.0:
                        recovered = _recover_tracked_ob_positions()
                        _last_recovery_at = now_recover
                        if recovered > 0:
                            logger.info(
                                f"[ALGO][RISK_LOOP] Recovered {recovered} OB position(s); resuming risk tracking"
                            )
                    logger.debug("[ALGO][RISK_LOOP] no tracked OB tickets; skipping snapshot")
                    time.sleep(algo_config.risk_check_interval_seconds)
                    continue

                now = time.time()
                if (now - last_snapshot_at) >= snapshot_ttl_seconds:
                    # Build a cross-account open-ticket snapshot for all order_block accounts.
                    ob_accounts = [
                        acc for acc in get_all_accounts()
                        if acc.enabled and "order_block" in (acc.strategy or [])
                    ]
                    ticket_owner: dict[str, object] = {}
                    ticket_raw: set = set()

                    if ob_accounts:
                        for acc in ob_accounts:
                            try:
                                if _connect_account(acc):
                                    positions = mt5_bridge.get_open_positions()
                                    for p in positions:
                                        tid = p.get("id", p.get("position_id"))
                                        if tid is None:
                                            continue
                                        ticket_owner[str(tid)] = acc
                                        ticket_raw.add(tid)
                            except Exception as e:
                                logger.warning(f"[ALGO][RISK_LOOP] account snapshot failed for {acc.label}: {e}")
                        _reconnect_primary()
                    else:
                        # Fallback to current active connection
                        positions = mt5_bridge.get_open_positions()
                        for p in positions:
                            tid = p.get("id", p.get("position_id"))
                            if tid is None:
                                continue
                            ticket_owner[str(tid)] = None
                            ticket_raw.add(tid)

                    cached_ticket_owner = ticket_owner
                    cached_ticket_raw = ticket_raw
                    last_snapshot_at = now

                open_ticket_strs = set(cached_ticket_owner.keys())
                logger.debug(
                    f"[ALGO][RISK_LOOP] open_tickets={list(cached_ticket_raw)} "
                    f"types={[type(t).__name__ for t in cached_ticket_raw]}"
                )

                with _obs_lock:
                    for ob in tracked_open_obs:
                        if ob.ticket and ob.trade_taken:
                            ticket_key = str(ob.ticket)
                            in_open_set = ob.ticket in cached_ticket_raw
                            in_open_set_str = ticket_key in open_ticket_strs
                            logger.debug(
                                f"[ALGO][RISK_LOOP] ticket_check ob_ticket={ob.ticket} "
                                f"type={type(ob.ticket).__name__} strict_match={in_open_set} "
                                f"string_match={in_open_set_str}"
                            )
                            _ob_debug(
                                "POSITION_MATCH",
                                ob_ticket=ob.ticket,
                                strict_match=in_open_set,
                                string_match=in_open_set_str,
                                open_ticket_count=len(open_ticket_strs),
                            )
                        if ob.ticket and ob.trade_taken and str(ob.ticket) in open_ticket_strs:
                            owner = cached_ticket_owner.get(str(ob.ticket))
                            if owner is not None:
                                try:
                                    _connect_account(owner)
                                except Exception as e:
                                    logger.warning(
                                        f"[ALGO][RISK_LOOP] owner switch failed for ticket={ob.ticket}: {e}"
                                    )
                                    continue
                            _manage_open_trade_risk(ob)
                    _reconnect_primary()
        except Exception as e:
            logger.error(f"[ALGO] Risk check error: {e}")

        time.sleep(algo_config.risk_check_interval_seconds)

    logger.info("[ALGO] Risk check loop stopped.")


def _algo_loop() -> None:
    global _algo_running
    symbols = algo_config.get_symbols()
    logger.info(
        f"[ALGO] Order Block strategy started | Symbols: {symbols} | "
        f"Analysis TF: {algo_config.analysis_timeframe}m | "
        f"Execution TF: {algo_config.execution_timeframe}m"
    )

    while _algo_running:
        try:
            if mt5_bridge.ensure_connected():
                for sym in algo_config.get_symbols():
                    try:
                        _scan_and_trade(sym)
                    except Exception as e:
                        logger.error(f"[ALGO] Scan error for {sym}: {e}")
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

    # Recover already-open OB trades so trailing/risk management keeps working after restart.
    _recover_tracked_ob_positions()

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
        all_obs_flat = [ob for obs in _active_obs.values() for ob in obs]
        obs_data = [
            {
                "id": ob.id,
                "direction": ob.direction,
                "symbol": ob.symbol,
                "high": ob.high,
                "low": ob.low,
                "midpoint": ob.midpoint,
                "time": ob.time.isoformat(),
                "active": ob.active,
                "trade_taken": ob.trade_taken,
                "ticket": ob.ticket,
            }
            for ob in all_obs_flat
        ]

    return {
        "running": _algo_running,
        "enabled": algo_config.enabled,
        "strategy": "order_block",
        "symbol": algo_config.symbol,
        "symbols": algo_config.get_symbols(),
        "analysis_timeframe": algo_config.analysis_timeframe,
        "execution_timeframe": algo_config.execution_timeframe,
        "risk_reward": algo_config.risk_reward_ratio,
        "risk_percent": algo_config.risk_percent,
        "active_order_blocks": obs_data,
        "total_obs_tracked": sum(len(v) for v in _active_obs.values()),
        "last_scan_at": _last_scan_at,
        "scan_summary": list(_last_scan_summary.values()),
    }


def update_algo_config(
    symbol: Optional[str] = None,
    enabled: Optional[bool] = None,
    risk_reward: Optional[float] = None,
    risk_percent: Optional[float] = None,
    max_drawdown_pct: Optional[float] = None,
    daily_loss_limit: Optional[float] = None,
    analysis_tf: Optional[int] = None,
    execution_tf: Optional[int] = None,
) -> dict:
    """Update algo configuration at runtime."""
    if symbol is not None:
        normalized_symbols = _normalize_symbols(symbol)
        if normalized_symbols:
            algo_config.symbol = normalized_symbols[0]
            algo_config.symbols = normalized_symbols
    if enabled is not None:
        algo_config.enabled = enabled
    if risk_reward is not None:
        algo_config.risk_reward_ratio = risk_reward
    if risk_percent is not None:
        algo_config.risk_percent = risk_percent
    if max_drawdown_pct is not None:
        # Accept either decimal form (0.10) or percent form (10).
        parsed = float(max_drawdown_pct)
        algo_config.max_drawdown_pct = (parsed / 100.0) if parsed > 1 else parsed
    if daily_loss_limit is not None:
        algo_config.daily_loss_limit = float(daily_loss_limit)
    if analysis_tf is not None:
        algo_config.analysis_timeframe = analysis_tf
    if execution_tf is not None:
        algo_config.execution_timeframe = execution_tf

    logger.info(f"[ALGO] Config updated: {algo_config}")
    return get_algo_status()

