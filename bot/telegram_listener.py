"""
Telegram listener using Telethon.
Monitors configured channels and passes messages to the signal processor.

Session strategy:
  1. If TG_SESSION_STRING is set in .env → use StringSession (fully portable, no file)
  2. Otherwise → use file-based session (requires manual auth on first run)
"""
import asyncio
import os
from datetime import datetime
from loguru import logger
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from bot import config
from bot.state import state
from bot.signal_parser import parse_signal
from bot.trade_executor import execute_signal


_client: TelegramClient | None = None


async def _handle_message(event) -> None:
    """Called for every new message in monitored channels."""
    text = event.raw_text or ""
    if not text.strip():
        return

    chat = await event.get_chat()
    channel_name = getattr(chat, "username", None) or str(chat.id)
    logger.info(f"[TG] New message from @{channel_name}: {text[:80]}...")

    state.signals_processed += 1
    sig = parse_signal(text)

    log_entry = {
        "symbol": sig.symbol,
        "side": sig.side,
        "sl": sig.sl,
        "tp": sig.tp[0] if sig.tp else None,
        "status": "pending" if sig.valid else "rejected",
        "channel": f"@{channel_name}",
        "reason": sig.reason,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw": text[:200],
    }
    state.add_signal(log_entry)

    if not sig.valid:
        logger.warning(f"Signal rejected: {sig.reason}")
        return

    logger.info(f"Valid signal: {sig.symbol} {sig.side.upper()} SL={sig.sl} TP={sig.tp}")
    if not state.running:
        log_entry["status"] = "blocked"
        log_entry["reason"] = "Bot is stopped â€” signal execution paused"
        logger.info("Signal received while bot stopped; execution skipped.")
        return

    await execute_signal(sig, channel=f"@{channel_name}")


async def start_listener() -> None:
    global _client

    if not config.TG_API_ID or not config.TG_API_HASH:
        logger.error("Telegram API credentials not configured.")
        return

    # ── Session strategy ──────────────────────────────────────────────────────
    session_string = os.environ.get("TG_SESSION_STRING", "").strip()

    if session_string:
        # Use portable string session — no file, no IP issues, fully automated
        logger.info("Using Telegram StringSession (automated mode)")
        session = StringSession(session_string)
    else:
        # Fall back to file-based session
        os.makedirs(config.TG_SESSION_DIR, exist_ok=True)
        session = f"{config.TG_SESSION_DIR}/{config.TG_SESSION_NAME}"
        logger.info(f"Using file-based Telegram session: {session}")

    _client = TelegramClient(session, config.TG_API_ID, config.TG_API_HASH)

    await _client.start(phone=config.TG_PHONE)
    state.telegram_connected = True
    logger.success("Telegram connected.")

    # Resolve channel entities — merge config + state channels
    all_channels = list(config.TG_CHANNELS)
    for ch in state.channels:
        if ch not in all_channels:
            all_channels.append(ch)

    channel_entities = []
    for ch in all_channels:
        try:
            entity = await _client.get_entity(ch)
            channel_entities.append(entity)
            logger.info(f"Monitoring channel: {ch}")
        except Exception as e:
            logger.warning(f"Could not resolve channel {ch}: {e}")

    if not channel_entities:
        logger.warning("No channels resolved. Check TG_CHANNELS in .env")

    @_client.on(events.NewMessage(chats=channel_entities))
    async def handler(event):
        chat = await event.get_chat()
        channel_name = getattr(chat, "username", None) or str(chat.id)
        logger.debug(f"[TG] Raw event received from @{channel_name}")
        await _handle_message(event)

    logger.info("Telegram listener running...")
    await _client.run_until_disconnected()
    state.telegram_connected = False


async def stop_listener() -> None:
    global _client
    if _client and _client.is_connected():
        await _client.disconnect()
        state.telegram_connected = False
        logger.info("Telegram listener stopped.")


def get_client() -> TelegramClient | None:
    return _client
