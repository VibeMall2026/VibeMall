"""
MT5 Bridge — connects to MetaTrader 5 on Windows PC and executes trades.

NOTE: MetaTrader5 Python library only works on Windows.
      On Ubuntu VPS this module is imported but MT5 calls are skipped
      (bot runs in "simulation" mode until Windows bridge is connected).
"""
import sys
import math
from typing import Optional
from loguru import logger
from bot import config

# Try importing MT5 — only available on Windows
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 library not available (Ubuntu). Running without MT5.")


# ── Connection ────────────────────────────────────────────────────────────────

def connect() -> bool:
    if not MT5_AVAILABLE:
        logger.warning("MT5 not available on this platform.")
        return False
    kwargs = {
        "login": config.MT5_LOGIN,
        "password": config.MT5_PASSWORD,
        "server": config.MT5_SERVER,
        "timeout": config.MT5_TIMEOUT_MS,
    }
    if config.MT5_PATH:
        kwargs["path"] = config.MT5_PATH

    if not mt5.initialize(**kwargs):
        logger.error(f"MT5 initialize failed: {mt5.last_error()}")
        return False
    info = mt5.account_info()
    logger.info(f"MT5 connected | Account: {info.login} | Balance: {info.balance} {info.currency}")
    return True


def disconnect() -> None:
    if MT5_AVAILABLE:
        mt5.shutdown()
        logger.info("MT5 disconnected.")


def is_connected() -> bool:
    if not MT5_AVAILABLE:
        return False
    try:
        return mt5.terminal_info() is not None
    except Exception:
        return False


# ── Account info ──────────────────────────────────────────────────────────────

def get_account_info() -> dict:
    if not MT5_AVAILABLE or not is_connected():
        return {}
    info = mt5.account_info()
    if not info:
        return {}
    return {
        "balance": info.balance,
        "equity": info.equity,
        "margin_free": info.margin_free,
        "currency": info.currency,
        "leverage": info.leverage,
        "login": info.login,
        "server": info.server,
    }


# ── Lot size calculation ───────────────────────────────────────────────────────

def calculate_lot(symbol: str, sl_points: float) -> float:
    """Calculate lot size based on risk % of account balance."""
    if not MT5_AVAILABLE or not is_connected():
        return 0.01
    info = mt5.account_info()
    if not info:
        return 0.01
    sym_info = mt5.symbol_info(symbol)
    if not sym_info:
        logger.warning(f"Symbol info not found: {symbol}")
        return 0.01

    risk_amount = info.balance * (config.RISK_PERCENT / 100.0)
    tick_value = sym_info.trade_tick_value
    tick_size = sym_info.trade_tick_size

    if tick_size == 0 or sl_points == 0:
        return sym_info.volume_min

    sl_ticks = sl_points / tick_size
    lot = risk_amount / (sl_ticks * tick_value)
    lot = max(sym_info.volume_min, min(sym_info.volume_max, lot))
    # Round to step
    step = sym_info.volume_step
    lot = round(math.floor(lot / step) * step, 8)
    return lot


# ── Open trade ────────────────────────────────────────────────────────────────

def open_trade(
    symbol: str,
    side: str,
    sl: float,
    tp: float,
    entry: Optional[float] = None,
    comment: str = "TG Signal",
) -> dict:
    """
    Open a market or pending order.
    Returns dict with success, ticket, message.
    """
    if not MT5_AVAILABLE or not is_connected():
        return {"success": False, "message": "MT5 not connected"}

    sym_info = mt5.symbol_info(symbol)
    if not sym_info:
        return {"success": False, "message": f"Symbol {symbol} not found"}

    if not sym_info.visible:
        mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return {"success": False, "message": f"No tick data for {symbol}"}

    order_type_map = {
        "buy": mt5.ORDER_TYPE_BUY,
        "sell": mt5.ORDER_TYPE_SELL,
    }
    order_type = order_type_map.get(side.lower())
    if order_type is None:
        return {"success": False, "message": f"Unknown side: {side}"}

    price = tick.ask if side.lower() == "buy" else tick.bid
    sl_points = abs(price - sl)
    lot = calculate_lot(symbol, sl_points)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": config.MT5_DEVIATION,
        "magic": config.MT5_MAGIC_NUMBER,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        return {"success": False, "message": f"order_send returned None: {mt5.last_error()}"}

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.success(f"Trade opened | {symbol} {side.upper()} | Lot: {lot} | Ticket: {result.order}")
        return {"success": True, "ticket": result.order, "lot": lot, "message": "Trade opened"}
    else:
        msg = f"Order failed: retcode={result.retcode} comment={result.comment}"
        logger.error(msg)
        return {"success": False, "message": msg}


# ── Modify position ───────────────────────────────────────────────────────────

def modify_position(position_id: int, sl: Optional[float] = None, tp: Optional[float] = None) -> dict:
    if not MT5_AVAILABLE or not is_connected():
        return {"success": False, "message": "MT5 not connected"}

    positions = mt5.positions_get(ticket=position_id)
    if not positions:
        return {"success": False, "message": f"Position {position_id} not found"}

    pos = positions[0]
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position_id,
        "symbol": pos.symbol,
        "sl": sl if sl is not None else pos.sl,
        "tp": tp if tp is not None else pos.tp,
        "magic": config.MT5_MAGIC_NUMBER,
    }
    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        return {"success": True, "message": "Position modified"}
    err = result.comment if result else str(mt5.last_error())
    return {"success": False, "message": f"Modify failed: {err}"}


# ── Get open positions ────────────────────────────────────────────────────────

def get_open_positions() -> list[dict]:
    if not MT5_AVAILABLE or not is_connected():
        return []
    positions = mt5.positions_get()
    if not positions:
        return []
    result = []
    for p in positions:
        result.append({
            "id": p.ticket,
            "position_id": p.ticket,
            "symbol": p.symbol,
            "side": "buy" if p.type == mt5.ORDER_TYPE_BUY else "sell",
            "volume": p.volume,
            "entry": p.price_open,
            "sl": p.sl,
            "tp": p.tp,
            "pnl": p.profit,
            "opened": str(p.time),
            "magic": p.magic,
            "comment": p.comment,
        })
    return result


# ── Get trade history ─────────────────────────────────────────────────────────

def get_trade_history(limit: int = 50) -> list[dict]:
    if not MT5_AVAILABLE or not is_connected():
        return []
    from datetime import datetime, timedelta
    from_date = datetime.now() - timedelta(days=30)
    deals = mt5.history_deals_get(from_date, datetime.now())
    if not deals:
        return []
    result = []
    for d in sorted(deals, key=lambda x: x.time, reverse=True)[:limit]:
        result.append({
            "ticket": d.ticket,
            "symbol": d.symbol,
            "side": "buy" if d.type == mt5.DEAL_TYPE_BUY else "sell",
            "volume": d.volume,
            "entry": d.price,
            "sl": 0,
            "tp": 0,
            "pnl": d.profit,
            "status": "win" if d.profit > 0 else "loss" if d.profit < 0 else "breakeven",
            "opened": str(datetime.fromtimestamp(d.time)),
            "comment": d.comment,
        })
    return result
