"""
FastAPI server — exposes bot control & data endpoints.
Called by the Django dashboard (trading/ app).
"""
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bot import config
from bot.state import state
from bot import mt5_bridge
from bot.signal_parser import parse_signal

app = FastAPI(title="Trading Bot API", version="1.0.0")

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.API_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ──────────────────────────────────────────────────────────────────────
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    if api_key != config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


# ── Pydantic models ───────────────────────────────────────────────────────────

class ControlRequest(BaseModel):
    action: str  # start | stop | restart | weekend_shutdown


class SettingsUpdate(BaseModel):
    risk_percent: Optional[float] = None
    reward_ratio: Optional[float] = None
    max_trades: Optional[int] = None
    max_positions: Optional[int] = None
    max_daily_loss: Optional[float] = None
    max_consecutive_losses: Optional[int] = None
    max_spread: Optional[int] = None
    duplicate_window: Optional[int] = None
    min_seconds: Optional[int] = None
    allow_pending: Optional[bool] = None


class ChannelRequest(BaseModel):
    channel: str


class ModifyPositionRequest(BaseModel):
    sl: Optional[float] = None
    tp: Optional[float] = None


class ParseSignalRequest(BaseModel):
    text: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/status", dependencies=[Depends(verify_api_key)])
async def get_status():
    account = mt5_bridge.get_account_info()
    return {
        "bot": {
            "running": state.running,
            "telegram_connected": state.telegram_connected,
            "mt5_connected": mt5_bridge.is_connected(),
        },
        "account": account,
        "signals_processed": state.signals_processed,
    }


@app.get("/stats", dependencies=[Depends(verify_api_key)])
async def get_stats():
    account = mt5_bridge.get_account_info()
    open_pos = mt5_bridge.get_open_positions()
    total_trades = state.daily_wins + state.daily_losses
    win_rate = (state.daily_wins / total_trades * 100) if total_trades > 0 else 0.0

    return {
        "bot": {
            "running": state.running,
            "telegram_connected": state.telegram_connected,
            "mt5_connected": mt5_bridge.is_connected(),
        },
        "account": account,
        "trades": {
            "total": total_trades,
            "open": len(open_pos),
        },
        "performance": {
            "winning_trades": state.daily_wins,
            "losing_trades": state.daily_losses,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(state.daily_net_pnl, 2),
        },
        "daily": {
            "wins": state.daily_wins,
            "losses": state.daily_losses,
            "trades_count": total_trades,
            "net_pnl": round(state.daily_net_pnl, 2),
        },
    }


@app.get("/open-trades", dependencies=[Depends(verify_api_key)])
async def get_open_trades():
    return mt5_bridge.get_open_positions()


@app.get("/trades", dependencies=[Depends(verify_api_key)])
async def get_trades():
    return mt5_bridge.get_trade_history(limit=50)


@app.get("/signals", dependencies=[Depends(verify_api_key)])
async def get_signals():
    return state.signal_log[:50]


@app.get("/settings", dependencies=[Depends(verify_api_key)])
async def get_settings():
    return {
        "channels": state.channels,
        "risk": {
            "risk_percent": state.risk_percent,
            "reward_ratio": state.reward_ratio,
            "max_trades": state.max_trades_per_day,
            "max_positions": state.max_open_positions,
            "max_daily_loss": state.max_daily_loss_percent,
            "max_consecutive_losses": state.max_consecutive_losses,
        },
        "validation": {
            "max_spread": state.max_spread_points,
            "duplicate_window": state.duplicate_window_minutes,
            "min_seconds": state.min_seconds_between_trades,
            "allow_pending": state.allow_pending_orders,
        },
    }


@app.put("/settings", dependencies=[Depends(verify_api_key)])
async def update_settings(body: SettingsUpdate):
    if body.risk_percent is not None:
        state.risk_percent = body.risk_percent
    if body.reward_ratio is not None:
        state.reward_ratio = body.reward_ratio
    if body.max_trades is not None:
        state.max_trades_per_day = body.max_trades
    if body.max_positions is not None:
        state.max_open_positions = body.max_positions
    if body.max_daily_loss is not None:
        state.max_daily_loss_percent = body.max_daily_loss
    if body.max_consecutive_losses is not None:
        state.max_consecutive_losses = body.max_consecutive_losses
    if body.max_spread is not None:
        state.max_spread_points = body.max_spread
    if body.duplicate_window is not None:
        state.duplicate_window_minutes = body.duplicate_window
    if body.min_seconds is not None:
        state.min_seconds_between_trades = body.min_seconds
    if body.allow_pending is not None:
        state.allow_pending_orders = body.allow_pending
    return {"success": True, "message": "Settings updated"}


@app.post("/channels", dependencies=[Depends(verify_api_key)])
async def add_channel(body: ChannelRequest):
    ch = body.channel.strip()
    if ch not in state.channels:
        state.channels.append(ch)
    return {"success": True, "channels": state.channels}


@app.delete("/channels", dependencies=[Depends(verify_api_key)])
async def remove_channel(body: ChannelRequest):
    ch = body.channel.strip()
    if ch in state.channels:
        state.channels.remove(ch)
    return {"success": True, "channels": state.channels}


@app.put("/positions/{position_id}", dependencies=[Depends(verify_api_key)])
async def modify_position(position_id: int, body: ModifyPositionRequest):
    result = mt5_bridge.modify_position(position_id, sl=body.sl, tp=body.tp)
    return result


@app.post("/parse-signal", dependencies=[Depends(verify_api_key)])
async def parse_signal_endpoint(body: ParseSignalRequest):
    sig = parse_signal(body.text)
    return sig.to_dict()


@app.post("/control", dependencies=[Depends(verify_api_key)])
async def control_bot(body: ControlRequest):
    action = body.action
    if action == "start":
        if state.running:
            return {"success": False, "message": "Bot already running"}
        state.running = True
        return {"success": True, "message": "Bot started", "status": "running"}

    elif action == "stop":
        state.running = False
        return {"success": True, "message": "Bot stopped", "status": "stopped"}

    elif action == "restart":
        state.running = False
        await asyncio.sleep(1)
        state.running = True
        return {"success": True, "message": "Bot restarted", "status": "running"}

    elif action == "weekend_shutdown":
        state.running = False
        return {"success": True, "message": "Weekend shutdown initiated", "status": "stopped"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
