"""
Human Mind Module — Gives the algo a human-like trading mindset.

Features implemented:
1. Trade Management  — Partial close (scale out), early exit on reversal, time-based exit
2. Market Context    — Session filter, news filter, spread filter
3. Trade Sizing      — Confidence-based lot sizing, consecutive loss reduction, daily loss limit
4. Re-entry Logic    — Missed entry recovery, second chance entry
5. Correlation       — Symbol correlation filter, max open trades per direction
6. Psychological     — Revenge trade prevention, overtrading prevention, choppy market filter
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo
from loguru import logger

from bot import config as runtime_config


# ── Thread-safe state ─────────────────────────────────────────────────────────

_lock = threading.RLock()

# --- Feature 3: Consecutive loss / daily limits ---
_consecutive_losses: int = 0
_daily_trade_count: int = 0
_daily_date: date = datetime.now(timezone.utc).date()
_daily_pnl: float = 0.0
_daily_halted: bool = False

# Per-account state so one account can pause without blocking the others.
_consecutive_losses_by_account: dict[str, int] = {}
_daily_trade_count_by_account: dict[str, int] = {}
_daily_date_by_account: dict[str, date] = {}
_daily_pnl_by_account: dict[str, float] = {}
_daily_halted_by_account: dict[str, bool] = {}
_last_loss_time_by_account: dict[str, datetime] = {}

# --- Feature 6: Revenge / cooldown ---
_last_loss_time: Optional[datetime] = None
_cooldown_seconds: int = 15 * 60   # 15 min after a loss

# --- Feature 5: Direction exposure ---
# Tracked externally via open positions — no extra state needed here

# --- Feature 4: Re-entry tracking ---
# Dict of setup_id -> {"attempts": int, "last_sl_hit_time": datetime}
_reentry_tracker: dict[str, dict] = {}


def _env_bool(key: str, default: bool) -> bool:
    raw = str(os.getenv(key, str(default))).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    try:
        return int(str(os.getenv(key, str(default))).strip())
    except Exception:
        return default


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _account_key(account_login: Optional[int]) -> Optional[str]:
    if account_login is None:
        return None
    try:
        return str(int(account_login))
    except Exception:
        return str(account_login).strip() or None


def _resolve_active_account_login(account_login: Optional[int] = None) -> Optional[int]:
    if account_login is not None:
        return account_login
    try:
        from bot import mt5_bridge as _bridge

        info = _bridge.get_account_info(attempt_reconnect=False)
        if info and info.get("login"):
            return int(info.get("login"))
    except Exception:
        pass
    return None


# ── Config (all tunable) ──────────────────────────────────────────────────────

class HumanMindConfig:
    # --- Session filter ---
    session_filter_enabled: bool = _env_bool("HUMAN_MIND_SESSION_FILTER_ENABLED", True)
    # UTC hours for allowed trading sessions (London + NY overlap)
    allowed_sessions: list[tuple[int, int]] = [
        (7, 17),   # London: 07:00–17:00 UTC
        (12, 21),  # New York: 12:00–21:00 UTC
    ]

    # --- Spread filter ---
    spread_filter_enabled: bool = True
    max_spread_pips: dict[str, float] = {
        "XAUUSD": 0.65,   # soft-relaxed for gold to reduce overblocking in normal spread expansion
        "EURUSD": 0.0003, # 3 pips
        "USDJPY": 0.04,   # 4 pips
        "GBPUSD": 0.0004, # 4 pips
        "USDCHF": 0.0004, # 4 pips
        "DEFAULT": 0.0005,
    }

    # --- News filter ---
    news_filter_enabled: bool = False   # Requires external news feed; disabled by default
    news_blackout_minutes: int = 30     # Block trades 30 min before/after high-impact news

    # --- Partial close ---
    partial_close_enabled: bool = runtime_config.PARTIAL_CLOSE_ENABLED
    partial_close_at_r: float = runtime_config.PARTIAL_CLOSE_TRIGGER_R
    partial_close_pct: float = runtime_config.PARTIAL_CLOSE_FRACTION

    # --- Early exit on reversal ---
    early_exit_enabled: bool = True
    reversal_body_ratio: float = 0.60   # Opposite candle body ratio to trigger exit

    # --- Time-based exit ---
    time_exit_enabled: bool = True
    max_trade_hours: float = 8.0        # Close trade if open > 8 hours with < 0.3R profit
    time_exit_min_r: float = 0.3        # Minimum R to NOT time-exit

    # --- Confidence-based sizing ---
    confidence_sizing_enabled: bool = True
    high_confidence_multiplier: float = 1.0   # Full risk
    low_confidence_multiplier: float = 0.5    # Half risk

    # --- Consecutive loss reduction ---
    consec_loss_enabled: bool = True
    consec_loss_reduce_at: int = _env_int("HUMAN_MIND_CONSEC_LOSS_REDUCE_AT", 1)
    consec_loss_pause_at: int = _env_int("HUMAN_MIND_CONSEC_LOSS_PAUSE_AT", 2)
    consec_loss_size_multiplier: float = 0.5

    # --- Daily limits ---
    daily_loss_limit_usd: float = 30.0
    daily_profit_limit_usd: float = 50.0
    daily_max_trades: int = _env_int(
        "HUMAN_MIND_DAILY_MAX_TRADES",
        min(int(runtime_config.MAX_TRADES_PER_DAY or 10), 6),
    )

    # --- Revenge trade cooldown ---
    revenge_cooldown_enabled: bool = True
    cooldown_after_loss_minutes: int = 15

    # --- Overtrading ---
    overtrading_prevention_enabled: bool = True

    # --- Choppy market filter ---
    choppy_filter_enabled: bool = True
    choppy_atr_ratio: float = 0.6       # ATR < 60% of avg ATR = choppy

    # --- Correlation filter ---
    correlation_filter_enabled: bool = True
    correlated_pairs: list[tuple[str, str]] = [
        ("EURUSD", "GBPUSD"),   # highly correlated
        ("EURUSD", "USDCHF"),   # inverse correlation
        ("XAUUSD", "USDJPY"),   # inverse correlation
    ]
    max_same_direction_trades: int = _env_int("HUMAN_MIND_MAX_SAME_DIRECTION_TRADES", 1)

    # --- Re-entry ---
    reentry_enabled: bool = True
    max_reentry_attempts: int = 1       # allow 1 re-entry after SL hit
    reentry_cooldown_minutes: int = 5   # wait 5 min before re-entry


cfg = HumanMindConfig()

_IST_TIMEZONE = ZoneInfo("Asia/Kolkata")
_MANUAL_MANAGEMENT_START_HOUR = 10
_MANUAL_MANAGEMENT_END_HOUR = 22


def is_manual_management_window(now: Optional[datetime] = None) -> bool:
    """
    Return True when automated exit management should stay paused.

    The window is 10:00 to 22:00 India time, so trades can still open with
    SL/TP attached, but trailing, reversal, time, and partial-close logic is
    skipped during that period.
    """
    current = now or datetime.now(_IST_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current_ist = current.astimezone(_IST_TIMEZONE)
    return _MANUAL_MANAGEMENT_START_HOUR <= current_ist.hour < _MANUAL_MANAGEMENT_END_HOUR


# ── Daily reset ───────────────────────────────────────────────────────────────

def _reset_daily_if_needed(account_login: Optional[int] = None) -> None:
    global _daily_trade_count, _daily_date, _daily_pnl, _daily_halted, _consecutive_losses
    today = _utc_today()
    account_key = _account_key(account_login)
    with _lock:
        if account_key is not None:
            if _daily_date_by_account.get(account_key) != today:
                _daily_date_by_account[account_key] = today
                _daily_trade_count_by_account[account_key] = 0
                _daily_pnl_by_account[account_key] = 0.0
                _daily_halted_by_account[account_key] = False
                _consecutive_losses_by_account[account_key] = 0
                _last_loss_time_by_account.pop(account_key, None)
                logger.info(f"[HUMAN_MIND] Daily counters reset for account={account_key}")
            return
        if _daily_date != today:
            _daily_date = today
            _daily_trade_count = 0
            _daily_pnl = 0.0
            _daily_halted = False
            _consecutive_losses = 0
            logger.info("[HUMAN_MIND] Daily counters reset")


# ── Feature 3: Record trade result ───────────────────────────────────────────

def record_trade_result(pnl: float, account_login: Optional[int] = None) -> None:
    """Call after every trade closes."""
    global _consecutive_losses, _last_loss_time, _daily_pnl, _daily_halted
    account_login = _resolve_active_account_login(account_login)
    account_key = _account_key(account_login)
    _reset_daily_if_needed(account_login=account_login)
    with _lock:
        if account_key is not None:
            _daily_pnl_by_account[account_key] = _daily_pnl_by_account.get(account_key, 0.0) + pnl
            if pnl < 0:
                _consecutive_losses_by_account[account_key] = _consecutive_losses_by_account.get(account_key, 0) + 1
                _last_loss_time_by_account[account_key] = datetime.utcnow()
                logger.info(
                    f"[HUMAN_MIND] Loss recorded for account={account_key}. "
                    f"Consecutive losses: {_consecutive_losses_by_account[account_key]}"
                )
            else:
                _consecutive_losses_by_account[account_key] = 0
                logger.info(f"[HUMAN_MIND] Win recorded for account={account_key}. Consecutive losses reset to 0")

            if _daily_pnl_by_account[account_key] <= -cfg.daily_loss_limit_usd:
                _daily_halted_by_account[account_key] = True
                logger.warning(
                    f"[HUMAN_MIND] ⛔ Daily loss limit ${cfg.daily_loss_limit_usd} hit "
                    f"for account={account_key} — halted for today"
                )
            elif _daily_pnl_by_account[account_key] >= cfg.daily_profit_limit_usd:
                _daily_halted_by_account[account_key] = True
                logger.info(
                    f"[HUMAN_MIND] ✅ Daily profit target ${cfg.daily_profit_limit_usd} hit "
                    f"for account={account_key} — halted for today"
                )
            return

        _daily_pnl += pnl
        if pnl < 0:
            _consecutive_losses += 1
            _last_loss_time = datetime.utcnow()
            logger.info(f"[HUMAN_MIND] Loss recorded. Consecutive losses: {_consecutive_losses}")
        else:
            _consecutive_losses = 0
            logger.info(f"[HUMAN_MIND] Win recorded. Consecutive losses reset to 0")

        if _daily_pnl <= -cfg.daily_loss_limit_usd:
            _daily_halted = True
            logger.warning(f"[HUMAN_MIND] ⛔ Daily loss limit ${cfg.daily_loss_limit_usd} hit — halted for today")
        elif _daily_pnl >= cfg.daily_profit_limit_usd:
            _daily_halted = True
            logger.info(f"[HUMAN_MIND] ✅ Daily profit target ${cfg.daily_profit_limit_usd} hit — halted for today")


def record_trade_opened(account_login: Optional[int] = None) -> None:
    """Call when a new trade is opened."""
    global _daily_trade_count
    account_login = _resolve_active_account_login(account_login)
    account_key = _account_key(account_login)
    _reset_daily_if_needed(account_login=account_login)
    with _lock:
        if account_key is not None:
            _daily_trade_count_by_account[account_key] = _daily_trade_count_by_account.get(account_key, 0) + 1
            return
        _daily_trade_count += 1


# ── Feature 2: Session filter ─────────────────────────────────────────────────

def is_in_trading_session() -> bool:
    """Return True if current UTC time is within an allowed trading session."""
    if not cfg.session_filter_enabled:
        return True
    now_hour = datetime.utcnow().hour
    for start_h, end_h in cfg.allowed_sessions:
        if start_h <= now_hour < end_h:
            return True
    logger.debug(f"[HUMAN_MIND] Outside trading session (UTC hour={now_hour})")
    return False


# ── Feature 2: Spread filter ──────────────────────────────────────────────────

def is_spread_acceptable(symbol: str, bid: float, ask: float) -> bool:
    """Return True if current spread is within acceptable limits."""
    if not cfg.spread_filter_enabled:
        return True
    spread = ask - bid
    max_spread = cfg.max_spread_pips.get(symbol, cfg.max_spread_pips["DEFAULT"])
    if spread > max_spread:
        logger.info(f"[HUMAN_MIND] Spread too wide on {symbol}: {spread:.5f} > {max_spread:.5f} — skip")
        return False
    return True


def check_spread_from_bridge(symbol: str) -> bool:
    """Fetch live bid/ask from bridge and check spread."""
    if not cfg.spread_filter_enabled:
        return True
    try:
        from bot import mt5_bridge as _bridge
        if _bridge.USE_BRIDGE:
            response = _bridge._call_bridge(f"/price?symbol={symbol}")
            if response and "bid" in response and "ask" in response:
                return is_spread_acceptable(symbol, float(response["bid"]), float(response["ask"]))
        else:
            try:
                import MetaTrader5 as mt5
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    return is_spread_acceptable(symbol, tick.bid, tick.ask)
            except Exception:
                pass
    except Exception as exc:
        logger.warning(f"[HUMAN_MIND] Spread check failed for {symbol}: {exc}")
    return True  # allow if check fails


# ── Feature 6: Revenge trade cooldown ────────────────────────────────────────

def is_in_cooldown(account_login: Optional[int] = None) -> bool:
    """Return True if we are in post-loss cooldown period."""
    if not cfg.revenge_cooldown_enabled:
        return False
    account_key = _account_key(account_login)
    with _lock:
        last_loss_time = _last_loss_time_by_account.get(account_key) if account_key is not None else _last_loss_time
        if last_loss_time is None:
            return False
        elapsed = (datetime.utcnow() - last_loss_time).total_seconds()
        if elapsed < cfg.cooldown_after_loss_minutes * 60:
            remaining = int((cfg.cooldown_after_loss_minutes * 60 - elapsed) / 60)
            if account_key is not None:
                logger.info(
                    f"[HUMAN_MIND] In cooldown after loss for account={account_key} — {remaining} min remaining"
                )
            else:
                logger.info(f"[HUMAN_MIND] In cooldown after loss — {remaining} min remaining")
            return True
    return False


# ── Feature 3: Consecutive loss check ────────────────────────────────────────

def is_paused_due_to_losses(account_login: Optional[int] = None) -> bool:
    """Return True if consecutive losses exceeded pause threshold."""
    if not cfg.consec_loss_enabled:
        return False
    account_key = _account_key(account_login)
    with _lock:
        losses = _consecutive_losses_by_account.get(account_key, 0) if account_key is not None else _consecutive_losses
        if losses >= cfg.consec_loss_pause_at:
            if account_key is not None:
                logger.warning(
                    f"[HUMAN_MIND] ⛔ {losses} consecutive losses — trading paused for account={account_key}"
                )
            else:
                logger.warning(f"[HUMAN_MIND] ⛔ {losses} consecutive losses — trading paused")
            return True
    return False


def get_lot_multiplier(base_confidence: float = 1.0) -> float:
    """
    Return lot size multiplier based on:
    - Consecutive losses (reduce size)
    - Confidence score (0.0–1.0)
    """
    multiplier = 1.0

    # Consecutive loss reduction
    if cfg.consec_loss_enabled:
        with _lock:
            losses = _consecutive_losses
        if losses >= cfg.consec_loss_reduce_at:
            multiplier *= cfg.consec_loss_size_multiplier
            logger.info(f"[HUMAN_MIND] Lot reduced to {multiplier:.0%} due to {losses} consecutive losses")

    # Confidence-based sizing
    if cfg.confidence_sizing_enabled:
        if base_confidence < 0.7:
            multiplier *= cfg.low_confidence_multiplier
            logger.info(f"[HUMAN_MIND] Lot reduced to {multiplier:.0%} due to low confidence ({base_confidence:.2f})")
        else:
            multiplier *= cfg.high_confidence_multiplier

    return max(0.1, min(1.0, multiplier))


# ── Feature 6: Daily limits & overtrading ────────────────────────────────────

def is_daily_halted(account_login: Optional[int] = None) -> bool:
    """Return True if daily profit/loss limit hit or max trades reached."""
    account_key = _account_key(account_login)
    _reset_daily_if_needed(account_login=account_login)
    with _lock:
        if account_key is not None:
            if _daily_halted_by_account.get(account_key, False):
                return True
            if cfg.overtrading_prevention_enabled and _daily_trade_count_by_account.get(account_key, 0) >= cfg.daily_max_trades:
                logger.warning(
                    f"[HUMAN_MIND] Max daily trades ({cfg.daily_max_trades}) reached for account={account_key} — no more trades today"
                )
                return True
            return False

        if _daily_halted:
            return True
        if cfg.overtrading_prevention_enabled and _daily_trade_count >= cfg.daily_max_trades:
            logger.warning(f"[HUMAN_MIND] Max daily trades ({cfg.daily_max_trades}) reached — no more trades today")
            return True
    return False


# ── Feature 6: Choppy market filter ──────────────────────────────────────────

def is_market_choppy(candles: list) -> bool:
    """
    Return True if market is choppy (low ATR relative to average).
    candles: list of Candle objects with high/low/close attributes.
    """
    if not cfg.choppy_filter_enabled or len(candles) < 30:
        return False
    try:
        period = 14
        trs = []
        for i in range(1, len(candles)):
            c = candles[i]
            p = candles[i - 1]
            trs.append(max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close)))
        if len(trs) < period * 2:
            return False
        current_atr = sum(trs[-period:]) / period
        baseline_atr = sum(trs[-period * 2:-period]) / period
        if baseline_atr <= 0:
            return False
        ratio = current_atr / baseline_atr
        if ratio < cfg.choppy_atr_ratio:
            logger.info(f"[HUMAN_MIND] Choppy market detected (ATR ratio={ratio:.2f}) — skip")
            return True
    except Exception as exc:
        logger.warning(f"[HUMAN_MIND] Choppy check error: {exc}")
    return False


# ── Feature 5: Correlation filter ────────────────────────────────────────────

def is_correlated_trade_blocked(symbol: str, direction: str, open_positions: list) -> bool:
    """
    Return True if opening this trade would violate correlation rules.
    open_positions: list of dicts with 'symbol' and 'side' keys.
    """
    if not cfg.correlation_filter_enabled:
        return False

    # Check max same-direction trades
    same_dir_count = sum(
        1 for p in open_positions
        if (p.get("side") == "buy" and direction == "bullish") or
           (p.get("side") == "sell" and direction == "bearish")
    )
    if same_dir_count >= cfg.max_same_direction_trades:
        logger.info(
            f"[HUMAN_MIND] Max {direction} trades ({cfg.max_same_direction_trades}) already open — skip {symbol}"
        )
        return True

    # Check correlated pairs
    open_symbols = {p.get("symbol"): p.get("side") for p in open_positions}
    for pair in cfg.correlated_pairs:
        if symbol not in pair:
            continue
        other = pair[0] if pair[1] == symbol else pair[1]
        if other not in open_symbols:
            continue
        other_side = open_symbols[other]
        # Positively correlated: EURUSD + GBPUSD — same direction = double risk
        if pair in [("EURUSD", "GBPUSD")]:
            if (other_side == "buy" and direction == "bullish") or \
               (other_side == "sell" and direction == "bearish"):
                logger.info(
                    f"[HUMAN_MIND] Correlated pair block: {symbol} {direction} conflicts with {other} {other_side}"
                )
                return True
        # Inversely correlated: EURUSD+USDCHF, XAUUSD+USDJPY — opposite direction = double risk
        if pair in [("EURUSD", "USDCHF"), ("XAUUSD", "USDJPY")]:
            if (other_side == "buy" and direction == "bearish") or \
               (other_side == "sell" and direction == "bullish"):
                logger.info(
                    f"[HUMAN_MIND] Inverse correlated block: {symbol} {direction} conflicts with {other} {other_side}"
                )
                return True
    return False


# ── Feature 4: Re-entry logic ─────────────────────────────────────────────────

def can_reenter(setup_id: str) -> bool:
    """Return True if a re-entry is allowed for this setup."""
    if not cfg.reentry_enabled:
        return False
    with _lock:
        info = _reentry_tracker.get(setup_id, {"attempts": 0, "last_sl_hit_time": None})
        if info["attempts"] >= cfg.max_reentry_attempts:
            return False
        if info["last_sl_hit_time"] is not None:
            elapsed = (datetime.utcnow() - info["last_sl_hit_time"]).total_seconds()
            if elapsed < cfg.reentry_cooldown_minutes * 60:
                return False
    return True


def record_sl_hit(setup_id: str) -> None:
    """Record that a setup's SL was hit (for re-entry tracking)."""
    with _lock:
        info = _reentry_tracker.get(setup_id, {"attempts": 0, "last_sl_hit_time": None})
        info["attempts"] += 1
        info["last_sl_hit_time"] = datetime.utcnow()
        _reentry_tracker[setup_id] = info
        logger.info(f"[HUMAN_MIND] SL hit recorded for {setup_id} (attempt #{info['attempts']})")


def cleanup_reentry_tracker(max_age_hours: int = 24) -> None:
    """Remove old entries from re-entry tracker."""
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    with _lock:
        to_remove = [
            sid for sid, info in _reentry_tracker.items()
            if info.get("last_sl_hit_time") and info["last_sl_hit_time"] < cutoff
        ]
        for sid in to_remove:
            del _reentry_tracker[sid]


# ── Feature 1: Partial close ──────────────────────────────────────────────────

def should_partial_close(entry: float, current_price: float, one_r: float, side: str,
                          partial_done: bool) -> bool:
    """Return True if partial close should be triggered (1R profit reached, not yet done)."""
    if is_manual_management_window():
        return False
    if not cfg.partial_close_enabled or partial_done or one_r <= 0:
        return False
    profit_r = (current_price - entry) / one_r if side == "buy" else (entry - current_price) / one_r
    return profit_r >= cfg.partial_close_at_r


def execute_partial_close(ticket: int, symbol: str, current_volume: float, close_fraction: Optional[float] = None) -> bool:
    """Close provided fraction (or default partial_close_pct) of the position."""
    fraction = cfg.partial_close_pct if close_fraction is None else float(close_fraction)
    fraction = max(0.05, min(0.95, fraction))
    close_volume = round(current_volume * fraction, 2)
    if close_volume <= 0:
        return False
    try:
        from bot import mt5_bridge as _bridge
        if _bridge.USE_BRIDGE:
            result = _bridge._call_bridge(
                f"/positions/{ticket}/partial_close",
                method="POST",
                json_data={"volume": close_volume},
            )
            success = bool(result and result.get("success"))
        else:
            try:
                import MetaTrader5 as mt5
                from bot.accounts import get_mt5_lock, get_all_accounts, _connect_account, connect_account_by_login

                with get_mt5_lock():
                    current_login = None
                    try:
                        info = mt5.account_info()
                        current_login = int(getattr(info, "login", 0) or 0) if info else None
                    except Exception:
                        current_login = None

                    pos = mt5.positions_get(ticket=ticket)
                    switched = False
                    if not pos:
                        # Multi-account safety: ticket may belong to a different MT5 account.
                        for acc in get_all_accounts():
                            try:
                                if not getattr(acc, "enabled", False):
                                    continue
                                if _connect_account(acc):
                                    switched = True
                                    pos = mt5.positions_get(ticket=ticket)
                                    if pos:
                                        break
                            except Exception:
                                continue

                    if not pos:
                        logger.warning(f"[HUMAN_MIND][PARTIAL_CLOSE_FAIL] ticket={ticket} reason=position_not_found")
                        # Best-effort restore previous connection.
                        if switched and current_login:
                            try:
                                connect_account_by_login(current_login)
                            except Exception:
                                pass
                        return False

                    p = pos[0]
                    pos_symbol = getattr(p, "symbol", symbol) or symbol
                    order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                    tick = mt5.symbol_info_tick(pos_symbol)
                    if not tick:
                        logger.warning(
                            f"[HUMAN_MIND][PARTIAL_CLOSE_FAIL] ticket={ticket} reason=no_tick_data symbol={pos_symbol}"
                        )
                        if switched and current_login:
                            try:
                                connect_account_by_login(current_login)
                            except Exception:
                                pass
                        return False
                    price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask

                    sym_info = mt5.symbol_info(pos_symbol)
                    preferred_filling = getattr(sym_info, "filling_mode", mt5.ORDER_FILLING_IOC) if sym_info else mt5.ORDER_FILLING_IOC
                    fill_candidates = []
                    for mode in (preferred_filling, mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK):
                        if mode not in fill_candidates:
                            fill_candidates.append(mode)

                    base_req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": pos_symbol,
                        "volume": close_volume,
                        "type": order_type,
                        "position": ticket,
                        "price": price,
                        "deviation": 20,
                        "magic": p.magic,
                        "comment": "ALGO:PARTIAL",
                        "type_time": mt5.ORDER_TIME_GTC,
                    }
                    last_result = None
                    success = False
                    for fill_mode in fill_candidates:
                        req = dict(base_req)
                        req["type_filling"] = fill_mode
                        result = mt5.order_send(req)
                        last_result = result
                        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                            success = True
                            break
                        # 10030 = Unsupported filling mode; try next candidate
                        if result and result.retcode == 10030:
                            continue
                        break

                    # Best-effort restore previous connection (don't force primary).
                    if switched and current_login:
                        try:
                            connect_account_by_login(current_login)
                        except Exception:
                            pass
            except Exception as exc:
                logger.error(f"[HUMAN_MIND] Partial close MT5 error: {exc}")
                return False
        if success:
            logger.success(f"[HUMAN_MIND] Partial close {close_volume} lots on ticket {ticket}")
        return success
    except Exception as exc:
        logger.error(f"[HUMAN_MIND] Partial close error: {exc}")
        return False


# ── Feature 1: Early exit on reversal ────────────────────────────────────────

def should_early_exit(side: str, candles: list) -> bool:
    """
    Return True if the last candle shows a strong reversal signal.
    candles: list of Candle objects.
    """
    if is_manual_management_window():
        return False
    if not cfg.early_exit_enabled or len(candles) < 2:
        return False
    try:
        last = candles[-1]
        body_ratio = last.body / last.range if last.range > 0 else 0
        if body_ratio < cfg.reversal_body_ratio:
            return False
        if side == "buy" and last.is_bearish:
            logger.info(f"[HUMAN_MIND] Early exit signal: strong bearish candle on BUY trade")
            return True
        if side == "sell" and last.is_bullish:
            logger.info(f"[HUMAN_MIND] Early exit signal: strong bullish candle on SELL trade")
            return True
    except Exception as exc:
        logger.warning(f"[HUMAN_MIND] Early exit check error: {exc}")
    return False


# ── Feature 1: Time-based exit ────────────────────────────────────────────────

def should_time_exit(opened_at: datetime, entry: float, current_price: float,
                     one_r: float, side: str) -> bool:
    """Return True if trade has been open too long with insufficient profit."""
    if is_manual_management_window():
        return False
    if not cfg.time_exit_enabled or one_r <= 0:
        return False
    try:
        hours_open = (datetime.utcnow() - opened_at).total_seconds() / 3600
        if hours_open < cfg.max_trade_hours:
            return False
        profit_r = (current_price - entry) / one_r if side == "buy" else (entry - current_price) / one_r
        if profit_r < cfg.time_exit_min_r:
            logger.info(
                f"[HUMAN_MIND] Time exit: trade open {hours_open:.1f}h with only {profit_r:.2f}R profit"
            )
            return True
    except Exception as exc:
        logger.warning(f"[HUMAN_MIND] Time exit check error: {exc}")
    return False


def close_trade(ticket: int, symbol: str, side: str, reason: str = "ALGO:EXIT") -> bool:
    """Close a full position."""
    try:
        from bot import mt5_bridge as _bridge
        logger.info(
            f"[HUMAN_MIND][CLOSE_ATTEMPT] ticket={ticket} symbol={symbol} side={side} "
            f"reason={reason} mode={'bridge' if _bridge.USE_BRIDGE else 'direct_mt5'}"
        )

        if _bridge.USE_BRIDGE:
            result = _bridge._call_bridge(
                f"/positions/{ticket}/close",
                method="POST",
                json_data={"reason": reason},
            )
            logger.info(f"[HUMAN_MIND][CLOSE_BRIDGE_RESP] ticket={ticket} response={result}")
            success = bool(result and result.get("success"))
        else:
            try:
                import MetaTrader5 as mt5
                from bot.accounts import get_mt5_lock, get_all_accounts, _connect_account, connect_account_by_login

                with get_mt5_lock():
                    current_login = None
                    try:
                        info = mt5.account_info()
                        current_login = int(getattr(info, "login", 0) or 0) if info else None
                    except Exception:
                        current_login = None

                    pos = mt5.positions_get(ticket=ticket)
                    switched = False
                    if not pos:
                        # Multi-account safety: ticket may belong to a different MT5 account.
                        for acc in get_all_accounts():
                            try:
                                if not getattr(acc, "enabled", False):
                                    continue
                                if _connect_account(acc):
                                    switched = True
                                    pos = mt5.positions_get(ticket=ticket)
                                    if pos:
                                        break
                            except Exception:
                                continue

                    if not pos:
                        logger.warning(f"[HUMAN_MIND][CLOSE_FAIL] ticket={ticket} reason=position_not_found")
                        if switched and current_login:
                            try:
                                connect_account_by_login(current_login)
                            except Exception:
                                pass
                        return False

                    p = pos[0]
                    pos_symbol = getattr(p, "symbol", symbol) or symbol
                    order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                    tick = mt5.symbol_info_tick(pos_symbol)
                    if not tick:
                        logger.warning(f"[HUMAN_MIND][CLOSE_FAIL] ticket={ticket} reason=no_tick_data symbol={pos_symbol}")
                        if switched and current_login:
                            try:
                                connect_account_by_login(current_login)
                            except Exception:
                                pass
                        return False
                    price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask

                    sym_info = mt5.symbol_info(pos_symbol)
                    preferred_filling = getattr(sym_info, "filling_mode", mt5.ORDER_FILLING_IOC) if sym_info else mt5.ORDER_FILLING_IOC
                    fill_candidates = []
                    for mode in (preferred_filling, mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK):
                        if mode not in fill_candidates:
                            fill_candidates.append(mode)

                    base_req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": pos_symbol,
                        "volume": p.volume,
                        "type": order_type,
                        "position": ticket,
                        "price": price,
                        "deviation": 20,
                        "magic": p.magic,
                        "comment": reason,
                        "type_time": mt5.ORDER_TIME_GTC,
                    }

                    last_result = None
                    success = False
                    for fill_mode in fill_candidates:
                        req = dict(base_req)
                        req["type_filling"] = fill_mode
                        result = mt5.order_send(req)
                        last_result = result
                        logger.info(
                            f"[HUMAN_MIND][CLOSE_MT5_RESP] ticket={ticket} fill={fill_mode} "
                            f"retcode={getattr(result, 'retcode', None)} comment={getattr(result, 'comment', None)}"
                        )
                        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                            success = True
                            break
                        # 10030 = Unsupported filling mode; try next candidate
                        if result and result.retcode == 10030:
                            continue
                        break

                    # Best-effort restore previous connection (don't force primary).
                    if switched and current_login:
                        try:
                            connect_account_by_login(current_login)
                        except Exception:
                            pass
            except Exception as exc:
                logger.error(f"[HUMAN_MIND] Close trade MT5 error: {exc}")
                return False

        if success:
            logger.success(f"[HUMAN_MIND] Trade {ticket} closed - reason: {reason}")
        else:
            logger.warning(f"[HUMAN_MIND][CLOSE_FAIL] ticket={ticket} reason={reason}")
        return success
    except Exception as exc:
        logger.error(f"[HUMAN_MIND] Close trade error: {exc}")
        return False

# ── Master gate: can_enter_trade ──────────────────────────────────────────────

def can_enter_trade(
    symbol: str,
    direction: str,
    candles: list,
    open_positions: list,
    account_login: Optional[int] = None,
    check_account_scoped_gates: bool = True,
) -> tuple[bool, str]:
    """
    Master check — call before every new trade entry.
    Returns (allowed: bool, reason: str).
    """
    # 1. Daily halt
    if check_account_scoped_gates and is_daily_halted(account_login=account_login):
        return False, "daily_halted"

    # 2. Spread filter
    if not check_spread_from_bridge(symbol):
        return False, "spread_too_wide"

    # 3. Revenge cooldown
    if check_account_scoped_gates and is_in_cooldown(account_login=account_login):
        return False, "cooldown_active"

    # 4. Consecutive loss pause
    if check_account_scoped_gates and is_paused_due_to_losses(account_login=account_login):
        return False, "consecutive_loss_pause"

    # 5. Choppy market
    if is_market_choppy(candles):
        return False, "choppy_market"

    # 6. Correlation
    if is_correlated_trade_blocked(symbol, direction, open_positions):
        return False, "correlation_blocked"

    return True, "ok"


# ── Status for dashboard ──────────────────────────────────────────────────────

def get_status(account_login: Optional[int] = None) -> dict:
    _reset_daily_if_needed(account_login=account_login)
    with _lock:
        account_key = _account_key(account_login)
        if account_key is not None:
            return {
                "session_ok": is_in_trading_session(),
                "daily_halted": _daily_halted_by_account.get(account_key, False),
                "daily_pnl": round(_daily_pnl_by_account.get(account_key, 0.0), 2),
                "daily_trade_count": _daily_trade_count_by_account.get(account_key, 0),
                "consecutive_losses": _consecutive_losses_by_account.get(account_key, 0),
                "in_cooldown": is_in_cooldown(account_login=account_login),
                "daily_loss_limit": cfg.daily_loss_limit_usd,
                "daily_profit_limit": cfg.daily_profit_limit_usd,
                "daily_max_trades": cfg.daily_max_trades,
                "cooldown_minutes": cfg.cooldown_after_loss_minutes,
                "consec_loss_pause_at": cfg.consec_loss_pause_at,
                "account_login": int(account_key),
            }
        return {
            "session_ok": is_in_trading_session(),
            "daily_halted": _daily_halted,
            "daily_pnl": round(_daily_pnl, 2),
            "daily_trade_count": _daily_trade_count,
            "consecutive_losses": _consecutive_losses,
            "in_cooldown": is_in_cooldown(),
            "daily_loss_limit": cfg.daily_loss_limit_usd,
            "daily_profit_limit": cfg.daily_profit_limit_usd,
            "daily_max_trades": cfg.daily_max_trades,
            "cooldown_minutes": cfg.cooldown_after_loss_minutes,
            "consec_loss_pause_at": cfg.consec_loss_pause_at,
        }


# ── Feature: Total portfolio profit close ────────────────────────────────────

# Total combined floating profit threshold for NON-XAU portfolio close
NON_XAU_TOTAL_PROFIT_CLOSE_USD: float = 1.0   # Close non-XAU basket when combined profit >= $1


def check_and_close_all_on_profit_target(open_positions: list) -> bool:
    """
    If total floating profit across NON-XAU open positions >= NON_XAU_TOTAL_PROFIT_CLOSE_USD,
    close all NON-XAU open positions immediately.
    XAUUSD positions are intentionally excluded and continue with normal strategy rules.
    Returns True if trades were closed.
    """
    if not open_positions:
        return False

    non_xau_positions = [
        p for p in open_positions
        if not str(p.get("symbol", "")).upper().startswith("XAUUSD")
    ]
    if not non_xau_positions:
        return False

    total_floating = sum(float(p.get("pnl", 0)) for p in non_xau_positions)
    if total_floating < NON_XAU_TOTAL_PROFIT_CLOSE_USD:
        return False

    logger.success(
        f"[HUMAN_MIND] 🎯 Non-XAU total profit ${total_floating:.2f} >= "
        f"${NON_XAU_TOTAL_PROFIT_CLOSE_USD} — closing {len(non_xau_positions)} non-XAU trades"
    )

    closed_count = 0
    for pos in non_xau_positions:
        ticket = pos.get("id") or pos.get("position_id")
        symbol = pos.get("symbol", "")
        side = pos.get("side", "buy")
        if ticket and symbol:
            if close_trade(int(ticket), symbol, side, "ALGO:NON_XAU_PROFIT_TARGET"):
                closed_count += 1

    logger.info(f"[HUMAN_MIND] Closed {closed_count}/{len(non_xau_positions)} non-XAU trades on profit target")
    return closed_count > 0

