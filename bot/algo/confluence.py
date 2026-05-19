"""
Order Block + FVG + Breakout confluence strategy for live algo trading.

This strategy keeps the original OB/FVG idea separate from the order_block module
and adds a same-direction range breakout requirement before an OB retest entry.
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
from bot.state import state
from bot.algo.order_block import (
    can_trade_with_reason,
    check_drawdown,
    get_risk_status,
    record_trade_pnl,
)


@dataclass
class AlgoConfig:
    symbol: str = "EURUSD"   # OB+FVG+Breakout — EURUSD only
    symbols: list = None     # Not used for confluence — single symbol only
    analysis_timeframe: int = 15
    execution_timeframe: int = 15
    risk_reward_ratio: float = 1.5
    risk_percent: float = 1.0
    breakout_lookback: int = 10
    trend_ema_period: int = 20
    atr_period: int = 14
    atr_min_multiplier: float = 0.4
    breakout_buffer_atr: float = 0.02
    fvg_min_body_ratio: float = 0.4
    max_active_setups: int = 5
    max_setup_age_bars: int = 30
    scan_interval_seconds: int = 60
    risk_check_interval_seconds: int = 1
    max_trades_per_setup: int = 1
    enabled: bool = True
    rr_breakeven: float = 1.0
    rr_lock_profit: float = 1.5
    trail_atr_mult: float = 1.0
    dollar_profit_trigger: float = 15.0
    dollar_profit_lock: float = 10.0
    dollar_lock_enabled: bool = True

    def get_symbols(self) -> list:
        return [self.symbol]  # Confluence — EURUSD only


algo_config = AlgoConfig()


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
class ConfluenceSetup:
    id: str
    direction: str
    ob_high: float
    ob_low: float
    ob_mid: float
    breakout_level: float
    time: datetime
    active: bool = True
    trade_taken: bool = False
    ticket: Optional[int] = None
    trade_count: int = 0
    entry_price: float = 0.0
    initial_sl: float = 0.0
    one_r: float = 0.0
    r_stage: int = 0
    dollar_lock_applied: bool = False
    created_bar: int = 0

    @property
    def sl_level(self) -> float:
        ob_size = max(self.ob_high - self.ob_low, 0.0)
        buffer = ob_size * 0.10
        if self.direction == "bullish":
            return self.ob_low - buffer
        return self.ob_high + buffer

    def tp_level(self, entry: float, rr: float) -> float:
        sl_distance = abs(entry - self.sl_level)
        if self.direction == "bullish":
            return entry + sl_distance * rr
        return entry - sl_distance * rr


_active_setups: list[ConfluenceSetup] = []
_setup_lock = threading.Lock()
_algo_thread: Optional[threading.Thread] = None
_risk_thread: Optional[threading.Thread] = None
_algo_running = False
_bar_counter = 0
_last_scan_at: Optional[str] = None
_last_scan_summary: dict[str, object] = {}


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
            logger.warning(f"[CONFLUENCE] Bridge candles fetch failed: {exc}")
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


def _get_current_price(symbol: str) -> Optional[float]:
    from bot import mt5_bridge as _bridge

    if _bridge.USE_BRIDGE:
        try:
            response = _bridge._call_bridge(f"/price?symbol={symbol}")
            if response and "bid" in response:
                return float(response["bid"])
        except Exception as exc:
            logger.warning(f"[CONFLUENCE] Bridge price fetch failed: {exc}")
        return None

    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return None
    tick = mt5.symbol_info_tick(symbol)
    return tick.bid if tick else None


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


def _detect_setups(candles: list[Candle], bar_index: int) -> list[ConfluenceSetup]:
    """
    Detect OB + FVG + Breakout confluence setups.

    2-phase approach (realistic):
    Phase 1 — Breakout: scan last N candles for a strong breakout above/below prior range.
    Phase 2 — OB zone: the candle just before the explosive breakout candle is the Order Block.

    Entry is triggered separately in _check_entry_signal when price retests the OB zone.
    """
    setups: list[ConfluenceSetup] = []
    if len(candles) < max(algo_config.breakout_lookback + 3, algo_config.atr_period + 3):
        return setups

    atr = _calculate_atr(candles, algo_config.atr_period)
    if atr is None:
        return setups

    buffer = atr * algo_config.breakout_buffer_atr

    # Scan last few candles for breakout (not just the last 3)
    scan_start = max(algo_config.breakout_lookback + 2, len(candles) - 5)
    for idx in range(scan_start, len(candles)):
        c_break = candles[idx]          # breakout candle
        c_ob = candles[idx - 1]         # order block = candle before breakout
        prior_window = candles[max(0, idx - algo_config.breakout_lookback - 1):idx - 1]

        if len(prior_window) < algo_config.breakout_lookback:
            continue

        prior_high = max(c.high for c in prior_window)
        prior_low = min(c.low for c in prior_window)

        # ── Bullish breakout ──────────────────────────────────────────────────
        if (
            c_break.is_bullish
            and c_break.body_ratio >= algo_config.fvg_min_body_ratio
            and c_break.close > prior_high + buffer
        ):
            setup_id = f"bullish_{c_break.time.strftime('%Y%m%d%H%M')}"
            setups.append(
                ConfluenceSetup(
                    id=setup_id,
                    direction="bullish",
                    ob_high=c_ob.high,
                    ob_low=c_ob.low,
                    ob_mid=(c_ob.high + c_ob.low) / 2,
                    breakout_level=prior_high,
                    time=c_break.time,
                    created_bar=bar_index,
                )
            )
            logger.debug(
                f"[CONFLUENCE] Bullish breakout detected | "
                f"OB: {c_ob.low:.5f}-{c_ob.high:.5f} | "
                f"Breakout level: {prior_high:.5f} | "
                f"Close: {c_break.close:.5f}"
            )

        # ── Bearish breakout ──────────────────────────────────────────────────
        elif (
            c_break.is_bearish
            and c_break.body_ratio >= algo_config.fvg_min_body_ratio
            and c_break.close < prior_low - buffer
        ):
            setup_id = f"bearish_{c_break.time.strftime('%Y%m%d%H%M')}"
            setups.append(
                ConfluenceSetup(
                    id=setup_id,
                    direction="bearish",
                    ob_high=c_ob.high,
                    ob_low=c_ob.low,
                    ob_mid=(c_ob.high + c_ob.low) / 2,
                    breakout_level=prior_low,
                    time=c_break.time,
                    created_bar=bar_index,
                )
            )
            logger.debug(
                f"[CONFLUENCE] Bearish breakout detected | "
                f"OB: {c_ob.low:.5f}-{c_ob.high:.5f} | "
                f"Breakout level: {prior_low:.5f} | "
                f"Close: {c_break.close:.5f}"
            )

    return setups


def _check_entry_signal(setup: ConfluenceSetup, candles_exec: list[Candle]) -> Optional[float]:
    """
    Entry signal: price retraces into OB zone and shows rejection.

    Bullish: price touches OB zone (between ob_low and ob_high) and closes bullish
    Bearish: price touches OB zone and closes bearish

    Relaxed from strict midpoint cross to zone touch + directional close.
    """
    if len(candles_exec) < 2:
        return None
    last = candles_exec[-1]
    prev = candles_exec[-2]

    if setup.direction == "bullish":
        # Price must touch the OB zone (low dips into zone)
        in_zone = last.low <= setup.ob_high and last.low >= setup.ob_low
        # Confirmation: close above OB midpoint with bullish candle
        confirmed = last.close >= setup.ob_mid and last.is_bullish
        if in_zone and confirmed:
            logger.debug(
                f"[CONFLUENCE] Bullish entry signal | "
                f"OB zone: {setup.ob_low:.5f}-{setup.ob_high:.5f} | "
                f"last.low={last.low:.5f} last.close={last.close:.5f}"
            )
            return last.close
    else:
        # Price must touch the OB zone (high reaches into zone)
        in_zone = last.high >= setup.ob_low and last.high <= setup.ob_high
        # Confirmation: close below OB midpoint with bearish candle
        confirmed = last.close <= setup.ob_mid and last.is_bearish
        if in_zone and confirmed:
            logger.debug(
                f"[CONFLUENCE] Bearish entry signal | "
                f"OB zone: {setup.ob_low:.5f}-{setup.ob_high:.5f} | "
                f"last.high={last.high:.5f} last.close={last.close:.5f}"
            )
            return last.close
    return None


def _execute_trade(setup: ConfluenceSetup, entry_price: float) -> bool:
    allowed, block_reason = can_trade_with_reason()
    if not allowed:
        logger.info(f"[CONFLUENCE] Trade blocked by risk management | reason={block_reason} | symbol={algo_config.symbol}")
        return False

    if check_drawdown():
        logger.info("[CONFLUENCE] Trade blocked: max drawdown exceeded")
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
            _sym_info = _mt5.symbol_info(algo_config.symbol)
            _tick_info = _mt5.symbol_info_tick(algo_config.symbol)
            if _sym_info and _tick_info:
                _price = _tick_info.ask if side == "buy" else _tick_info.bid
                _lot = max(_sym_info.volume_min, 0.01)
                _order_type = _mt5.ORDER_TYPE_BUY if side == "buy" else _mt5.ORDER_TYPE_SELL
                _dollar_per_unit = abs(_mt5.order_calc_profit(_order_type, algo_config.symbol, _lot, _price, _price + _sym_info.trade_tick_size) or 0)
                if _dollar_per_unit > 0:
                    _max_dist = _cap_usd * (_sym_info.trade_tick_size / _dollar_per_unit)
        elif mt5_bridge.USE_BRIDGE:
            _symbol_dollar_per_point = {
                "XAUUSD": 0.01, "EURUSD": 0.1, "USDJPY": 0.1, "GBPUSD": 0.1, "USDCHF": 0.1,
            }
            _max_dist = _cap_usd * _symbol_dollar_per_point.get(algo_config.symbol, 0.1)

        if _max_dist and _max_dist > 0:
            if _sl_dist > _max_dist:
                sl = entry_price - _max_dist if side == "buy" else entry_price + _max_dist
                logger.info(f"[CONFLUENCE] SL capped to ${_cap_usd}: {sl:.5f}")
            if _tp_dist > _max_dist:
                tp = entry_price + _max_dist if side == "buy" else entry_price - _max_dist
                logger.info(f"[CONFLUENCE] TP capped to ${_cap_usd}: {tp:.5f}")
    except Exception as _cap_exc:
        logger.warning(f"[CONFLUENCE] $10 cap calculation failed: {_cap_exc}")

    # Non-XAU pairs: force fixed 100-point target.
    _sym = str(getattr(setup, "symbol", "") or algo_config.symbol).upper()
    if _sym != "XAUUSD":
        pip_size = 0.01 if _sym.endswith("JPY") else 0.0001
        point_size = pip_size / 10.0
        tp = entry_price + (100 * point_size) if side == "buy" else entry_price - (100 * point_size)
        logger.info(f"[CONFLUENCE] Non-XAU fixed TP applied: 100 points -> TP={tp:.5f}")

    one_r = abs(entry_price - sl)

    # Execute only on accounts with 'confluence' strategy assigned
    from bot.accounts import get_all_accounts, _connect_account, _reconnect_primary
    from bot.accounts import _execute_single

    conf_accounts = [
        acc for acc in get_all_accounts()
        if acc.enabled and "confluence" in (acc.strategy or [])
    ]

    ticket = None
    if not conf_accounts:
        logger.warning("[CONFLUENCE] No accounts with 'confluence' strategy — using primary")
        result = mt5_bridge.open_trade(
            symbol=algo_config.symbol,
            side=side,
            sl=sl,
            tp=tp,
            entry=entry_price,
            order_type="market",
            risk_percent=algo_config.risk_percent,
            comment=f"ALGO:CONF:{setup.id[:8]}",
        )
        if not result.get("success"):
            logger.error(f"[CONFLUENCE] Trade failed: {result.get('message')}")
            return False
        ticket = result.get("ticket")
    else:
        results = []
        for acc in conf_accounts:
            try:
                if _connect_account(acc):
                    r = _execute_single(
                        symbol=algo_config.symbol,
                        side=side,
                        sl=sl,
                        tp=tp,
                        entry=entry_price,
                        order_type="market",
                        risk_percent=algo_config.risk_percent,
                        comment=f"ALGO:CONF:{setup.id[:8]}",
                    )
                    r["account_label"] = acc.label
                    r["login"] = acc.login
                    results.append(r)
            except Exception as _e:
                logger.error(f"[CONFLUENCE] Trade error on {acc.label}: {_e}")
        _reconnect_primary()
        successes = [r for r in results if r.get("success")]
        if not successes:
            logger.error(f"[CONFLUENCE] Trade failed on all confluence accounts: {results}")
            return False
        ticket = successes[0].get("ticket")
        for r in successes:
            logger.success(f"[CONFLUENCE] Trade on {r.get('account_label')} | Ticket: {r.get('ticket')}")

    setup.trade_taken = True
    setup.ticket = ticket
    setup.active = False
    setup.trade_count += 1
    setup.entry_price = entry_price
    setup._opened_at = datetime.utcnow()
    setup._partial_closed = False
    setup.initial_sl = sl
    setup.one_r = one_r
    setup.r_stage = 0

    # Persist to trade journal
    from bot.trade_journal import record_trade_open
    entry_reason = f"OB+FVG+Breakout Confluence {setup.direction} on {algo_config.symbol}"
    record_trade_open(
        ticket=ticket,
        symbol=algo_config.symbol,
        side=side,
        entry_price=entry_price,
        initial_sl=sl,
        initial_tp=tp,
        one_r=one_r,
        risk_reward=algo_config.risk_reward_ratio,
        entry_reason=entry_reason,
        source="ALGO:Confluence",
        strategy="confluence",
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
        "source": "ALGO:Confluence",
        "setup_id": setup.id,
        "ticket": ticket,
    })
    logger.success(
        f"[CONFLUENCE] Trade opened | {algo_config.symbol} {side.upper()} | "
        f"Entry: {entry_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f} | Ticket: {ticket}"
    )
    return True


def _manage_open_trade_risk(setup: ConfluenceSetup) -> None:
    if not setup.ticket or setup.one_r <= 0:
        return

    current_price = _get_current_price(algo_config.symbol)
    if current_price is None:
        return

    side = "buy" if setup.direction == "bullish" else "sell"
    entry = setup.entry_price
    one_r = setup.one_r

    # ── Human Mind: partial close, early exit, time-based exit ───────────────
    from bot.algo.human_mind import (
        should_early_exit, should_time_exit, should_partial_close,
        execute_partial_close, close_trade,
    )
    _candles_hm = _get_candles(algo_config.symbol, algo_config.execution_timeframe, 10)

    if not getattr(setup, '_partial_closed', False):
        if should_partial_close(entry, current_price, one_r, side, False):
            try:
                _positions = mt5_bridge.get_open_positions()
                for _pos in _positions:
                    if _pos.get("id") == setup.ticket or _pos.get("position_id") == setup.ticket:
                        _vol = float(_pos.get("volume", 0.01))
                        if execute_partial_close(setup.ticket, algo_config.symbol, _vol):
                            setup._partial_closed = True
                            logger.info(f"[CONFLUENCE] Partial close done on ticket {setup.ticket} at 1R")
                        break
            except Exception as _exc:
                logger.warning(f"[CONFLUENCE] Partial close check failed: {_exc}")

    if _candles_hm and should_early_exit(side, _candles_hm):
        if close_trade(setup.ticket, algo_config.symbol, side, "ALGO:REVERSAL_EXIT"):
            setup.trade_taken = False
            setup.active = False
            setup.ticket = None
            return

    _opened_at = getattr(setup, '_opened_at', None)
    if _opened_at and should_time_exit(_opened_at, entry, current_price, one_r, side):
        if close_trade(setup.ticket, algo_config.symbol, side, "ALGO:TIME_EXIT"):
            setup.trade_taken = False
            setup.active = False
            setup.ticket = None
            return

    profit_r = (current_price - entry) / one_r if side == "buy" else (entry - current_price) / one_r
    new_sl = None

    # ── SL Trail: starts from ANY positive profit ─────────────────────────────
    _candles_trail = _get_candles(algo_config.symbol, algo_config.execution_timeframe, 20)
    _atr_trail = _calculate_atr(_candles_trail, algo_config.atr_period) if _candles_trail else None
    if profit_r > 0 and _atr_trail:
        if side == "buy":
            _trail_sl = current_price - _atr_trail * algo_config.trail_atr_mult
            if _trail_sl > setup.initial_sl:
                new_sl = _trail_sl
                setup.r_stage = 3
        else:
            _trail_sl = current_price + _atr_trail * algo_config.trail_atr_mult
            if _trail_sl < setup.initial_sl:
                new_sl = _trail_sl
                setup.r_stage = 3

    if algo_config.dollar_lock_enabled and not setup.dollar_lock_applied:
        try:
            open_positions = mt5_bridge.get_open_positions()
            for pos in open_positions:
                if pos.get("id") == setup.ticket or pos.get("position_id") == setup.ticket:
                    floating_pnl = float(pos.get("pnl", 0))
                    current_offset = abs(current_price - entry)
                    if floating_pnl >= algo_config.dollar_profit_trigger and current_offset > 0:
                        lock_offset = current_offset * (algo_config.dollar_profit_lock / floating_pnl)
                        dollar_lock_sl = entry + lock_offset if side == "buy" else entry - lock_offset
                        current_sl = setup.initial_sl
                        is_better = (side == "buy" and dollar_lock_sl > current_sl) or (side == "sell" and dollar_lock_sl < current_sl)
                        if is_better:
                            new_sl = dollar_lock_sl
                            setup.dollar_lock_applied = True
                    break
        except Exception as exc:
            logger.warning(f"[CONFLUENCE] Dollar lock check failed: {exc}")

    if profit_r >= algo_config.rr_lock_profit and setup.r_stage < 2:
        r_sl = entry + one_r if side == "buy" else entry - one_r
        setup.r_stage = 2
        new_sl = r_sl if new_sl is None else (max(new_sl, r_sl) if side == "buy" else min(new_sl, r_sl))
    elif profit_r >= algo_config.rr_breakeven and setup.r_stage < 1:
        r_sl = entry
        setup.r_stage = 1
        new_sl = r_sl if new_sl is None else (max(new_sl, r_sl) if side == "buy" else min(new_sl, r_sl))

    if setup.r_stage >= 2:
        candles = _get_candles(algo_config.symbol, algo_config.execution_timeframe, 20)
        atr = _calculate_atr(candles, algo_config.atr_period) if candles else None
        if atr:
            trail_sl = current_price - atr * algo_config.trail_atr_mult if side == "buy" else current_price + atr * algo_config.trail_atr_mult
            new_sl = trail_sl if new_sl is None else (max(new_sl, trail_sl) if side == "buy" else min(new_sl, trail_sl))
            setup.r_stage = 3

    if new_sl is not None:
        current_sl = setup.initial_sl
        should_update = (side == "buy" and new_sl > current_sl) or (side == "sell" and new_sl < current_sl)
        if should_update:
            result = mt5_bridge.modify_position(setup.ticket, sl=new_sl)
            if result.get("success"):
                setup.initial_sl = new_sl
                logger.info(f"[CONFLUENCE] SL updated to {new_sl:.5f} (stage={setup.r_stage})")


def _scan_and_trade() -> None:
    global _active_setups, _bar_counter, _last_scan_at, _last_scan_summary
    _bar_counter += 1

    symbol = algo_config.symbol
    check_drawdown()

    open_positions = mt5_bridge.get_open_positions()
    open_tickets = {p.get("id") for p in open_positions}

    with _setup_lock:
        for setup in _active_setups:
            if setup.trade_taken and setup.ticket and setup.ticket not in open_tickets:
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
                    logger.warning(f"[CONFLUENCE] Could not fetch PnL for ticket {setup.ticket}: {exc}")
                setup.trade_taken = False
                setup.ticket = None
                setup.r_stage = 0
                setup.dollar_lock_applied = False
                setup.active = pnl_val >= 0

    candles_analysis = _get_candles(symbol, algo_config.analysis_timeframe, max(algo_config.breakout_lookback + 10, 80))
    if len(candles_analysis) < algo_config.breakout_lookback + 3:
        logger.debug(f"[CONFLUENCE] Not enough candles for {symbol} on analysis timeframe")
        return

    new_setups = _detect_setups(candles_analysis, _bar_counter)
    added_count = 0
    with _setup_lock:
        existing_ids = {setup.id for setup in _active_setups}
        for setup in new_setups:
            if setup.id in existing_ids:
                continue
            if not _is_trend_aligned(candles_analysis, setup.direction):
                continue
            if not _is_volatility_sufficient(candles_analysis):
                continue
            _active_setups.append(setup)
            added_count += 1
            logger.info(
                f"[CONFLUENCE] New {setup.direction} setup | "
                f"OB: {setup.ob_low:.5f}-{setup.ob_high:.5f} | Breakout: {setup.breakout_level:.5f}"
            )

        _active_setups = [s for s in _active_setups if (s.active or s.trade_taken)]
        _active_setups = [
            s for s in _active_setups
            if (_bar_counter - s.created_bar) <= algo_config.max_setup_age_bars or s.trade_taken
        ]
        _active_setups = sorted(_active_setups, key=lambda item: item.time, reverse=True)[:algo_config.max_active_setups]

    logger.debug(
        f"[CONFLUENCE] Scan complete for {symbol} | "
        f"detected={len(new_setups)} | added={added_count} | tracked={len(_active_setups)}"
    )
    _last_scan_at = datetime.now().isoformat()
    _last_scan_summary = {
        "symbol": symbol,
        "detected": len(new_setups),
        "added": added_count,
        "tracked": len(_active_setups),
        "at": _last_scan_at,
    }

    allowed, block_reason = can_trade_with_reason()
    if not state.running or not algo_config.enabled or not allowed:
        if state.running and algo_config.enabled and not allowed:
            logger.debug(f"[CONFLUENCE] Scan gate blocked | reason={block_reason} | symbol={symbol}")
        return

    open_positions = mt5_bridge.get_open_positions()
    algo_positions = [p for p in open_positions if "ALGO:" in str(p.get("comment", ""))]
    if len(algo_positions) >= 2:
        return

    candles_exec = _get_candles(symbol, algo_config.execution_timeframe, 20)
    if len(candles_exec) < 3:
        return

    current_price = _get_current_price(symbol)
    if current_price is None:
        return

    with _setup_lock:
        for setup in _active_setups:
            if not setup.active or setup.trade_taken:
                continue
            if setup.trade_count >= algo_config.max_trades_per_setup:
                setup.active = False
                continue
            if setup.direction == "bullish" and current_price < setup.ob_low:
                setup.active = False
                continue
            if setup.direction == "bearish" and current_price > setup.ob_high:
                setup.active = False
                continue
            entry = _check_entry_signal(setup, candles_exec)
            if entry:
                # ── Human Mind gate ───────────────────────────────────────────
                from bot.algo.human_mind import can_enter_trade
                allowed, reason = can_enter_trade(
                    symbol=symbol,
                    direction=setup.direction,
                    candles=candles_exec,
                    open_positions=open_positions,
                )
                if not allowed:
                    logger.info(f"[CONFLUENCE] Trade blocked by human_mind: {reason} | {setup.id}")
                    continue
                _execute_trade(setup, entry)
                break


def _risk_check_loop() -> None:
    global _algo_running
    logger.info("[CONFLUENCE] Risk check loop started")
    while _algo_running:
        try:
            if mt5_bridge.ensure_connected():
                open_positions = mt5_bridge.get_open_positions()
                # ── Total portfolio profit close check ────────────────────────
                try:
                    from bot.algo.human_mind import check_and_close_all_on_profit_target
                    if check_and_close_all_on_profit_target(open_positions):
                        with _setup_lock:
                            for _s in _active_setups:
                                if _s.trade_taken:
                                    _s.trade_taken = False
                                    _s.active = False
                                    _s.ticket = None
                        time.sleep(algo_config.risk_check_interval_seconds)
                        continue
                except Exception as _pte:
                    logger.warning(f"[CONFLUENCE] Profit target close check failed: {_pte}")

                open_tickets = {p.get("id") for p in open_positions}
                with _setup_lock:
                    for setup in _active_setups:
                        if setup.trade_taken and setup.ticket in open_tickets:
                            _manage_open_trade_risk(setup)
        except Exception as exc:
            logger.error(f"[CONFLUENCE] Risk check error: {exc}")
        time.sleep(algo_config.risk_check_interval_seconds)
    logger.info("[CONFLUENCE] Risk check loop stopped")


def _algo_loop() -> None:
    global _algo_running
    logger.info(
        f"[CONFLUENCE] Strategy started | Symbol: {algo_config.symbol} | "
        f"Analysis TF: {algo_config.analysis_timeframe}m | Execution TF: {algo_config.execution_timeframe}m"
    )
    while _algo_running:
        try:
            if mt5_bridge.ensure_connected():
                _scan_and_trade()
        except Exception as exc:
            logger.error(f"[CONFLUENCE] Scan error: {exc}")
        time.sleep(algo_config.scan_interval_seconds)
    logger.info("[CONFLUENCE] Strategy stopped")


def start_algo() -> bool:
    global _algo_running, _algo_thread, _risk_thread
    if _algo_running:
        logger.warning("[CONFLUENCE] Already running")
        return False
    _algo_running = True
    _algo_thread = threading.Thread(target=_algo_loop, daemon=True, name="ConfluenceAlgoThread")
    _risk_thread = threading.Thread(target=_risk_check_loop, daemon=True, name="ConfluenceRiskThread")
    _algo_thread.start()
    _risk_thread.start()
    logger.success(
        f"[CONFLUENCE] Strategy started | Scan: {algo_config.scan_interval_seconds}s | "
        f"Risk check: {algo_config.risk_check_interval_seconds}s | "
        f"{'trading ENABLED' if algo_config.enabled else 'scan-only mode'}"
    )
    return True


def stop_algo() -> bool:
    global _algo_running
    if not _algo_running:
        return False
    _algo_running = False
    logger.info("[CONFLUENCE] Stopping strategy...")
    return True


def get_algo_status() -> dict:
    with _setup_lock:
        setups = [
            {
                "id": s.id,
                "direction": s.direction,
                "ob_high": s.ob_high,
                "ob_low": s.ob_low,
                "ob_mid": s.ob_mid,
                "breakout_level": s.breakout_level,
                "time": s.time.isoformat(),
                "active": s.active,
                "trade_taken": s.trade_taken,
                "ticket": s.ticket,
            }
            for s in _active_setups
        ]
    return {
        "running": _algo_running,
        "enabled": algo_config.enabled,
        "strategy": "confluence",
        "symbol": algo_config.symbol,
        "symbols": algo_config.get_symbols(),
        "analysis_timeframe": algo_config.analysis_timeframe,
        "execution_timeframe": algo_config.execution_timeframe,
        "risk_reward": algo_config.risk_reward_ratio,
        "risk_percent": algo_config.risk_percent,
        "active_confluence_setups": setups,
        "active_order_blocks": [],
        "total_confluence_setups": len(_active_setups),
        "last_scan_at": _last_scan_at,
        "scan_summary": _last_scan_summary,
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
    logger.info(f"[CONFLUENCE] Config updated: {algo_config}")
    return get_algo_status()
