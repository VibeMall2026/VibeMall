"""
MT5 Bridge — Windows PC par chalavo.

Aa script:
1. MT5 sathe connect kare chhe
2. HTTP server chalave chhe (port 8001)
3. VPS bot na trade requests accept kare chhe
4. MT5 par execute kare chhe

Windows PC par run karo:
  pip install MetaTrader5 fastapi uvicorn python-dotenv
  python bot/mt5_bridge_windows.py
"""
import os
import math
import threading
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import MetaTrader5 as mt5
import uvicorn
from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────
MT5_LOGIN      = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD   = os.getenv("MT5_PASSWORD", "")
MT5_SERVER     = os.getenv("MT5_SERVER", "MetaQuotes-Demo")
MT5_PATH       = os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
MT5_TIMEOUT_MS = int(os.getenv("MT5_TIMEOUT_MS", "60000"))
MT5_DEVIATION  = int(os.getenv("MT5_DEVIATION", "20"))
MT5_MAGIC      = int(os.getenv("MT5_MAGIC_NUMBER", "550001"))
RISK_PERCENT   = float(os.getenv("RISK_PERCENT", "0.1"))
MAX_RISK_AMOUNT_USD = float(os.getenv("MAX_RISK_AMOUNT_USD", "30"))
MAX_PROFIT_AMOUNT_USD = float(os.getenv("MAX_PROFIT_AMOUNT_USD", "50"))
MAX_LOT_PER_TRADE = float(os.getenv("MAX_LOT_PER_TRADE", "0.02"))
API_KEY        = os.getenv("API_KEY", "")
BRIDGE_PORT    = int(os.getenv("BRIDGE_PORT", "8001"))

app = FastAPI(title="MT5 Bridge", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


# ── MT5 Connection ────────────────────────────────────────────────────────────

def connect_mt5() -> bool:
    kwargs = dict(
        login=MT5_LOGIN,
        password=MT5_PASSWORD,
        server=MT5_SERVER,
        timeout=MT5_TIMEOUT_MS,
    )
    if MT5_PATH:
        kwargs["path"] = MT5_PATH
    if not mt5.initialize(**kwargs):
        print(f"[MT5] Initialize failed: {mt5.last_error()}")
        return False
    info = mt5.account_info()
    print(f"[MT5] Connected | Account: {info.login} | Balance: {info.balance} {info.currency}")
    return True


def is_connected() -> bool:
    try:
        return mt5.terminal_info() is not None
    except Exception:
        return False


def ensure_connected() -> bool:
    if not is_connected():
        return connect_mt5()
    return True


# ── Lot calculation ───────────────────────────────────────────────────────────

def calculate_lot(symbol: str, sl_distance: float) -> float:
    return calculate_lot_with_risk(symbol, sl_distance, risk_percent=None)


def calculate_lot_with_risk(symbol: str, sl_distance: float, risk_percent: Optional[float] = None) -> float:
    info = mt5.account_info()
    sym = mt5.symbol_info(symbol)
    if not info or not sym or sl_distance == 0:
        return sym.volume_min if sym else 0.01
    effective_risk_percent = RISK_PERCENT if risk_percent is None else risk_percent
    risk_amount = info.balance * (effective_risk_percent / 100.0)
    tick_value = sym.trade_tick_value
    tick_size  = sym.trade_tick_size
    if tick_size == 0:
        return sym.volume_min
    sl_ticks = sl_distance / tick_size
    lot = risk_amount / (sl_ticks * tick_value)
    lot = max(sym.volume_min, min(sym.volume_max, lot))
    step = sym.volume_step
    lot = round(math.floor(lot / step) * step, 8)
    return lot


def _cap_lot_by_pnl_limits(
    *,
    sym,
    symbol: str,
    side: str,
    price: float,
    sl: float,
    tp: float,
    lot: float,
) -> float | None:
    """Cap lot using actual estimated SL/TP dollars."""
    caps: list[float] = []
    order_type = mt5.ORDER_TYPE_BUY if side.lower() == "buy" else mt5.ORDER_TYPE_SELL

    if MAX_RISK_AMOUNT_USD > 0 and sl > 0:
        loss_one_lot = mt5.order_calc_profit(order_type, symbol, 1.0, price, sl)
        loss_one_lot_abs = abs(float(loss_one_lot or 0.0))
        if loss_one_lot_abs > 0:
            caps.append(MAX_RISK_AMOUNT_USD / loss_one_lot_abs)

    if MAX_PROFIT_AMOUNT_USD > 0 and tp > 0:
        profit_one_lot = mt5.order_calc_profit(order_type, symbol, 1.0, price, tp)
        profit_one_lot_abs = abs(float(profit_one_lot or 0.0))
        if profit_one_lot_abs > 0:
            caps.append(MAX_PROFIT_AMOUNT_USD / profit_one_lot_abs)

    if caps:
        lot = min(lot, min(caps))

    if MAX_LOT_PER_TRADE > 0:
        lot = min(lot, MAX_LOT_PER_TRADE)

    if lot < sym.volume_min:
        return None

    lot = max(sym.volume_min, min(sym.volume_max, lot))
    step = sym.volume_step or sym.volume_min or 0.01
    lot = round(math.floor(lot / step) * step, 8)
    if lot < sym.volume_min:
        return None
    return lot


# ── Pydantic models ───────────────────────────────────────────────────────────

class TradeRequest(BaseModel):
    symbol: str
    side: str          # buy | sell
    order_type: str = "market"
    sl: float
    tp: float
    entry: Optional[float] = None
    risk_percent: Optional[float] = None
    comment: str = "VPS Signal"


class ModifyRequest(BaseModel):
    sl: Optional[float] = None
    tp: Optional[float] = None


def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    if api_key != API_KEY:
        raise HTTPException(403, "Invalid API key")
    return api_key


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    connected = is_connected()
    account = {}
    if connected:
        info = mt5.account_info()
        if info:
            account = {
                "login": info.login,
                "balance": info.balance,
                "equity": info.equity,
                "margin_free": info.margin_free,
                "currency": info.currency,
            }
    return {"mt5_connected": connected, "account": account}


@app.get("/account")
def get_account(_: str = Security(verify_api_key)):
    if not ensure_connected():
        raise HTTPException(503, "MT5 not connected")
    info = mt5.account_info()
    if not info:
        raise HTTPException(503, "Could not get account info")
    return {
        "balance": info.balance,
        "equity": info.equity,
        "margin_free": info.margin_free,
        "currency": info.currency,
        "leverage": info.leverage,
        "login": info.login,
        "server": info.server,
    }


@app.get("/positions")
def get_positions(_: str = Security(verify_api_key)):
    if not ensure_connected():
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
            "comment": p.comment,
        })
    return result


@app.put("/positions/{position_id}")
def modify_position(position_id: int, body: ModifyRequest, _: str = Security(verify_api_key)):
    if not ensure_connected():
        raise HTTPException(503, "MT5 not connected")
    positions = mt5.positions_get(ticket=position_id)
    if not positions:
        raise HTTPException(404, f"Position {position_id} not found")
    pos = positions[0]
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position_id,
        "symbol": pos.symbol,
        "sl": body.sl if body.sl is not None else pos.sl,
        "tp": body.tp if body.tp is not None else pos.tp,
        "magic": MT5_MAGIC,
    }
    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        return {"success": True, "message": "Position modified"}
    err = result.comment if result else str(mt5.last_error())
    raise HTTPException(400, f"Modify failed: {err}")


@app.post("/trade")
def open_trade(body: TradeRequest, _: str = Security(verify_api_key)):
    if not ensure_connected():
        raise HTTPException(503, "MT5 not connected")

    symbol = body.symbol
    side   = body.side.lower()

    # Select symbol
    sym_info = mt5.symbol_info(symbol)
    if not sym_info:
        raise HTTPException(400, f"Symbol {symbol} not found")
    if not sym_info.visible:
        mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        raise HTTPException(400, f"No tick data for {symbol}")

    normalized_order_type = (body.order_type or "market").lower().replace(" ", "_")
    normalized_order_type = normalized_order_type.replace("_", "")

    if normalized_order_type == "market":
        price = tick.ask if side == "buy" else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
        action = mt5.TRADE_ACTION_DEAL
    else:
        if body.entry is None:
            raise HTTPException(400, "Pending order requires an entry price")
        price = body.entry
        pending_type_map = {
            "buylimit": mt5.ORDER_TYPE_BUY_LIMIT,
            "buystop": mt5.ORDER_TYPE_BUY_STOP,
            "selllimit": mt5.ORDER_TYPE_SELL_LIMIT,
            "sellstop": mt5.ORDER_TYPE_SELL_STOP,
        }
        order_type = pending_type_map.get(normalized_order_type)
        action = mt5.TRADE_ACTION_PENDING
        if order_type is None:
            raise HTTPException(400, f"Unsupported order type: {body.order_type}")
        if normalized_order_type == "buylimit" and price >= tick.ask:
            raise HTTPException(400, "BUY LIMIT entry must be below current ask")
        if normalized_order_type == "buystop" and price <= tick.ask:
            raise HTTPException(400, "BUY STOP entry must be above current ask")
        if normalized_order_type == "selllimit" and price <= tick.bid:
            raise HTTPException(400, "SELL LIMIT entry must be above current bid")
        if normalized_order_type == "sellstop" and price >= tick.bid:
            raise HTTPException(400, "SELL STOP entry must be below current bid")

    sl_distance = abs(price - body.sl)
    lot = calculate_lot_with_risk(symbol, sl_distance, risk_percent=body.risk_percent)

    lot = _cap_lot_by_pnl_limits(
        sym=sym_info,
        symbol=symbol,
        side=side,
        price=price,
        sl=body.sl,
        tp=body.tp,
        lot=lot,
    )
    if lot is None:
        raise HTTPException(400, "Trade blocked: broker minimum lot exceeds configured per-trade risk/lot caps")

    request = {
        "action":       action,
        "symbol":       symbol,
        "volume":       lot,
        "type":         order_type,
        "price":        price,
        "sl":           body.sl,
        "tp":           body.tp,
        "deviation":    MT5_DEVIATION,
        "magic":        MT5_MAGIC,
        "comment":      body.comment,
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        raise HTTPException(500, f"order_send returned None: {mt5.last_error()}")

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"[MT5] Trade opened | {symbol} {side.upper()} | Lot: {lot} | Ticket: {result.order}")
        return {"success": True, "ticket": result.order, "lot": lot, "price": price}

    raise HTTPException(400, f"Order failed: retcode={result.retcode} | {result.comment}")


@app.get("/history")
def get_history(limit: int = 50, _: str = Security(verify_api_key)):
    if not ensure_connected():
        return []
    from datetime import datetime, timedelta
    from_date = datetime.now() - timedelta(days=30)
    deals = mt5.history_deals_get(from_date, datetime.now())
    if not deals:
        return []

    # Build map of position_id → (comment, side) from opening deals
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
        if d.entry == mt5.DEAL_ENTRY_IN:
            continue
        if not d.symbol:
            continue
        if d.profit == 0 and d.volume == 0:
            continue
        comment = position_comments.get(d.position_id, "") or d.comment or ""
        # Use opening deal side; fallback: closing DEAL_TYPE_SELL means it was a BUY position
        side = position_sides.get(d.position_id, "buy" if d.type == mt5.DEAL_TYPE_SELL else "sell")
        result.append({
            "ticket": d.ticket,
            "symbol": d.symbol,
            "side": side,
            "volume": d.volume,
            "entry": d.price,
            "pnl": d.profit,
            "status": "win" if d.profit > 0 else "loss" if d.profit < 0 else "breakeven",
            "opened": datetime.utcfromtimestamp(d.time).strftime("%Y-%m-%d %H:%M:%S"),
            "comment": comment,
        })
        if len(result) >= limit:
            break
    return result


@app.get("/candles")
def get_candles(symbol: str, timeframe: int = 15, count: int = 100, _: str = Security(verify_api_key)):
    """Return OHLCV candles for algo strategy (used by Ubuntu VPS)."""
    if not ensure_connected():
        raise HTTPException(503, "MT5 not connected")

    tf_map = {
        1: mt5.TIMEFRAME_M1,
        5: mt5.TIMEFRAME_M5,
        15: mt5.TIMEFRAME_M15,
        30: mt5.TIMEFRAME_M30,
        60: mt5.TIMEFRAME_H1,
        240: mt5.TIMEFRAME_H4,
        1440: mt5.TIMEFRAME_D1,
    }
    tf = tf_map.get(timeframe, mt5.TIMEFRAME_M15)

    # Select symbol if not visible
    sym_info = mt5.symbol_info(symbol)
    if sym_info and not sym_info.visible:
        mt5.symbol_select(symbol, True)

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        return []

    from datetime import datetime as dt
    result = []
    for r in rates:
        result.append({
            "time": dt.fromtimestamp(r['time']).isoformat(),
            "open": float(r['open']),
            "high": float(r['high']),
            "low": float(r['low']),
            "close": float(r['close']),
            "volume": float(r['tick_volume']),
        })
    return result


@app.get("/price")
def get_price(symbol: str, _: str = Security(verify_api_key)):
    """Return current bid/ask price for a symbol (used by Ubuntu VPS algo)."""
    if not ensure_connected():
        raise HTTPException(503, "MT5 not connected")

    # Select symbol if not visible
    sym_info = mt5.symbol_info(symbol)
    if sym_info and not sym_info.visible:
        mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        raise HTTPException(404, f"No tick data for {symbol}")

    return {
        "symbol": symbol,
        "bid": tick.bid,
        "ask": tick.ask,
        "time": tick.time,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  MT5 Bridge Starting")
    print(f"  Port: {BRIDGE_PORT}")
    print(f"  MT5 Login: {MT5_LOGIN} @ {MT5_SERVER}")
    print("=" * 50)

    # Connect MT5
    if connect_mt5():
        print("[MT5] Connected successfully!")
    else:
        print("[MT5] WARNING: Could not connect. Check MT5 terminal is open.")

    # Start HTTP server
    uvicorn.run(app, host="0.0.0.0", port=BRIDGE_PORT, log_level="info")
