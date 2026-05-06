"""
Risk manager — checks all limits before allowing a trade.
"""
from datetime import datetime, timezone

from loguru import logger
from bot.state import state
from bot import config
from bot import mt5_bridge


def can_trade(symbol: str) -> tuple[bool, str]:
    """
    Returns (allowed, reason).
    Checks daily limits, open positions, spread, etc.
    """
    state.reset_daily_if_needed()

    # Daily trade limit
    if state.daily_trades >= state.max_trades_per_day:
        return False, f"Daily trade limit reached ({state.max_trades_per_day})"

    recent_trades = mt5_bridge.get_trade_history(limit=200)

    # Consecutive loss limit
    consecutive_losses = 0
    for trade in recent_trades:
        status = trade.get("status")
        if status == "loss":
            consecutive_losses += 1
            continue
        if status in ("win", "breakeven"):
            break
    if consecutive_losses >= state.max_consecutive_losses:
        return False, f"Consecutive loss limit reached ({state.max_consecutive_losses})"

    # Open positions limit
    open_pos = mt5_bridge.get_open_positions()
    if len(open_pos) >= state.max_open_positions:
        return False, f"Max open positions reached ({state.max_open_positions})"

    # Daily loss limit
    account = mt5_bridge.get_account_info()
    if account:
        balance = account.get("balance", 0)
        if balance > 0:
            today = datetime.now(timezone.utc).date()
            today_pnl = 0.0
            for trade in recent_trades:
                opened = str(trade.get("opened", ""))
                if opened.startswith(str(today)):
                    today_pnl += float(trade.get("pnl", 0) or 0)
            loss_pct = abs(today_pnl) / balance * 100
            if today_pnl < 0 and loss_pct >= state.max_daily_loss_percent:
                return False, f"Daily loss limit reached ({loss_pct:.1f}% >= {state.max_daily_loss_percent}%)"

    # Spread check
    if mt5_bridge.MT5_AVAILABLE and mt5_bridge.is_connected():
        try:
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(symbol)
            sym_info = mt5.symbol_info(symbol)
            if tick and sym_info and sym_info.trade_tick_size > 0:
                spread_points = (tick.ask - tick.bid) / sym_info.trade_tick_size
                if spread_points > state.max_spread_points:
                    return False, f"Spread too high: {spread_points:.0f} > {state.max_spread_points}"
        except Exception as e:
            logger.warning(f"Spread check failed: {e}")

    return True, "OK"
