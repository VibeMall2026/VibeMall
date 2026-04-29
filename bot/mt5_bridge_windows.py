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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
API_KEY        = os.getenv("API_KEY", "Paladiya@2023")
BRIDGE_PORT    = int(os.getenv("BRIDGE_PORT", "8001"))

app = FastAPI(title="MT5 Bridge", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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
    info = mt5.account_info()
    sym = mt5.symbol_info(symbol)
    if not info or not sym or sl_distance == 0:
        return sym.volume_min if sym else 0.01
    risk_amount = info.balance * (RISK_PERCENT / 100.0)
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


# ── Pydantic models ───────────────────────────────────────────────────────────

class TradeRequest(BaseModel):
    symbol: str
    side: str          # buy | sell
    sl: float
    tp: float
    entry: Optional[float] = None
    comment: str = "VPS Signal"


class ModifyRequest(BaseModel):
    sl: Optional[float] = None
    tp: Optional[float] = None


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
def get_account():
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
def get_positions():
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
def modify_position(position_id: int, body: ModifyRequest):
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
def open_trade(body: TradeRequest):
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

    price = tick.ask if side == "buy" else tick.bid
    sl_distance = abs(price - body.sl)
    lot = calculate_lot(symbol, sl_distance)

    order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
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
def get_history(limit: int = 50):
    if not ensure_connected():
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
            "pnl": d.profit,
            "status": "win" if d.profit > 0 else "loss" if d.profit < 0 else "breakeven",
            "opened": str(d.time),
            "comment": d.comment,
        })
    return result


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
