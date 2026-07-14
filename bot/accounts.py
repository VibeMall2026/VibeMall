"""
Multi-account MT5 manager.

Supports multiple MT5 accounts — each account gets its own MT5 connection.
Trades are executed on ALL enabled accounts simultaneously.

NOTE: MT5 Python library supports only ONE active connection per process.
      We use mt5.initialize() with different credentials to switch accounts.
      For true parallel execution, we execute sequentially (fast enough).
"""
from __future__ import annotations

import os
import json
import threading
import time
import subprocess
from datetime import datetime, timezone, timedelta, date as _date
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from loguru import logger

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

from bot import config as _config

_accounts_lock = threading.Lock()
_mt5_op_lock = threading.RLock()
_account_trade_halts: dict[int, str] = {}  # login -> YYYY-MM-DD (halt day)
_account_trade_halts_until: dict[int, str] = {}  # login -> ISO UTC datetime (halt until)
_account_trade_halt_reasons: dict[int, str] = {}  # login -> reason code
_account_trade_resume_overrides: dict[int, str] = {}  # login -> YYYY-MM-DD (manual resume override day)
_trade_mode_persist_lock = threading.Lock()
_active_login: int | None = None
_last_connect_attempt_ts: dict[int, float] = {}
_last_connect_fail_ts: dict[int, float] = {}
_last_connect_success_ts: dict[int, float] = {}
_last_connect_success_log_ts: dict[int, float] = {}
_last_terminal_launch_ts_by_path: dict[str, float] = {}
_next_reconnect_allowed_ts_by_login: dict[int, float] = {}
_reconnect_backoff_seconds_by_login: dict[int, float] = {}

# Connection-throttle tuning to reduce MT5 authorization flapping during rapid account switching.
CONNECT_MIN_RETRY_SECONDS = 3.0
CONNECT_RECENT_OK_SECONDS = 1.5
CONNECT_SUCCESS_LOG_INTERVAL_SECONDS = 60.0

# Persist per-account trade-mode so it survives bot restarts and avoids
# "Trading: ON again after refresh" when FastAPI process reloads / API URL changes.
_TRADE_MODE_STORE_PATH = Path(__file__).resolve().parent / "sessions" / "account_trade_modes.json"


def _load_trade_modes_from_disk(*, log_success: bool = True, log_errors: bool = True) -> None:
    """Best-effort load of persisted trade-mode state into memory."""
    global _account_trade_halts, _account_trade_halts_until, _account_trade_halt_reasons, _account_trade_resume_overrides
    try:
        if not _TRADE_MODE_STORE_PATH.exists():
            return
        raw = _TRADE_MODE_STORE_PATH.read_text(encoding="utf-8")
        if not raw.strip():
            return
        data = json.loads(raw)
        if not isinstance(data, dict):
            return
        halts = data.get("halts", {})
        halts_until = data.get("halts_until", {})
        halt_reasons = data.get("halt_reasons", {})
        resume_overrides = data.get("resume_overrides", {})
        if isinstance(halts, dict):
            _account_trade_halts = {int(k): str(v) for k, v in halts.items() if str(k).strip()}
        if isinstance(halts_until, dict):
            _account_trade_halts_until = {int(k): str(v) for k, v in halts_until.items() if str(k).strip()}
        if isinstance(halt_reasons, dict):
            _account_trade_halt_reasons = {
                int(k): str(v).strip()
                for k, v in halt_reasons.items()
                if str(k).strip() and str(v).strip()
            }
        if isinstance(resume_overrides, dict):
            _account_trade_resume_overrides = {
                int(k): str(v).strip()
                for k, v in resume_overrides.items()
                if str(k).strip() and str(v).strip()
            }
        if log_success:
            logger.info(
                f"[ACCOUNTS] Loaded trade-modes from disk: "
                f"halts={len(_account_trade_halts)} halts_until={len(_account_trade_halts_until)}"
            )
    except Exception as exc:
        if log_errors:
            logger.warning(f"[ACCOUNTS] Could not load trade-modes: {exc}")


def _persist_trade_modes_to_disk() -> None:
    """Best-effort persist of in-memory trade-mode state to disk."""
    try:
        _TRADE_MODE_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "halts": {str(k): v for k, v in (_account_trade_halts or {}).items()},
            "halts_until": {str(k): v for k, v in (_account_trade_halts_until or {}).items()},
            "halt_reasons": {str(k): v for k, v in (_account_trade_halt_reasons or {}).items()},
            "resume_overrides": {str(k): v for k, v in (_account_trade_resume_overrides or {}).items()},
        }
        _TRADE_MODE_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[ACCOUNTS] Could not persist trade-modes: {exc}")


def _utc_today() -> _date:
    return datetime.now(timezone.utc).date()


def _utc_today_iso() -> str:
    return _utc_today().isoformat()


def _launch_mt5_terminal(path: str) -> bool:
    """Best-effort launch of the MT5 terminal executable."""
    terminal_path = str(path or "").strip()
    if not terminal_path:
        return False
    if os.name != "nt":
        return False
    try:
        terminal_lower = terminal_path.lower()
        running = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-CimInstance Win32_Process | Where-Object {{$_.Name -ieq 'terminal64.exe' -and $_.CommandLine -and ($_.CommandLine -like '*{terminal_lower}*')}} | Select-Object -First 1 -ExpandProperty ProcessId",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if str(running.stdout or "").strip():
            logger.info(f"[ACCOUNTS] MT5 terminal already running: {terminal_path}")
            return False
    except Exception:
        pass
    now_ts = time.monotonic()
    last_launch_ts = _last_terminal_launch_ts_by_path.get(terminal_path, 0.0)
    if (now_ts - last_launch_ts) < 300.0:
        return False
    try:
        if not Path(terminal_path).exists():
            logger.warning(f"[ACCOUNTS] MT5 terminal path not found: {terminal_path}")
            return False
        subprocess.Popen(
            [terminal_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(Path(terminal_path).parent),
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        _last_terminal_launch_ts_by_path[terminal_path] = now_ts
        logger.info(f"[ACCOUNTS] Launched MT5 terminal: {terminal_path}")
        return True
    except Exception as exc:
        logger.warning(f"[ACCOUNTS] Could not launch MT5 terminal: {exc}")
        return False


def _mark_reconnect_failure(login: int) -> None:
    now_ts = time.monotonic()
    current = float(_reconnect_backoff_seconds_by_login.get(login, 5.0) or 5.0)
    _next_reconnect_allowed_ts_by_login[login] = now_ts + current
    _reconnect_backoff_seconds_by_login[login] = min(300.0, max(5.0, current * 2.0))


def _mark_reconnect_success(login: int) -> None:
    _next_reconnect_allowed_ts_by_login.pop(login, None)
    _reconnect_backoff_seconds_by_login.pop(login, None)


def _reconnect_backoff_active(login: int) -> bool:
    return time.monotonic() < float(_next_reconnect_allowed_ts_by_login.get(login, 0.0) or 0.0)


def _halt_reason_text(reason_code: str | None) -> str:
    code = str(reason_code or "").strip().lower()
    mapping = {
        "legacy_stop_today": "Old halt",
        "manual_stop_today": "Manual stop",
        "manual_stop_until": "Manual stop until time",
        "daily_profit_stop": "Daily profit hit",
        "daily_loss_stop": "Daily loss hit",
        "floating_profit_stop": "Floating profit hit",
        "floating_loss_stop": "Floating loss hit",
    }
    return mapping.get(code, "Trading stopped")

# The5ers funded-account policy (applies only to the specific breakout account)
THE5ERS_FUNDED_LOGIN = 26259636
THE5ERS_ACCOUNT_SIZE = 2500.0
THE5ERS_MAX_DAILY_LOSS_PCT = 5.0
THE5ERS_MAX_TOTAL_LOSS_PCT = 10.0
THE5ERS_EQUITY_FLOOR = 2250.0
THE5ERS_MAX_TRADES_PER_DAY = 15
THE5ERS_MIN_SECONDS_BETWEEN_BREAKOUT_ENTRIES = 65
THE5ERS_MAX_SIMULTANEOUS_BREAKOUT_TRADES = 2
THE5ERS_POLICY_ENFORCED = os.getenv("THE5ERS_POLICY_ENFORCED", "false").strip().lower() in {"1", "true", "yes", "on"}
try:
    DAILY_PROFIT_STOP_USD = float(os.getenv("DAILY_PROFIT_STOP_USD", "15"))
except Exception:
    DAILY_PROFIT_STOP_USD = 15.0


def get_mt5_lock() -> threading.RLock:
    """Global MT5 operation lock shared across modules."""
    return _mt5_op_lock


def _parse_utc_dt(value: str) -> Optional[datetime]:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except Exception:
                dt = None
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_news_blackout_reason(now_utc: Optional[datetime] = None) -> Optional[str]:
    """
    Returns a reason string when current UTC time is inside news blackout window,
    otherwise returns None.
    """
    if not bool(getattr(_config, "NEWS_FILTER_ENABLED", False)):
        return None
    raw = str(os.getenv("NEWS_EVENTS_UTC", getattr(_config, "NEWS_EVENTS_UTC_RAW", "")) or "").strip()
    if not raw:
        return None

    before_min = max(0, int(getattr(_config, "NEWS_BLOCK_BEFORE_MINUTES", 5) or 5))
    after_min = max(0, int(getattr(_config, "NEWS_BLOCK_AFTER_MINUTES", 5) or 5))
    now = now_utc or datetime.now(timezone.utc)

    for chunk in raw.split(","):
        event_dt = _parse_utc_dt(chunk)
        if not event_dt:
            continue
        window_start = event_dt - timedelta(minutes=before_min)
        window_end = event_dt + timedelta(minutes=after_min)
        if window_start <= now <= window_end:
            return (
                f"news_blackout(event_utc={event_dt.isoformat()},"
                f"window={window_start.isoformat()}..{window_end.isoformat()})"
            )
    return None


@dataclass
class MT5Account:
    id: str                    # unique id (e.g. "acc_1")
    label: str                 # display name (e.g. "Demo Account 1")
    login: int
    password: str
    server: str
    path: str = ""
    enabled: bool = True
    connected: bool = False
    balance: float = 0.0
    equity: float = 0.0
    currency: str = "USD"
    leverage: int = 100
    error: str = ""
    strategy: list = None   # list of strategy IDs assigned to this account
    allowed_symbols: Optional[list[str]] = None  # None = all symbols; otherwise whitelist

    def __post_init__(self):
        if self.strategy is None:
            self.strategy = ["signal_forge"]
        # Normalize allowed_symbols.
        if self.allowed_symbols is not None:
            try:
                cleaned: list[str] = []
                for s in list(self.allowed_symbols):
                    ss = str(s or "").strip()
                    if ss and ss not in cleaned:
                        cleaned.append(ss)
                self.allowed_symbols = cleaned or None
            except Exception:
                self.allowed_symbols = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "login": self.login,
            "server": self.server,
            "enabled": self.enabled,
            "connected": self.connected,
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "currency": self.currency,
            "leverage": self.leverage,
            "error": self.error,
            "strategy": self.strategy if isinstance(self.strategy, list) else [self.strategy],
            "allowed_symbols": self.allowed_symbols,
        }


# ── Account registry ──────────────────────────────────────────────────────────

_accounts: list[MT5Account] = []


def _normalize_single_strategy(strategy) -> list[str]:
    """Store exactly one strategy per account for predictable runner behavior."""
    if isinstance(strategy, list):
        strategy = strategy[0] if strategy else "signal_forge"
    return [str(strategy or "signal_forge").strip()]


def _normalize_strategies(strategy) -> list[str]:
    """Accept string or list[str] and return normalized list[str] (deduped)."""
    if strategy is None:
        return ["signal_forge"]
    raw = list(strategy) if isinstance(strategy, (list, tuple, set)) else [strategy]
    cleaned: list[str] = []
    for s in raw:
        sid = str(s or "").strip()
        if sid and sid not in cleaned:
            cleaned.append(sid)
    return cleaned or ["signal_forge"]


def _load_default_account() -> None:
    """Load the primary account from config on startup."""
    if _config.MT5_LOGIN > 0 and _config.MT5_PASSWORD and _config.MT5_SERVER:
        primary_label = str(os.getenv("MT5_ACCOUNT_LABEL", "") or "").strip() or "Primary Account"
        primary = MT5Account(
            id="acc_1",
            label=primary_label,
            login=_config.MT5_LOGIN,
            password=_config.MT5_PASSWORD,
            server=_config.MT5_SERVER,
            path=_config.MT5_PATH,
            enabled=True,
            strategy=_normalize_single_strategy(getattr(_config, "MT5_PRIMARY_STRATEGY", "signal_forge")),
            allowed_symbols=(
                [s.strip().upper() for s in getattr(_config, "MT5_PRIMARY_ALLOWED_SYMBOLS", []) if str(s).strip()]
                or None
            ),
        )
        _accounts.append(primary)


def _load_extra_accounts() -> None:
    """
    Load extra MT5 accounts from MT5_EXTRA_ACCOUNTS config.

    Reads directly from bot/.env file at call time so changes take effect
    without restarting the bot process.

    Format (semicolon-separated entries):
        Label|login|password|server|strategy|path|allowed_symbols

    allowed_symbols is optional and can be comma-separated, e.g.:
        XAUUSD
        XAUUSD,BTCUSD

    Example:
        Example Account|106903766|password|MetaQuotes-Demo|breakout|C:\MT5\terminal64.exe|XAUUSD
    """
    # In one-account-per-process mode, skip loading shared extra accounts from .env.
    # Each process should only run its own primary account credentials.
    if str(os.getenv("BOT_SINGLE_ACCOUNT_MODE", "")).strip().lower() in {"1", "true", "yes", "on"}:
        logger.info("[ACCOUNTS] BOT_SINGLE_ACCOUNT_MODE=on -> skipping MT5_EXTRA_ACCOUNTS load")
        return

    # Read directly from .env file so live changes are picked up without restart
    from pathlib import Path

    raw = ""
    env_path = Path(__file__).parent / ".env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("MT5_EXTRA_ACCOUNTS="):
                raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    except Exception as exc:
        logger.warning(f"[ACCOUNTS] Could not read .env for extra accounts: {exc}")

    # Fallback to config/env var if .env read failed
    if not raw:
        raw = (os.getenv("MT5_EXTRA_ACCOUNTS") or _config.MT5_EXTRA_ACCOUNTS or "").strip()

    if not raw:
        return

    entries = [e.strip() for e in raw.split(";") if e.strip()]
    for i, entry in enumerate(entries, start=2):
        parts = entry.split("|")
        if len(parts) < 4:
            logger.warning(f"[ACCOUNTS] Skipping malformed extra account entry: {entry!r}")
            continue

        label = parts[0].strip()
        try:
            login = int(parts[1].strip())
        except ValueError:
            logger.warning(f"[ACCOUNTS] Invalid login in extra account entry: {entry!r}")
            continue
        password = parts[2].strip()
        if password.startswith("${") and password.endswith("}"):
            password = os.getenv(password[2:-1].strip(), password)
        elif password.startswith("$"):
            password = os.getenv(password[1:].strip(), password)
        server = parts[3].strip()
        strategies = _normalize_single_strategy(
            [s.strip() for s in parts[4].split("+")] if len(parts) >= 5 else ["signal_forge"]
        )
        account_path = parts[5].strip() if len(parts) >= 6 else _config.MT5_PATH
        allowed_symbols = None
        if len(parts) >= 7 and str(parts[6]).strip():
            allowed_symbols = [
                s.strip().upper()
                for s in str(parts[6]).split(",")
                if s and s.strip()
            ] or None

        # Avoid duplicates — check by login number
        if any(a.login == login for a in _accounts):
            logger.debug(f"[ACCOUNTS] Extra account already loaded: {label} ({login})")
            continue

        # Find next available acc_id
        existing_ids = {a.id for a in _accounts}
        j = 2
        while f"acc_{j}" in existing_ids:
            j += 1
        acc_id = f"acc_{j}"

        acc = MT5Account(
            id=acc_id,
            label=label or f"Account {j}",
            login=login,
            password=password,
            server=server,
            path=account_path,
            enabled=True,
            strategy=strategies,
            allowed_symbols=allowed_symbols,
        )
        _accounts.append(acc)
        logger.info(
            f"[ACCOUNTS] Loaded extra account from config: {acc.label} "
            f"({acc.login}@{acc.server}) strategy={strategies}"
        )


_load_default_account()
_load_extra_accounts()
_load_trade_modes_from_disk()


def get_all_accounts() -> list[MT5Account]:
    with _accounts_lock:
        return list(_accounts)


def get_accounts_runtime_status() -> list[dict]:
    """
    Return lightweight runtime status for each account for heartbeat logging.
    """
    now_ts = time.monotonic()
    rows: list[dict] = []
    with _accounts_lock:
        snapshot = list(_accounts)
    for acc in snapshot:
        mode = get_account_trade_mode(acc.login)
        allowed = bool(mode.get("allowed"))
        halt_reason = str(
            mode.get("stop_reason_code")
            or mode.get("stop_reason_text")
            or mode.get("reason")
            or ""
        )
        last_ok = _last_connect_success_ts.get(int(acc.login), 0.0)
        last_fail = _last_connect_fail_ts.get(int(acc.login), 0.0)
        rows.append(
            {
                "label": acc.label,
                "login": int(acc.login),
                "enabled": bool(acc.enabled),
                "connected": bool(acc.connected),
                "error": str(acc.error or ""),
                "strategy": list(acc.strategy or []),
                "trade_allowed": bool(allowed),
                "halt_reason": str(halt_reason or ""),
                "last_ok_s": round(now_ts - last_ok, 1) if last_ok else None,
                "last_fail_s": round(now_ts - last_fail, 1) if last_fail else None,
            }
        )
    return rows


def sync_account_runtime(
    *,
    login: int | None,
    connected: bool,
    balance: float | None = None,
    equity: float | None = None,
    currency: str | None = None,
    error: str | None = None,
) -> None:
    """
    Update in-memory account runtime flags for heartbeat visibility.
    Safe no-op when login is not found.
    """
    key = int(login or 0)
    with _accounts_lock:
        for acc in _accounts:
            if key and int(acc.login) != key:
                continue
            acc.connected = bool(connected)
            if balance is not None:
                acc.balance = float(balance)
            if equity is not None:
                acc.equity = float(equity)
            if currency:
                acc.currency = str(currency)
            acc.error = str(error or "")
            if key:
                break


def stop_account_for_today(login: int, reason_code: str = "manual_stop_today") -> None:
    """Stop trade execution for this account for the current UTC day."""
    with _trade_mode_persist_lock:
        _load_trade_modes_from_disk(log_success=False, log_errors=False)
        _account_trade_halts[int(login)] = _utc_today_iso()
        _account_trade_halt_reasons[int(login)] = str(reason_code or "manual_stop_today").strip().lower()
        _account_trade_resume_overrides.pop(int(login), None)
        # Clear any stop-until when explicit stop-today is set.
        _account_trade_halts_until.pop(int(login), None)
        _persist_trade_modes_to_disk()
    # Prevent delayed fills from already-placed pending orders.
    _cancel_pending_orders_for_login(int(login))


def stop_account_until(login: int, until_utc: datetime, reason_code: str = "manual_stop_until") -> None:
    """
    Stop trade execution for this account until a specific UTC datetime.
    If until_utc is in the past, this clears the stop.
    """
    key = int(login)
    with _trade_mode_persist_lock:
        _load_trade_modes_from_disk(log_success=False, log_errors=False)
        now = datetime.now(timezone.utc)
        if until_utc <= now:
            _account_trade_halts_until.pop(key, None)
            _account_trade_halt_reasons.pop(key, None)
            _account_trade_resume_overrides.pop(key, None)
            _persist_trade_modes_to_disk()
            return
        # Use a stable ISO format so it can round-trip safely through APIs.
        _account_trade_halts_until[key] = until_utc.astimezone(timezone.utc).isoformat()
        _account_trade_halt_reasons[key] = str(reason_code or "manual_stop_until").strip().lower()
        _account_trade_resume_overrides.pop(key, None)
        # Clear stop-today so we only have one active halt source.
        _account_trade_halts.pop(key, None)
        _persist_trade_modes_to_disk()
    # Prevent delayed fills from already-placed pending orders.
    _cancel_pending_orders_for_login(int(login))


def start_account_now(login: int) -> None:
    """Manually resume trading for this account immediately."""
    with _trade_mode_persist_lock:
        _load_trade_modes_from_disk(log_success=False, log_errors=False)
        key = int(login)
        _account_trade_halts.pop(key, None)
        _account_trade_halts_until.pop(key, None)
        _account_trade_halt_reasons.pop(key, None)
        _account_trade_resume_overrides[key] = _utc_today_iso()
        _persist_trade_modes_to_disk()
    try:
        from bot.algo.order_block import clear_account_risk_halt
        clear_account_risk_halt(int(login))
    except Exception:
        pass


def is_manual_resume_override_active(login: int) -> bool:
    key = int(login)
    with _trade_mode_persist_lock:
        _load_trade_modes_from_disk(log_success=False, log_errors=False)
        override_day = _account_trade_resume_overrides.get(key)
        if not override_day:
            return False
        today = _utc_today_iso()
        if override_day == today:
            return True
        _account_trade_resume_overrides.pop(key, None)
        _persist_trade_modes_to_disk()
        return False


def is_account_trade_allowed_today(login: int) -> tuple[bool, str]:
    """
    Returns (allowed, reason).
    Auto-resets on next day.
    """
    # Stop/start changes can be written by a different API/process. Reload the
    # tiny shared file before every gate check so live strategy instances do not
    # keep stale in-memory trade modes.
    _load_trade_modes_from_disk(log_success=False, log_errors=False)

    key = int(login)

    if is_manual_resume_override_active(key):
        return True, "manual_resume_override"

    # Priority 1: stop-until (datetime-based).
    until_iso = _account_trade_halts_until.get(key)
    if until_iso:
        try:
            until_dt = datetime.fromisoformat(until_iso)
            if until_dt.tzinfo is None:
                until_dt = until_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now < until_dt.astimezone(timezone.utc):
                return False, f"stopped_until_{until_dt.astimezone(timezone.utc).isoformat()}"
            # Expired → auto-resume.
            with _trade_mode_persist_lock:
                _account_trade_halts_until.pop(key, None)
                _account_trade_halt_reasons.pop(key, None)
                _persist_trade_modes_to_disk()
        except Exception:
            # If stored value is corrupted, fail open and clear it.
            with _trade_mode_persist_lock:
                _account_trade_halts_until.pop(key, None)
                _account_trade_halt_reasons.pop(key, None)
                _persist_trade_modes_to_disk()

    # Priority 2: stop-today (date-based).
    halted_day = _account_trade_halts.get(key)
    if not halted_day:
        return True, "allowed"
    today = _utc_today_iso()
    if halted_day != today:
        # Auto-reset on next day.
        with _trade_mode_persist_lock:
            _account_trade_halts.pop(key, None)
            _account_trade_halt_reasons.pop(key, None)
            _persist_trade_modes_to_disk()
        return True, "auto_resumed_new_day"
    return False, "manually_stopped_for_today"


def get_account_trade_mode(login: int) -> dict:
    allowed, reason = is_account_trade_allowed_today(login)
    until_iso = _account_trade_halts_until.get(int(login))
    halted_day = _account_trade_halts.get(int(login))
    stop_reason_code = _account_trade_halt_reasons.get(int(login), "")
    if (halted_day or until_iso) and not stop_reason_code:
        stop_reason_code = "legacy_stop_today"
    return {
        "login": int(login),
        "allowed": allowed,
        "reason": reason,
        "halt_until": until_iso,
        "halt_day": halted_day,
        "stop_reason_code": stop_reason_code,
        "stop_reason_text": _halt_reason_text(stop_reason_code) if (halted_day or until_iso) else "",
        "manual_resume_override": is_manual_resume_override_active(int(login)),
    }


def get_account(account_id: str) -> Optional[MT5Account]:
    with _accounts_lock:
        for acc in _accounts:
            if acc.id == account_id:
                return acc
    return None


def get_accounts_for_strategy(strategy_id: str) -> list[MT5Account]:
    """
    Return enabled accounts that have the given strategy assigned.
    Strategy assignment is stored as a list of strategy IDs in acc.strategy.
    """
    sid = str(strategy_id or "").strip()
    if not sid:
        return []
    with _accounts_lock:
        return [
            acc for acc in _accounts
            if acc.enabled and sid in (acc.strategy or [])
        ]


def connect_account_by_login(login: int) -> bool:
    """
    Switch the active MT5 connection to the account with the given login.
    Returns True on successful connection.
    """
    try:
        target_login = int(login)
    except Exception:
        return False
    with _accounts_lock:
        acc = next((a for a in _accounts if int(a.login) == target_login), None)
    if not acc:
        return False
    return _connect_account(acc)


def reconnect_primary() -> None:
    """Public wrapper to restore primary account connection after account switching."""
    _reconnect_primary()


def add_account(
    label: str,
    login: int,
    password: str,
    server: str,
    path: str = "",
    strategy="signal_forge",
    allowed_symbols: Optional[list[str]] = None,
) -> MT5Account:
    """Add a new MT5 account."""
    with _accounts_lock:
        # Generate unique ID
        existing_ids = {acc.id for acc in _accounts}
        i = 1
        while f"acc_{i}" in existing_ids:
            i += 1
        acc_id = f"acc_{i}"

        acc = MT5Account(
            id=acc_id,
            label=label or f"Account {i}",
            login=login,
            password=password,
            server=server,
            path=path or _config.MT5_PATH,
            enabled=True,
            strategy=_normalize_strategies(strategy),
            allowed_symbols=allowed_symbols,
        )
        _accounts.append(acc)
        logger.info(f"[ACCOUNTS] Added account: {acc.label} ({acc.login}@{acc.server}) strategy={acc.strategy}")
        return acc


def remove_account(account_id: str) -> bool:
    """Remove an account."""
    with _accounts_lock:
        for i, acc in enumerate(_accounts):
            if acc.id == account_id:
                _accounts.pop(i)
                logger.info(f"[ACCOUNTS] Removed account: {account_id}")
                return True
    return False


def toggle_account(account_id: str, enabled: bool) -> bool:
    """Enable or disable an account."""
    acc = get_account(account_id)
    if acc:
        acc.enabled = enabled
        if not enabled:
            # When an account is disabled, treat it as offline in UI.
            acc.connected = False
            if not acc.error:
                acc.error = "Disabled"
        else:
            if acc.error == "Disabled":
                acc.error = ""
        logger.info(f"[ACCOUNTS] Account {account_id} {'enabled' if enabled else 'disabled'}")
        return True
    return False


def update_account_strategy(account_id: str, strategy) -> bool:
    """Update the single strategy assigned to an account."""
    from bot.strategies import get_strategy
    strategies = _normalize_single_strategy(strategy)
    if not get_strategy(strategies[0]):
        logger.warning(f"[ACCOUNTS] Unknown strategy: {strategies[0]}")
        return False
    acc = get_account(account_id)
    if acc:
        old = acc.strategy
        acc.strategy = strategies
        logger.info(f"[ACCOUNTS] Account {account_id} strategy updated: {old} -> {strategies}")
        return True
    return False


def update_account_strategies(account_id: str, strategies) -> bool:
    """Update MULTIPLE strategies assigned to an account."""
    from bot.strategies import get_strategy
    sids = _normalize_strategies(strategies)
    for sid in sids:
        if not get_strategy(sid):
            logger.warning(f"[ACCOUNTS] Unknown strategy: {sid}")
            return False
    acc = get_account(account_id)
    if acc:
        old = acc.strategy
        acc.strategy = sids
        logger.info(f"[ACCOUNTS] Account {account_id} strategies updated: {old} -> {sids}")
        return True
    return False


def update_account_allowed_symbols(account_id: str, allowed_symbols: Optional[list[str]]) -> bool:
    """Set allowed symbols (None = all)."""
    acc = get_account(account_id)
    if not acc:
        return False
    acc.allowed_symbols = allowed_symbols
    # Normalize via __post_init logic
    acc.__post_init__()
    logger.info(f"[ACCOUNTS] Account {account_id} allowed_symbols updated: {acc.allowed_symbols}")
    return True


# ── Connection management ─────────────────────────────────────────────────────

def _connect_account(acc: MT5Account) -> bool:
    """Connect to a specific MT5 account (switches active connection)."""
    global _active_login
    if not MT5_AVAILABLE:
        return False
    with _mt5_op_lock:
        now_ts = time.monotonic()
        target_login = int(acc.login)

        # If we recently failed this login, back off briefly to avoid rapid auth flapping.
        last_fail = _last_connect_fail_ts.get(target_login, 0.0)
        if last_fail and (now_ts - last_fail) < CONNECT_MIN_RETRY_SECONDS:
            wait_left = CONNECT_MIN_RETRY_SECONDS - (now_ts - last_fail)
            acc.connected = False
            acc.error = f"Backoff active ({wait_left:.1f}s) after recent auth/connect failure"
            return False

        if _reconnect_backoff_active(target_login):
            acc.connected = False
            acc.error = "Reconnect backoff active"
            return False

        # Fast path: if current MT5 session is already on this login and alive, skip re-init.
        try:
            info = mt5.account_info()
            current_login = int(getattr(info, "login", 0) or 0) if info else 0
            if current_login == target_login and mt5.terminal_info() is not None:
                acc.connected = True
                acc.error = ""
                if info:
                    acc.balance = getattr(info, "balance", acc.balance)
                    acc.equity = getattr(info, "equity", acc.equity)
                    acc.currency = getattr(info, "currency", acc.currency)
                    acc.leverage = getattr(info, "leverage", acc.leverage)
                _active_login = target_login
                _last_connect_success_ts[target_login] = now_ts
                _mark_reconnect_success(target_login)
                return True
        except Exception:
            pass

        connect_timeout_ms = _config.MT5_TIMEOUT_MS
        attempts = (1, 2)
        # Funded account can intermittently hang the MT5 IPC channel.
        # Keep this probe short so dashboard refresh doesn't block for minutes.
        if acc.login == THE5ERS_FUNDED_LOGIN:
            connect_timeout_ms = min(connect_timeout_ms, 8000)
            attempts = (1,)

        kwargs = {
            "login": acc.login,
            "password": acc.password,
            "server": acc.server,
            "timeout": connect_timeout_ms,
        }
        if acc.path:
            kwargs["path"] = acc.path
        if getattr(_config, "MT5_PORTABLE", False):
            kwargs["portable"] = True

        last_err = ""
        for attempt in attempts:
            _last_connect_attempt_ts[target_login] = time.monotonic()
            # Shutdown existing connection first
            mt5.shutdown()

            if mt5.initialize(**kwargs):
                info = mt5.account_info()
                if info:
                    acc.balance = info.balance
                    acc.equity = info.equity
                    acc.currency = info.currency
                    acc.leverage = info.leverage
                acc.connected = True
                acc.error = ""
                _active_login = target_login
                _last_connect_success_ts[target_login] = time.monotonic()
                _last_connect_fail_ts.pop(target_login, None)
                now_log_ts = time.monotonic()
                last_log_ts = _last_connect_success_log_ts.get(target_login, 0.0)
                if (now_log_ts - last_log_ts) >= CONNECT_SUCCESS_LOG_INTERVAL_SECONDS:
                    logger.success(
                        f"[ACCOUNTS] Connected: {acc.label} | Balance: {acc.balance} {acc.currency}"
                    )
                    _last_connect_success_log_ts[target_login] = now_log_ts
                return True

            last_err = str(mt5.last_error())
            _last_connect_fail_ts[target_login] = time.monotonic()
            _mark_reconnect_failure(target_login)
            if ("IPC send failed" in last_err or "IPC timeout" in last_err) and attempt == 1:
                launch_path = acc.path or _config.MT5_PATH
                if _launch_mt5_terminal(launch_path):
                    time.sleep(4)
                    continue
            if attempt == 1 and len(attempts) > 1:
                time.sleep(0.4)

        acc.connected = False
        acc.error = last_err
        logger.error(f"[ACCOUNTS] Failed to connect {acc.label}: {last_err}")
        return False


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
    """Cap lot by actual MT5 PnL estimate instead of only tick-value math."""
    from bot import config as cfg
    import math

    order_type = mt5.ORDER_TYPE_BUY if side.lower() == "buy" else mt5.ORDER_TYPE_SELL
    caps: list[float] = []

    # Symbol-specific risk cap (XAUUSD tends to need tighter safety defaults).
    max_risk_usd = float(getattr(cfg, "MAX_RISK_AMOUNT_USD", 0.0) or 0.0)
    try:
        sym_norm = str(symbol or "").upper().replace("/", "").replace(" ", "")
        if sym_norm.startswith("XAUUSD"):
            xau_cap = float(getattr(cfg, "XAUUSD_MAX_RISK_USD", 10.0) or 10.0)
            if xau_cap > 0:
                max_risk_usd = xau_cap if max_risk_usd <= 0 else min(max_risk_usd, xau_cap)
    except Exception:
        pass

    if max_risk_usd > 0 and sl > 0:
        loss_one_lot = mt5.order_calc_profit(order_type, symbol, 1.0, price, sl)
        loss_one_lot_abs = abs(float(loss_one_lot or 0.0))
        if loss_one_lot_abs > 0:
            caps.append(max_risk_usd / loss_one_lot_abs)

    if cfg.MAX_PROFIT_AMOUNT_USD > 0 and tp > 0:
        profit_one_lot = mt5.order_calc_profit(order_type, symbol, 1.0, price, tp)
        profit_one_lot_abs = abs(float(profit_one_lot or 0.0))
        if profit_one_lot_abs > 0:
            caps.append(cfg.MAX_PROFIT_AMOUNT_USD / profit_one_lot_abs)

    if caps:
        lot = min(lot, min(caps))

    if cfg.MAX_LOT_PER_TRADE > 0:
        lot = min(lot, cfg.MAX_LOT_PER_TRADE)

    # If caps would require a volume smaller than broker's minimum, return None
    # (caller may choose to override to min lot if within policy).
    if lot < sym_info.volume_min:
        return None

    lot = max(sym_info.volume_min, min(sym_info.volume_max, lot))
    step = sym_info.volume_step or sym_info.volume_min or 0.01

    # Avoid float edge cases: when lot is ~0.01 but represented as 0.009999999,
    # floor() can drop it to 0.00 and incorrectly fail.
    eps = step * 1e-6
    lot = round(math.floor((lot + eps) / step) * step, 8)
    lot = max(sym_info.volume_min, lot)

    if lot < sym_info.volume_min:
        return None
    return lot


def refresh_account_info() -> None:
    """Refresh balance/equity for all enabled accounts."""
    if not MT5_AVAILABLE:
        return

    with _accounts_lock:
        accounts_copy = list(_accounts)

    for acc in accounts_copy:
        if not acc.enabled:
            acc.connected = False
            continue
        try:
            if _connect_account(acc):
                info = mt5.account_info()
                if info:
                    acc.balance = info.balance
                    acc.equity = info.equity
                    acc.currency = info.currency
                    acc.connected = True
        except Exception as e:
            acc.error = str(e)
            acc.connected = False
            logger.error(f"[ACCOUNTS] Refresh error for {acc.label}: {e}")

    # Reconnect primary account at the end
    _reconnect_primary()


def probe_marketwatch_symbols(login: int, password: str, server: str, path: str = "") -> list[str]:
    """
    Temporarily connect to the given account and return visible MarketWatch symbols.
    Reconnects the primary account at the end.
    """
    if not MT5_AVAILABLE:
        return []
    temp = MT5Account(
        id="probe",
        label="Probe",
        login=int(login),
        password=str(password or ""),
        server=str(server or ""),
        path=str(path or ""),
        enabled=True,
        strategy=["signal_forge"],
    )
    symbols: list[str] = []
    with _mt5_op_lock:
        try:
            if _connect_account(temp):
                rows = mt5.symbols_get() or []
                for s in rows:
                    try:
                        if getattr(s, "visible", False):
                            name = str(getattr(s, "name", "") or "").strip()
                            if name:
                                symbols.append(name)
                    except Exception:
                        continue
        finally:
            _reconnect_primary()
    # Deduplicate + sort.
    out: list[str] = []
    for s in symbols:
        if s not in out:
            out.append(s)
    return sorted(out)


def _reconnect_primary() -> None:
    """Reconnect to primary account after multi-account operations, if configured."""
    primary = get_account("acc_1")
    if primary and primary.enabled:
        _connect_account(primary)
    else:
        ensure_any_account_connected()


def _cancel_pending_orders_for_login(login: int) -> int:
    """
    Best-effort cancel all pending orders for a specific account login.
    Returns number of successfully canceled orders.
    """
    if not MT5_AVAILABLE:
        return 0

    target = None
    with _accounts_lock:
        for acc in _accounts:
            if int(getattr(acc, "login", 0) or 0) == int(login) and acc.enabled:
                target = acc
                break
    if target is None:
        return 0

    canceled = 0
    with _mt5_op_lock:
        try:
            if not _connect_account(target):
                return 0
            pending_orders = mt5.orders_get() or []
            for order in pending_orders:
                try:
                    ticket = int(getattr(order, "ticket", 0) or 0)
                    if not ticket:
                        continue
                    req = {
                        "action": mt5.TRADE_ACTION_REMOVE,
                        "order": ticket,
                        "comment": "MANUAL_STOP_CANCEL_PENDING",
                    }
                    result = mt5.order_send(req)
                    if result and getattr(result, "retcode", None) == mt5.TRADE_RETCODE_DONE:
                        canceled += 1
                except Exception:
                    continue
        except Exception as exc:
            logger.warning(f"[ACCOUNTS] Pending cancel failed for login={login}: {exc}")
        finally:
            _reconnect_primary()

    if canceled:
        logger.warning(f"[ACCOUNTS] Canceled {canceled} pending order(s) for login={login} after manual stop")
    return canceled


def ensure_any_account_connected() -> bool:
    """
    Ensure at least one enabled MT5 account is connected for market-data scans.
    Falls back to the first enabled account if no active terminal connection exists.
    """
    if not MT5_AVAILABLE:
        return False

    try:
        if mt5.terminal_info() is not None:
            return True
    except Exception:
        pass

    with _accounts_lock:
        accounts_copy = [acc for acc in _accounts if acc.enabled]

    for acc in accounts_copy:
        try:
            if _connect_account(acc):
                logger.info(f"[ACCOUNTS] Auto-connected scan session using {acc.label}")
                return True
        except Exception as exc:
            logger.warning(f"[ACCOUNTS] Auto-connect failed for {acc.label}: {exc}")

    return False


# ── Multi-account trade execution ─────────────────────────────────────────────

def execute_on_all_accounts(
    symbol: str,
    side: str,
    sl: float,
    tp: float,
    entry=None,
    order_type: str = "market",
    risk_percent=None,
    comment: str = "TG Signal",
    strategy_id: str | None = None,
    exclude_strategy_id: str | None = None,
) -> list[dict]:
    """
    Execute trade on ALL enabled accounts.
    Returns list of results per account.
    """
    algo_trade = str(comment or "").upper().startswith("ALGO:")

    def notify_algo_failures(rows: list[dict]) -> None:
        if not algo_trade:
            return
        for row in rows or []:
            if row.get("success"):
                continue
            try:
                from bot.telegram_notifier import send_algo_error_alert

                send_algo_error_alert(
                    account_label=str(row.get("account_label") or row.get("account") or "N/A"),
                    login=row.get("login"),
                    strategy_id=str(strategy_id or "").strip() or None,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    reason=row.get("message") or "algo_execution_failed",
                    comment=comment,
                    severity="ERROR",
                )
            except Exception as notify_exc:
                logger.warning(f"[ACCOUNTS] Could not send algo error alert: {notify_exc}")

    if not MT5_AVAILABLE:
        results = [{"success": False, "message": "MT5 not available", "account": "N/A"}]
        notify_algo_failures(results)
        return results

    if algo_trade:
        from bot.state import state as _bot_state

        if not bool(getattr(_bot_state, "running", False)):
            results = [{
                "success": False,
                "message": "Algo execution blocked: bot is stopped",
                "account_id": None,
                "account_label": None,
                "login": None,
            }]
            notify_algo_failures(results)
            return results

        if strategy_id:
            try:
                from bot.algo.runner import get_runner_status

                running_strategies = set(get_runner_status().get("running_strategies", []) or [])
                if strategy_id not in running_strategies:
                    results = [{
                        "success": False,
                        "message": f"Algo execution blocked: strategy '{strategy_id}' is stopped",
                        "account_id": None,
                        "account_label": None,
                        "login": None,
                    }]
                    notify_algo_failures(results)
                    return results
            except Exception as runner_exc:
                logger.warning(f"[ACCOUNTS] Runner-status gate check failed open: {runner_exc}")

    news_reason = _get_news_blackout_reason()
    if news_reason:
        logger.warning(f"[ACCOUNTS] Trade skipped for all accounts: {news_reason}")
        results = [{
            "success": False,
            "message": f"Trade blocked: {news_reason}",
            "account_id": None,
            "account_label": None,
            "login": None,
        }]
        notify_algo_failures(results)
        return results

    from bot import config as cfg
    import math

    with _accounts_lock:
        accounts_copy = [
            acc for acc in _accounts
            if acc.enabled and (not strategy_id or strategy_id in (acc.strategy or []))
            and (not exclude_strategy_id or exclude_strategy_id not in (acc.strategy or []))
        ]

    # Strict strategy routing: when strategy_id is provided, do not fallback.
    if strategy_id and not accounts_copy:
        results = [{
            "success": False,
            "message": f"No enabled accounts mapped to strategy '{strategy_id}'",
            "account_id": None,
            "account_label": None,
            "login": None,
        }]
        notify_algo_failures(results)
        return results

    results = []

    for acc in accounts_copy:
        try:
            with _mt5_op_lock:
                if not _connect_account(acc):
                    results.append({
                        "success": False,
                        "message": f"Could not connect to {acc.label}",
                        "account_id": acc.id,
                        "account_label": acc.label,
                        "login": acc.login,
                    })
                    continue

                # Manual per-account stop-for-today gate.
                allowed_today, halt_reason = is_account_trade_allowed_today(acc.login)
                if not allowed_today:
                    results.append({
                        "success": False,
                        "message": f"Account paused for today ({halt_reason})",
                        "account_id": acc.id,
                        "account_label": acc.label,
                        "login": acc.login,
                    })
                    logger.warning(f"[ACCOUNTS] Trade skipped for {acc.label}: {halt_reason}")
                    continue

                # Per-account allowed symbols gate.
                if acc.allowed_symbols:
                    sym = str(symbol or "").strip()
                    if sym and sym not in acc.allowed_symbols:
                        results.append({
                            "success": False,
                            "message": f"Symbol not allowed for this account ({sym})",
                            "account_id": acc.id,
                            "account_label": acc.label,
                            "login": acc.login,
                        })
                        logger.warning(f"[ACCOUNTS] Trade skipped for {acc.label}: symbol_not_allowed {sym}")
                        continue

                effective_risk_percent = risk_percent
                if algo_trade:
                    try:
                        from bot.algo.human_mind import can_enter_trade, get_lot_multiplier

                        direction = "bullish" if str(side).lower() == "buy" else "bearish"
                        open_positions_raw = mt5.positions_get() or []
                        open_positions = [
                            {
                                "symbol": getattr(p, "symbol", ""),
                                "side": "buy" if getattr(p, "type", None) == mt5.ORDER_TYPE_BUY else "sell",
                                "comment": getattr(p, "comment", ""),
                                "pnl": float(getattr(p, "profit", 0.0) or 0.0),
                            }
                            for p in open_positions_raw
                        ]
                        allowed_algo, algo_reason = can_enter_trade(
                            symbol=symbol,
                            direction=direction,
                            candles=[],
                            open_positions=open_positions,
                            account_login=acc.login,
                        )
                        if not allowed_algo:
                            results.append({
                                "success": False,
                                "message": f"Algo quality gate block: {algo_reason}",
                                "account_id": acc.id,
                                "account_label": acc.label,
                                "login": acc.login,
                            })
                            logger.warning(f"[ACCOUNTS] Algo trade skipped for {acc.label}: {algo_reason}")
                            continue
                        base_risk = _config.RISK_PERCENT if risk_percent is None else float(risk_percent)
                        effective_risk_percent = max(0.01, base_risk * float(get_lot_multiplier(1.0)))
                    except Exception as algo_gate_exc:
                        logger.warning(f"[ACCOUNTS] Algo quality gate failed open for {acc.label}: {algo_gate_exc}")

                # Account-specific prop-firm compliance guard (only this one account).
                if THE5ERS_POLICY_ENFORCED and strategy_id == "breakout" and acc.login == THE5ERS_FUNDED_LOGIN:
                    allowed, reason = _check_the5ers_breakout_policy(acc)
                    if not allowed:
                        results.append({
                            "success": False,
                            "message": f"The5ers policy block: {reason}",
                            "account_id": acc.id,
                            "account_label": acc.label,
                            "login": acc.login,
                        })
                        logger.warning(f"[ACCOUNTS] The5ers policy blocked breakout trade: {reason}")
                        continue

                # Hard daily profit stop per account:
                # once realized PnL reaches the configured target, stop opening new trades for today.
                try:
                    from datetime import datetime, timezone
                    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                    end = datetime.now(timezone.utc)
                    deals = mt5.history_deals_get(start, end) or []
                    # IMPORTANT:
                    # MT5 history_deals_get returns not only trade deals, but also BALANCE/CREDIT
                    # operations (deposits/withdrawals) where `profit` can equal the deposited amount.
                    # That can falsely trigger the "daily profit stop" (e.g. profit shows $3000).
                    #
                    # So we count ONLY trade-related, realized deals:
                    # - position_id must be present (>0)  -> excludes balance operations
                    # - entry must NOT be DEAL_ENTRY_IN    -> only realized/closing legs
                    today_realized = 0.0
                    deal_entry_in = getattr(mt5, "DEAL_ENTRY_IN", None)
                    for d in deals:
                        try:
                            position_id = int(getattr(d, "position_id", 0) or 0)
                            if position_id <= 0:
                                continue
                            entry = getattr(d, "entry", None)
                            if deal_entry_in is not None and entry == deal_entry_in:
                                continue
                            today_realized += (
                                float(getattr(d, "profit", 0.0) or 0.0)
                                + float(getattr(d, "commission", 0.0) or 0.0)
                                + float(getattr(d, "swap", 0.0) or 0.0)
                            )
                        except Exception:
                            continue
                except Exception:
                    today_realized = 0.0

                if (not is_manual_resume_override_active(int(acc.login))) and today_realized >= DAILY_PROFIT_STOP_USD:
                    # Per-account day halt (does NOT impact other accounts).
                    stop_account_for_today(int(acc.login), reason_code="daily_profit_stop")
                    results.append({
                        "success": False,
                        "message": (
                            f"Daily profit stop reached (${today_realized:.2f} >= ${DAILY_PROFIT_STOP_USD:.2f}); "
                            "account paused for today"
                        ),
                        "account_id": acc.id,
                        "account_label": acc.label,
                        "login": acc.login,
                    })
                    logger.warning(
                        f"[ACCOUNTS] Daily profit stop block on {acc.label}: "
                        f"${today_realized:.2f} >= ${DAILY_PROFIT_STOP_USD:.2f}"
                    )
                    continue

                # Execute trade on this account
                result = _execute_single(
                    symbol=symbol,
                    side=side,
                    sl=sl,
                    tp=tp,
                    entry=entry,
                    order_type=order_type,
                    risk_percent=effective_risk_percent,
                    comment=comment,
                )
                result["account_id"] = acc.id
                result["account_label"] = acc.label
                result["login"] = acc.login
                results.append(result)

                strategy_label = strategy_id or "generic"
                if result.get("success"):
                    if algo_trade:
                        try:
                            from bot.algo.human_mind import record_trade_opened
                            record_trade_opened(account_login=acc.login)
                        except Exception as record_exc:
                            logger.warning(f"[ACCOUNTS] Could not record algo trade open: {record_exc}")
                        try:
                            from bot.telegram_notifier import send_algo_execution_alert

                            send_algo_execution_alert(
                                symbol=symbol,
                                side=side,
                                account_label=str(acc.label or ""),
                                login=acc.login,
                                ticket=result.get("ticket"),
                                lot=result.get("lot"),
                                strategy_id=str(strategy_id or "").strip() or None,
                                comment=comment,
                            )
                        except Exception as notify_exc:
                            logger.warning(f"[ACCOUNTS] Could not send algo execution alert: {notify_exc}")
                    logger.success(
                        f"[EXECUTION][UNIFIED] strategy={strategy_label} account={acc.label} "
                        f"login={acc.login} status=SUCCESS ticket={result.get('ticket')} "
                        f"symbol={symbol} side={side.upper()} order_type={order_type} "
                        f"lot={result.get('lot')} entry={float(entry or 0):.5f} "
                        f"sl={float(sl) if sl is not None else 'none'} "
                        f"tp={float(tp) if tp is not None else 'none'}"
                    )
                else:
                    logger.error(
                        f"[EXECUTION][UNIFIED] strategy={strategy_label} account={acc.label} "
                        f"login={acc.login} status=FAILED symbol={symbol} side={side.upper()} "
                        f"order_type={order_type} reason={result.get('message')}"
                    )

        except Exception as e:
            logger.error(f"[ACCOUNTS] Exception on {acc.label}: {e}")
            results.append({
                "success": False,
                "message": str(e),
                "account_id": acc.id,
                "account_label": acc.label,
                "login": acc.login,
            })

    # Always reconnect primary account after multi-account execution
    _reconnect_primary()

    notify_algo_failures(results)
    return results


def _check_the5ers_breakout_policy(acc: MT5Account) -> tuple[bool, str]:
    """Compliance/risk checks for The5ers funded breakout account only."""
    try:
        from bot import mt5_bridge as _bridge
        info = mt5.account_info()
        if not info:
            return False, "could not read account info"

        balance = float(getattr(info, "balance", 0.0) or 0.0)
        equity = float(getattr(info, "equity", 0.0) or 0.0)

        # Maximum total loss protection (equity floor).
        pct_floor = THE5ERS_ACCOUNT_SIZE * (1.0 - THE5ERS_MAX_TOTAL_LOSS_PCT / 100.0)
        hard_floor = max(THE5ERS_EQUITY_FLOOR, pct_floor)
        if equity <= hard_floor:
            return False, f"equity floor reached (equity={equity:.2f}, floor={hard_floor:.2f})"

        # Daily realized loss check.
        history = _bridge.get_trade_history(limit=2000)
        today = datetime.now(timezone.utc).date().isoformat()
        daily_realized = 0.0
        breakout_trades_today = 0
        last_breakout_open_ts = None
        for t in history:
            comment = str(t.get("comment", "") or "")
            opened = str(t.get("opened", "") or "")
            if len(opened) < 10 or opened[:10] != today:
                continue
            pnl = float(t.get("pnl", 0) or 0)
            daily_realized += pnl
            if "ALGO:BRK" in comment:
                breakout_trades_today += 1
                try:
                    dt = datetime.fromisoformat(opened.replace("Z", "+00:00").replace(" ", "T"))
                    if last_breakout_open_ts is None or dt > last_breakout_open_ts:
                        last_breakout_open_ts = dt
                except Exception:
                    pass

        max_daily_loss_usd = THE5ERS_ACCOUNT_SIZE * (THE5ERS_MAX_DAILY_LOSS_PCT / 100.0)
        if daily_realized <= -max_daily_loss_usd:
            return False, f"daily loss limit reached ({daily_realized:.2f} <= -{max_daily_loss_usd:.2f})"

        # Hard cap: max trades/day.
        if breakout_trades_today >= THE5ERS_MAX_TRADES_PER_DAY:
            return False, f"max trades/day reached ({breakout_trades_today}/{THE5ERS_MAX_TRADES_PER_DAY})"

        # Anti-HFT / no ultra-fast repetitive entries.
        if last_breakout_open_ts is not None:
            now_utc = datetime.now(timezone.utc)
            seconds_since_last = (now_utc - last_breakout_open_ts).total_seconds()
            if seconds_since_last < THE5ERS_MIN_SECONDS_BETWEEN_BREAKOUT_ENTRIES:
                return False, (
                    "entry frequency too high "
                    f"({seconds_since_last:.0f}s < {THE5ERS_MIN_SECONDS_BETWEEN_BREAKOUT_ENTRIES}s)"
                )

        # No bulk trading: cap simultaneous breakout positions on this account.
        open_positions = _bridge.get_open_positions()
        open_breakout_positions = [
            p for p in open_positions if "ALGO:BRK" in str(p.get("comment", "") or "")
        ]
        if len(open_breakout_positions) >= THE5ERS_MAX_SIMULTANEOUS_BREAKOUT_TRADES:
            return False, (
                "simultaneous breakout position cap reached "
                f"({len(open_breakout_positions)}/{THE5ERS_MAX_SIMULTANEOUS_BREAKOUT_TRADES})"
            )

        return True, "ok"
    except Exception as exc:
        return False, f"policy-check error: {exc}"


def _execute_single(
    symbol: str,
    side: str,
    sl: float,
    tp: float,
    entry=None,
    order_type: str = "market",
    risk_percent=None,
    comment: str = "TG Signal",
) -> dict:
    """Execute trade on currently connected MT5 account."""
    import math
    from bot import config as cfg

    def _normalize_sym(s: str) -> str:
        return "".join(ch for ch in str(s or "").upper() if ch.isalnum())

    def _is_xau_symbol(raw_symbol: str) -> bool:
        return str(raw_symbol or "").upper().startswith("XAUUSD")

    news_reason = _get_news_blackout_reason()
    if news_reason:
        return {"success": False, "message": f"Trade blocked: {news_reason}"}

    def _resolve_symbol_name(raw_symbol: str) -> str | None:
        # Exact match first
        info = mt5.symbol_info(raw_symbol)
        if info:
            return raw_symbol

        wanted = _normalize_sym(raw_symbol)
        if not wanted:
            return None

        # Broker suffix/prefix variants fallback (e.g., XAUUSD.a, XAUUSDm)
        all_symbols = mt5.symbols_get()
        if not all_symbols:
            return None

        candidates = []
        for s in all_symbols:
            name = getattr(s, "name", "")
            norm = _normalize_sym(name)
            if norm == wanted:
                candidates.append(name)
                continue
            if norm.startswith(wanted) or wanted in norm:
                candidates.append(name)

        if not candidates:
            return None

        # Prefer shortest/closest name to avoid odd synthetic variants.
        candidates = sorted(candidates, key=lambda x: (len(x), x))
        return candidates[0]

    def _today_realized_pnl_usd() -> float:
        """
        Calculate today's realized PnL for the CURRENT connected account.
        Uses MT5 deal history (profit + commission + swap).
        """
        try:
            from datetime import datetime, timezone
            start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            end = datetime.now(timezone.utc)
            deals = mt5.history_deals_get(start, end)
            if not deals:
                return 0.0
            # IMPORTANT:
            # history_deals_get includes BALANCE/CREDIT operations (deposits/withdrawals)
            # which can appear as "profit" and falsely trigger daily target/profit-stop logic.
            #
            # We count ONLY realized trade deals:
            # - position_id must exist (>0) -> excludes balance operations
            # - entry must NOT be DEAL_ENTRY_IN -> exclude opening legs; keep closes/outs
            total = 0.0
            deal_entry_in = getattr(mt5, "DEAL_ENTRY_IN", None)
            for d in deals:
                try:
                    position_id = int(getattr(d, "position_id", 0) or 0)
                    if position_id <= 0:
                        continue
                    entry = getattr(d, "entry", None)
                    if deal_entry_in is not None and entry == deal_entry_in:
                        continue
                    profit = float(getattr(d, "profit", 0.0) or 0.0)
                    commission = float(getattr(d, "commission", 0.0) or 0.0)
                    swap = float(getattr(d, "swap", 0.0) or 0.0)
                    total += (profit + commission + swap)
                except Exception:
                    continue
            return float(total or 0.0)
        except Exception:
            return 0.0

    def _risk_scale_for_today_pnl(today_pnl: float) -> float:
        """
        Per-account dynamic risk scaling:
        - >= $10 profit: reduce slightly
        - >= $20 profit: reduce more
        - >= $30 profit: reduce further
        """
        if today_pnl >= 30.0:
            return 0.50
        if today_pnl >= 20.0:
            return 0.65
        if today_pnl >= 10.0:
            return 0.80
        return 1.0

    resolved_symbol = _resolve_symbol_name(symbol)
    if not resolved_symbol:
        return {"success": False, "message": f"Symbol {symbol} not found"}
    if resolved_symbol != symbol:
        logger.info(f"[ACCOUNTS] Symbol mapped: {symbol} -> {resolved_symbol}")

    sym_info = mt5.symbol_info(resolved_symbol)
    if not sym_info:
        return {"success": False, "message": f"Symbol {resolved_symbol} not found"}

    if not sym_info.visible:
        mt5.symbol_select(resolved_symbol, True)

    tick = mt5.symbol_info_tick(resolved_symbol)
    if not tick:
        return {"success": False, "message": f"No tick data for {resolved_symbol}"}

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

    normalized = (order_type or "market").lower().replace(" ", "").replace("_", "")

    if normalized == "market":
        mt5_order_type = market_type_map.get(side.lower())
        action = mt5.TRADE_ACTION_DEAL
        price = tick.ask if side.lower() == "buy" else tick.bid
    else:
        mt5_order_type = pending_type_map.get(normalized)
        action = mt5.TRADE_ACTION_PENDING
        price = entry
        if price is None:
            return {"success": False, "message": "Pending order requires entry price"}

    if mt5_order_type is None:
        return {"success": False, "message": f"Unknown order type: {order_type}"}

    # Calculate lot size
    info = mt5.account_info()
    balance = info.balance if info else 0
    eff_risk = cfg.RISK_PERCENT if risk_percent is None else risk_percent
    today_realized = _today_realized_pnl_usd()
    risk_scale = _risk_scale_for_today_pnl(today_realized)
    eff_risk *= risk_scale
    if risk_scale < 1.0:
        logger.info(
            f"[ACCOUNTS] Dynamic risk reduce active | today_pnl={today_realized:.2f} | "
            f"scale={risk_scale:.2f} | eff_risk={eff_risk:.4f}%"
        )
    risk_amount = balance * (eff_risk / 100.0)
    # Daily drawdown-safe risk cap:
    # Keep per-trade risk low enough so even multiple SL hits should stay within
    # today's remaining daily loss budget.
    daily_loss_budget_usd = max(0.0, balance * (cfg.MAX_DAILY_LOSS_PERCENT / 100.0))
    loss_used_today_usd = max(0.0, -float(today_realized))
    remaining_daily_loss_budget_usd = max(0.0, daily_loss_budget_usd - loss_used_today_usd)
    if remaining_daily_loss_budget_usd <= 0:
        return {"success": False, "message": "Trade blocked: daily drawdown budget exhausted"}

    # Conservative split of remaining drawdown budget across potential SL events.
    # We use the tighter of max open positions and max trades/day as risk slots.
    risk_slots = max(1, min(int(cfg.MAX_OPEN_POSITIONS or 1), int(cfg.MAX_TRADES_PER_DAY or 1)))
    dd_safe_risk_cap = remaining_daily_loss_budget_usd / risk_slots
    if dd_safe_risk_cap > 0:
        risk_amount = min(risk_amount, dd_safe_risk_cap)
        logger.info(
            f"[ACCOUNTS] DD-safe cap applied | remaining_dd_budget=${remaining_daily_loss_budget_usd:.2f} | "
            f"slots={risk_slots} | per_trade_cap=${dd_safe_risk_cap:.2f}"
        )

    # Daily target rule:
    # After +$30 realized on this account, cap next-trade risk to max $15.
    if today_realized >= 30.0:
        risk_amount = min(risk_amount, 15.0)
        logger.info(
            f"[ACCOUNTS] Daily target reached on account (+${today_realized:.2f}); "
            f"risk amount capped to ${risk_amount:.2f} for next trades"
        )
    sl_points = abs(price - sl)

    tick_value = sym_info.trade_tick_value
    tick_size = sym_info.trade_tick_size
    if tick_size > 0 and sl_points > 0 and tick_value > 0:
        sl_ticks = sl_points / tick_size
        lot = risk_amount / (sl_ticks * tick_value)
        lot = max(sym_info.volume_min, min(sym_info.volume_max, lot))
        step = sym_info.volume_step
        # Avoid float edge cases near volume_min/step.
        eps = (step or sym_info.volume_min or 0.01) * 1e-6
        lot = round(math.floor((lot + eps) / step) * step, 8)
        lot = max(sym_info.volume_min, lot)
    else:
        lot = sym_info.volume_min

    lot = _cap_lot_by_pnl_limits(
        sym_info=sym_info,
        symbol=resolved_symbol,
        side=side,
        price=price,
        sl=sl,
        tp=tp,
        lot=lot,
    )
    if lot is None:
        return {"success": False, "message": "Trade blocked: broker minimum lot exceeds configured per-trade risk/lot caps"}

    try:
        _c = str(comment or "").upper()
        _is_ob_or_brk = ("ALGO:OB" in _c) or ("ALGO:BRK" in _c)
        if _is_ob_or_brk and (not _is_xau_symbol(resolved_symbol)):
            non_xau_cap = max(sym_info.volume_min, float(cfg.MAX_LOT_PER_TRADE) * 0.5)
            if lot > non_xau_cap:
                step = sym_info.volume_step or sym_info.volume_min or 0.01
                eps = step * 1e-6
                lot = round(math.floor((non_xau_cap + eps) / step) * step, 8)
                lot = max(sym_info.volume_min, lot)
                logger.info(
                    f"[ACCOUNTS][RISK] Non-XAU hard lot cap applied | symbol={resolved_symbol} "
                    f"lot={lot:.2f} cap={non_xau_cap:.2f} strategy_comment={comment}"
                )
        # MultiTF strategy: keep XAU lot conservative.
        _is_mtf = "ALGO:MTF" in _c
        if _is_mtf and _is_xau_symbol(resolved_symbol):
            mtf_xau_cap = max(sym_info.volume_min, 0.05)
            if lot > mtf_xau_cap:
                step = sym_info.volume_step or sym_info.volume_min or 0.01
                eps = step * 1e-6
                lot = round(math.floor((mtf_xau_cap + eps) / step) * step, 8)
                lot = max(sym_info.volume_min, lot)
                logger.info(
                    f"[ACCOUNTS][RISK] MultiTF XAU hard lot cap applied | symbol={resolved_symbol} "
                    f"lot={lot:.2f} cap={mtf_xau_cap:.2f} strategy_comment={comment}"
                )
    except Exception as _lot_cap_exc:
        logger.warning(f"[ACCOUNTS] Non-XAU hard cap guard failed: {_lot_cap_exc}")

    preferred_filling = getattr(sym_info, "filling_mode", mt5.ORDER_FILLING_IOC)
    fill_candidates = []
    for mode in (preferred_filling, mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK):
        if mode not in fill_candidates:
            fill_candidates.append(mode)

    request = {
        "action": action,
        "symbol": resolved_symbol,
        "volume": lot,
        "type": mt5_order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": cfg.MT5_DEVIATION,
        "magic": cfg.MT5_MAGIC_NUMBER,
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
            return {"success": True, "ticket": result.order, "lot": lot, "message": "Trade opened"}
        # 10030 = Unsupported filling mode; try next candidate
        if result and result.retcode == 10030:
            continue
        if result is None:
            continue
        return {"success": False, "message": f"retcode={result.retcode} {result.comment}"}

    if last_result is None:
        return {"success": False, "message": f"order_send None: {mt5.last_error()}"}
    return {"success": False, "message": f"retcode={last_result.retcode} {last_result.comment}"}
