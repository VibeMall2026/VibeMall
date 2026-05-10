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
    strategy: str = "order_block"   # strategy assigned to this account

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
            "strategy": self.strategy,
        }


# ── Account registry ──────────────────────────────────────────────────────────

_accounts: list[MT5Account] = []


def _load_default_account() -> None:
    """Load the primary account from config on startup."""
    if _config.MT5_LOGIN:
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


_load_default_account()


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
            strategy=strategy,
        )
        _accounts.append(acc)
        logger.info(f"[ACCOUNTS] Added account: {acc.label} ({acc.login}@{acc.server}) strategy={strategy}")
        return acc


def remove_account(account_id: str) -> bool:
    """Remove an account (cannot remove primary acc_1)."""
    if account_id == "acc_1":
        logger.warning("[ACCOUNTS] Cannot remove primary account")
        return False
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


def update_account_strategy(account_id: str, strategy: str) -> bool:
    """Update the strategy assigned to an account."""
    from bot.strategies import get_strategy
    if not get_strategy(strategy):
        logger.warning(f"[ACCOUNTS] Unknown strategy: {strategy}")
        return False
    acc = get_account(account_id)
    if acc:
        old = acc.strategy
        acc.strategy = strategy
        logger.info(f"[ACCOUNTS] Account {account_id} strategy: {old} → {strategy}")
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
    """Reconnect to primary account after multi-account operations."""
    primary = get_account("acc_1")
    if primary and primary.enabled:
        _connect_account(primary)


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
