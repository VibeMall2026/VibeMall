"""
MT5 Bridge — connects to MetaTrader 5 on Windows PC and executes trades.

NOTE: MetaTrader5 Python library only works on Windows.
      On Ubuntu VPS this module is imported but MT5 calls are skipped
      (bot runs in "simulation" mode until Windows bridge is connected).
"""
import os
import sys
import math
import time
import threading
import subprocess
from datetime import datetime
from typing import Optional
import requests
from loguru import logger
from bot import config

# Try importing MT5 — only available on Windows
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 library not available (Ubuntu). Running without MT5.")

# Bridge configuration (for Ubuntu VPS → Windows PC delegation)
BRIDGE_URL = os.getenv("MT5_BRIDGE_URL", "").strip()
BRIDGE_API_KEY = os.getenv("MT5_BRIDGE_API_KEY", "")
USE_BRIDGE = not MT5_AVAILABLE and bool(BRIDGE_URL)

if USE_BRIDGE:
    logger.info(f"Bridge mode enabled: {BRIDGE_URL}")
elif not MT5_AVAILABLE:
    logger.warning("MT5 not available and no bridge configured")


_reconnect_lock = threading.Lock()
_last_reconnect_attempt_ts = 0.0
_RECONNECT_COOLDOWN_SECONDS = 3.0
_last_terminal_launch_ts_by_path: dict[str, float] = {}
_TERMINAL_RELAUNCH_COOLDOWN_SECONDS = 300.0


def _launch_mt5_terminal(path: str) -> bool:
    terminal_path = str(path or "").strip()
    if not terminal_path:
        return False
    if os.name != "nt":
        return False
    now_ts = time.monotonic()
    last_launch_ts = _last_terminal_launch_ts_by_path.get(terminal_path, 0.0)
    if (now_ts - last_launch_ts) < _TERMINAL_RELAUNCH_COOLDOWN_SECONDS:
        return False
    try:
        from pathlib import Path

        if not Path(terminal_path).exists():
            logger.warning(f"MT5 terminal path not found: {terminal_path}")
            return False
        subprocess.Popen(
            [terminal_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(Path(terminal_path).parent),
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        _last_terminal_launch_ts_by_path[terminal_path] = now_ts
        logger.info(f"MT5 terminal launched: {terminal_path}")
        return True
    except Exception as exc:
        logger.warning(f"Could not launch MT5 terminal: {exc}")
        return False


# ── Bridge HTTP Client ────────────────────────────────────────────────────────

def _call_bridge(endpoint: str, method: str = "GET", json_data: dict = None, timeout: int = 5) -> Optional[dict]:
    """
    Call Windows bridge HTTP endpoint.
    Returns response JSON dict on success, None on failure.
    """
    if not BRIDGE_URL:
        return None
    
    url = f"{BRIDGE_URL}{endpoint}"
    headers = {"X-API-Key": BRIDGE_API_KEY} if BRIDGE_API_KEY else {}
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=timeout)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=json_data, timeout=timeout)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=json_data, timeout=timeout)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return None
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.Timeout:
        logger.error(f"Bridge request timeout: {url}")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"Bridge connection error: {url}")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"Bridge HTTP error: {e.response.status_code} - {url}")
        return None
    except Exception as e:
        logger.error(f"Bridge request failed: {e}")
        return None


def _check_bridge_health() -> bool:
    """
    Check if Windows bridge is connected to MT5.
    Returns True if bridge is reachable and MT5 is connected.
    """
    response = _call_bridge("/health")
    if response is None:
        return False
    return response.get("mt5_connected", False)


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
    if getattr(config, "MT5_PORTABLE", False):
        kwargs["portable"] = True

    # If no primary credentials are configured, try any enabled account directly.
    if not config.MT5_LOGIN:
        from bot.accounts import ensure_any_account_connected
        return ensure_any_account_connected()

    from bot.accounts import get_mt5_lock
    with get_mt5_lock():
        if not mt5.initialize(**kwargs):
            last_error = str(mt5.last_error())
            logger.error(f"MT5 initialize failed: {last_error}")
            if "IPC send failed" in last_error or "IPC timeout" in last_error:
                launch_path = config.MT5_PATH or ""
                if _launch_mt5_terminal(launch_path):
                    time.sleep(4)
                    if mt5.initialize(**kwargs) and mt5.login(config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
                        info = mt5.account_info()
                        if info and int(getattr(info, "login", 0) or 0) == int(config.MT5_LOGIN):
                            logger.info(
                                f"MT5 reconnected after terminal relaunch | Account: {info.login} | "
                                f"Balance: {info.balance} {info.currency}"
                            )
                            return True
            # In single-account mode, never fallback to another account login.
            if os.getenv("BOT_SINGLE_ACCOUNT_MODE", "").strip().lower() not in ("1", "true", "yes", "on"):
                from bot.accounts import ensure_any_account_connected
                if ensure_any_account_connected():
                    logger.warning("MT5 primary connect failed; using enabled account fallback")
                    return True
            return False
        # Enforce explicit login so terminal's previously saved account is not reused silently.
        if not mt5.login(config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
            logger.error(f"MT5 login failed for {config.MT5_LOGIN}@{config.MT5_SERVER}: {mt5.last_error()}")
            mt5.shutdown()
            return False

        info = mt5.account_info()
        if not info or int(getattr(info, "login", 0) or 0) != int(config.MT5_LOGIN):
            actual_login = getattr(info, "login", "unknown") if info else "none"
            logger.error(
                f"MT5 login mismatch: expected {config.MT5_LOGIN}, got {actual_login}"
            )
            mt5.shutdown()
            return False
        logger.info(f"MT5 connected | Account: {info.login} | Balance: {info.balance} {info.currency}")
        return True


def disconnect() -> None:
    if MT5_AVAILABLE:
        from bot.accounts import get_mt5_lock
        with get_mt5_lock():
            mt5.shutdown()
            logger.info("MT5 disconnected.")


def is_connected() -> bool:
    if not MT5_AVAILABLE:
        return False
    from bot.accounts import get_mt5_lock
    try:
        with get_mt5_lock():
            return mt5.terminal_info() is not None
    except Exception:
        return False


def ensure_connected() -> bool:
    """Return an active MT5 connection, attempting a reconnect if needed."""
    # Bridge delegation mode
    if USE_BRIDGE:
        return _check_bridge_health()
    
    # Direct MT5 mode (existing code)
    if not MT5_AVAILABLE:
        return False
    if is_connected():
        # If explicit credentials are configured, verify the active MT5 session
        # belongs to that login; otherwise reconnect with requested account.
        if config.MT5_LOGIN:
            from bot.accounts import get_mt5_lock
            with get_mt5_lock():
                info = mt5.account_info()
            active_login = int(getattr(info, "login", 0) or 0) if info else 0
            if active_login != int(config.MT5_LOGIN):
                logger.warning(
                    f"MT5 connected with different login (active={active_login}, expected={config.MT5_LOGIN}); reconnecting"
                )
                disconnect()
            else:
                return True
        else:
            return True

    global _last_reconnect_attempt_ts
    acquired = _reconnect_lock.acquire(blocking=False)
    if not acquired:
        wait_until = time.monotonic() + max(1.0, _RECONNECT_COOLDOWN_SECONDS)
        while time.monotonic() < wait_until:
            if is_connected():
                return True
            time.sleep(0.1)
        return is_connected()

    try:
        now = time.monotonic()
        if (now - _last_reconnect_attempt_ts) < _RECONNECT_COOLDOWN_SECONDS:
            return is_connected()
        _last_reconnect_attempt_ts = now
        logger.warning("MT5 connection inactive. Attempting reconnect...")
        if connect():
            return True
    finally:
        _reconnect_lock.release()

    # In single-account mode, never fallback to another account login.
    if os.getenv("BOT_SINGLE_ACCOUNT_MODE", "").strip().lower() in ("1", "true", "yes", "on"):
        return False

    from bot.accounts import ensure_any_account_connected
    return ensure_any_account_connected()


# ── Account info ──────────────────────────────────────────────────────────────

def get_account_info(*, attempt_reconnect: bool = True) -> dict:
    # Bridge delegation mode
    if USE_BRIDGE:
        response = _call_bridge("/account")
        return response if response is not None else {}
    
    # Direct MT5 mode (existing code)
    if not MT5_AVAILABLE:
        return {}
    if attempt_reconnect:
        if not ensure_connected():
            return {}
    elif not is_connected():
        return {}
    from bot.accounts import get_mt5_lock
    with get_mt5_lock():
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
    """Backward-compatible wrapper using configured risk percentage."""
    return calculate_lot_with_risk(symbol, sl_points, risk_percent=None)


def calculate_lot_with_risk(symbol: str, sl_points: float, risk_percent: Optional[float] = None) -> float:
    """Calculate lot size based on risk % of account balance."""
    # Bridge delegation mode - fetch account info from bridge
    if USE_BRIDGE:
        account_response = _call_bridge("/account")
        if account_response is None:
            logger.warning("Bridge account info unavailable, using minimum lot")
            return 0.01
        
        balance = account_response.get("balance", 0)
        if balance == 0:
            return 0.01
        
        # Note: Symbol info is not available via bridge yet
        # For now, use conservative defaults
        # TODO: Add /symbol_info endpoint to bridge or fetch locally
        effective_risk_percent = config.RISK_PERCENT if risk_percent is None else risk_percent
        risk_amount = balance * (effective_risk_percent / 100.0)
        
        # Conservative lot calculation without symbol info
        # Assume standard forex pair with $10 per pip per lot
        lot = risk_amount / (sl_points * 10)
        lot = max(0.01, min(100.0, lot))  # Clamp to reasonable range
        lot = round(lot, 2)  # Round to 2 decimals
        return lot
    
    # Direct MT5 mode (existing code)
    if not MT5_AVAILABLE or not ensure_connected():
        return 0.01
    info = mt5.account_info()
    if not info:
        return 0.01
    sym_info = mt5.symbol_info(symbol)
    if not sym_info:
        logger.warning(f"Symbol info not found: {symbol}")
        return 0.01

    effective_risk_percent = config.RISK_PERCENT if risk_percent is None else risk_percent
    risk_amount = info.balance * (effective_risk_percent / 100.0)
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
    """Cap lot using actual MT5 profit calculation so metals size safely."""
    order_type = mt5.ORDER_TYPE_BUY if side.lower() == "buy" else mt5.ORDER_TYPE_SELL
    caps: list[float] = []

    # Symbol-specific risk cap (XAUUSD tends to need tighter safety defaults).
    max_risk_usd = float(getattr(config, "MAX_RISK_AMOUNT_USD", 0.0) or 0.0)
    try:
        sym_norm = str(symbol or "").upper().replace("/", "").replace(" ", "")
        if sym_norm.startswith("XAUUSD"):
            xau_cap = float(getattr(config, "XAUUSD_MAX_RISK_USD", 10.0) or 10.0)
            if xau_cap > 0:
                max_risk_usd = xau_cap if max_risk_usd <= 0 else min(max_risk_usd, xau_cap)
    except Exception:
        pass

    if max_risk_usd > 0 and sl > 0:
        loss_one_lot = mt5.order_calc_profit(order_type, symbol, 1.0, price, sl)
        loss_one_lot_abs = abs(float(loss_one_lot or 0.0))
        if loss_one_lot_abs > 0:
            caps.append(max_risk_usd / loss_one_lot_abs)

    if config.MAX_PROFIT_AMOUNT_USD > 0 and tp > 0:
        profit_one_lot = mt5.order_calc_profit(order_type, symbol, 1.0, price, tp)
        profit_one_lot_abs = abs(float(profit_one_lot or 0.0))
        if profit_one_lot_abs > 0:
            caps.append(config.MAX_PROFIT_AMOUNT_USD / profit_one_lot_abs)

    if caps:
        lot = min(lot, min(caps))

    if config.MAX_LOT_PER_TRADE > 0:
        lot = min(lot, config.MAX_LOT_PER_TRADE)

    if lot < sym_info.volume_min:
        return None

    lot = max(sym_info.volume_min, min(sym_info.volume_max, lot))
    step = sym_info.volume_step or sym_info.volume_min or 0.01
    lot = round(math.floor(lot / step) * step, 8)
    if lot < sym_info.volume_min:
        return None
    return lot


# ── Open trade ────────────────────────────────────────────────────────────────

def open_trade(
    symbol: str,
    side: str,
    sl: float,
    tp: float,
    entry: Optional[float] = None,
    order_type: str = "market",
    risk_percent: Optional[float] = None,
    comment: str = "TG Signal",
) -> dict:
    """
    Open a market or pending order.
    Returns dict with success, ticket, message.
    """
    # Bridge delegation mode
    if USE_BRIDGE:
        json_data = {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "sl": sl,
            "tp": tp,
            "entry": entry,
            "risk_percent": risk_percent,
            "comment": comment,
        }
        response = _call_bridge("/trade", method="POST", json_data=json_data)
        if response is None:
            return {"success": False, "message": "Bridge request failed"}
        return response
    
    # Direct MT5 mode (existing code)
    if not MT5_AVAILABLE or not ensure_connected():
        return {"success": False, "message": "MT5 not connected"}

    from bot.accounts import get_mt5_lock
    with get_mt5_lock():
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

        normalized_order_type = (order_type or "market").lower().replace(" ", "_")
        normalized_order_type = normalized_order_type.replace("_", "")

        if normalized_order_type == "market":
            mt5_order_type = market_type_map.get(side.lower())
            action = mt5.TRADE_ACTION_DEAL
            price = tick.ask if side.lower() == "buy" else tick.bid
        else:
            mt5_order_type = pending_type_map.get(normalized_order_type)
            action = mt5.TRADE_ACTION_PENDING
            price = entry
            if price is None:
                return {"success": False, "message": "Pending order requires an entry price"}
            if normalized_order_type == "buylimit" and price >= tick.ask:
                return {"success": False, "message": "BUY LIMIT entry must be below current ask"}
            if normalized_order_type == "buystop" and price <= tick.ask:
                return {"success": False, "message": "BUY STOP entry must be above current ask"}
            if normalized_order_type == "selllimit" and price <= tick.bid:
                return {"success": False, "message": "SELL LIMIT entry must be above current bid"}
            if normalized_order_type == "sellstop" and price >= tick.bid:
                return {"success": False, "message": "SELL STOP entry must be below current bid"}

        if mt5_order_type is None:
            return {"success": False, "message": f"Unknown order type: {order_type}"}

        sl_points = abs(price - sl)
        lot = calculate_lot_with_risk(symbol, sl_points, risk_percent=risk_percent)

        lot = _cap_lot_by_pnl_limits(
            sym_info=sym_info,
            symbol=symbol,
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
            "symbol": symbol,
            "volume": lot,
            "type": mt5_order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": config.MT5_DEVIATION,
            "magic": config.MT5_MAGIC_NUMBER,
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
                logger.success(
                    f"Trade opened | {symbol} {side.upper()} | Type: {normalized_order_type} | Lot: {lot} | Ticket: {result.order}"
                )
                return {"success": True, "ticket": result.order, "lot": lot, "message": "Trade opened"}
            if result and result.retcode == 10030:
                continue
            if result is None:
                continue
            msg = f"Order failed: retcode={result.retcode} comment={result.comment}"
            logger.error(msg)
            return {"success": False, "message": msg}

        if last_result is None:
            return {"success": False, "message": f"order_send returned None: {mt5.last_error()}"}
        msg = f"Order failed: retcode={last_result.retcode} comment={last_result.comment}"
        logger.error(msg)
        return {"success": False, "message": msg}


# ── Modify position ───────────────────────────────────────────────────────────

def modify_position(position_id: int, sl: Optional[float] = None, tp: Optional[float] = None) -> dict:
    # Bridge delegation mode
    if USE_BRIDGE:
        json_data = {}
        if sl is not None:
            json_data["sl"] = sl
        if tp is not None:
            json_data["tp"] = tp
        response = _call_bridge(f"/positions/{position_id}", method="PUT", json_data=json_data)
        if response is None:
            return {"success": False, "message": "Bridge request failed"}
        return response
    
    # Direct MT5 mode (existing code)
    if not MT5_AVAILABLE or not ensure_connected():
        return {"success": False, "message": "MT5 not connected"}

    # Guard against account-switch races in multi-thread + multi-account mode.
    from bot.accounts import get_mt5_lock
    with get_mt5_lock():
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
    # Bridge delegation mode
    if USE_BRIDGE:
        response = _call_bridge("/positions")
        return response if response is not None else []
    
    # Direct MT5 mode (existing code)
    if not MT5_AVAILABLE or not ensure_connected():
        return []
    from bot.accounts import get_mt5_lock
    with get_mt5_lock():
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


def get_current_price(symbol: str, side: Optional[str] = None) -> Optional[float]:
    """
    Return current symbol price.
    side:
      - "buy"  -> ask
      - "sell" -> bid
      - None / "mid" -> midpoint
    """
    # Bridge delegation mode
    if USE_BRIDGE:
        response = _call_bridge("/tick", method="GET", timeout=5)
        # Bridge may not expose symbol-specific tick endpoint; fail gracefully.
        if not isinstance(response, dict):
            return None
        bid = response.get("bid")
        ask = response.get("ask")
        try:
            bid_f = float(bid)
            ask_f = float(ask)
        except Exception:
            return None
        s = str(side or "mid").strip().lower()
        if s == "buy":
            return ask_f
        if s == "sell":
            return bid_f
        return (bid_f + ask_f) / 2.0

    # Direct MT5 mode
    if not MT5_AVAILABLE or not ensure_connected():
        return None

    from bot.accounts import get_mt5_lock
    with get_mt5_lock():
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None
        bid = float(getattr(tick, "bid", 0.0) or 0.0)
        ask = float(getattr(tick, "ask", 0.0) or 0.0)
        s = str(side or "mid").strip().lower()
        if s == "buy":
            return ask if ask > 0 else None
        if s == "sell":
            return bid if bid > 0 else None
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        return ask if ask > 0 else (bid if bid > 0 else None)


def close_position(position_id: int) -> dict:
    """Fully close an open position by ticket/position id."""
    # Bridge delegation mode
    if USE_BRIDGE:
        response = _call_bridge(f"/positions/{position_id}/close", method="POST", json_data={})
        if response is None:
            return {"success": False, "message": "Bridge request failed"}
        return response

    # Direct MT5 mode
    if not MT5_AVAILABLE or not ensure_connected():
        return {"success": False, "message": "MT5 not connected"}

    from bot.accounts import get_mt5_lock
    with get_mt5_lock():
        positions = mt5.positions_get(ticket=position_id)
        if not positions:
            return {"success": False, "message": f"Position {position_id} not found"}

        pos = positions[0]
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            return {"success": False, "message": f"No tick data for {pos.symbol}"}
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": position_id,
            "price": price,
            "deviation": config.MT5_DEVIATION,
            "magic": config.MT5_MAGIC_NUMBER,
            "comment": "ALGO:WEEKEND_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return {"success": True, "message": "Position closed"}
        err = result.comment if result else str(mt5.last_error())
        return {"success": False, "message": f"Close failed: {err}"}


def close_positions_for_weekend(exempt_symbols: Optional[set[str]] = None) -> dict:
    """
    Close all open positions except exempt symbols (default: BTCUSD variants).
    Intended for Friday pre-close safety.
    """
    exempt = {s.upper().replace("/", "").replace(" ", "") for s in (exempt_symbols or {"BTCUSD"})}
    positions = get_open_positions()
    closed = []
    skipped = []
    failed = []

    for p in positions:
        pid = p.get("id") or p.get("position_id")
        symbol = str(p.get("symbol") or "").strip()
        symbol_norm = symbol.upper().replace("/", "").replace(" ", "")
        # Allow common broker suffix/prefix variants like BTCUSDm, xBTCUSD.
        if any(ex in symbol_norm for ex in exempt):
            skipped.append({"position_id": pid, "symbol": symbol, "reason": "exempt_symbol"})
            continue

        result = close_position(int(pid)) if pid is not None else {"success": False, "message": "missing_position_id"}
        if result.get("success"):
            closed.append({"position_id": pid, "symbol": symbol})
        else:
            failed.append({"position_id": pid, "symbol": symbol, "error": result.get("message", "unknown_error")})

    summary = {
        "success": len(failed) == 0,
        "timestamp": datetime.utcnow().isoformat(),
        "total_open": len(positions),
        "closed_count": len(closed),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "closed": closed,
        "skipped": skipped,
        "failed": failed,
    }
    logger.info(
        f"[WEEKEND] Close non-exempt positions done | open={summary['total_open']} "
        f"closed={summary['closed_count']} skipped={summary['skipped_count']} failed={summary['failed_count']}"
    )
    return summary


# ── Get trade history ─────────────────────────────────────────────────────────

def get_trade_history(limit: int = 50) -> list[dict]:
    # Bridge delegation mode
    if USE_BRIDGE:
        response = _call_bridge(f"/history?limit={limit}")
        return response if response is not None else []
    
    # Direct MT5 mode (existing code)
    if not MT5_AVAILABLE or not ensure_connected():
        return []
    from datetime import datetime, timedelta, timezone

    # Use fixed wide range to avoid ALL timezone/broker-time issues
    from_date = datetime(2020, 1, 1)
    to_date = datetime(2030, 1, 1)
    deals = mt5.history_deals_get(from_date, to_date)
    if not deals:
        return []

    # Build map of position_id → comment and side from opening deals
    position_comments: dict = {}
    position_sides: dict = {}
    for d in deals:
        if d.entry == mt5.DEAL_ENTRY_IN:
            if d.comment:
                position_comments[d.position_id] = d.comment
            # DEAL_TYPE_BUY (0) = opening a BUY position
            # DEAL_TYPE_SELL (1) = opening a SELL position
            position_sides[d.position_id] = "buy" if d.type == mt5.DEAL_TYPE_BUY else "sell"

    result = []
    for d in sorted(deals, key=lambda x: x.time, reverse=True):
        # Include all closing deal types:
        # DEAL_ENTRY_OUT     = normal close (SL/TP hit, manual close button)
        # DEAL_ENTRY_OUT_BY  = close by opposite position (hedge accounts)
        # Skip DEAL_ENTRY_IN (trade open) and DEAL_ENTRY_INOUT (balance ops)
        if d.entry == mt5.DEAL_ENTRY_IN:
            continue
        # Skip pure balance/deposit/withdrawal/commission operations (no symbol)
        if not d.symbol:
            continue
        # Skip zero-profit deals that are just commission/swap records
        # (but keep breakeven trades that have a symbol and volume)
        if d.profit == 0 and d.volume == 0:
            continue

        # Get comment from opening deal via position_id, fallback to closing deal comment
        comment = position_comments.get(d.position_id, "") or d.comment or ""

        # Determine source and channel
        if "ALGO:OB" in comment:
            source = "ALGO"
            channel = "⚡ Algo Strategy"
        elif "goldsingnaltest" in comment or "BENGOLDTRADER" in comment or comment.startswith("TG:"):
            source = "TELEGRAM"
            channel = comment.replace("TG:", "").strip()
        elif comment:
            source = "MANUAL"
            channel = comment[:20]
        else:
            source = "MANUAL"
            channel = "-"

        result.append({
            "ticket": d.ticket,
            "position_id": d.position_id,
            "symbol": d.symbol,
            "side": position_sides.get(d.position_id, "buy" if d.type == mt5.DEAL_TYPE_SELL else "sell"),
            "volume": d.volume,
            "entry": d.price,
            "sl": "-",
            "tp": "-",
            "rr": "-",
            "pnl": round(d.profit, 2),
            "status": "win" if d.profit > 0 else "loss" if d.profit < 0 else "breakeven",
            "source": source,
            "channel": channel,
            "comment": comment,
            "opened": datetime.utcfromtimestamp(d.time).strftime("%Y-%m-%d %H:%M:%S"),
        })
        if len(result) >= limit:
            break
    return result
