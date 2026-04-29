"""
Central configuration — reads from environment / .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from bot/ directory
load_dotenv(Path(__file__).parent / ".env")


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)).strip())
    except (TypeError, ValueError):
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)).strip())
    except (TypeError, ValueError):
        return default


def _list(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default).strip()
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else []


# ── Telegram ──────────────────────────────────────────────────────────────────
TG_API_ID: int = _int("TG_API_ID", 0)
TG_API_HASH: str = os.getenv("TG_API_HASH", "")
TG_PHONE: str = os.getenv("TG_PHONE", "")
TG_SESSION_NAME: str = os.getenv("TG_SESSION_NAME", "telegram_to_mt5")
TG_SESSION_DIR: str = os.getenv("TG_SESSION_DIR", "sessions")
TG_CHANNELS: list[str] = _list("TG_CHANNELS")
TG_RECONNECT_DELAY: int = _int("TG_RECONNECT_DELAY_SECONDS", 10)

# ── MT5 ───────────────────────────────────────────────────────────────────────
MT5_LOGIN: int = _int("MT5_LOGIN", 0)
MT5_PASSWORD: str = os.getenv("MT5_PASSWORD", "")
MT5_SERVER: str = os.getenv("MT5_SERVER", "MetaQuotes-Demo")
MT5_PATH: str = os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
MT5_TIMEOUT_MS: int = _int("MT5_TIMEOUT_MS", 60000)
MT5_DEVIATION: int = _int("MT5_DEVIATION", 20)
MT5_MAGIC_NUMBER: int = _int("MT5_MAGIC_NUMBER", 550001)

# ── Admin notifications ────────────────────────────────────────────────────────
ADMIN_CHAT_ID: str = os.getenv("ADMIN_CHAT_ID", "")
ADMIN_BOT_TOKEN: str = os.getenv("ADMIN_BOT_TOKEN", "")

# ── API server ────────────────────────────────────────────────────────────────
API_KEY: str = os.getenv("API_KEY", "Paladiya@2023")
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = _int("API_PORT", 8000)
API_ALLOWED_IPS: list[str] = _list("API_ALLOWED_IPS", "127.0.0.1,::1")
API_CORS_ORIGINS: list[str] = _list(
    "API_CORS_ORIGINS",
    "http://127.0.0.1:5173,http://localhost:5173,http://localhost:8000",
)

# ── Bot behaviour ─────────────────────────────────────────────────────────────
AUTO_START: bool = _bool("AUTO_START", False)
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Risk management ───────────────────────────────────────────────────────────
RISK_PERCENT: float = _float("RISK_PERCENT", 0.1)
FIXED_REWARD_RATIO: float = _float("FIXED_REWARD_RATIO", 2.0)
MAX_TRADES_PER_DAY: int = _int("MAX_TRADES_PER_DAY", 10)
MAX_OPEN_POSITIONS: int = _int("MAX_OPEN_POSITIONS", 3)
MAX_DAILY_LOSS_PERCENT: float = _float("MAX_DAILY_LOSS_PERCENT", 3.0)
MAX_CONSECUTIVE_LOSSES: int = _int("MAX_CONSECUTIVE_LOSSES", 3)

# ── Trade management ──────────────────────────────────────────────────────────
BREAKEVEN_TRIGGER_R: float = _float("BREAKEVEN_TRIGGER_R", 1.0)
PARTIAL_CLOSE_TRIGGER_R: float = _float("PARTIAL_CLOSE_TRIGGER_R", 1.5)
PARTIAL_CLOSE_FRACTION: float = _float("PARTIAL_CLOSE_FRACTION", 0.5)
TRAILING_STOP_ENABLED: bool = _bool("TRAILING_STOP_ENABLED", False)
TRAILING_STOP_DISTANCE_R: float = _float("TRAILING_STOP_DISTANCE_R", 1.0)
CLOSE_OPPOSITE_DUPLICATES: bool = _bool("CLOSE_OPPOSITE_DUPLICATES", False)

# ── Signal validation ─────────────────────────────────────────────────────────
MAX_SPREAD_POINTS: int = _int("MAX_SPREAD_POINTS", 80)
DUPLICATE_WINDOW_MINUTES: int = _int("DUPLICATE_WINDOW_MINUTES", 0)
MIN_SECONDS_BETWEEN_TRADES: int = _int("MIN_SECONDS_BETWEEN_TRADES", 5)
ALLOW_PENDING_ORDERS: bool = _bool("ALLOW_PENDING_ORDERS", True)
