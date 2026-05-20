"""
Breakout retest strategy for live algo trading.

Core logic:
1. Detect a strong close above/below a recent range on the analysis timeframe.
2. Confirm trend, volatility, and relative volume.
3. Wait for a retest on the execution timeframe.
4. Enter on directional rejection from the breakout level.
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
from bot.algo.order_block import (
    can_trade_with_reason,
    get_risk_status,
    record_trade_pnl,
)


@dataclass
class AlgoConfig:
    symbol: str = "XAUUSD"
    symbols: list = None  # Multi-symbol list — if set, overrides symbol
    analysis_timeframe: int = 15
    execution_timeframe: int = 15
    risk_reward_ratio: float = 1.5
    risk_percent: float = 1.0
    breakout_lookback: int = 10
    trend_ema_period: int = 20
    atr_period: int = 14
    atr_min_multiplier: float = 0.45
    range_min_atr_multiplier: float = 0.8
    breakout_buffer_atr: float = 0.05
    min_breakout_body_ratio: float = 0.45
    min_volume_multiplier: float = 1.00
    retest_tolerance_atr: float = 0.25
    # Keep Friday (15-05-2026) strict behavior by default
    require_trend_alignment: bool = True
    require_volatility_filter: bool = True
    use_human_mind_gate: bool = True
    max_active_breakouts: int = 5
    scan_interval_seconds: int = 60
    risk_check_interval_seconds: int = 1
    max_trades_per_setup: int = 1
    enabled: bool = True
    rr_breakeven: float = 1.0
    rr_lock_profit: float = 1.5
    trail_atr_mult: float = 0.8         # Tighter trailing stop
    dollar_profit_trigger: float = 8.0  # Trigger at $8 floating profit
    dollar_profit_lock: float = 5.0     # Lock $5 profit
    dollar_lock_enabled: bool = True
    quick_book_profit_usd: float = 5.0
    risky_quick_book_profit_usd: float = 3.0
    extended_profit_min_usd: float = 7.0
    extended_profit_max_usd: float = 10.0
    early_sl_avoid_ratio: float = 0.65
    staged_book_level_1_pct: float = 0.40
    staged_book_level_2_pct: float = 0.30

    def get_symbols(self) -> list:
        """Return list of symbols to trade."""
        if self.symbols:
            return self.symbols
        return [self.symbol]


algo_config = AlgoConfig()
algo_config.symbols = ["XAUUSD", "EURUSD", "USDJPY", "GBPUSD", "USDCHF"]


def _normalize_symbols(symbol_value: Optional[str]) -> list[str]:
    """Normalize a single symbol or comma-separated symbol list."""
    if not symbol_value:
        return []
    return [part.strip().upper() for part in str(symbol_value).split(",") if part.strip()]


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
        return self.body / self.range if self.range > 0 else 0.0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


@dataclass
class BreakoutSetup:
    id: str
    direction: str
    breakout_level: float
    range_high: float
    range_low: float
    time: datetime
    symbol: str = "XAUUSD"  # symbol this setup was detected on
    active: bool = True
    trade_taken: bool = False
    ticket: Optional[int] = None
    trade_count: int = 0
    entry_price: float = 0.0
    initial_sl: float = 0.0
    one_r: float = 0.0
    r_stage: int = 0
    dollar_lock_applied: bool = False
    staged_book_1_done: bool = False
    staged_book_2_done: bool = False
    # Multi-account support:
    # breakout strategy can be mapped to multiple MT5 accounts. Execution returns
    # one ticket per account. Risk management MUST operate per-account.
    account_tickets: list[dict] = field(default_factory=list)  # [{"login":int,"ticket":int,"label":str}]
    account_state: dict[str, dict] = field(default_factory=dict)  # login -> per-account state dict

    @property
    def sl_level(self) -> float:
        range_size = max(self.range_high - self.range_low, 0.0)
        buffer = range_size * 0.15
        if self.direction == "bullish":
            return self.range_low - buffer
        return self.range_high + buffer

    def tp_level(self, entry: float, rr: float) -> float:
        sl_distance = abs(entry - self.sl_level)
        if self.direction == "bullish":
            return entry + sl_distance * rr
        return entry - sl_distance * rr


_active_breakouts: dict[str, list] = {}  # keyed by symbol
_breakout_lock = threading.Lock()
_algo_thread: Optional[threading.Thread] = None
_risk_thread: Optional[threading.Thread] = None
_algo_running = False
_last_scan_at: Optional[str] = None
_last_scan_summary: dict[str, dict] = {}


def _get_open_positions_all_breakout_accounts() -> list[dict]:
    """
    Return open positions across ALL breakout-mapped accounts (direct MT5 mode).
    In bridge mode (single account), falls back to mt5_bridge.get_open_positions().
    Each returned position is enriched with account_login/account_label when possible.
    """
    # Bridge mode cannot iterate multiple accounts.
    if mt5_bridge.USE_BRIDGE or not MT5_AVAILABLE:
        return mt5_bridge.get_open_positions()

    try:
        from bot.accounts import get_accounts_for_strategy, connect_account_by_login, reconnect_primary
        accounts = get_accounts_for_strategy("breakout")
        all_positions: list[dict] = []
        for acc in accounts:
            if not connect_account_by_login(acc.login):
                continue
            positions = mt5_bridge.get_open_positions()
            for p in positions:
                p["account_login"] = acc.login
                p["account_label"] = acc.label
            all_positions.extend(positions)
        reconnect_primary()
        return all_positions
    except Exception as exc:
        logger.warning(f"[BREAKOUT] Could not collect multi-account open positions: {exc}")
        return mt5_bridge.get_open_positions()


def _find_live_position_for_setup(setup: BreakoutSetup, open_positions: list[dict]) -> dict | None:
    """
    Resolve the current live MT5 position for this setup.
    Ticket mapping can differ across brokers/accounts, so we match by:
    1) ticket/position_id exact
    2) ALGO comment prefix + symbol fallback
    """
    expected_tag = f"ALGO:BRK:{setup.id[:8]}"
    for pos in open_positions:
        pid = pos.get("id")
        ppid = pos.get("position_id")
        if setup.ticket and (pid == setup.ticket or ppid == setup.ticket):
            return pos

    # Fallback by comment+symbol when ticket mismatch happens.
    matches = [
        p for p in open_positions
        if str(p.get("symbol", "")) == str(getattr(setup, "symbol", ""))
        and expected_tag in str(p.get("comment", "") or "")
    ]
    if matches:
        # Most recent first if timestamp available.
        matches = sorted(matches, key=lambda p: str(p.get("opened", "") or ""), reverse=True)
        return matches[0]
    return None


def _get_candles(symbol: str, timeframe_minutes: int, count: int) -> list[Candle]:
    from bot import mt5_bridge as _bridge

    if _bridge.USE_BRIDGE:
        try:
            response = _bridge._call_bridge(
                f"/candles?symbol={symbol}&timeframe={timeframe_minutes}&count={count}"
            )
            if response and isinstance(response, list):
                return [
                    Candle(
                        time=datetime.fromisoformat(r["time"]) if isinstance(r["time"], str) else datetime.fromtimestamp(r["time"]),
                        open=float(r["open"]),
                        high=float(r["high"]),
                        low=float(r["low"]),
                        close=float(r["close"]),
                        volume=float(r.get("volume", r.get("tick_volume", 0))),
                    )
                    for r in response
                ]
        except Exception as exc:
            logger.warning(f"[BREAKOUT] Bridge candles fetch failed: {exc}")
        return []

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
    rates = mt5.copy_rates_from_pos(symbol, tf_map.get(timeframe_minutes, mt5.TIMEFRAME_M15), 0, count)
    if rates is None or len(rates) == 0:
        return []
    return [
        Candle(
            time=datetime.fromtimestamp(r["time"]),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["tick_volume"]),
        )
        for r in rates
    ]


def _get_current_price(symbol: str, side: Optional[str] = None) -> Optional[float]:
    from bot import mt5_bridge as _bridge

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
        except Exception as exc:
            logger.warning(f"[BREAKOUT] Bridge price fetch failed: {exc}")
        return None

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


def _calculate_ema(candles: list[Candle], period: int) -> Optional[float]:
    if len(candles) < period:
        return None
    closes = [c.close for c in candles]
    ema = sum(closes[:period]) / period
    k = 2 / (period + 1)
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return ema


def _calculate_atr(candles: list[Candle], period: int) -> Optional[float]:
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        current = candles[i]
        previous = candles[i - 1]
        trs.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return sum(trs[-period:]) / period


def _average_volume(candles: list[Candle], period: int = 10) -> float:
    if not candles:
        return 0.0
    sample = candles[-period:]
    return sum(c.volume for c in sample) / len(sample)


def _is_trend_aligned(candles: list[Candle], direction: str) -> bool:
    ema = _calculate_ema(candles, algo_config.trend_ema_period)
    if ema is None:
        return True
    current_price = candles[-1].close
    return current_price > ema if direction == "bullish" else current_price < ema


def _is_volatility_sufficient(candles: list[Candle]) -> bool:
    atr = _calculate_atr(candles, algo_config.atr_period)
    if atr is None:
        return True
    baseline = _calculate_atr(candles[:-algo_config.atr_period], algo_config.atr_period)
    if baseline is None:
        return True
    return atr >= baseline * algo_config.atr_min_multiplier


def _detect_breakouts(candles: list[Candle]) -> list[BreakoutSetup]:
    setups: list[BreakoutSetup] = []
    if len(candles) < algo_config.breakout_lookback + 2:
        return setups

    start_idx = max(algo_config.breakout_lookback, len(candles) - 3)
    for idx in range(start_idx, len(candles)):
        window = candles[idx - algo_config.breakout_lookback:idx]
        current = candles[idx]

        range_high = max(c.high for c in window)
        range_low = min(c.low for c in window)
        range_size = range_high - range_low
        atr = _calculate_atr(candles[: idx + 1], algo_config.atr_period)
        avg_volume = _average_volume(window)

        if atr is None or range_size <= 0:
            continue

        if range_size < atr * algo_config.range_min_atr_multiplier:
            continue

        buffer = atr * algo_config.breakout_buffer_atr
        volume_ok = True if avg_volume <= 0 else current.volume >= avg_volume * algo_config.min_volume_multiplier
        body_ok = current.body_ratio >= algo_config.min_breakout_body_ratio

        if (
            current.is_bullish
            and body_ok
            and volume_ok
            and current.close > range_high + buffer
        ):
            setups.append(
                BreakoutSetup(
                    id=f"bullish_{current.time.strftime('%Y%m%d%H%M')}",
                    direction="bullish",
                    breakout_level=range_high,
                    range_high=range_high,
                    range_low=range_low,
                    time=current.time,
                )
            )
        elif (
            current.is_bearish
            and body_ok
            and volume_ok
            and current.close < range_low - buffer
        ):
            setups.append(
                BreakoutSetup(
                    id=f"bearish_{current.time.strftime('%Y%m%d%H%M')}",
                    direction="bearish",
                    breakout_level=range_low,
                    range_high=range_high,
                    range_low=range_low,
                    time=current.time,
                )
            )

    return setups


def _check_entry_signal(setup: BreakoutSetup, candles_exec: list[Candle]) -> Optional[float]:
    if len(candles_exec) < 2:
        return None

    last = candles_exec[-1]
    prev = candles_exec[-2]
    atr = _calculate_atr(candles_exec, min(algo_config.atr_period, max(len(candles_exec) - 1, 1)))
    tolerance = (atr or max(setup.range_high - setup.range_low, 0.0)) * algo_config.retest_tolerance_atr

    if setup.direction == "bullish":
        touched = last.low <= setup.breakout_level + tolerance
        confirmed = last.close > setup.breakout_level and last.is_bullish and last.close >= prev.close
        if touched and confirmed:
            return last.close
    else:
        touched = last.high >= setup.breakout_level - tolerance
        confirmed = last.close < setup.breakout_level and last.is_bearish and last.close <= prev.close
        if touched and confirmed:
            return last.close

    return None


def _execute_breakout_trade(setup: BreakoutSetup, entry_price: float) -> bool:
    # Breakout strategy can run on multiple accounts; drawdown must be evaluated
    # per-account (handled separately). Avoid a wrong-account drawdown block here.
    allowed, block_reason = can_trade_with_reason(skip_drawdown=True)
    if not allowed:
        logger.info(f"[BREAKOUT] Trade blocked by risk management | reason={block_reason} | symbol={setup.symbol}")
        return False

    sl = setup.sl_level
    tp = setup.tp_level(entry_price, algo_config.risk_reward_ratio)
    side = "buy" if setup.direction == "bullish" else "sell"

    # ── $10 SL / $10 TP hard cap ──────────────────────────────────────────────
    try:
        _cap_usd = 10.0
        _sl_dist = abs(entry_price - sl)
        _tp_dist = abs(tp - entry_price)
        _max_dist = None

        if MT5_AVAILABLE and mt5_bridge.is_connected():
            import MetaTrader5 as _mt5
            _sym = _mt5.symbol_info(setup.symbol)
            _tick = _mt5.symbol_info_tick(setup.symbol)
            if _sym and _tick:
                _price = _tick.ask if side == "buy" else _tick.bid
                _lot = max(_sym.volume_min, 0.01)
                _order_type = _mt5.ORDER_TYPE_BUY if side == "buy" else _mt5.ORDER_TYPE_SELL
                _dollar_per_unit = abs(_mt5.order_calc_profit(_order_type, setup.symbol, _lot, _price, _price + _sym.trade_tick_size) or 0)
                if _dollar_per_unit > 0:
                    _max_dist = _cap_usd * (_sym.trade_tick_size / _dollar_per_unit)
        elif mt5_bridge.USE_BRIDGE:
            _symbol_dollar_per_point = {
                "XAUUSD": 0.01, "EURUSD": 0.1, "USDJPY": 0.1, "GBPUSD": 0.1, "USDCHF": 0.1,
            }
            _max_dist = _cap_usd * _symbol_dollar_per_point.get(setup.symbol, 0.1)

        if _max_dist and _max_dist > 0:
            if _sl_dist > _max_dist:
                sl = entry_price - _max_dist if side == "buy" else entry_price + _max_dist
                logger.info(f"[BREAKOUT] SL capped to ${_cap_usd}: {sl:.5f}")
            if _tp_dist > _max_dist:
                tp = entry_price + _max_dist if side == "buy" else entry_price - _max_dist
                logger.info(f"[BREAKOUT] TP capped to ${_cap_usd}: {tp:.5f}")
    except Exception as _cap_exc:
        logger.warning(f"[BREAKOUT] $10 cap calculation failed: {_cap_exc}")

    # Non-XAU pairs: force fixed 40-point target.
    if str(setup.symbol).upper() != "XAUUSD":
        pip_size = 0.01 if str(setup.symbol).upper().endswith("JPY") else 0.0001
        point_size = pip_size / 10.0
        tp = entry_price + (40 * point_size) if side == "buy" else entry_price - (40 * point_size)
        logger.info(f"[BREAKOUT] Non-XAU fixed TP applied: 40 points -> TP={tp:.5f}")

    one_r = abs(entry_price - sl)

    logger.info(
        f"[BREAKOUT] {setup.symbol} {side.upper()} | "
        f"Entry: {entry_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f} | "
        f"Breakout level: {setup.breakout_level:.5f} | Range: {setup.range_low:.5f}-{setup.range_high:.5f}"
    )

    # Execute via centralized multi-account engine (now supports filling-mode fallback).
    from bot.accounts import execute_on_all_accounts
    results = execute_on_all_accounts(
        symbol=setup.symbol,
        side=side,
        sl=sl,
        tp=tp,
        entry=entry_price,
        order_type="market",
        risk_percent=algo_config.risk_percent,
        comment=f"ALGO:BRK:{setup.id[:8]}",
        strategy_id="breakout",
    )
    successes = [r for r in results if r.get("success")]
    if not successes:
        logger.error(f"[BREAKOUT] Trade failed on all breakout accounts: {results}")
        return False
    ticket = successes[0].get("ticket")
    for r in successes:
        logger.success(
            f"[BREAKOUT] Trade on {r.get('account_label')} ({r.get('login')}) | "
            f"Ticket: {r.get('ticket')} | {setup.symbol} {side.upper()}"
        )

    setup.trade_taken = True
    setup.ticket = ticket
    setup.account_tickets = [
        {
            "login": int(r.get("login")) if r.get("login") is not None else None,
            "ticket": int(r.get("ticket")) if r.get("ticket") is not None else None,
            "label": r.get("account_label") or "",
        }
        for r in successes
        if r.get("login") is not None and r.get("ticket") is not None
    ]
    setup.active = False
    setup.trade_count += 1
    setup.entry_price = entry_price
    setup._opened_at = datetime.utcnow()
    setup._partial_closed = False
    setup.initial_sl = sl
    setup.one_r = one_r
    setup.r_stage = 0

    # Per-account management state (required for staged booking, early SL avoid, trailing).
    setup.account_state = {}
    for item in setup.account_tickets:
        login = str(item.get("login"))
        setup.account_state[login] = {
            "ticket": int(item.get("ticket")),
            "entry_price": float(entry_price),
            "one_r": float(one_r),
            "initial_sl": float(sl),
            "r_stage": 0,
            "dollar_lock_applied": False,
            "staged_book_1_done": False,
            "staged_book_2_done": False,
            "partial_closed": False,
            "opened_at": setup._opened_at,
        }

    state.signal_log.insert(0, {
        "time": datetime.now().isoformat(),
        "symbol": setup.symbol,
        "side": side,
        "entry": entry_price,
        "sl": sl,
        "tp": tp,
        "one_r": one_r,
        "status": "executed",
        "source": "ALGO:Breakout",
        "setup_id": setup.id,
        "ticket": ticket,
    })

    # Persist to trade journal
    from bot.trade_journal import record_trade_open
    entry_reason = (
        f"Range Breakout {setup.direction} on {setup.symbol} | "
        f"Level: {setup.breakout_level:.5f} | "
        f"Range: {setup.range_low:.5f}-{setup.range_high:.5f}"
    )
    record_trade_open(
        ticket=ticket,
        symbol=setup.symbol,
        side=side,
        entry_price=entry_price,
        initial_sl=sl,
        initial_tp=tp,
        one_r=one_r,
        risk_reward=algo_config.risk_reward_ratio,
        entry_reason=entry_reason,
        source="ALGO:Breakout",
        strategy="breakout",
    )

    logger.success(f"[BREAKOUT] Trade opened | Ticket: {ticket} | R:R 1:{algo_config.risk_reward_ratio}")
    return True


def _manage_open_trade_risk_for_account(
    *,
    setup: BreakoutSetup,
    live_pos: dict,
    ticket: int,
    account_state: dict,
) -> None:
    """
    Manage one open position (one account) for this setup.
    NOTE: Caller must ensure correct MT5 account connection is active.
    """
    if not ticket:
        return
    one_r = float(account_state.get("one_r") or 0.0)
    if one_r <= 0:
        return

    side = "buy" if setup.direction == "bullish" else "sell"
    _sym = getattr(setup, "symbol", algo_config.symbol)
    current_price = _get_current_price(_sym, side=side)
    if current_price is None:
        return

    entry = float(account_state.get("entry_price") or setup.entry_price or 0.0)

    # ── Human Mind: partial close, early exit, time-based exit ───────────────
    from bot.algo.human_mind import (
        should_early_exit, should_time_exit, should_partial_close,
        execute_partial_close, close_trade,
    )
    _candles_hm = _get_candles(_sym, algo_config.execution_timeframe, 10)

    if not bool(account_state.get("partial_closed")):
        if should_partial_close(entry, current_price, one_r, side, False):
            try:
                _vol = float(live_pos.get("volume", 0.01))
                if execute_partial_close(ticket, _sym, _vol):
                    account_state["partial_closed"] = True
                    logger.info(f"[BREAKOUT] Partial close done on ticket {ticket} at 1R")
            except Exception as _exc:
                logger.warning(f"[BREAKOUT] Partial close check failed: {_exc}")

    if _candles_hm and should_early_exit(side, _candles_hm):
        logger.info(f"[BREAKOUT][EXIT_SIGNAL] ticket={ticket} reason=REVERSAL_EXIT symbol={_sym} side={side}")
        if close_trade(ticket, _sym, side, "ALGO:REVERSAL_EXIT"):
            return
        logger.warning(f"[BREAKOUT][EXIT_FAIL] ticket={ticket} reason=REVERSAL_EXIT symbol={_sym}")

    _opened_at = account_state.get("opened_at") or getattr(setup, "_opened_at", None)
    if _opened_at and should_time_exit(_opened_at, entry, current_price, one_r, side):
        logger.info(f"[BREAKOUT][EXIT_SIGNAL] ticket={ticket} reason=TIME_EXIT symbol={_sym} side={side}")
        if close_trade(ticket, _sym, side, "ALGO:TIME_EXIT"):
            return
        logger.warning(f"[BREAKOUT][EXIT_FAIL] ticket={ticket} reason=TIME_EXIT symbol={_sym}")

    def _has_continuation_bias(candles: list[Candle], trade_side: str) -> bool:
        if len(candles) < 3:
            return False
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        if trade_side == "buy":
            return c2.is_bullish and c3.is_bullish and c3.close >= c2.close >= c1.close
        return c2.is_bearish and c3.is_bearish and c3.close <= c2.close <= c1.close

    continuation_bias = _has_continuation_bias(_candles_hm or [], side)
    floating_pnl = None
    try:
        floating_pnl = float(live_pos.get("pnl", 0) or 0)
    except Exception as exc:
        logger.warning(f"[BREAKOUT] Could not read floating pnl for ticket {setup.ticket}: {exc}")

    # Human-style staged booking:
    # +$5 partial, +$7 partial, +$10 close remaining.
    if floating_pnl is not None:
        # Risky condition quick-book: lock small gain at +$3
        # Risky signal = no continuation + opposite pressure seen.
        opposite_pressure_now = False
        if _candles_hm and len(_candles_hm) >= 2:
            if side == "buy":
                opposite_pressure_now = _candles_hm[-1].is_bearish and _candles_hm[-2].is_bearish
            else:
                opposite_pressure_now = _candles_hm[-1].is_bullish and _candles_hm[-2].is_bullish

        if floating_pnl >= algo_config.risky_quick_book_profit_usd and (not continuation_bias) and opposite_pressure_now:
            if close_trade(ticket, _sym, side, "ALGO:BOOK_3_RISKY"):
                return

        _vol = float(live_pos.get("volume", 0.0) or 0.0)
        if (not bool(account_state.get("staged_book_1_done"))) and floating_pnl >= algo_config.quick_book_profit_usd and _vol > 0:
            if execute_partial_close(ticket, _sym, _vol, close_fraction=algo_config.staged_book_level_1_pct):
                account_state["staged_book_1_done"] = True
                logger.info(f"[BREAKOUT] Stage-1 partial book at +${algo_config.quick_book_profit_usd:.2f}")
                return

        if (not bool(account_state.get("staged_book_2_done"))) and floating_pnl >= algo_config.extended_profit_min_usd and _vol > 0:
            if execute_partial_close(ticket, _sym, _vol, close_fraction=algo_config.staged_book_level_2_pct):
                account_state["staged_book_2_done"] = True
                logger.info(f"[BREAKOUT] Stage-2 partial book at +${algo_config.extended_profit_min_usd:.2f}")
                return

        # If momentum weak after +$7, exit remaining. Otherwise hold till +$10.
        if floating_pnl >= algo_config.extended_profit_min_usd and not continuation_bias:
            if close_trade(ticket, _sym, side, "ALGO:BOOK_7_WEAK"):
                return
        if floating_pnl >= algo_config.extended_profit_max_usd:
            if close_trade(ticket, _sym, side, "ALGO:BOOK_10_STAGED"):
                return

    # Human-style SL avoidance:
    # If price has moved too close to SL, exit early (with/without strong opposite candles).
    try:
        initial_sl = float(account_state.get("initial_sl") or setup.initial_sl or 0.0)
        sl_dist = abs(entry - initial_sl)
        if sl_dist > 0 and _candles_hm and len(_candles_hm) >= 2:
            if side == "buy":
                adverse_ratio = max(0.0, (entry - current_price) / sl_dist)
                opposite_pressure = _candles_hm[-1].is_bearish and _candles_hm[-2].is_bearish
            else:
                adverse_ratio = max(0.0, (current_price - entry) / sl_dist)
                opposite_pressure = _candles_hm[-1].is_bullish and _candles_hm[-2].is_bullish
            if adverse_ratio >= algo_config.early_sl_avoid_ratio:
                reason = "ALGO:EARLY_SL_AVOID_STRONG" if opposite_pressure else "ALGO:EARLY_SL_NEAR"
                if close_trade(ticket, _sym, side, reason):
                    return
    except Exception as exc:
        logger.warning(f"[BREAKOUT] Early SL avoid check failed: {exc}")

    profit_r = (current_price - entry) / one_r if side == "buy" else (entry - current_price) / one_r
    new_sl = None

    # ── SL Trail: starts from ANY positive profit ─────────────────────────────
    _candles_trail = _get_candles(_sym, algo_config.execution_timeframe, 20)
    _atr_trail = _calculate_atr(_candles_trail, algo_config.atr_period) if _candles_trail else None
    if profit_r > 0 and _atr_trail:
        initial_sl = float(account_state.get("initial_sl") or setup.initial_sl or 0.0)
        if side == "buy":
            _trail_sl = current_price - _atr_trail * algo_config.trail_atr_mult
            if _trail_sl > initial_sl:
                new_sl = _trail_sl
                account_state["r_stage"] = 3
        else:
            _trail_sl = current_price + _atr_trail * algo_config.trail_atr_mult
            if _trail_sl < initial_sl:
                new_sl = _trail_sl
                account_state["r_stage"] = 3

    if algo_config.dollar_lock_enabled and not bool(account_state.get("dollar_lock_applied")):
        try:
            floating_pnl = float(live_pos.get("pnl", 0))
            current_offset = abs(current_price - entry)
            if floating_pnl >= algo_config.dollar_profit_trigger and current_offset > 0:
                lock_offset = current_offset * (algo_config.dollar_profit_lock / floating_pnl)
                dollar_lock_sl = entry + lock_offset if side == "buy" else entry - lock_offset
                current_sl = float(account_state.get("initial_sl") or setup.initial_sl or 0.0)
                is_better = (side == "buy" and dollar_lock_sl > current_sl) or (side == "sell" and dollar_lock_sl < current_sl)
                if is_better:
                    new_sl = dollar_lock_sl
                    account_state["dollar_lock_applied"] = True
        except Exception as exc:
            logger.warning(f"[BREAKOUT] Dollar lock check failed: {exc}")

    if profit_r >= algo_config.rr_lock_profit and int(account_state.get("r_stage", 0)) < 2:
        r_sl = entry + one_r if side == "buy" else entry - one_r
        account_state["r_stage"] = 2
        new_sl = r_sl if new_sl is None else (max(new_sl, r_sl) if side == "buy" else min(new_sl, r_sl))
    elif profit_r >= algo_config.rr_breakeven and int(account_state.get("r_stage", 0)) < 1:
        r_sl = entry
        account_state["r_stage"] = 1
        new_sl = r_sl if new_sl is None else (max(new_sl, r_sl) if side == "buy" else min(new_sl, r_sl))

    if int(account_state.get("r_stage", 0)) >= 2:
        candles = _get_candles(setup.symbol, algo_config.execution_timeframe, 20)
        atr = _calculate_atr(candles, algo_config.atr_period) if candles else None
        if atr:
            trail_sl = current_price - atr * algo_config.trail_atr_mult if side == "buy" else current_price + atr * algo_config.trail_atr_mult
            new_sl = trail_sl if new_sl is None else (max(new_sl, trail_sl) if side == "buy" else min(new_sl, trail_sl))
            account_state["r_stage"] = 3

    if new_sl is not None:
        current_sl = float(account_state.get("initial_sl") or setup.initial_sl or 0.0)
        should_update = (side == "buy" and new_sl > current_sl) or (side == "sell" and new_sl < current_sl)
        if should_update:
            result = mt5_bridge.modify_position(ticket, sl=new_sl)
            if result.get("success"):
                old_sl = current_sl
                account_state["initial_sl"] = new_sl
                stage_names = {0: "initial", 1: "breakeven", 2: "profit_lock", 3: "trailing"}
                stage = int(account_state.get("r_stage", 0))
                stage_label = stage_names.get(stage, str(stage))
                logger.info(f"[BREAKOUT] SL updated to {new_sl:.5f} (stage={stage_label})")
                # Persist to journal
                from bot.trade_journal import record_sl_trail
                record_sl_trail(ticket, old_sl, new_sl, stage_label)


def _scan_and_trade(symbol: str = None) -> None:
    global _active_breakouts, _last_scan_at, _last_scan_summary

    if symbol is None:
        symbol = algo_config.symbol

    # Per-symbol breakout list
    if symbol not in _active_breakouts:
        _active_breakouts[symbol] = []
    symbol_setups = _active_breakouts[symbol]

    open_positions = _get_open_positions_all_breakout_accounts()
    open_tickets = set()
    for p in open_positions:
        if p.get("id") is not None:
            open_tickets.add(str(p.get("id")))
        if p.get("position_id") is not None:
            open_tickets.add(str(p.get("position_id")))

    with _breakout_lock:
        for setup in symbol_setups:
            # Multi-account positions are managed in the risk loop. Avoid
            # incorrectly marking a trade closed based on a single account snapshot.
            if setup.account_state:
                continue
            if setup.trade_taken and setup.ticket and str(setup.ticket) not in open_tickets:
                pnl_val = 0.0
                try:
                    history = mt5_bridge.get_trade_history(limit=10)
                    for trade in history:
                        if trade.get("ticket") == setup.ticket or trade.get("position_id") == setup.ticket:
                            pnl_val = float(trade.get("pnl", 0))
                            record_trade_pnl(pnl_val)
                            from bot.algo.human_mind import record_trade_result, record_sl_hit
                            record_trade_result(pnl_val)
                            if pnl_val < 0:
                                record_sl_hit(setup.id)
                            break
                except Exception as exc:
                    logger.warning(f"[BREAKOUT] Could not fetch PnL for ticket {setup.ticket}: {exc}")

                setup.trade_taken = False
                setup.ticket = None
                setup.r_stage = 0
                setup.dollar_lock_applied = False
                setup.staged_book_1_done = False
                setup.staged_book_2_done = False
                setup.active = pnl_val >= 0

    candles_analysis = _get_candles(symbol, algo_config.analysis_timeframe, algo_config.breakout_lookback + 60)
    if len(candles_analysis) < algo_config.breakout_lookback + 2:
        logger.debug(f"[BREAKOUT] Not enough candles for {symbol} on analysis timeframe")
        return

    new_setups = _detect_breakouts(candles_analysis)
    added_count = 0
    with _breakout_lock:
        existing_ids = {setup.id for setup in symbol_setups}
        for setup in new_setups:
            if setup.id in existing_ids:
                continue
            if algo_config.require_trend_alignment and not _is_trend_aligned(candles_analysis, setup.direction):
                continue
            if algo_config.require_volatility_filter and not _is_volatility_sufficient(candles_analysis):
                continue
            setup.symbol = symbol  # tag setup with its symbol
            symbol_setups.append(setup)
            added_count += 1
            logger.info(
                f"[BREAKOUT] New {setup.direction} breakout on {symbol} | "
                f"Level: {setup.breakout_level:.5f} | Range: {setup.range_low:.5f}-{setup.range_high:.5f} | "
                f"Time: {setup.time}"
            )

        _active_breakouts[symbol] = [s for s in symbol_setups if s.active or s.trade_taken]
        _active_breakouts[symbol] = sorted(_active_breakouts[symbol], key=lambda item: item.time, reverse=True)[:algo_config.max_active_breakouts]
        symbol_setups = _active_breakouts[symbol]

    logger.debug(
        f"[BREAKOUT] Scan complete for {symbol} | "
        f"detected={len(new_setups)} | added={added_count} | tracked={len(symbol_setups)}"
    )
    _last_scan_at = datetime.now().isoformat()
    _last_scan_summary[symbol] = {
        "symbol": symbol,
        "detected": len(new_setups),
        "added": added_count,
        "tracked": len(symbol_setups),
        "at": _last_scan_at,
    }

    allowed, block_reason = can_trade_with_reason()
    if not state.running or not algo_config.enabled or not allowed:
        if state.running and algo_config.enabled and not allowed:
            logger.debug(f"[BREAKOUT] Scan gate blocked | reason={block_reason} | symbol={symbol}")
        return

    open_positions = mt5_bridge.get_open_positions()
    open_tickets = set()
    for p in open_positions:
        if p.get("id") is not None:
            open_tickets.add(str(p.get("id")))
        if p.get("position_id") is not None:
            open_tickets.add(str(p.get("position_id")))
    # Count algo positions for THIS symbol only — don't block other symbols
    algo_positions = [
        p for p in open_positions
        if "ALGO:" in str(p.get("comment", "")) and p.get("symbol") == symbol
    ]

    with _breakout_lock:
        for setup in symbol_setups:
            if setup.trade_taken and setup.ticket and str(setup.ticket) not in open_tickets:
                setup.trade_taken = False
                setup.active = True
                setup.ticket = None
                setup.dollar_lock_applied = False
                setup.r_stage = 0
                setup.staged_book_1_done = False
                setup.staged_book_2_done = False

    if len(algo_positions) >= 2:
        return

    candles_exec = _get_candles(symbol, algo_config.execution_timeframe, 25)
    if len(candles_exec) < 5:
        return

    current_price = _get_current_price(symbol, side="mid")
    if current_price is None:
        return

    with _breakout_lock:
        for setup in symbol_setups:
            if not setup.active or setup.trade_taken:
                continue
            if setup.trade_count >= algo_config.max_trades_per_setup:
                setup.active = False
                continue
            if setup.direction == "bullish" and current_price < setup.range_low:
                setup.active = False
                continue
            if setup.direction == "bearish" and current_price > setup.range_high:
                setup.active = False
                continue

            entry = _check_entry_signal(setup, candles_exec)
            if entry:
                # ── Human Mind gate ───────────────────────────────────────────
                if algo_config.use_human_mind_gate:
                    from bot.algo.human_mind import can_enter_trade
                    allowed, reason = can_enter_trade(
                        symbol=symbol,
                        direction=setup.direction,
                        candles=candles_exec,
                        open_positions=open_positions,
                    )
                    if not allowed:
                        logger.info(f"[BREAKOUT] Trade blocked by human_mind: {reason} | {setup.id}")
                        continue
                _execute_breakout_trade(setup, entry)
                break


def _risk_check_loop() -> None:
    global _algo_running
    logger.info("[BREAKOUT] Risk check loop started")
    while _algo_running:
        try:
            if mt5_bridge.ensure_connected():
                # Multi-account management (direct MT5)
                if not mt5_bridge.USE_BRIDGE and MT5_AVAILABLE:
                    from bot.accounts import get_accounts_for_strategy, connect_account_by_login, reconnect_primary
                    accounts = get_accounts_for_strategy("breakout")
                    for acc in accounts:
                        if not connect_account_by_login(acc.login):
                            continue
                        open_positions = mt5_bridge.get_open_positions()

                        # Per-account "non-xau basket" profit close
                        try:
                            from bot.algo.human_mind import check_and_close_all_on_profit_target
                            check_and_close_all_on_profit_target(open_positions)
                        except Exception as _pte:
                            logger.warning(f"[BREAKOUT] Profit target close check failed: {_pte}")

                        open_tickets = set()
                        for p in open_positions:
                            if p.get("id") is not None:
                                open_tickets.add(str(p.get("id")))
                            if p.get("position_id") is not None:
                                open_tickets.add(str(p.get("position_id")))

                        with _breakout_lock:
                            all_setups = [s for setups in _active_breakouts.values() for s in setups]
                            for setup in all_setups:
                                st = setup.account_state.get(str(acc.login)) if getattr(setup, "account_state", None) else None
                                if not st:
                                    continue
                                ticket = int(st.get("ticket") or 0)
                                if not ticket:
                                    continue
                                # Closed?
                                if str(ticket) not in open_tickets:
                                    pnl_val = 0.0
                                    try:
                                        history = mt5_bridge.get_trade_history(limit=50)
                                        for trade in history:
                                            if trade.get("ticket") == ticket or trade.get("position_id") == ticket:
                                                pnl_val = float(trade.get("pnl", 0))
                                                record_trade_pnl(pnl_val)
                                                from bot.algo.human_mind import record_trade_result, record_sl_hit
                                                record_trade_result(pnl_val)
                                                if pnl_val < 0:
                                                    record_sl_hit(setup.id)
                                                break
                                    except Exception as exc:
                                        logger.warning(f"[BREAKOUT] Could not fetch PnL for ticket {ticket}: {exc}")
                                    # Remove per-account state
                                    try:
                                        setup.account_state.pop(str(acc.login), None)
                                    except Exception:
                                        pass
                                    # If all accounts closed, reset setup flags
                                    if not setup.account_state:
                                        setup.trade_taken = False
                                        setup.ticket = None
                                        setup.r_stage = 0
                                        setup.dollar_lock_applied = False
                                        setup.staged_book_1_done = False
                                        setup.staged_book_2_done = False
                                        setup.active = pnl_val >= 0
                                    continue

                                # Still open: manage risk for THIS account/ticket
                                expected_tag = f"ALGO:BRK:{setup.id[:8]}"
                                live_pos = None
                                for pos in open_positions:
                                    pid = pos.get("id") or pos.get("position_id")
                                    if pid == ticket:
                                        live_pos = pos
                                        break
                                if live_pos is None:
                                    # Fallback by comment+symbol
                                    for pos in open_positions:
                                        if (
                                            str(pos.get("symbol", "")) == str(getattr(setup, "symbol", ""))
                                            and expected_tag in str(pos.get("comment", "") or "")
                                        ):
                                            live_pos = pos
                                            break
                                if live_pos:
                                    _manage_open_trade_risk_for_account(
                                        setup=setup,
                                        live_pos=live_pos,
                                        ticket=ticket,
                                        account_state=st,
                                    )
                    reconnect_primary()
                else:
                    # Bridge mode: single-account management (legacy)
                    open_positions = mt5_bridge.get_open_positions()
                    open_tickets = set()
                    for p in open_positions:
                        if p.get("id") is not None:
                            open_tickets.add(str(p.get("id")))
                        if p.get("position_id") is not None:
                            open_tickets.add(str(p.get("position_id")))
                    with _breakout_lock:
                        all_setups = [s for setups in _active_breakouts.values() for s in setups]
                        for setup in all_setups:
                            if setup.trade_taken and setup.ticket and str(setup.ticket) in open_tickets:
                                st = setup.account_state.get("global") if getattr(setup, "account_state", None) else {}
                                _manage_open_trade_risk_for_account(
                                    setup=setup,
                                    live_pos=_find_live_position_for_setup(setup, open_positions) or {},
                                    ticket=int(setup.ticket),
                                    account_state=st,
                                )
        except Exception as exc:
            logger.error(f"[BREAKOUT] Risk check error: {exc}")
        time.sleep(algo_config.risk_check_interval_seconds)
    logger.info("[BREAKOUT] Risk check loop stopped")


def _algo_loop() -> None:
    global _algo_running
    symbols = algo_config.get_symbols()
    logger.info(
        f"[BREAKOUT] Strategy started | Symbols: {symbols} | "
        f"Analysis TF: {algo_config.analysis_timeframe}m | Execution TF: {algo_config.execution_timeframe}m"
    )
    while _algo_running:
        try:
            if mt5_bridge.ensure_connected():
                for sym in algo_config.get_symbols():
                    try:
                        _scan_and_trade(sym)
                    except Exception as e:
                        logger.error(f"[BREAKOUT] Scan error for {sym}: {e}")
        except Exception as exc:
            logger.error(f"[BREAKOUT] Scan error: {exc}")
        time.sleep(algo_config.scan_interval_seconds)
    logger.info("[BREAKOUT] Strategy stopped")


def start_algo() -> bool:
    global _algo_running, _algo_thread, _risk_thread
    if _algo_running:
        logger.warning("[BREAKOUT] Already running")
        return False
    _algo_running = True
    _algo_thread = threading.Thread(target=_algo_loop, daemon=True, name="BreakoutAlgoThread")
    _risk_thread = threading.Thread(target=_risk_check_loop, daemon=True, name="BreakoutRiskThread")
    _algo_thread.start()
    _risk_thread.start()
    logger.success(
        f"[BREAKOUT] Strategy started | Scan: {algo_config.scan_interval_seconds}s | "
        f"Risk check: {algo_config.risk_check_interval_seconds}s | "
        f"{'trading ENABLED' if algo_config.enabled else 'scan-only mode'}"
    )
    return True


def stop_algo() -> bool:
    global _algo_running
    if not _algo_running:
        return False
    _algo_running = False
    logger.info("[BREAKOUT] Stopping strategy...")
    return True


def get_algo_status() -> dict:
    with _breakout_lock:
        all_setups_flat = [s for setups in _active_breakouts.values() for s in setups]
        setups = [
            {
                "id": setup.id,
                "direction": setup.direction,
                "breakout_level": setup.breakout_level,
                "range_high": setup.range_high,
                "range_low": setup.range_low,
                "time": setup.time.isoformat(),
                "active": setup.active,
                "trade_taken": setup.trade_taken,
                "ticket": setup.ticket,
            }
            for setup in all_setups_flat
        ]

    return {
        "running": _algo_running,
        "enabled": algo_config.enabled,
        "strategy": "breakout",
        "symbol": algo_config.symbol,
        "symbols": algo_config.get_symbols(),
        "analysis_timeframe": algo_config.analysis_timeframe,
        "execution_timeframe": algo_config.execution_timeframe,
        "risk_reward": algo_config.risk_reward_ratio,
        "risk_percent": algo_config.risk_percent,
        "trail_atr_mult": algo_config.trail_atr_mult,
        "rr_breakeven": algo_config.rr_breakeven,
        "rr_lock_profit": algo_config.rr_lock_profit,
        "use_human_mind_gate": algo_config.use_human_mind_gate,
        "quick_book_profit_usd": algo_config.quick_book_profit_usd,
        "risky_quick_book_profit_usd": algo_config.risky_quick_book_profit_usd,
        "extended_profit_min_usd": algo_config.extended_profit_min_usd,
        "extended_profit_max_usd": algo_config.extended_profit_max_usd,
        "early_sl_avoid_ratio": algo_config.early_sl_avoid_ratio,
        "staged_book_level_1_pct": algo_config.staged_book_level_1_pct,
        "staged_book_level_2_pct": algo_config.staged_book_level_2_pct,
        "active_breakouts": setups,
        "active_order_blocks": [],
        "total_breakouts_tracked": sum(len(v) for v in _active_breakouts.values()),
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
    trail_atr_mult: Optional[float] = None,
    rr_breakeven: Optional[float] = None,
    rr_lock_profit: Optional[float] = None,
    use_human_mind_gate: Optional[bool] = None,
    quick_book_profit_usd: Optional[float] = None,
    risky_quick_book_profit_usd: Optional[float] = None,
    extended_profit_min_usd: Optional[float] = None,
    extended_profit_max_usd: Optional[float] = None,
    early_sl_avoid_ratio: Optional[float] = None,
) -> dict:
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
    if analysis_tf is not None:
        algo_config.analysis_timeframe = analysis_tf
    if execution_tf is not None:
        algo_config.execution_timeframe = execution_tf
    if trail_atr_mult is not None:
        algo_config.trail_atr_mult = float(trail_atr_mult)
    if rr_breakeven is not None:
        algo_config.rr_breakeven = float(rr_breakeven)
    if rr_lock_profit is not None:
        algo_config.rr_lock_profit = float(rr_lock_profit)
    if use_human_mind_gate is not None:
        algo_config.use_human_mind_gate = bool(use_human_mind_gate)
    if quick_book_profit_usd is not None:
        algo_config.quick_book_profit_usd = float(quick_book_profit_usd)
    if risky_quick_book_profit_usd is not None:
        algo_config.risky_quick_book_profit_usd = float(risky_quick_book_profit_usd)
    if extended_profit_min_usd is not None:
        algo_config.extended_profit_min_usd = float(extended_profit_min_usd)
    if extended_profit_max_usd is not None:
        algo_config.extended_profit_max_usd = float(extended_profit_max_usd)
    if early_sl_avoid_ratio is not None:
        algo_config.early_sl_avoid_ratio = float(early_sl_avoid_ratio)

    logger.info(f"[BREAKOUT] Config updated: {algo_config}")
    return get_algo_status()
