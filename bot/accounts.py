"""
Multi-account MT5 manager.

Supports multiple MT5 accounts — each account gets its own MT5 connection.
Trades are executed on ALL enabled accounts simultaneously.

NOTE: MT5 Python library supports only ONE active connection per process.
      We use mt5.initialize() with different credentials to switch accounts.
      For true parallel execution, we execute sequentially (fast enough).
"""
from __future__ import annotations

import threading
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
        Label|login|password|server|strategy

    Example:
        Range Breakout Demo|106903766|IbLcNr_4|MetaQuotes-Demo|breakout
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
        server = parts[3].strip()
        strategies = _normalize_single_strategy(
            [s.strip() for s in parts[4].split("+")] if len(parts) >= 5 else ["order_block"]
        )

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
            path=_config.MT5_PATH,
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


def get_account(account_id: str) -> Optional[MT5Account]:
    with _accounts_lock:
        for acc in _accounts:
            if acc.id == account_id:
                return acc
    return None


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

    kwargs = {
        "login": acc.login,
        "password": acc.password,
        "server": acc.server,
        "timeout": _config.MT5_TIMEOUT_MS,
    }
    if acc.path:
        kwargs["path"] = acc.path

    # Shutdown existing connection first
    mt5.shutdown()

    if not mt5.initialize(**kwargs):
        err = str(mt5.last_error())
        acc.connected = False
        acc.error = err
        logger.error(f"[ACCOUNTS] Failed to connect {acc.label}: {err}")
        return False

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


def _cap_lot_by_pnl_limits(
    *,
    sym_info,
    symbol: str,
    side: str,
    price: float,
    sl: float,
    tp: float,
    lot: float,
) -> float:
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

    lot = max(sym_info.volume_min, min(sym_info.volume_max, lot))
    step = sym_info.volume_step or sym_info.volume_min or 0.01
    lot = round(math.floor(lot / step) * step, 8)
    return max(sym_info.volume_min, lot)


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
        accounts_copy = [acc for acc in _accounts if acc.enabled]

    results = []

    for acc in accounts_copy:
        try:
            if not _connect_account(acc):
                results.append({
                    "success": False,
                    "message": f"Could not connect to {acc.label}",
                    "account_id": acc.id,
                    "account_label": acc.label,
                    "login": acc.login,
                })
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

            if result.get("success"):
                logger.success(
                    f"[ACCOUNTS] Trade on {acc.label} ({acc.login}) | "
                    f"Ticket: {result.get('ticket')} | {symbol} {side.upper()}"
                )
            else:
                logger.error(f"[ACCOUNTS] Trade failed on {acc.label}: {result.get('message')}")

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

    sym_info = mt5.symbol_info(symbol)
    if not sym_info:
        return {"success": False, "message": f"Symbol {symbol} not found"}

    if not sym_info.visible:
        mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return {"success": False, "message": f"No tick data for {symbol}"}

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
    risk_amount = balance * (eff_risk / 100.0)
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
        symbol=symbol,
        side=side,
        price=price,
        sl=sl,
        tp=tp,
        lot=lot,
    )

    request = {
        "action": action,
        "symbol": symbol,
        "volume": lot,
        "type": mt5_order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": cfg.MT5_DEVIATION,
        "magic": cfg.MT5_MAGIC_NUMBER,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        return {"success": False, "message": f"order_send None: {mt5.last_error()}"}

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        return {"success": True, "ticket": result.order, "lot": lot, "message": "Trade opened"}
    else:
        return {"success": False, "message": f"retcode={result.retcode} {result.comment}"}
