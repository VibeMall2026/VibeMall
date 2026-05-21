"""
Shared in-memory state for the bot.
All modules read/write this single object.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional
import threading


@dataclass
class BotState:
    # Runtime flags
    running: bool = False
    mt5_connected: bool = False
    telegram_connected: bool = False

    # Channels being monitored
    channels: list[str] = field(default_factory=list)

    # Daily counters (reset at midnight)
    _today: date = field(default_factory=date.today)
    daily_wins: int = 0
    daily_losses: int = 0
    daily_trades: int = 0
    daily_net_pnl: float = 0.0
    signals_processed: int = 0
    consecutive_losses: int = 0

    # Signal log (last 100)
    signal_log: list[dict] = field(default_factory=list)

    # Raw channel messages log (last 200)
    channel_messages: list[dict] = field(default_factory=list)

    # Settings (mirrors config, can be updated at runtime)
    risk_percent: float = 0.1
    reward_ratio: float = 2.0
    max_trades_per_day: int = 10
    max_open_positions: int = 3
    max_daily_loss_percent: float = 3.0
    max_consecutive_losses: int = 3
    max_spread_points: int = 80
    duplicate_window_minutes: int = 0
    min_seconds_between_trades: int = 5
    allow_pending_orders: bool = True

    # Manual trading pause (blocks NEW trades only).
    # Stored as a date (UTC). Trading resumes automatically after that date passes.
    paused_until: Optional[date] = None

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reset_daily_if_needed(self) -> None:
        today = date.today()
        if today != self._today:
            self._today = today
            self.daily_wins = 0
            self.daily_losses = 0
            self.daily_trades = 0
            self.daily_net_pnl = 0.0
            self.consecutive_losses = 0

    def _utc_today(self) -> date:
        return datetime.now(timezone.utc).date()

    def is_trading_paused(self) -> tuple[bool, Optional[date]]:
        """
        Returns (paused, paused_until).
        Auto-clears pause after it expires.
        """
        with self._lock:
            if not self.paused_until:
                return False, None
            if self._utc_today() > self.paused_until:
                # Auto-resume after date passes.
                self.paused_until = None
                return False, None
            return True, self.paused_until

    def set_pause_until(self, until: Optional[date]) -> None:
        """Pause trading until end of given UTC date (inclusive). Set None to clear."""
        with self._lock:
            self.paused_until = until

    def add_signal(self, entry: dict) -> None:
        with self._lock:
            self.signal_log.insert(0, entry)
            if len(self.signal_log) > 100:
                self.signal_log = self.signal_log[:100]

    def record_trade(self, pnl: float) -> None:
        with self._lock:
            self.reset_daily_if_needed()
            self.daily_trades += 1
            self.daily_net_pnl += pnl
            if pnl > 0:
                self.daily_wins += 1
                self.consecutive_losses = 0
            elif pnl < 0:
                self.daily_losses += 1
                self.consecutive_losses += 1


# Singleton
state = BotState()

# Initialize channels from config
from bot import config as _config
state.channels = list(_config.TG_CHANNELS)
state.risk_percent = _config.RISK_PERCENT
state.reward_ratio = _config.FIXED_REWARD_RATIO
state.max_trades_per_day = _config.MAX_TRADES_PER_DAY
state.max_open_positions = _config.MAX_OPEN_POSITIONS
state.max_daily_loss_percent = _config.MAX_DAILY_LOSS_PERCENT
state.max_consecutive_losses = _config.MAX_CONSECUTIVE_LOSSES
state.max_spread_points = _config.MAX_SPREAD_POINTS
state.duplicate_window_minutes = _config.DUPLICATE_WINDOW_MINUTES
state.min_seconds_between_trades = _config.MIN_SECONDS_BETWEEN_TRADES
state.allow_pending_orders = _config.ALLOW_PENDING_ORDERS

# Initialize paused-until from config if provided.
if getattr(_config, "PAUSED_UNTIL", ""):
    try:
        state.paused_until = datetime.strptime(_config.PAUSED_UNTIL[:10], "%Y-%m-%d").date()
    except Exception:
        state.paused_until = None
