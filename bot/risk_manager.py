"""
Risk manager — checks all limits before allowing a trade.
"""
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

    # Consecutive loss limit
    if state.consecutive_losses >= state.max_consecutive_losses:
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
            loss_pct = abs(state.daily_net_pnl) / balance * 100
            if state.daily_net_pnl < 0 and loss_pct >= state.max_daily_loss_percent:
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
