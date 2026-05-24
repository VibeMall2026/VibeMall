"""
Multi-Timeframe Support/Resistance Rejection Strategy (MultiTF Rejection)
=========================================================================
HTF (default): 15m  -> builds Support/Resistance levels from swing highs/lows
LTF (default): 5m   -> entry confirmation + execution

BUY:
 - Pick nearest HTF support (pivot low) below/at current price
 - Wait for LTF candle to touch/sweep support (low <= support) AND close above it
 - Entry at confirmation close
 - SL:
    - Normally: previous LTF candle close
    - Special rule: if |prev_close - current_open| <= 20 pips -> fixed 50 pip SL from entry
 - TP: RR-based (default RR=2.0)
 - BE: at 1R -> SL to entry
 - Trailing: after BE, for every +10 pips further profit -> move SL +10 pips

SELL is symmetric using HTF resistance (pivot high).
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


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class AlgoConfig:
    symbol: str = "XAUUSD"
    symbols: list[str] | None = None

    analysis_timeframe: int = 15
    execution_timeframe: int = 5

    # S/R detection (pivot/fractal style)
    pivot_lookback: int = 3          # candles on each side for swing confirmation
    max_levels: int = 20             # keep last N supports and N resistances
    level_tolerance_pips: float = 2  # snap/merge levels within this distance (pips)

    # Risk
    risk_reward_ratio: float = 2.0
    risk_percent: float = 1.0
    enabled: bool = True

    trend_filter_enabled: bool = True
    trend_ema_period: int = 50

    atr_filter_enabled: bool = True
    atr_period: int = 14
    atr_min_multiplier: float = 0.7

    max_spread_pips: float = 60.0
    min_rejection_close_pips: float = 5.0
    require_confirmation_candle_direction: bool = True
    min_minutes_between_trades: int = 20

    # SL rules
    special_sl_trigger_pips: float = 20.0
    special_sl_fixed_pips: float = 50.0

    # BE + trail rules
    trail_step_pips: float = 10.0

    scan_interval_seconds: int = 30
    risk_check_interval_seconds: int = 1

    # XAUUSD pip size selected by user: 0.01 = 1 pip
    xau_pip_size: float = 0.01

    def get_symbols(self) -> list[str]:
        if self.symbols:
            return list(self.symbols)
        return [self.symbol]


algo_config = AlgoConfig()


def _normalize_symbols(symbol_value: Optional[str]) -> list[str]:
    if not symbol_value:
        return []
    return [part.strip().upper() for part in str(symbol_value).split(",") if part.strip()]


def _pip_size(symbol: str) -> float:
    sym = (symbol or "").upper()
    # User preference for XAUUSD
    if sym.startswith("XAU"):
        return float(algo_config.xau_pip_size)
    # JPY pairs commonly use 0.01 as pip
    if sym.endswith("JPY"):
        return 0.01
    # Default forex pip
    return 0.0001


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class SRLevel:
    price: float
    kind: str  # "support" | "resistance"
    time: datetime


@dataclass
class TradeState:
    ticket: int
    symbol: str
    side: str  # "buy" | "sell"
    entry: float
    sl: float
    tp: float
    risk_pips: float
    be_applied: bool = False
    last_trail_step: int = 0


# ── Runtime state ─────────────────────────────────────────────────────────────

_levels: dict[str, dict[str, list[SRLevel]]] = {}  # symbol -> {"support":[], "resistance":[]}
_open_trades: dict[int, TradeState] = {}  # ticket -> TradeState

_levels_lock = threading.Lock()

_algo_thread: Optional[threading.Thread] = None
_risk_thread: Optional[threading.Thread] = None
_algo_running: bool = False

_last_scan_at: Optional[str] = None
_last_scan_summary: dict[str, dict] = {}
_last_trade_at: dict[str, datetime] = {}


# ── MT5 / bridge helpers (same pattern as order_block.py) ─────────────────────

def _get_candles(symbol: str, timeframe_minutes: int, count: int) -> list[Candle]:
    from bot import mt5_bridge as _bridge

    if _bridge.USE_BRIDGE:
        try:
            response = _bridge._call_bridge(
                f"/candles?symbol={symbol}&timeframe={timeframe_minutes}&count={count}"
            )
            if response and isinstance(response, list):
                out: list[Candle] = []
                for r in response:
                    out.append(Candle(
                        time=datetime.fromisoformat(r["time"]) if isinstance(r.get("time"), str) else datetime.fromtimestamp(r["time"]),
                        open=float(r["open"]),
                        high=float(r["high"]),
                        low=float(r["low"]),
                        close=float(r["close"]),
                        volume=float(r.get("volume", r.get("tick_volume", 0)) or 0),
                    ))
                return out
        except Exception as exc:
            logger.warning(f"[MTF] Bridge candles fetch failed: {exc}")
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
    tf = tf_map.get(timeframe_minutes, mt5.TIMEFRAME_M15)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        return []
    out: list[Candle] = []
    for r in rates:
        out.append(Candle(
            time=datetime.fromtimestamp(r["time"]),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["tick_volume"] or 0),
        ))
    return out


def _get_current_price(symbol: str, side: Optional[str] = None) -> Optional[float]:
    from bot import mt5_bridge as _bridge

    bid_ask = _get_bid_ask(symbol)
    if not bid_ask:
        return None
    bid, ask = bid_ask

    if side == "buy":
        return ask
    if side == "sell":
        return bid
    return (bid + ask) / 2.0


def _get_bid_ask(symbol: str) -> Optional[tuple[float, float]]:
    from bot import mt5_bridge as _bridge

    if _bridge.USE_BRIDGE:
        try:
            response = _bridge._call_bridge(f"/price?symbol={symbol}")
            if response and "bid" in response and "ask" in response:
                bid = float(response["bid"])
                ask = float(response["ask"])
                return bid, ask
        except Exception as exc:
            logger.warning(f"[MTF] Bridge price fetch failed: {exc}")
        return None

    if not MT5_AVAILABLE or not mt5_bridge.is_connected():
        return None
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return None
    return float(tick.bid), float(tick.ask)


def _calculate_ema(values: list[float], period: int) -> Optional[float]:
    p = int(period or 0)
    if p <= 1 or len(values) < p:
        return None
    k = 2.0 / (p + 1.0)
    ema = sum(values[:p]) / float(p)
    for v in values[p:]:
        ema = (float(v) * k) + (ema * (1.0 - k))
    return float(ema)


def _calculate_atr(candles: list[Candle], period: int) -> Optional[float]:
    p = int(period or 0)
    if p <= 1 or len(candles) < (p + 1):
        return None
    trs: list[float] = []
    for i in range(1, len(candles)):
        c = candles[i]
        prev = candles[i - 1]
        tr = max(
            float(c.high - c.low),
            abs(float(c.high - prev.close)),
            abs(float(c.low - prev.close)),
        )
        trs.append(tr)
    window = trs[-p:]
    if len(window) < p:
        return None
    return float(sum(window) / float(p))


# ── S/R detection ─────────────────────────────────────────────────────────────

def _merge_level(levels: list[SRLevel], new_level: SRLevel, tolerance_pips: float, symbol: str) -> None:
    pip = _pip_size(symbol)
    tol = tolerance_pips * pip
    for existing in levels:
        if abs(existing.price - new_level.price) <= tol:
            # Keep the more recent timestamp, keep a blended price (stabilize)
            existing.time = max(existing.time, new_level.time)
            existing.price = (existing.price + new_level.price) / 2.0
            return
    levels.append(new_level)


def _build_sr_levels(symbol: str, candles_15m: list[Candle]) -> tuple[list[SRLevel], list[SRLevel]]:
    lb = max(2, int(algo_config.pivot_lookback))
    if len(candles_15m) < (lb * 2 + 5):
        return [], []

    supports: list[SRLevel] = []
    resistances: list[SRLevel] = []

    # Candles are assumed chronological (oldest -> newest) in bridge? In MT5 copy_rates_from_pos(0,count)
    # returns newest first; order_block treats it as returned and iterates windows. We will normalize to oldest->newest.
    if candles_15m and candles_15m[0].time > candles_15m[-1].time:
        candles = list(reversed(candles_15m))
    else:
        candles = candles_15m

    for i in range(lb, len(candles) - lb):
        c = candles[i]
        left = candles[i - lb:i]
        right = candles[i + 1:i + 1 + lb]
        if not left or not right:
            continue

        # Pivot low => support
        if all(c.low < x.low for x in left) and all(c.low <= x.low for x in right):
            _merge_level(
                supports,
                SRLevel(price=c.low, kind="support", time=c.time),
                tolerance_pips=algo_config.level_tolerance_pips,
                symbol=symbol,
            )

        # Pivot high => resistance
        if all(c.high > x.high for x in left) and all(c.high >= x.high for x in right):
            _merge_level(
                resistances,
                SRLevel(price=c.high, kind="resistance", time=c.time),
                tolerance_pips=algo_config.level_tolerance_pips,
                symbol=symbol,
            )

    # Keep most recent levels
    supports = sorted(supports, key=lambda x: x.time, reverse=True)[:algo_config.max_levels]
    resistances = sorted(resistances, key=lambda x: x.time, reverse=True)[:algo_config.max_levels]
    return supports, resistances


def _nearest_support(price: float, supports: list[SRLevel]) -> Optional[SRLevel]:
    below = [s for s in supports if s.price <= price]
    if not below:
        return None
    return max(below, key=lambda s: s.price)


def _nearest_resistance(price: float, resistances: list[SRLevel]) -> Optional[SRLevel]:
    above = [r for r in resistances if r.price >= price]
    if not above:
        return None
    return min(above, key=lambda r: r.price)


# ── Entry + execution ─────────────────────────────────────────────────────────

def _calc_initial_sl_tp(symbol: str, side: str, entry: float, prev_close: float, current_open: float) -> tuple[float, float, float]:
    """
    Returns (sl, tp, risk_pips)
    """
    pip = _pip_size(symbol)
    special_trigger = algo_config.special_sl_trigger_pips * pip

    use_fixed = abs(prev_close - current_open) <= special_trigger
    if use_fixed:
        risk_pips = algo_config.special_sl_fixed_pips
        risk_dist = risk_pips * pip
        sl = entry - risk_dist if side == "buy" else entry + risk_dist
    else:
        sl = prev_close
        # Safety: SL must be on correct side; otherwise fallback to fixed SL distance
        if side == "buy" and sl >= entry:
            risk_pips = algo_config.special_sl_fixed_pips
            sl = entry - (risk_pips * pip)
        elif side == "sell" and sl <= entry:
            risk_pips = algo_config.special_sl_fixed_pips
            sl = entry + (risk_pips * pip)

    risk_dist = abs(entry - sl)
    risk_pips = risk_dist / pip if pip > 0 else 0.0
    if str(symbol).upper() != "XAUUSD":
        point = pip / 10.0
        tp = entry + (100 * point) if side == "buy" else entry - (100 * point)
    else:
        rr = float(algo_config.risk_reward_ratio or 2.0)
        tp = entry + (risk_dist * rr) if side == "buy" else entry - (risk_dist * rr)
    return sl, tp, float(risk_pips)


def _execute_trade(symbol: str, side: str, entry: float, sl: float, tp: float, level: SRLevel) -> Optional[int]:
    # Execute only on accounts that have 'my_strategy' assigned
    from bot.accounts import get_all_accounts, execute_on_all_accounts, is_account_trade_allowed_today

    accounts = [acc for acc in get_all_accounts() if acc.enabled and "my_strategy" in (acc.strategy or [])]
    comment = f"ALGO:MTF:{level.kind[:1].upper()}:{int(level.price * 100):d}"

    if not accounts:
        # Fallback (single-account mode): still enforce per-account trade halt.
        try:
            if MT5_AVAILABLE:
                info = mt5.account_info()
                login = int(getattr(info, "login", 0) or 0) if info else 0
                if login:
                    allowed_today, halt_reason = is_account_trade_allowed_today(login)
                    if not allowed_today:
                        logger.warning(f"[MTF] Trade blocked (trade-mode): login={login} reason={halt_reason}")
                        return None
        except Exception:
            pass

        logger.warning("[MTF] No accounts with 'my_strategy' assigned — using primary connection")
        result = mt5_bridge.open_trade(
            symbol=symbol,
            side=side,
            sl=sl,
            tp=tp,
            entry=entry,
            order_type="market",
            risk_percent=algo_config.risk_percent,
            comment=comment,
        )
        if not result.get("success"):
            logger.error(f"[MTF] Trade failed: {result.get('message')}")
            return None
        return result.get("ticket")

    # Multi-account execution
    results = execute_on_all_accounts(
        symbol=symbol,
        side=side,
        sl=sl,
        tp=tp,
        entry=entry,
        order_type="market",
        risk_percent=algo_config.risk_percent,
        comment=comment,
        strategy_id="my_strategy",
    )
    successes = [r for r in results if r.get("success")]
    if not successes:
        logger.error(f"[MTF] Trade failed on all my_strategy accounts: {results}")
        return None
    ticket = successes[0].get("ticket")
    for r in successes:
        logger.success(f"[MTF] Trade on {r.get('account_label')} ({r.get('login')}) | Ticket={r.get('ticket')}")
    return ticket


def _maybe_open_trade(symbol: str) -> None:
    global _last_scan_at, _last_scan_summary

    if not state.running or not algo_config.enabled:
        return

    # Do not stack: one open position per symbol for this strategy
    try:
        positions = mt5_bridge.get_open_positions()
        if any((p.get("comment", "") or "").startswith("ALGO:MTF") and p.get("symbol") == symbol for p in positions):
            return
    except Exception:
        pass

    candles_15 = _get_candles(symbol, algo_config.analysis_timeframe, 250)
    candles_5 = _get_candles(symbol, algo_config.execution_timeframe, 50)
    if len(candles_15) < 20 or len(candles_5) < 3:
        return

    if candles_15 and candles_15[0].time > candles_15[-1].time:
        candles_15 = list(reversed(candles_15))

    # Normalize 5m candles to chronological
    if candles_5 and candles_5[0].time > candles_5[-1].time:
        candles_5 = list(reversed(candles_5))

    bid_ask = _get_bid_ask(symbol)
    if not bid_ask:
        return
    bid, ask = bid_ask
    pip = _pip_size(symbol)
    spread_pips = (ask - bid) / pip if pip > 0 else 0.0
    if algo_config.max_spread_pips and spread_pips > float(algo_config.max_spread_pips):
        _last_scan_at = datetime.now().isoformat()
        _last_scan_summary[symbol] = {
            "symbol": symbol,
            "detected": 0,
            "added": 0,
            "tracked": 0,
            "at": _last_scan_at,
            "opened_trade": False,
            "reason": "spread",
            "spread_pips": round(spread_pips, 2),
        }
        return

    current_price = (bid + ask) / 2.0

    if algo_config.min_minutes_between_trades and symbol in _last_trade_at:
        elapsed = (datetime.now() - _last_trade_at[symbol]).total_seconds() / 60.0
        if elapsed < float(algo_config.min_minutes_between_trades):
            _last_scan_at = datetime.now().isoformat()
            _last_scan_summary[symbol] = {
                "symbol": symbol,
                "detected": 0,
                "added": 0,
                "tracked": 0,
                "at": _last_scan_at,
                "opened_trade": False,
                "reason": "cooldown",
                "cooldown_left_min": round(float(algo_config.min_minutes_between_trades) - elapsed, 2),
            }
            return

    closes_15 = [c.close for c in candles_15]
    ema = _calculate_ema(closes_15, algo_config.trend_ema_period) if algo_config.trend_filter_enabled else None
    buy_allowed = True
    sell_allowed = True
    if algo_config.trend_filter_enabled and ema is not None:
        buy_allowed = current_price >= ema
        sell_allowed = current_price <= ema

    atr = _calculate_atr(candles_15, algo_config.atr_period) if algo_config.atr_filter_enabled else None
    atr_ok = True
    if algo_config.atr_filter_enabled and atr is not None:
        mult = float(algo_config.atr_min_multiplier or 1.0)
        lookback = int(algo_config.atr_period) * 3
        if len(candles_15) >= (lookback + 1) and lookback > 0:
            atr_ref = _calculate_atr(candles_15[-(lookback + 1):], lookback) or atr
        else:
            atr_ref = atr
        atr_ok = atr >= (atr_ref * mult)

    if (algo_config.trend_filter_enabled and ema is None) or (algo_config.atr_filter_enabled and atr is None):
        _last_scan_at = datetime.now().isoformat()
        _last_scan_summary[symbol] = {
            "symbol": symbol,
            "detected": 0,
            "added": 0,
            "tracked": 0,
            "at": _last_scan_at,
            "opened_trade": False,
            "reason": "indicators_unavailable",
        }
        return

    if not atr_ok:
        _last_scan_at = datetime.now().isoformat()
        _last_scan_summary[symbol] = {
            "symbol": symbol,
            "detected": 0,
            "added": 0,
            "tracked": 0,
            "at": _last_scan_at,
            "opened_trade": False,
            "reason": "atr_filter",
            "atr": atr,
        }
        return

    supports, resistances = _build_sr_levels(symbol, candles_15)
    support = _nearest_support(current_price, supports)
    resistance = _nearest_resistance(current_price, resistances)

    with _levels_lock:
        _levels[symbol] = {"support": supports, "resistance": resistances}

    last = candles_5[-1]   # confirmation candle (just closed)
    prev = candles_5[-2]   # previous candle (SL reference)

    opened = False
    min_close_pips = float(algo_config.min_rejection_close_pips or 0.0)
    min_close_dist = min_close_pips * pip
    if support and buy_allowed and last.low <= support.price and last.close > (support.price + min_close_dist):
        if algo_config.require_confirmation_candle_direction and not (last.close > last.open):
            pass
        else:
            side = "buy"
            entry = last.close
            sl, tp, risk_pips = _calc_initial_sl_tp(symbol, side, entry, prev.close, last.open)
            ticket = _execute_trade(symbol, side, entry, sl, tp, support)
            if ticket:
                _open_trades[ticket] = TradeState(ticket=ticket, symbol=symbol, side=side, entry=entry, sl=sl, tp=tp, risk_pips=risk_pips)
                opened = True
                _last_trade_at[symbol] = datetime.now()
                state.signal_log.insert(0, {
                    "time": datetime.now().isoformat(),
                    "symbol": symbol,
                    "side": side,
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "status": "executed",
                    "source": "ALGO:MultiTF",
                    "strategy": "my_strategy",
                    "level": {"kind": "support", "price": support.price},
                    "ticket": ticket,
                })
                logger.success(f"[MTF] BUY opened | {symbol} | entry={entry:.5f} sl={sl:.5f} tp={tp:.5f}")

    elif resistance and sell_allowed and last.high >= resistance.price and last.close < (resistance.price - min_close_dist):
        if algo_config.require_confirmation_candle_direction and not (last.close < last.open):
            pass
        else:
            side = "sell"
            entry = last.close
            sl, tp, risk_pips = _calc_initial_sl_tp(symbol, side, entry, prev.close, last.open)
            ticket = _execute_trade(symbol, side, entry, sl, tp, resistance)
            if ticket:
                _open_trades[ticket] = TradeState(ticket=ticket, symbol=symbol, side=side, entry=entry, sl=sl, tp=tp, risk_pips=risk_pips)
                opened = True
                _last_trade_at[symbol] = datetime.now()
                state.signal_log.insert(0, {
                    "time": datetime.now().isoformat(),
                    "symbol": symbol,
                    "side": side,
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "status": "executed",
                    "source": "ALGO:MultiTF",
                    "strategy": "my_strategy",
                    "level": {"kind": "resistance", "price": resistance.price},
                    "ticket": ticket,
                })
                logger.success(f"[MTF] SELL opened | {symbol} | entry={entry:.5f} sl={sl:.5f} tp={tp:.5f}")

    _last_scan_at = datetime.now().isoformat()
    _last_scan_summary[symbol] = {
        "symbol": symbol,
        "detected": int(bool(support)) + int(bool(resistance)),
        "added": 0,
        "tracked": len(supports) + len(resistances),
        "at": _last_scan_at,
        "opened_trade": opened,
        "spread_pips": round(spread_pips, 2),
        "ema": ema,
        "buy_allowed": buy_allowed,
        "sell_allowed": sell_allowed,
        "atr": atr,
        "atr_ok": atr_ok,
    }


# ── Risk management loop (BE + step trailing) ─────────────────────────────────

def _manage_trade(tr: TradeState) -> None:
    pip = _pip_size(tr.symbol)
    step_pips = float(algo_config.trail_step_pips)
    step_dist = step_pips * pip

    # Use live price
    current = _get_current_price(tr.symbol, side="buy" if tr.side == "buy" else "sell")
    if current is None:
        return

    # Profit in pips
    if tr.side == "buy":
        profit_pips = (current - tr.entry) / pip
    else:
        profit_pips = (tr.entry - current) / pip

    # Break-even at 1R (risk_pips)
    new_sl = None
    if (not tr.be_applied) and profit_pips >= tr.risk_pips:
        new_sl = tr.entry
        tr.be_applied = True
        tr.last_trail_step = 0

    # After BE: trail every +10 pips
    if tr.be_applied and profit_pips > tr.risk_pips:
        extra = profit_pips - tr.risk_pips
        steps = int(extra // step_pips)
        if steps > tr.last_trail_step:
            if tr.side == "buy":
                candidate = tr.entry + (steps * step_dist)
                if candidate > (new_sl if new_sl is not None else tr.sl):
                    new_sl = candidate
            else:
                candidate = tr.entry - (steps * step_dist)
                if candidate < (new_sl if new_sl is not None else tr.sl):
                    new_sl = candidate
            tr.last_trail_step = steps

    if new_sl is None:
        return

    # Only improve SL
    should_update = (tr.side == "buy" and new_sl > tr.sl) or (tr.side == "sell" and new_sl < tr.sl)
    if not should_update:
        return

    result = mt5_bridge.modify_position(tr.ticket, sl=new_sl)
    if result.get("success"):
        logger.info(f"[MTF] SL updated | ticket={tr.ticket} old={tr.sl:.5f} new={new_sl:.5f}")
        tr.sl = new_sl
    else:
        logger.warning(f"[MTF] SL update failed | ticket={tr.ticket} resp={result}")


def _risk_loop() -> None:
    while _algo_running:
        try:
            # Remove closed trades
            open_positions = mt5_bridge.get_open_positions()
            open_tickets = {int(p.get("id") or p.get("position_id")) for p in open_positions if (p.get("id") or p.get("position_id"))}
            for ticket in list(_open_trades.keys()):
                if ticket not in open_tickets:
                    _open_trades.pop(ticket, None)

            for tr in list(_open_trades.values()):
                _manage_trade(tr)
        except Exception as exc:
            logger.debug(f"[MTF] Risk loop error: {exc}")
        time.sleep(algo_config.risk_check_interval_seconds)


def _algo_loop() -> None:
    while _algo_running:
        try:
            if mt5_bridge.ensure_connected():
                for sym in algo_config.get_symbols():
                    try:
                        _maybe_open_trade(sym)
                    except Exception as exc:
                        logger.error(f"[MTF] Scan error for {sym}: {exc}")
        except Exception as exc:
            logger.error(f"[MTF] Algo loop error: {exc}")
        time.sleep(algo_config.scan_interval_seconds)


# ── Public API (required by manager/runner) ───────────────────────────────────

def start_algo() -> bool:
    global _algo_thread, _risk_thread, _algo_running
    if _algo_running:
        return False
    _algo_running = True
    _algo_thread = threading.Thread(target=_algo_loop, daemon=True, name="MultiTFAlgoThread")
    _risk_thread = threading.Thread(target=_risk_loop, daemon=True, name="MultiTFRiskThread")
    _algo_thread.start()
    _risk_thread.start()
    logger.success(f"[MTF] MultiTF Rejection started | scan={algo_config.scan_interval_seconds}s | risk={algo_config.risk_check_interval_seconds}s")
    return True


def stop_algo() -> bool:
    global _algo_running
    if not _algo_running:
        return False
    _algo_running = False
    logger.info("[MTF] Stopping MultiTF Rejection...")
    return True


def get_algo_status() -> dict:
    with _levels_lock:
        levels_snapshot = _levels.copy()
    return {
        "running": _algo_running,
        "enabled": algo_config.enabled,
        "strategy": "my_strategy",
        "symbol": algo_config.symbol,
        "symbols": algo_config.get_symbols(),
        "analysis_timeframe": algo_config.analysis_timeframe,
        "execution_timeframe": algo_config.execution_timeframe,
        "risk_reward": algo_config.risk_reward_ratio,
        "risk_percent": algo_config.risk_percent,
        "last_scan_at": _last_scan_at,
        "scan_summary": list(_last_scan_summary.values()),
        "levels": {
            sym: {
                "support": [s.price for s in data.get("support", [])][:10],
                "resistance": [r.price for r in data.get("resistance", [])][:10],
            }
            for sym, data in levels_snapshot.items()
        },
        "open_trades": [
            {
                "ticket": t.ticket,
                "symbol": t.symbol,
                "side": t.side,
                "entry": t.entry,
                "sl": t.sl,
                "tp": t.tp,
                "be_applied": t.be_applied,
                "last_trail_step": t.last_trail_step,
            }
            for t in _open_trades.values()
        ],
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
        normalized = _normalize_symbols(symbol)
        if normalized:
            algo_config.symbol = normalized[0]
            algo_config.symbols = normalized
    if enabled is not None:
        algo_config.enabled = bool(enabled)
    if risk_reward is not None:
        algo_config.risk_reward_ratio = float(risk_reward)
    if risk_percent is not None:
        algo_config.risk_percent = float(risk_percent)
    if analysis_tf is not None:
        algo_config.analysis_timeframe = int(analysis_tf)
    if execution_tf is not None:
        algo_config.execution_timeframe = int(execution_tf)

    logger.info(f"[MTF] Config updated: {algo_config}")
    return get_algo_status()
