"""
Outbound Telegram notifications for bot events.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from bot import config


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


async def _send_message(chat_id: str, text: str) -> None:
    from bot.telegram_listener import get_client

    client = get_client()
    if client and client.is_connected():
        await client.send_message(chat_id, text)
        return
    try:
        await _send_via_telethon_session(chat_id, text)
        return
    except Exception:
        await _send_via_bot_api(chat_id, text)


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
    chat_id = _get_alert_destination()
    if not chat_id:
        return False

    strategy = _extract_strategy_name(strategy_id, comment)
    side_text = str(side or "").upper()
    when_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        "✅ Algo Trade Executed\n"
        f"Symbol: {symbol}\n"
        f"Direction: {side_text}\n"
        f"Strategy: {strategy}\n"
        f"Account: {account_label} ({login})\n"
        f"Ticket: {ticket}\n"
        f"Lot: {lot}\n"
        f"Time: {when_utc}"
    )

    try:
        from bot.telegram_listener import get_client

        client = get_client()
        if client and client.is_connected():
            loop = getattr(client, "loop", None)
            if loop and loop.is_running():
                fut = asyncio.run_coroutine_threadsafe(_send_message(chat_id, text), loop)
                fut.result(timeout=12)
            else:
                asyncio.run(_send_message(chat_id, text))
        else:
            asyncio.run(_send_message(chat_id, text))
        logger.info(
            f"[TG_NOTIFY] Algo execution alert sent to {chat_id} | "
            f"{symbol} {side_text} | account={account_label} login={login}"
        )
        return True
    except Exception as exc:
        logger.warning(
            f"[TG_NOTIFY] Could not send algo execution alert to {chat_id}: {exc}"
        )
        return False
