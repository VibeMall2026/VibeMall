"""
Multi-account MT5 manager.

Supports multiple MT5 accounts — each account gets its own MT5 connection.
Trades are executed on ALL enabled accounts simultaneously.

NOTE: MT5 Python library supports only ONE active connection per process.
      We use mt5.initialize() with different credentials to switch accounts.
      For true parallel execution, we execute sequentially (fast enough).
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone, date as _date
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

from bot import config as _config

_accounts_lock = threading.Lock()
_mt5_op_lock = threading.RLock()
_account_trade_halts: dict[int, str] = {}  # login -> YYYY-MM-DD (halt day)

# The5ers funded-account policy (applies only to the specific breakout account)
THE5ERS_FUNDED_LOGIN = 26259636
THE5ERS_ACCOUNT_SIZE = 2500.0
THE5ERS_MAX_DAILY_LOSS_PCT = 5.0
THE5ERS_MAX_TOTAL_LOSS_PCT = 10.0
THE5ERS_EQUITY_FLOOR = 2250.0
THE5ERS_MAX_TRADES_PER_DAY = 15
THE5ERS_MIN_SECONDS_BETWEEN_BREAKOUT_ENTRIES = 65
THE5ERS_MAX_SIMULTANEOUS_BREAKOUT_TRADES = 2
THE5ERS_POLICY_ENFORCED = os.getenv("THE5ERS_POLICY_ENFORCED", "false").strip().lower() in {"1", "true", "yes", "on"}
DAILY_PROFIT_STOP_USD = 45.0


def get_mt5_lock() -> threading.RLock:
    """Global MT5 operation lock shared across modules."""
    return _mt5_op_lock


@dataclass
class MT5Account:
    id: str                    # unique id (e.g. "acc_1")
    label: str                 # display name (e.g. "Demo Account 1")
    login: int
    password: str
    server: str
    path: str = ""
    enabled: bool = True
    connected: bool = False
    balance: float = 0.0
    equity: float = 0.0
    currency: str = "USD"
    leverage: int = 100
    error: str = ""
    strategy: list = None   # list of strategy IDs assigned to this account

    def __post_init__(self):
        if self.strategy is None:
            self.strategy = ["order_block"]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "login": self.login,
            "server": self.server,
            "enabled": self.enabled,
            "connected": self.connected,
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "currency": self.currency,
            "leverage": self.leverage,
            "error": self.error,
            "strategy": self.strategy if isinstance(self.strategy, list) else [self.strategy],
        }


# ── Account registry ──────────────────────────────────────────────────────────

_accounts: list[MT5Account] = []


def _normalize_single_strategy(strategy) -> list[str]:
    """Store exactly one strategy per account for predictable runner behavior."""
    if isinstance(strategy, list):
        strategy = strategy[0] if strategy else "order_block"
    return [str(strategy or "order_block").strip()]


def _load_default_account() -> None:
    """Load the primary account from config on startup."""
    if _config.MT5_LOGIN > 0 and _config.MT5_PASSWORD and _config.MT5_SERVER:
        primary = MT5Account(
            id="acc_1",
            label="Primary Account",
            login=_config.MT5_LOGIN,
            password=_config.MT5_PASSWORD,
            server=_config.MT5_SERVER,
            path=_config.MT5_PATH,
            enabled=True,
        )
        _accounts.append(primary)


def _load_extra_accounts() -> None:
    """
    Load extra MT5 accounts from MT5_EXTRA_ACCOUNTS config.

    Reads directly from bot/.env file at call time so changes take effect
    without restarting the bot process.

    Format (semicolon-separated entries):
        Label|login|password|server|strategy|path

    Example:
        Range Breakout Demo|106903766|IbLcNr_4|MetaQuotes-Demo|breakout|C:\MT5\terminal64.exe
    """
    # Read directly from .env file so live changes are picked up without restart
    import os
    from pathlib import Path

    raw = ""
    env_path = Path(__file__).parent / ".env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("MT5_EXTRA_ACCOUNTS="):
                raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    except Exception as exc:
        logger.warning(f"[ACCOUNTS] Could not read .env for extra accounts: {exc}")

    # Fallback to config/env var if .env read failed
    if not raw:
        raw = (os.getenv("MT5_EXTRA_ACCOUNTS") or _config.MT5_EXTRA_ACCOUNTS or "").strip()

    if not raw:
        return

    entries = [e.strip() for e in raw.split(";") if e.strip()]
    for i, entry in enumerate(entries, start=2):
        parts = entry.split("|")
        if len(parts) < 4:
            logger.warning(f"[ACCOUNTS] Skipping malformed extra account entry: {entry!r}")
            continue

        label = parts[0].strip()
        try:
            login = int(parts[1].strip())
        except ValueError:
            logger.warning(f"[ACCOUNTS] Invalid login in extra account entry: {entry!r}")
            continue
        password = parts[2].strip()
        if password.startswith("${") and password.endswith("}"):
            password = os.getenv(password[2:-1].strip(), password)
        elif password.startswith("$"):
            password = os.getenv(password[1:].strip(), password)
        server = parts[3].strip()
        strategies = _normalize_single_strategy(
            [s.strip() for s in parts[4].split("+")] if len(parts) >= 5 else ["order_block"]
        )
        account_path = parts[5].strip() if len(parts) >= 6 else _config.MT5_PATH

        # Avoid duplicates — check by login number
        if any(a.login == login for a in _accounts):
            logger.debug(f"[ACCOUNTS] Extra account already loaded: {label} ({login})")
            continue

        # Find next available acc_id
        existing_ids = {a.id for a in _accounts}
        j = 2
        while f"acc_{j}" in existing_ids:
            j += 1
        acc_id = f"acc_{j}"

        acc = MT5Account(
            id=acc_id,
            label=label or f"Account {j}",
            login=login,
            password=password,
            server=server,
            path=account_path,
            enabled=True,
            strategy=strategies,
        )
        _accounts.append(acc)
        logger.info(
            f"[ACCOUNTS] Loaded extra account from config: {acc.label} "
            f"({acc.login}@{acc.server}) strategy={strategies}"
        )


_load_default_account()
_load_extra_accounts()


def get_all_accounts() -> list[MT5Account]:
    with _accounts_lock:
        return list(_accounts)


def stop_account_for_today(login: int) -> None:
    """Stop trade execution for this account for the current UTC day."""
    _account_trade_halts[int(login)] = _date.today().isoformat()


def start_account_now(login: int) -> None:
    """Manually resume trading for this account immediately."""
    _account_trade_halts.pop(int(login), None)


def is_account_trade_allowed_today(login: int) -> tuple[bool, str]:
    """
    Returns (allowed, reason).
    Auto-resets on next day.
    """
    key = int(login)
    halted_day = _account_trade_halts.get(key)
    if not halted_day:
        return True, "allowed"
    today = _date.today().isoformat()
    if halted_day != today:
        # Auto-reset on next day.
        _account_trade_halts.pop(key, None)
        return True, "auto_resumed_new_day"
    return False, "manually_stopped_for_today"


def get_account_trade_mode(login: int) -> dict:
    allowed, reason = is_account_trade_allowed_today(login)
    return {
        "login": int(login),
        "allowed": allowed,
        "reason": reason,
    }


def get_account(account_id: str) -> Optional[MT5Account]:
    with _accounts_lock:
        for acc in _accounts:
            if acc.id == account_id:
                return acc
    return None


def get_accounts_for_strategy(strategy_id: str) -> list[MT5Account]:
    """
    Return enabled accounts that have the given strategy assigned.
    Strategy assignment is stored as a list of strategy IDs in acc.strategy.
    """
    sid = str(strategy_id or "").strip()
    if not sid:
        return []
    with _accounts_lock:
        return [
            acc for acc in _accounts
            if acc.enabled and sid in (acc.strategy or [])
        ]


def connect_account_by_login(login: int) -> bool:
    """
    Switch the active MT5 connection to the account with the given login.
    Returns True on successful connection.
    """
    try:
        target_login = int(login)
    except Exception:
        return False
    with _accounts_lock:
        acc = next((a for a in _accounts if int(a.login) == target_login), None)
    if not acc:
        return False
    return _connect_account(acc)


def reconnect_primary() -> None:
    """Public wrapper to restore primary account connection after account switching."""
    _reconnect_primary()


def add_account(label: str, login: int, password: str, server: str, path: str = "", strategy: str = "order_block") -> MT5Account:
    """Add a new MT5 account."""
    with _accounts_lock:
        # Generate unique ID
        existing_ids = {acc.id for acc in _accounts}
        i = 1
        while f"acc_{i}" in existing_ids:
            i += 1
        acc_id = f"acc_{i}"

        acc = MT5Account(
            id=acc_id,
            label=label or f"Account {i}",
            login=login,
            password=password,
            server=server,
            path=path or _config.MT5_PATH,
            enabled=True,
            strategy=_normalize_single_strategy(strategy),
        )
        _accounts.append(acc)
        logger.info(f"[ACCOUNTS] Added account: {acc.label} ({acc.login}@{acc.server}) strategy={acc.strategy}")
        return acc


def remove_account(account_id: str) -> bool:
    """Remove an account."""
    with _accounts_lock:
        for i, acc in enumerate(_accounts):
            if acc.id == account_id:
                _accounts.pop(i)
                logger.info(f"[ACCOUNTS] Removed account: {account_id}")
                return True
    return False


def toggle_account(account_id: str, enabled: bool) -> bool:
    """Enable or disable an account."""
    acc = get_account(account_id)
    if acc:
        acc.enabled = enabled
        logger.info(f"[ACCOUNTS] Account {account_id} {'enabled' if enabled else 'disabled'}")
        return True
    return False


def update_account_strategy(account_id: str, strategy) -> bool:
    """Update the single strategy assigned to an account."""
    from bot.strategies import get_strategy
    strategies = _normalize_single_strategy(strategy)
    if not get_strategy(strategies[0]):
        logger.warning(f"[ACCOUNTS] Unknown strategy: {strategies[0]}")
        return False
    acc = get_account(account_id)
    if acc:
        old = acc.strategy
        acc.strategy = strategies
        logger.info(f"[ACCOUNTS] Account {account_id} strategy updated: {old} -> {strategies}")
        return True
    return False


# ── Connection management ─────────────────────────────────────────────────────

def _connect_account(acc: MT5Account) -> bool:
    """Connect to a specific MT5 account (switches active connection)."""
    if not MT5_AVAILABLE:
        return False
    with _mt5_op_lock:
        connect_timeout_ms = _config.MT5_TIMEOUT_MS
        attempts = (1, 2)
        # Funded account can intermittently hang the MT5 IPC channel.
        # Keep this probe short so dashboard refresh doesn't block for minutes.
        if acc.login == THE5ERS_FUNDED_LOGIN:
            connect_timeout_ms = min(connect_timeout_ms, 8000)
            attempts = (1,)

        kwargs = {
            "login": acc.login,
            "password": acc.password,
            "server": acc.server,
            "timeout": connect_timeout_ms,
        }
        if acc.path:
            kwargs["path"] = acc.path

        last_err = ""
        for attempt in attempts:
            # Shutdown existing connection first
            mt5.shutdown()

            if mt5.initialize(**kwargs):
                info = mt5.account_info()
                if info:
                    acc.balance = info.balance
                    acc.equity = info.equity
                    acc.currency = info.currency
                    acc.leverage = info.leverage
                acc.connected = True
                acc.error = ""
                logger.success(f"[ACCOUNTS] Connected: {acc.label} | Balance: {acc.balance} {acc.currency}")
                return True

            last_err = str(mt5.last_error())
            if attempt == 1 and len(attempts) > 1:
                time.sleep(0.4)

        acc.connected = False
        acc.error = last_err
        logger.error(f"[ACCOUNTS] Failed to connect {acc.label}: {last_err}")
        return False


def _cap_lot_by_pnl_limits(
    *,
    sym_info,
    symbol: str,
    side: str,
    price: float,
    sl: float,
    tp: float,
    lot: float,
) -> float | None:
    """Cap lot by actual MT5 PnL estimate instead of only tick-value math."""
    from bot import config as cfg
    import math

    order_type = mt5.ORDER_TYPE_BUY if side.lower() == "buy" else mt5.ORDER_TYPE_SELL
    caps: list[float] = []

    if cfg.MAX_RISK_AMOUNT_USD > 0 and sl > 0:
        loss_one_lot = mt5.order_calc_profit(order_type, symbol, 1.0, price, sl)
        loss_one_lot_abs = abs(float(loss_one_lot or 0.0))
        if loss_one_lot_abs > 0:
            caps.append(cfg.MAX_RISK_AMOUNT_USD / loss_one_lot_abs)

    if cfg.MAX_PROFIT_AMOUNT_USD > 0 and tp > 0:
        profit_one_lot = mt5.order_calc_profit(order_type, symbol, 1.0, price, tp)
        profit_one_lot_abs = abs(float(profit_one_lot or 0.0))
        if profit_one_lot_abs > 0:
            caps.append(cfg.MAX_PROFIT_AMOUNT_USD / profit_one_lot_abs)

    if caps:
        lot = min(lot, min(caps))

    if cfg.MAX_LOT_PER_TRADE > 0:
        lot = min(lot, cfg.MAX_LOT_PER_TRADE)

    if lot < sym_info.volume_min:
        return None

    lot = max(sym_info.volume_min, min(sym_info.volume_max, lot))
    step = sym_info.volume_step or sym_info.volume_min or 0.01
    lot = round(math.floor(lot / step) * step, 8)
    if lot < sym_info.volume_min:
        return None
    return lot


def refresh_account_info() -> None:
    """Refresh balance/equity for all enabled accounts."""
    if not MT5_AVAILABLE:
        return

    with _accounts_lock:
        accounts_copy = list(_accounts)

    for acc in accounts_copy:
        if not acc.enabled:
            continue
        try:
            if _connect_account(acc):
                info = mt5.account_info()
                if info:
                    acc.balance = info.balance
                    acc.equity = info.equity
                    acc.currency = info.currency
                    acc.connected = True
        except Exception as e:
            acc.error = str(e)
            acc.connected = False
            logger.error(f"[ACCOUNTS] Refresh error for {acc.label}: {e}")

    # Reconnect primary account at the end
    _reconnect_primary()


def _reconnect_primary() -> None:
    """Reconnect to primary account after multi-account operations, if configured."""
    primary = get_account("acc_1")
    if primary and primary.enabled:
        _connect_account(primary)
    else:
        ensure_any_account_connected()


def ensure_any_account_connected() -> bool:
    """
    Ensure at least one enabled MT5 account is connected for market-data scans.
    Falls back to the first enabled account if no active terminal connection exists.
    """
    if not MT5_AVAILABLE:
        return False

    try:
        if mt5.terminal_info() is not None:
            return True
    except Exception:
        pass

    with _accounts_lock:
        accounts_copy = [acc for acc in _accounts if acc.enabled]

    for acc in accounts_copy:
        try:
            if _connect_account(acc):
                logger.info(f"[ACCOUNTS] Auto-connected scan session using {acc.label}")
                return True
        except Exception as exc:
            logger.warning(f"[ACCOUNTS] Auto-connect failed for {acc.label}: {exc}")

    return False


# ── Multi-account trade execution ─────────────────────────────────────────────

def execute_on_all_accounts(
    symbol: str,
    side: str,
    sl: float,
    tp: float,
    entry=None,
    order_type: str = "market",
    risk_percent=None,
    comment: str = "TG Signal",
    strategy_id: str | None = None,
    exclude_strategy_id: str | None = None,
) -> list[dict]:
    """
    Execute trade on ALL enabled accounts.
    Returns list of results per account.
    """
    if not MT5_AVAILABLE:
        return [{"success": False, "message": "MT5 not available", "account": "N/A"}]

    from bot import config as cfg
    import math

    with _accounts_lock:
        accounts_copy = [
            acc for acc in _accounts
            if acc.enabled and (not strategy_id or strategy_id in (acc.strategy or []))
            and (not exclude_strategy_id or exclude_strategy_id not in (acc.strategy or []))
        ]

    # Strict strategy routing: when strategy_id is provided, do not fallback.
    if strategy_id and not accounts_copy:
        return [{
            "success": False,
            "message": f"No enabled accounts mapped to strategy '{strategy_id}'",
            "account_id": None,
            "account_label": None,
            "login": None,
        }]

    results = []

    for acc in accounts_copy:
        try:
            with _mt5_op_lock:
                if not _connect_account(acc):
                    results.append({
                        "success": False,
                        "message": f"Could not connect to {acc.label}",
                        "account_id": acc.id,
                        "account_label": acc.label,
                        "login": acc.login,
                    })
                    continue

                # Manual per-account stop-for-today gate.
                allowed_today, halt_reason = is_account_trade_allowed_today(acc.login)
                if not allowed_today:
                    results.append({
                        "success": False,
                        "message": f"Account paused for today ({halt_reason})",
                        "account_id": acc.id,
                        "account_label": acc.label,
                        "login": acc.login,
                    })
                    logger.warning(f"[ACCOUNTS] Trade skipped for {acc.label}: {halt_reason}")
                    continue

                # Account-specific prop-firm compliance guard (only this one account).
                if THE5ERS_POLICY_ENFORCED and strategy_id == "breakout" and acc.login == THE5ERS_FUNDED_LOGIN:
                    allowed, reason = _check_the5ers_breakout_policy(acc)
                    if not allowed:
                        results.append({
                            "success": False,
                            "message": f"The5ers policy block: {reason}",
                            "account_id": acc.id,
                            "account_label": acc.label,
                            "login": acc.login,
                        })
                        logger.warning(f"[ACCOUNTS] The5ers policy blocked breakout trade: {reason}")
                        continue

                # Hard daily profit stop per account:
                # once realized PnL reaches +$45, stop opening new trades for today.
                try:
                    from datetime import datetime, timezone
                    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                    end = datetime.now(timezone.utc)
                    deals = mt5.history_deals_get(start, end) or []
                    today_realized = sum(
                        float(getattr(d, "profit", 0.0) or 0.0)
                        + float(getattr(d, "commission", 0.0) or 0.0)
                        + float(getattr(d, "swap", 0.0) or 0.0)
                        for d in deals
                    )
                except Exception:
                    today_realized = 0.0

                if today_realized >= DAILY_PROFIT_STOP_USD:
                    results.append({
                        "success": False,
                        "message": (
                            f"Daily profit stop reached (${today_realized:.2f} >= ${DAILY_PROFIT_STOP_USD:.2f}); "
                            "no more trades today"
                        ),
                        "account_id": acc.id,
                        "account_label": acc.label,
                        "login": acc.login,
                    })
                    logger.warning(
                        f"[ACCOUNTS] Daily profit stop block on {acc.label}: "
                        f"${today_realized:.2f} >= ${DAILY_PROFIT_STOP_USD:.2f}"
                    )
                    continue

                # Execute trade on this account
                result = _execute_single(
                    symbol=symbol,
                    side=side,
                    sl=sl,
                    tp=tp,
                    entry=entry,
                    order_type=order_type,
                    risk_percent=risk_percent,
                    comment=comment,
                )
                result["account_id"] = acc.id
                result["account_label"] = acc.label
                result["login"] = acc.login
                results.append(result)

                strategy_label = strategy_id or "generic"
                if result.get("success"):
                    logger.success(
                        f"[EXECUTION][UNIFIED] strategy={strategy_label} account={acc.label} "
                        f"login={acc.login} status=SUCCESS ticket={result.get('ticket')} "
                        f"symbol={symbol} side={side.upper()} order_type={order_type}"
                    )
                else:
                    logger.error(
                        f"[EXECUTION][UNIFIED] strategy={strategy_label} account={acc.label} "
                        f"login={acc.login} status=FAILED symbol={symbol} side={side.upper()} "
                        f"order_type={order_type} reason={result.get('message')}"
                    )

        except Exception as e:
            logger.error(f"[ACCOUNTS] Exception on {acc.label}: {e}")
            results.append({
                "success": False,
                "message": str(e),
                "account_id": acc.id,
                "account_label": acc.label,
                "login": acc.login,
            })

    # Always reconnect primary account after multi-account execution
    _reconnect_primary()

    return results


def _check_the5ers_breakout_policy(acc: MT5Account) -> tuple[bool, str]:
    """Compliance/risk checks for The5ers funded breakout account only."""
    try:
        from bot import mt5_bridge as _bridge
        info = mt5.account_info()
        if not info:
            return False, "could not read account info"

        balance = float(getattr(info, "balance", 0.0) or 0.0)
        equity = float(getattr(info, "equity", 0.0) or 0.0)

        # Maximum total loss protection (equity floor).
        pct_floor = THE5ERS_ACCOUNT_SIZE * (1.0 - THE5ERS_MAX_TOTAL_LOSS_PCT / 100.0)
        hard_floor = max(THE5ERS_EQUITY_FLOOR, pct_floor)
        if equity <= hard_floor:
            return False, f"equity floor reached (equity={equity:.2f}, floor={hard_floor:.2f})"

        # Daily realized loss check.
        history = _bridge.get_trade_history(limit=2000)
        today = datetime.now(timezone.utc).date().isoformat()
        daily_realized = 0.0
        breakout_trades_today = 0
        last_breakout_open_ts = None
        for t in history:
            comment = str(t.get("comment", "") or "")
            opened = str(t.get("opened", "") or "")
            if len(opened) < 10 or opened[:10] != today:
                continue
            pnl = float(t.get("pnl", 0) or 0)
            daily_realized += pnl
            if "ALGO:BRK" in comment:
                breakout_trades_today += 1
                try:
                    dt = datetime.fromisoformat(opened.replace("Z", "+00:00").replace(" ", "T"))
                    if last_breakout_open_ts is None or dt > last_breakout_open_ts:
                        last_breakout_open_ts = dt
                except Exception:
                    pass

        max_daily_loss_usd = THE5ERS_ACCOUNT_SIZE * (THE5ERS_MAX_DAILY_LOSS_PCT / 100.0)
        if daily_realized <= -max_daily_loss_usd:
            return False, f"daily loss limit reached ({daily_realized:.2f} <= -{max_daily_loss_usd:.2f})"

        # Hard cap: max trades/day.
        if breakout_trades_today >= THE5ERS_MAX_TRADES_PER_DAY:
            return False, f"max trades/day reached ({breakout_trades_today}/{THE5ERS_MAX_TRADES_PER_DAY})"

        # Anti-HFT / no ultra-fast repetitive entries.
        if last_breakout_open_ts is not None:
            now_utc = datetime.now(timezone.utc)
            seconds_since_last = (now_utc - last_breakout_open_ts).total_seconds()
            if seconds_since_last < THE5ERS_MIN_SECONDS_BETWEEN_BREAKOUT_ENTRIES:
                return False, (
                    "entry frequency too high "
                    f"({seconds_since_last:.0f}s < {THE5ERS_MIN_SECONDS_BETWEEN_BREAKOUT_ENTRIES}s)"
                )

        # No bulk trading: cap simultaneous breakout positions on this account.
        open_positions = _bridge.get_open_positions()
        open_breakout_positions = [
            p for p in open_positions if "ALGO:BRK" in str(p.get("comment", "") or "")
        ]
        if len(open_breakout_positions) >= THE5ERS_MAX_SIMULTANEOUS_BREAKOUT_TRADES:
            return False, (
                "simultaneous breakout position cap reached "
                f"({len(open_breakout_positions)}/{THE5ERS_MAX_SIMULTANEOUS_BREAKOUT_TRADES})"
            )

        return True, "ok"
    except Exception as exc:
        return False, f"policy-check error: {exc}"


def _execute_single(
    symbol: str,
    side: str,
    sl: float,
    tp: float,
    entry=None,
    order_type: str = "market",
    risk_percent=None,
    comment: str = "TG Signal",
) -> dict:
    """Execute trade on currently connected MT5 account."""
    import math
    from bot import config as cfg

    def _normalize_sym(s: str) -> str:
        return "".join(ch for ch in str(s or "").upper() if ch.isalnum())

    def _resolve_symbol_name(raw_symbol: str) -> str | None:
        # Exact match first
        info = mt5.symbol_info(raw_symbol)
        if info:
            return raw_symbol

        wanted = _normalize_sym(raw_symbol)
        if not wanted:
            return None

        # Broker suffix/prefix variants fallback (e.g., XAUUSD.a, XAUUSDm)
        all_symbols = mt5.symbols_get()
        if not all_symbols:
            return None

        candidates = []
        for s in all_symbols:
            name = getattr(s, "name", "")
            norm = _normalize_sym(name)
            if norm == wanted:
                candidates.append(name)
                continue
            if norm.startswith(wanted) or wanted in norm:
                candidates.append(name)

        if not candidates:
            return None

        # Prefer shortest/closest name to avoid odd synthetic variants.
        candidates = sorted(candidates, key=lambda x: (len(x), x))
        return candidates[0]

    def _today_realized_pnl_usd() -> float:
        """
        Calculate today's realized PnL for the CURRENT connected account.
        Uses MT5 deal history (profit + commission + swap).
        """
        try:
            from datetime import datetime, timezone
            start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now(timezone.utc)
            deals = mt5.history_deals_get(start, end)
            if not deals:
                return 0.0
            total = 0.0
            for d in deals:
                profit = float(getattr(d, "profit", 0.0) or 0.0)
                commission = float(getattr(d, "commission", 0.0) or 0.0)
                swap = float(getattr(d, "swap", 0.0) or 0.0)
                total += (profit + commission + swap)
            return total
        except Exception:
            return 0.0

    def _risk_scale_for_today_pnl(today_pnl: float) -> float:
        """
        Per-account dynamic risk scaling:
        - >= $10 profit: reduce slightly
        - >= $20 profit: reduce more
        - >= $30 profit: reduce further
        """
        if today_pnl >= 30.0:
            return 0.50
        if today_pnl >= 20.0:
            return 0.65
        if today_pnl >= 10.0:
            return 0.80
        return 1.0

    resolved_symbol = _resolve_symbol_name(symbol)
    if not resolved_symbol:
        return {"success": False, "message": f"Symbol {symbol} not found"}
    if resolved_symbol != symbol:
        logger.info(f"[ACCOUNTS] Symbol mapped: {symbol} -> {resolved_symbol}")

    sym_info = mt5.symbol_info(resolved_symbol)
    if not sym_info:
        return {"success": False, "message": f"Symbol {resolved_symbol} not found"}

    if not sym_info.visible:
        mt5.symbol_select(resolved_symbol, True)

    tick = mt5.symbol_info_tick(resolved_symbol)
    if not tick:
        return {"success": False, "message": f"No tick data for {resolved_symbol}"}

    market_type_map = {
        "buy": mt5.ORDER_TYPE_BUY,
        "sell": mt5.ORDER_TYPE_SELL,
    }
    pending_type_map = {
        "buylimit": mt5.ORDER_TYPE_BUY_LIMIT,
        "buystop": mt5.ORDER_TYPE_BUY_STOP,
        "selllimit": mt5.ORDER_TYPE_SELL_LIMIT,
        "sellstop": mt5.ORDER_TYPE_SELL_STOP,
    }

    normalized = (order_type or "market").lower().replace(" ", "").replace("_", "")

    if normalized == "market":
        mt5_order_type = market_type_map.get(side.lower())
        action = mt5.TRADE_ACTION_DEAL
        price = tick.ask if side.lower() == "buy" else tick.bid
    else:
        mt5_order_type = pending_type_map.get(normalized)
        action = mt5.TRADE_ACTION_PENDING
        price = entry
        if price is None:
            return {"success": False, "message": "Pending order requires entry price"}

    if mt5_order_type is None:
        return {"success": False, "message": f"Unknown order type: {order_type}"}

    # Calculate lot size
    info = mt5.account_info()
    balance = info.balance if info else 0
    eff_risk = cfg.RISK_PERCENT if risk_percent is None else risk_percent
    today_realized = _today_realized_pnl_usd()
    risk_scale = _risk_scale_for_today_pnl(today_realized)
    eff_risk *= risk_scale
    if risk_scale < 1.0:
        logger.info(
            f"[ACCOUNTS] Dynamic risk reduce active | today_pnl={today_realized:.2f} | "
            f"scale={risk_scale:.2f} | eff_risk={eff_risk:.4f}%"
        )
    risk_amount = balance * (eff_risk / 100.0)
    # Daily drawdown-safe risk cap:
    # Keep per-trade risk low enough so even multiple SL hits should stay within
    # today's remaining daily loss budget.
    daily_loss_budget_usd = max(0.0, balance * (cfg.MAX_DAILY_LOSS_PERCENT / 100.0))
    loss_used_today_usd = max(0.0, -float(today_realized))
    remaining_daily_loss_budget_usd = max(0.0, daily_loss_budget_usd - loss_used_today_usd)
    if remaining_daily_loss_budget_usd <= 0:
        return {"success": False, "message": "Trade blocked: daily drawdown budget exhausted"}

    # Conservative split of remaining drawdown budget across potential SL events.
    # We use the tighter of max open positions and max trades/day as risk slots.
    risk_slots = max(1, min(int(cfg.MAX_OPEN_POSITIONS or 1), int(cfg.MAX_TRADES_PER_DAY or 1)))
    dd_safe_risk_cap = remaining_daily_loss_budget_usd / risk_slots
    if dd_safe_risk_cap > 0:
        risk_amount = min(risk_amount, dd_safe_risk_cap)
        logger.info(
            f"[ACCOUNTS] DD-safe cap applied | remaining_dd_budget=${remaining_daily_loss_budget_usd:.2f} | "
            f"slots={risk_slots} | per_trade_cap=${dd_safe_risk_cap:.2f}"
        )

    # Daily target rule:
    # After +$30 realized on this account, cap next-trade risk to max $15.
    if today_realized >= 30.0:
        risk_amount = min(risk_amount, 15.0)
        logger.info(
            f"[ACCOUNTS] Daily target reached on account (+${today_realized:.2f}); "
            f"risk amount capped to ${risk_amount:.2f} for next trades"
        )
    sl_points = abs(price - sl)

    tick_value = sym_info.trade_tick_value
    tick_size = sym_info.trade_tick_size
    if tick_size > 0 and sl_points > 0 and tick_value > 0:
        sl_ticks = sl_points / tick_size
        lot = risk_amount / (sl_ticks * tick_value)
        lot = max(sym_info.volume_min, min(sym_info.volume_max, lot))
        step = sym_info.volume_step
        lot = round(math.floor(lot / step) * step, 8)
    else:
        lot = sym_info.volume_min

    lot = _cap_lot_by_pnl_limits(
        sym_info=sym_info,
        symbol=resolved_symbol,
        side=side,
        price=price,
        sl=sl,
        tp=tp,
        lot=lot,
    )
    if lot is None:
        return {"success": False, "message": "Trade blocked: broker minimum lot exceeds configured per-trade risk/lot caps"}

    preferred_filling = getattr(sym_info, "filling_mode", mt5.ORDER_FILLING_IOC)
    fill_candidates = []
    for mode in (preferred_filling, mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK):
        if mode not in fill_candidates:
            fill_candidates.append(mode)

    request = {
        "action": action,
        "symbol": resolved_symbol,
        "volume": lot,
        "type": mt5_order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": cfg.MT5_DEVIATION,
        "magic": cfg.MT5_MAGIC_NUMBER,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
    }
    last_result = None
    for fill_mode in fill_candidates:
        req = dict(request)
        req["type_filling"] = fill_mode
        result = mt5.order_send(req)
        last_result = result
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return {"success": True, "ticket": result.order, "lot": lot, "message": "Trade opened"}
        # 10030 = Unsupported filling mode; try next candidate
        if result and result.retcode == 10030:
            continue
        if result is None:
            continue
        return {"success": False, "message": f"retcode={result.retcode} {result.comment}"}

    if last_result is None:
        return {"success": False, "message": f"order_send None: {mt5.last_error()}"}
    return {"success": False, "message": f"retcode={last_result.retcode} {last_result.comment}"}
