"""
Outbound Telegram notifications for bot events.
"""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from bot import config

_error_alert_lock = threading.Lock()
_last_error_alert_ts: dict[str, float] = {}
_error_alert_counts: dict[str, int] = {}


def _shorten(value: object, limit: int = 700) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _get_alert_destination() -> str:
    if getattr(config, "TG_EXECUTION_ALERT_CHAT", "").strip():
        return config.TG_EXECUTION_ALERT_CHAT.strip()
    if getattr(config, "ADMIN_CHAT_ID", "").strip():
        return config.ADMIN_CHAT_ID.strip()
    channels = list(getattr(config, "TG_CHANNELS", []) or [])
    return str(channels[0]).strip() if channels else ""


def _extract_strategy_name(strategy_id: str | None, comment: str | None) -> str:
    if str(strategy_id or "").strip():
        return str(strategy_id).strip()
    raw = str(comment or "").strip()
    if raw.upper().startswith("ALGO:"):
        parts = raw.split(":")
        if len(parts) >= 2 and parts[1].strip():
            return parts[1].strip().lower()
    return "algo"


def _is_signal_forge_notice(
    strategy_id: str | None,
    comment: str | None,
    account_label: str | None = None,
) -> bool:
    sid = str(strategy_id or "").strip().lower()
    if sid in {"signal_forge", "sfg"}:
        label = str(account_label or "").strip().lower()
        return any(
            marker in label
            for marker in (
                "signal forge gold",
                "signalforgegold",
                "the5ers funded",
                "signal forge gold 5%",
                "signal forge gold demo",
            )
        )
    raw = str(comment or "").strip().upper()
    return raw.startswith("ALGO:SFG") or "SIGNAL_FORGE" in raw


async def _send_via_bot_api(chat_id: str, text: str) -> None:
    import httpx

    if not config.ADMIN_BOT_TOKEN or not chat_id:
        raise RuntimeError("bot_api_not_configured")
    url = f"https://api.telegram.org/bot{config.ADMIN_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={"chat_id": chat_id, "text": text})
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"telegram_bot_api_error: {data}")


async def _send_via_telethon_session(chat_id: str, text: str) -> None:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    session_string = (config.TG_SESSION_STRING or "").strip()
    if session_string:
        session = StringSession(session_string)
    else:
        session_path = Path(config.TG_SESSION_DIR) / config.TG_SESSION_NAME
        if not session_path.exists():
            raise RuntimeError("telethon_session_not_configured")
        session = str(session_path)

    client = TelegramClient(session, config.TG_API_ID, config.TG_API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("telethon_session_not_authorized")
    try:
        await client.send_message(chat_id, text)
    finally:
        await client.disconnect()


async def _send_via_live_client(chat_id: str, text: str) -> None:
    from bot.telegram_listener import get_client

    client = get_client()
    if client is None:
        raise RuntimeError("live_client_not_available")

    loop = getattr(client, "loop", None)
    if loop is None or not loop.is_running():
        raise RuntimeError("live_client_loop_not_running")

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is loop:
        await client.send_message(chat_id, text)
        return

    fut = asyncio.run_coroutine_threadsafe(client.send_message(chat_id, text), loop)
    await asyncio.wrap_future(fut)


async def _send_message(chat_id: str, text: str) -> str:
    errors: list[str] = []

    try:
        await _send_via_bot_api(chat_id, text)
        return "bot_api"
    except Exception as exc:
        errors.append(f"bot_api={exc}")

    try:
        await _send_via_live_client(chat_id, text)
        return "live_client"
    except Exception as exc:
        errors.append(f"live_client={exc}")

    try:
        await _send_via_telethon_session(chat_id, text)
        return "telethon_session"
    except Exception as exc:
        errors.append(f"telethon_session={exc}")

    raise RuntimeError(" | ".join(errors))


def send_algo_execution_alert(
    *,
    symbol: str,
    side: str,
    account_label: str,
    login: int | str | None,
    ticket: int | str | None,
    lot: float | str | None,
    strategy_id: str | None = None,
    comment: str | None = None,
) -> bool:
    if not _is_signal_forge_notice(strategy_id, comment, account_label=account_label):
        return False
    chat_id = _get_alert_destination()
    if not chat_id:
        return False

    strategy = _extract_strategy_name(strategy_id, comment)
    side_text = str(side or "").upper()
    when_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        f"Account: {account_label}\n"
        f"Symbol: {symbol}\n"
        f"Direction: {side_text}\n"
        f"Lot Size: {lot}\n"
        "\n"
        f"Strategy: {strategy}\n"
        f"Login: {login}\n"
        f"Ticket: {ticket}\n"
        f"Time: {when_utc}"
    )

    try:
        method = asyncio.run(_send_message(chat_id, text))
        logger.info(
            f"[TG_NOTIFY] Algo execution alert sent to {chat_id} | "
            f"{symbol} {side_text} | account={account_label} login={login} | "
            f"via={method} | thread={threading.current_thread().name}"
        )
        return True
    except Exception as exc:
        logger.warning(
            f"[TG_NOTIFY] Could not send algo execution alert to {chat_id}: {exc}"
        )
        return False


def send_algo_error_alert(
    *,
    account_label: str | None = None,
    login: int | str | None = None,
    strategy_id: str | None = None,
    symbol: str | None = None,
    side: str | None = None,
    order_type: str | None = None,
    reason: str | None = None,
    comment: str | None = None,
    severity: str = "ERROR",
) -> bool:
    if not getattr(config, "TG_ALGO_ERROR_ALERTS_ENABLED", True):
        return False
    if not _is_signal_forge_notice(strategy_id, comment, account_label=account_label):
        return False

    chat_id = _get_alert_destination()
    if not chat_id:
        return False

    strategy = _extract_strategy_name(strategy_id, comment)
    reason_text = _shorten(reason or "unknown_error")
    dedupe_seconds = max(0, int(getattr(config, "TG_ALGO_ERROR_DEDUPE_SECONDS", 60) or 0))
    dedupe_key = "|".join(
        [
            str(account_label or ""),
            str(login or ""),
            str(strategy or ""),
            str(symbol or ""),
            str(side or ""),
            reason_text[:180],
        ]
    )

    now = time.monotonic()
    with _error_alert_lock:
        sent_count = _error_alert_counts.get(dedupe_key, 0)
        if sent_count >= 5:
            return False
        if dedupe_seconds > 0:
            last = _last_error_alert_ts.get(dedupe_key, 0.0)
            if now - last < dedupe_seconds:
                return False
            _last_error_alert_ts[dedupe_key] = now
        _error_alert_counts[dedupe_key] = sent_count + 1

    when_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        f"⚠️ ALGO {str(severity or 'ERROR').upper()}\n"
        f"Account: {account_label or 'N/A'}\n"
        f"Login: {login or 'N/A'}\n"
        f"Strategy: {strategy}\n"
        f"Symbol: {symbol or 'N/A'}\n"
        f"Direction: {str(side or 'N/A').upper()}\n"
        f"Order Type: {order_type or 'N/A'}\n"
        f"Reason: {reason_text}\n"
        f"Time: {when_utc}"
    )

    try:
        method = asyncio.run(_send_message(chat_id, text))
        logger.info(
            f"[TG_NOTIFY] Algo error alert sent to {chat_id} | "
            f"account={account_label} login={login} strategy={strategy} via={method}"
        )
        return True
    except Exception as exc:
        logger.warning(f"[TG_NOTIFY] Could not send algo error alert to {chat_id}: {exc}")
        return False


def send_text_alert(text: str, chat_id: str | None = None) -> bool:
    destination = str(chat_id or _get_alert_destination() or "").strip()
    if not destination or not str(text or "").strip():
        return False
    try:
        method = asyncio.run(_send_message(destination, str(text)))
        logger.info(
            f"[TG_NOTIFY] Text alert sent to {destination} via={method} | "
            f"thread={threading.current_thread().name}"
        )
        return True
    except Exception as exc:
        logger.warning(f"[TG_NOTIFY] Could not send text alert to {destination}: {exc}")
        return False
