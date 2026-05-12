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
    can_trade,
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
    atr_min_multiplier: float = 0.5
    breakout_buffer_atr: float = 0.10
    fvg_min_body_ratio: float = 0.60
    max_active_setups: int = 5
    max_setup_age_bars: int = 20
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
    setups: list[ConfluenceSetup] = []
    if len(candles) < max(algo_config.breakout_lookback + 3, algo_config.atr_period + 3):
        return setups

    c1 = candles[-3]
    c2 = candles[-2]
    c3 = candles[-1]
    atr = _calculate_atr(candles, algo_config.atr_period)
    if atr is None:
        return setups

    prior_window = candles[-(algo_config.breakout_lookback + 3):-3]
    if len(prior_window) < algo_config.breakout_lookback:
        return setups

    prior_high = max(c.high for c in prior_window)
    prior_low = min(c.low for c in prior_window)
    buffer = atr * algo_config.breakout_buffer_atr

    if (
        c2.is_bullish
        and c2.body_ratio >= algo_config.fvg_min_body_ratio
        and c3.low > c1.high
        and c3.close > prior_high + buffer
    ):
        setups.append(
            ConfluenceSetup(
                id=f"bullish_{c3.time.strftime('%Y%m%d%H%M')}",
                direction="bullish",
                ob_high=c1.high,
                ob_low=c1.low,
                ob_mid=(c1.high + c1.low) / 2,
                breakout_level=prior_high,
                time=c3.time,
                created_bar=bar_index,
            )
        )

    if (
        c2.is_bearish
        and c2.body_ratio >= algo_config.fvg_min_body_ratio
        and c3.high < c1.low
        and c3.close < prior_low - buffer
    ):
        setups.append(
            ConfluenceSetup(
                id=f"bearish_{c3.time.strftime('%Y%m%d%H%M')}",
                direction="bearish",
                ob_high=c1.high,
                ob_low=c1.low,
                ob_mid=(c1.high + c1.low) / 2,
                breakout_level=prior_low,
                time=c3.time,
                created_bar=bar_index,
            )
        )

    return setups


def _check_entry_signal(setup: ConfluenceSetup, candles_exec: list[Candle]) -> Optional[float]:
    if len(candles_exec) < 2:
        return None
    last = candles_exec[-1]
    prev = candles_exec[-2]

    if setup.direction == "bullish":
        touched = last.low <= setup.ob_mid and last.low >= setup.ob_low
        confirmed = last.close > setup.ob_mid and prev.close <= setup.ob_mid
        if touched and confirmed:
            return last.close
    else:
        touched = last.high >= setup.ob_mid and last.high <= setup.ob_high
        confirmed = last.close < setup.ob_mid and prev.close >= setup.ob_mid
        if touched and confirmed:
            return last.close
    return None


def _execute_trade(setup: ConfluenceSetup, entry_price: float) -> bool:
    if not can_trade():
        logger.info("[CONFLUENCE] Trade blocked by risk management rules")
        return False

    if check_drawdown():
        logger.info("[CONFLUENCE] Trade blocked: max drawdown exceeded")
        return False

    sl = setup.sl_level
    tp = setup.tp_level(entry_price, algo_config.risk_reward_ratio)
    side = "buy" if setup.direction == "bullish" else "sell"
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
    profit_r = (current_price - entry) / one_r if side == "buy" else (entry - current_price) / one_r
    new_sl = None

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
    global _active_setups, _bar_counter
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
        return

    new_setups = _detect_setups(candles_analysis, _bar_counter)
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

    if not state.running or not algo_config.enabled or not can_trade():
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
                _execute_trade(setup, entry)
                break


def _risk_check_loop() -> None:
    global _algo_running
    logger.info("[CONFLUENCE] Risk check loop started")
    while _algo_running:
        try:
            if mt5_bridge.is_connected():
                open_positions = mt5_bridge.get_open_positions()
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
            if mt5_bridge.is_connected():
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
        "analysis_timeframe": algo_config.analysis_timeframe,
        "execution_timeframe": algo_config.execution_timeframe,
        "risk_reward": algo_config.risk_reward_ratio,
        "risk_percent": algo_config.risk_percent,
        "active_confluence_setups": setups,
        "active_order_blocks": [],
        "total_confluence_setups": len(_active_setups),
    }


def update_algo_config(
    symbol: Optional[str] = None,
    enabled: Optional[bool] = None,
    risk_reward: Optional[float] = None,
    risk_percent: Optional[float] = None,
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
