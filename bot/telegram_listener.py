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
from bot.telegram_notifier import send_text_alert


_client: TelegramClient | None = None
_COMMAND_ALIASES = {
    "status": "status",
    "botstatus": "status",
    "bstop": "bstop",
    "breakoutdemostop": "bstop",
    "bstart": "bstart",
    "breakoutdemostart": "bstart",
    "sstop": "sstop",
    "signalforgestop": "sstop",
    "signalforgegoldstop": "sstop",
    "sstart": "sstart",
    "signalforgestart": "sstart",
    "signalforgegoldstart": "sstart",
}
_CONTROL_COMMANDS = set(_COMMAND_ALIASES.values())


def _normalize_key(text: str) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def _canonical_command(text: str) -> str:
    return _COMMAND_ALIASES.get(_normalize_key(text), "")


def _build_status_text() -> str:
    from bot.accounts import get_all_accounts, get_account_trade_mode

    rows: list[str] = ["📊 Bot Account Status"]
    accounts = list(get_all_accounts() or [])
    if not accounts:
        rows.append("No accounts found")
        return "\n".join(rows)

    for acc in accounts:
        mode = get_account_trade_mode(int(acc.login))
        trading_state = "ON" if mode.get("allowed") else "OFF"
        mt5_state = "ONLINE" if getattr(acc, "connected", False) else "OFFLINE"
        reason = str(mode.get("stop_reason_text") or mode.get("reason") or "").strip()
        rows.append(
            f"\n{acc.label}\n"
            f"Login: {acc.login}\n"
            f"MT5: {mt5_state}\n"
            f"Trading: {trading_state}"
        )
        if reason and trading_state == "OFF":
            rows.append(f"Reason: {reason}")

    return "\n".join(rows)


def _find_stop_target(command_text: str):
    from bot.accounts import get_all_accounts

    command = _canonical_command(command_text)
    if command not in _CONTROL_COMMANDS:
        return None

    accounts = list(get_all_accounts() or [])
    if not accounts:
        return None

    if command in {"bstop", "bstart"}:
        for acc in accounts:
            label = str(getattr(acc, "label", "") or "").strip().lower()
            if label == "breakout demo":
                return acc
        for acc in accounts:
            label = str(getattr(acc, "label", "") or "").strip().lower()
            strategies = [str(s).strip().lower() for s in list(getattr(acc, "strategy", []) or [])]
            if "breakout" in strategies and "demo" in label:
                return acc
        return None

    if command in {"sstop", "sstart"}:
        for acc in accounts:
            label = str(getattr(acc, "label", "") or "").strip().lower()
            if label in {"signal forge gold", "signnal forge gold", "signalforge"}:
                return acc
        for acc in accounts:
            label = str(getattr(acc, "label", "") or "").strip().lower()
            strategies = [str(s).strip().lower() for s in list(getattr(acc, "strategy", []) or [])]
            if "signal_forge" in strategies and "signal" in label:
                return acc
        return None

    return None


async def _reply_control_status(event, text: str) -> None:
    try:
        await event.reply(text)
    except Exception as exc:
        logger.warning(f"[TG_CMD] Could not send inline reply: {exc}")


async def _handle_control_command(event, text: str, channel_name: str) -> bool:
    from bot.accounts import get_account_trade_mode, stop_account_for_today, start_account_now

    command = _canonical_command(text)
    if command == "status":
        await _reply_control_status(event, _build_status_text())
        return True

    if command not in _CONTROL_COMMANDS:
        return False

    acc = _find_stop_target(text)
    if acc is None:
        await _reply_control_status(
            event,
            f"❌ Command failed\n"
            f"Command: {command}\n"
            f"Reason: Target account not found",
        )
        return True

    action_text = ""
    if command in {"bstop", "sstop"}:
        reason_code = f"telegram_{command}_stop_today"
        stop_account_for_today(int(acc.login), reason_code=reason_code)
        action_text = "Stop trading for today"
        logger.warning(
            f"[TG_CMD] Stop-today command accepted from @{channel_name} | "
            f"command={command} | account={acc.label} ({acc.login})"
        )
    elif command in {"bstart", "sstart"}:
        start_account_now(int(acc.login))
        action_text = "Start trading now"
        logger.warning(
            f"[TG_CMD] Start-now command accepted from @{channel_name} | "
            f"command={command} | account={acc.label} ({acc.login})"
        )
    else:
        return False

    mode = get_account_trade_mode(int(acc.login))

    with state._lock:
        state.channel_messages.insert(0, {
            "channel": f"@{channel_name}",
            "text": f"[COMMAND] {command}",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        if len(state.channel_messages) > 200:
            state.channel_messages = state.channel_messages[:200]

    state.add_signal({
        "symbol": "",
        "side": "",
        "sl": None,
        "tp": None,
        "status": "command",
        "channel": f"@{channel_name}",
        "reason": f"{action_text} on {acc.label}",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw": text[:200],
    })

    halt_text = mode.get("stop_reason_text") or ("Trading ON" if mode.get("allowed") else "Manual stop")
    inline_status = (
        f"✅ Command success\n"
        f"Command: {command}\n"
        f"Account: {acc.label}\n"
        f"Action: {action_text}\n"
        f"State: {'Trading ON' if mode.get('allowed') else 'Trading OFF for today'}"
    )
    await _reply_control_status(event, inline_status)
    send_text_alert(
        f"Command accepted\n"
        f"Account: {acc.label}\n"
        f"Login: {acc.login}\n"
        f"Action: {action_text}\n"
        f"Current state: {'Trading ON' if mode.get('allowed') else 'Trading OFF for today'}\n"
        f"Auto resume: {'Not needed' if mode.get('allowed') else 'Next UTC day'}\n"
        f"Source: @{channel_name}\n"
        f"Reason: {halt_text}"
    )
    return True


async def _handle_message(event) -> None:
    """Called for every new message in monitored channels."""
    text = event.raw_text or ""
    if not text.strip():
        return

    chat = await event.get_chat()
    channel_name = getattr(chat, "username", None) or str(chat.id)
    logger.info(f"[TG] New message from @{channel_name}: {text[:80]}...")

    if await _handle_control_command(event, text, channel_name):
        return

    # Store raw message in channel_messages log
    with state._lock:
        state.channel_messages.insert(0, {
            "channel": f"@{channel_name}",
            "text": text[:500],
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        if len(state.channel_messages) > 200:
            state.channel_messages = state.channel_messages[:200]

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
