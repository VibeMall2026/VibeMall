"""
FastAPI server — exposes bot control & data endpoints.
Called by the Django dashboard (trading/ app).
"""
import asyncio
from datetime import datetime
from typing import Optional

from loguru import logger
from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bot import config
from bot.state import state
from bot import mt5_bridge
from bot.signal_parser import parse_signal
from bot.algo.manager import (
    get_active_strategy_id,
    get_algo_status,
    get_risk_status,
    select_strategy,
    start_algo,
    stop_algo,
    update_algo_config,
)

app = FastAPI(title="Trading Bot API", version="1.0.0")

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.API_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def restrict_client_ips(request: Request, call_next):
    if request.url.path in ("/health", "/accounts/debug"):
        return await call_next(request)

    allowed_ips = {ip.strip() for ip in config.API_ALLOWED_IPS if ip.strip()}
    if allowed_ips:
        client_host = request.client.host if request.client else ""
        if client_host and client_host not in allowed_ips:
            return JSONResponse(status_code=403, content={"detail": f"IP not allowed: {client_host}"})

    return await call_next(request)

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
    # mt5.terminal_info() is not thread-safe from uvicorn thread
    # state.mt5_connected is set by main/reconnect thread — use that
    mt5_connected = state.mt5_connected
    return {
        "bot": {
            "running": state.running,
            "telegram_connected": state.telegram_connected,
            "mt5_connected": mt5_connected,
        },
        "account": account,
        "signals_processed": state.signals_processed,
    }


@app.get("/health")
async def health():
    """Quick health check — called by Django dashboard."""
    return {
        "running": state.running,
        "mt5_connected": state.mt5_connected,
        "telegram_connected": state.telegram_connected,
    }


@app.get("/stats", dependencies=[Depends(verify_api_key)])
async def get_stats():
    account = mt5_bridge.get_account_info()
    open_pos = mt5_bridge.get_open_positions()
    mt5_connected = state.mt5_connected
    # Calculate stats from actual MT5 trade history (not in-memory counters)
    trades = mt5_bridge.get_trade_history(limit=500)

    from datetime import datetime, timezone, date
    today = datetime.now(timezone.utc).date()

    total_wins = sum(1 for t in trades if t.get('status') == 'win')
    total_losses = sum(1 for t in trades if t.get('status') == 'loss')
    total_pnl = sum(float(t.get('pnl', 0)) for t in trades)
    total_trades = total_wins + total_losses

    # Today's stats — filter by today's date
    today_trades = [t for t in trades if t.get('opened', '').startswith(str(today))]
    today_wins = sum(1 for t in today_trades if t.get('status') == 'win')
    today_losses = sum(1 for t in today_trades if t.get('status') == 'loss')
    today_pnl = sum(float(t.get('pnl', 0)) for t in today_trades)
    today_total = today_wins + today_losses

    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0

    return {
        "bot": {
            "running": state.running,
            "telegram_connected": state.telegram_connected,
            "mt5_connected": mt5_connected,
        },
        "account": account,
        "trades": {
            "total": total_trades,
            "open": len(open_pos),
        },
        "performance": {
            "winning_trades": total_wins,
            "losing_trades": total_losses,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
        },
        "daily": {
            "wins": today_wins,
            "losses": today_losses,
            "trades_count": today_total,
            "net_pnl": round(today_pnl, 2),
        },
    }


@app.get("/open-trades", dependencies=[Depends(verify_api_key)])
async def get_open_trades():
    return mt5_bridge.get_open_positions()


@app.get("/trades", dependencies=[Depends(verify_api_key)])
async def get_trades():
    return mt5_bridge.get_trade_history(limit=100)


@app.get("/signals", dependencies=[Depends(verify_api_key)])
async def get_signals():
    return state.signal_log[:50]


@app.get("/channel-messages", dependencies=[Depends(verify_api_key)])
async def get_channel_messages():
    """Return raw messages received from all monitored channels."""
    return state.channel_messages[:100]


@app.get("/messages", dependencies=[Depends(verify_api_key)])
async def get_messages():
    """Return raw channel messages log."""
    return state.channel_messages[:100]


@app.get("/settings", dependencies=[Depends(verify_api_key)])
async def get_settings():
    # Use state.channels if populated, otherwise fall back to config
    channels = state.channels if state.channels else list(config.TG_CHANNELS)
    return {
        "channels": channels,
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
    # Ensure state.channels is populated from config first
    if not state.channels:
        state.channels = list(config.TG_CHANNELS)
    if ch not in state.channels:
        state.channels.append(ch)
        _persist_channels()
    return {"success": True, "channels": state.channels}


@app.delete("/channels", dependencies=[Depends(verify_api_key)])
async def remove_channel(body: ChannelRequest):
    ch = body.channel.strip()
    if not state.channels:
        state.channels = list(config.TG_CHANNELS)
    if ch in state.channels:
        state.channels.remove(ch)
        _persist_channels()
    return {"success": True, "channels": state.channels}


def _persist_channels() -> None:
    """Write current state.channels back to bot/.env TG_CHANNELS."""
    import re
    from pathlib import Path
    env_path = Path(__file__).parent / ".env"
    try:
        content = env_path.read_text(encoding="utf-8")
        new_value = ",".join(state.channels)
        content = re.sub(
            r"^TG_CHANNELS=.*$",
            f"TG_CHANNELS={new_value}",
            content,
            flags=re.MULTILINE,
        )
        env_path.write_text(content, encoding="utf-8")
        logger.info(f"Persisted channels to bot/.env: {new_value}")
    except Exception as e:
        logger.warning(f"Could not persist channels: {e}")


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


# ── Shortcut endpoints (called by Django trading/views.py) ────────────────────

@app.post("/start", dependencies=[Depends(verify_api_key)])
async def start_bot():
    """Shortcut: start the bot."""
    if state.running:
        return {"success": False, "message": "Bot already running", "status": "running"}
    state.running = True
    return {"success": True, "message": "Bot started", "status": "running"}


@app.post("/stop", dependencies=[Depends(verify_api_key)])
async def stop_bot():
    """Shortcut: stop the bot."""
    state.running = False
    return {"success": True, "message": "Bot stopped", "status": "stopped"}


@app.get("/strategy/{strategy_id}/stats", dependencies=[Depends(verify_api_key)])
async def strategy_stats(strategy_id: str):
    """Return per-strategy dashboard stats — fetches history from ALL assigned accounts."""
    from bot.accounts import get_all_accounts, _connect_account, _reconnect_primary
    from bot.strategies import get_strategy

    strat = get_strategy(strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

    assigned_accounts = [
        acc for acc in get_all_accounts()
        if strategy_id in (acc.strategy or [])
    ]

    comment_map = {
        "order_block": "ALGO:OB",
        "breakout": "ALGO:BRK",
        "confluence": "ALGO:CONF",
    }
    comment_prefix = comment_map.get(strategy_id, f"ALGO:{strategy_id[:3].upper()}")
    assigned_logins = {acc.login for acc in assigned_accounts}

    all_history = []
    all_positions = []

    try:
        import MetaTrader5 as _mt5
        MT5_AVAIL = True
    except ImportError:
        MT5_AVAIL = False

    if MT5_AVAIL and assigned_accounts:
        for acc in assigned_accounts:
            try:
                if _connect_account(acc):
                    acc_history = mt5_bridge.get_trade_history(limit=500)
                    for t in acc_history:
                        t["account_login"] = acc.login
                        t["account_label"] = acc.label
                    all_history.extend(acc_history)
                    acc_positions = mt5_bridge.get_open_positions()
                    for p in acc_positions:
                        p["account_login"] = acc.login
                        p["account_label"] = acc.label
                    all_positions.extend(acc_positions)
            except Exception as e:
                logger.warning(f"[STRATEGY] Could not fetch history for {acc.label}: {e}")
        _reconnect_primary()
    else:
        all_history = mt5_bridge.get_trade_history(limit=500)
        all_positions = mt5_bridge.get_open_positions()

    history = [t for t in all_history if comment_prefix in str(t.get("comment", ""))]
    if not history and assigned_logins:
        history = all_history

    open_trades = [
        p for p in all_positions
        if comment_prefix in str(p.get("comment", ""))
        or p.get("account_login") in assigned_logins
    ]

    seen = set()
    unique_history = []
    for t in history:
        key = t.get("ticket") or t.get("position_id")
        if key not in seen:
            seen.add(key)
            unique_history.append(t)
    history = unique_history

    wins = sum(1 for t in history if t.get("status") == "win")
    losses = sum(1 for t in history if t.get("status") == "loss")
    total_pnl = sum(float(t.get("pnl", 0)) for t in history)
    total = wins + losses

    return {
        "strategy": strat,
        "accounts": [acc.to_dict() for acc in assigned_accounts],
        "open_trades": open_trades,
        "recent_trades": history[:50],
        "stats": {
            "wins": wins,
            "losses": losses,
            "total": total,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "total_pnl": round(total_pnl, 2),
        },
    }






# ── Algo Trading Endpoints ────────────────────────────────────────────────────

class AlgoConfigUpdate(BaseModel):
    strategy_id: Optional[str] = None
    symbol: Optional[str] = None
    enabled: Optional[bool] = None
    risk_reward: Optional[float] = None
    risk_percent: Optional[float] = None
    analysis_tf: Optional[int] = None
    execution_tf: Optional[int] = None


# ── MT5 Accounts Endpoints ────────────────────────────────────────────────────

class AccountAddRequest(BaseModel):
    label: str
    login: int
    password: str
    server: str
    path: Optional[str] = ""
    strategy: Optional[str] = "order_block"


@app.get("/strategies", dependencies=[Depends(verify_api_key)])
async def list_strategies():
    """List all available strategies."""
    from bot.strategies import get_all_strategies
    return get_all_strategies()


@app.get("/accounts/debug")
async def debug_accounts():
    """Debug endpoint — shows raw .env read result and current account list."""
    import os
    from pathlib import Path

    env_path = Path(__file__).parent / ".env"
    raw_line = ""
    env_exists = env_path.exists()
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("MT5_EXTRA_ACCOUNTS="):
                raw_line = stripped
                break
    except Exception as exc:
        raw_line = f"ERROR: {exc}"

    from bot.accounts import get_all_accounts, _accounts
    return {
        "env_path": str(env_path),
        "env_exists": env_exists,
        "raw_line_found": raw_line,
        "MT5_EXTRA_ACCOUNTS_os_env": os.getenv("MT5_EXTRA_ACCOUNTS", "NOT SET"),
        "accounts_count": len(_accounts),
        "accounts": [a.to_dict() for a in _accounts],
    }


@app.get("/accounts", dependencies=[Depends(verify_api_key)])
async def list_accounts():
    """List all configured MT5 accounts."""
    from bot.accounts import get_all_accounts, _load_extra_accounts
    # Re-run extra account loader so any new .env entries appear without restart
    _load_extra_accounts()
    return [acc.to_dict() for acc in get_all_accounts()]


@app.post("/accounts", dependencies=[Depends(verify_api_key)])
async def add_account(body: AccountAddRequest):
    """Add a new MT5 account."""
    from bot.accounts import add_account as _add
    strategy = body.strategy or "order_block"
    acc = _add(
        label=body.label,
        login=body.login,
        password=body.password,
        server=body.server,
        path=body.path or "",
        strategy=strategy,
    )
    return {"success": True, "account": acc.to_dict()}


@app.delete("/accounts/{account_id}", dependencies=[Depends(verify_api_key)])
async def delete_account(account_id: str):
    """Remove an MT5 account."""
    from bot.accounts import remove_account as _remove
    success = _remove(account_id)
    return {"success": success, "message": "Removed" if success else "Cannot remove primary account"}


@app.post("/accounts/{account_id}/toggle", dependencies=[Depends(verify_api_key)])
async def toggle_account(account_id: str, body: dict = {}):
    """Enable or disable an MT5 account."""
    from bot.accounts import toggle_account as _toggle
    enabled = body.get("enabled", True)
    success = _toggle(account_id, enabled)
    return {"success": success}


@app.put("/accounts/{account_id}/strategy", dependencies=[Depends(verify_api_key)])
async def update_strategy(account_id: str, body: dict = {}):
    """Update strategy for an account."""
    from bot.accounts import update_account_strategy
    strategy = body.get("strategy", "order_block")
    success = update_account_strategy(account_id, strategy)
    return {"success": success}


@app.post("/accounts/refresh", dependencies=[Depends(verify_api_key)])
async def refresh_accounts():
    """Refresh balance/equity for all accounts."""
    from bot.accounts import refresh_account_info, get_all_accounts
    refresh_account_info()
    return [acc.to_dict() for acc in get_all_accounts()]


@app.get("/algo/runner-status", dependencies=[Depends(verify_api_key)])
async def algo_runner_status():
    """Return live status for all strategy threads managed by the parallel runner."""
    from bot.algo.runner import get_runner_status
    return get_runner_status()


@app.get("/algo/status", dependencies=[Depends(verify_api_key)])
async def algo_status():
    """Get current live algo strategy status."""
    from bot.algo.runner import get_runner_status

    status = get_algo_status()
    runner_status = get_runner_status()
    running_strategies = runner_status.get("running_strategies", [])
    status["running_strategies"] = running_strategies
    status["strategy_statuses"] = runner_status.get("statuses", {})
    status["active_strategy"] = get_active_strategy_id()
    status["running"] = bool(running_strategies)
    status["risk"] = get_risk_status()
    return status


@app.post("/algo/start", dependencies=[Depends(verify_api_key)])
async def algo_start(body: dict = {}):
    """Start one strategy or all account-assigned strategies."""
    strategy_id = body.get("strategy_id")
    if strategy_id:
        success = start_algo(strategy_id)
        return {"success": success, "message": "Algo started" if success else "Algo already running"}

    from bot.algo.runner import start_all_strategies

    started = start_all_strategies()
    return {
        "success": bool(started),
        "started": started,
        "message": f"Started strategies: {', '.join(started)}" if started else "No new strategies started",
    }


@app.post("/algo/stop", dependencies=[Depends(verify_api_key)])
async def algo_stop():
    """Stop all strategy threads managed by the parallel runner."""
    from bot.algo.runner import get_runner_status, stop_all_strategies

    before = get_runner_status().get("running_strategies", [])
    stop_all_strategies()
    return {
        "success": bool(before),
        "stopped": before,
        "message": f"Stopped strategies: {', '.join(before)}" if before else "Algo not running",
    }


@app.put("/algo/strategy", dependencies=[Depends(verify_api_key)])
async def algo_select_strategy(body: dict = {}):
    """Switch the active live algo strategy module."""
    strategy_id = body.get("strategy_id")
    if not strategy_id:
        raise HTTPException(status_code=400, detail="strategy_id is required")
    result = select_strategy(strategy_id)
    return {"success": True, **result}


@app.get("/algo/strategy", dependencies=[Depends(verify_api_key)])
async def algo_active_strategy():
    """Return the currently selected live algo strategy."""
    return {"active_strategy": get_active_strategy_id()}


@app.post("/algo/enable", dependencies=[Depends(verify_api_key)])
async def algo_enable():
    """Enable algo trading (will execute real trades)."""
    update_algo_config(enabled=True)
    return {"success": True, "message": "Algo trading enabled — will execute real trades"}


@app.post("/algo/disable", dependencies=[Depends(verify_api_key)])
async def algo_disable():
    """Disable algo trading (scan only, no trades)."""
    update_algo_config(enabled=False)
    return {"success": True, "message": "Algo trading disabled — scan only mode"}


@app.put("/algo/config", dependencies=[Depends(verify_api_key)])
async def algo_update_config(body: AlgoConfigUpdate):
    """Update algo strategy configuration at runtime."""
    status = update_algo_config(
        strategy_id=body.strategy_id,
        symbol=body.symbol,
        enabled=body.enabled,
        risk_reward=body.risk_reward,
        risk_percent=body.risk_percent,
        analysis_tf=body.analysis_tf,
        execution_tf=body.execution_tf,
    )
    return {"success": True, "config": status}


@app.get("/algo/trades", dependencies=[Depends(verify_api_key)])
async def algo_trades():
    """
    Return all trades executed by the algo strategy.
    Pulls from MT5 trade history filtered by ALGO comment.
    Also includes in-memory signal_log entries for current session.
    """
    # From MT5 history (persistent across restarts)
    mt5_trades = mt5_bridge.get_trade_history(limit=200)
    algo_mt5 = [t for t in mt5_trades if "ALGO:" in str(t.get("comment", ""))]

    # From in-memory signal log (current session) — merge detail fields
    algo_mem = {s.get("ticket"): s for s in state.signal_log if str(s.get("source", "")).startswith("ALGO:")}

    # Enrich MT5 trades with in-memory detail
    for t in algo_mt5:
        ticket = t.get("ticket")
        if ticket in algo_mem:
            mem = algo_mem[ticket]
            t["entry_reason"] = mem.get("entry_reason")
            t["initial_sl"] = mem.get("initial_sl")
            t["initial_tp"] = mem.get("initial_tp")
            t["sl_trail_log"] = mem.get("sl_trail_log", [])
            t["exit_reason"] = mem.get("exit_reason")
            t["risk_reward"] = mem.get("risk_reward")
            t["one_r"] = mem.get("one_r")

    # Add in-memory trades not yet in MT5 history
    mt5_tickets = {t.get("ticket") for t in algo_mt5}
    for ticket, s in algo_mem.items():
        if ticket not in mt5_tickets:
            algo_mt5.insert(0, s)

    # Stats
    total = len(algo_mt5)
    wins = len([t for t in algo_mt5 if float(t.get("pnl", 0)) > 0 or t.get("status") == "win"])
    losses = len([t for t in algo_mt5 if float(t.get("pnl", 0)) < 0 or t.get("status") == "loss"])
    total_pnl = sum(float(t.get("pnl", 0)) for t in algo_mt5)

    return {
        "trades": algo_mt5,
        "stats": {
            "total": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "total_pnl": round(total_pnl, 2),
        }
    }


@app.get("/algo/trade-detail/{ticket}", dependencies=[Depends(verify_api_key)])
async def algo_trade_detail(ticket: int):
    """Return full detail for a specific algo trade including entry reason, SL trail, exit reason."""
    from bot.trade_journal import get_trade, enrich_trade

    # 1. Check persistent journal first (survives restarts)
    journal_entry = get_trade(ticket)

    # 2. Check in-memory signal log
    mem_entry = None
    for entry in state.signal_log:
        if entry.get("ticket") == ticket:
            mem_entry = entry
            break

    # 3. Check MT5 history
    mt5_entry = None
    history = mt5_bridge.get_trade_history(limit=200)
    for t in history:
        if t.get("ticket") == ticket or t.get("position_id") == ticket:
            mt5_entry = t
            break

    # Merge: journal > memory > mt5
    if journal_entry:
        detail = dict(journal_entry)
        # Enrich with MT5 data if available
        if mt5_entry:
            detail["pnl"] = mt5_entry.get("pnl", detail.get("final_pnl"))
            detail["status"] = mt5_entry.get("status", "")
            detail["opened"] = mt5_entry.get("opened", detail.get("opened_at", ""))
            detail["volume"] = mt5_entry.get("volume", "")
        # Enrich with memory data
        if mem_entry:
            detail["sl_trail_log"] = mem_entry.get("sl_trail_log") or detail.get("sl_trail_log", [])
        return {"found": True, "detail": detail}

    if mem_entry:
        return {"found": True, "detail": mem_entry}

    if mt5_entry:
        # Determine entry reason from comment
        comment = mt5_entry.get("comment", "")
        if "ALGO:OB" in comment:
            entry_reason = "Order Block + FVG (Algo)"
        elif "ALGO:BRK" in comment:
            entry_reason = "Range Breakout Retest (Algo)"
        elif "ALGO:CONF" in comment:
            entry_reason = "OB + FVG + Breakout Confluence (Algo)"
        elif comment.startswith("TG:"):
            entry_reason = f"Telegram Signal — {comment.replace('TG:', '').strip()}"
        else:
            entry_reason = comment or "Telegram Signal / Manual"

        mt5_entry["entry_reason"] = entry_reason
        mt5_entry["sl_trail_log"] = []
        mt5_entry["initial_sl"] = mt5_entry.get("sl", "-")
        mt5_entry["initial_tp"] = mt5_entry.get("tp", "-")
        return {"found": True, "detail": mt5_entry}

    return {"found": False, "detail": {}}
