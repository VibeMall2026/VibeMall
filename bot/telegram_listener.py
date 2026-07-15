"""
Telegram listener using Telethon.
Monitors configured channels and passes messages to the signal processor.

Session strategy:
  1. If TG_SESSION_STRING is set in .env → use StringSession (fully portable, no file)
  2. Otherwise → use file-based session (requires manual auth on first run)
"""
import asyncio
import os
import shlex
from datetime import datetime, timedelta, timezone, date
from types import SimpleNamespace
from zoneinfo import ZoneInfo
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
    "start": "start",
    "stop": "stop",
    "help": "help",
    "status": "status",
    "botstatus": "status",
    "botstart": "start",
    "botstop": "stop",
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
    token = str(text or "").strip().split()[0] if str(text or "").strip() else ""
    if "@" in token:
        token = token.split("@", 1)[0]
    return _COMMAND_ALIASES.get(_normalize_key(token), "")


def _build_help_text() -> str:
    return (
        "Trading bot control commands\n\n"
        "/start - Start the bot and strategies\n"
        "/stop - Stop the bot and strategies\n"
        "/status - Show account trading status\n"
        "/signal_forge_stop [time] - Stop Signal Forge Gold until next XAUUSD reopen or a custom time\n"
        "/signal_forge_start - Start Signal Forge Gold now\n"
        "Time examples: /signal_forge_stop 2026-07-12 18:00\n"
        "               /signal_forge_stop 18:00"
    )


def _next_xauusd_reopen_utc(now_utc: datetime | None = None) -> datetime:
    now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    today_2200 = now.replace(hour=22, minute=0, second=0, microsecond=0)
    weekday = now.weekday()  # Monday=0 ... Sunday=6

    if weekday <= 3:
        return today_2200 if now < today_2200 else today_2200 + timedelta(days=1)
    if weekday == 4:
        return today_2200 + timedelta(days=2)
    if weekday == 5:
        return today_2200 + timedelta(days=1)
    return today_2200 if now < today_2200 else today_2200 + timedelta(days=1)


def _parse_trade_date(raw_value) -> date | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except Exception:
        pass
    try:
        iso = text.replace("Z", "+00:00").replace(" ", "T")
        return datetime.fromisoformat(iso).date()
    except Exception:
        return None


def _parse_stop_until_datetime(command_text: str) -> tuple[datetime | None, str]:
    parts = shlex.split(str(command_text or "").strip())
    if len(parts) <= 1:
        return _next_xauusd_reopen_utc(), "next_xauusd_reopen"

    raw_arg = " ".join(parts[1:]).strip()
    if not raw_arg:
        return None, "missing_time"

    try:
        iso_value = raw_arg.replace("Z", "+00:00").replace(" ", "T")
        parsed = datetime.fromisoformat(iso_value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("Europe/Berlin"))
        return parsed.astimezone(timezone.utc), "custom_time"
    except Exception:
        pass

    try:
        local_tz = ZoneInfo("Europe/Berlin")
        now_local = datetime.now(local_tz)
        if ":" in raw_arg and "-" not in raw_arg:
            parsed_local = datetime.strptime(raw_arg, "%H:%M").replace(
                year=now_local.year,
                month=now_local.month,
                day=now_local.day,
                tzinfo=local_tz,
            )
            return parsed_local.astimezone(timezone.utc), "custom_time"
    except Exception:
        pass

    return None, "invalid_time"


def _is_signal_forge_account(acc) -> bool:
    label = str(getattr(acc, "label", "") or "").strip().lower()
    strategies = {str(s).strip().lower() for s in list(getattr(acc, "strategy", []) or [])}
    return "signal_forge" in strategies or "signal" in label


def _build_signal_forge_overview_text(acc) -> str:
    from bot.accounts import _connect_account, _reconnect_primary
    from bot import mt5_bridge

    if not acc or not acc.enabled:
        return "Signal Forge Gold overview unavailable: target account not available."

    if not _connect_account(acc):
        return (
            "Signal Forge Gold overview unavailable: could not connect to the account.\n"
            f"Account: {acc.label}\n"
            f"Login: {acc.login}"
        )

    try:
        account_info = mt5_bridge.get_account_info() or {}
        trades = mt5_bridge.get_trade_history(limit=500) or []
        today = datetime.now(timezone.utc).date()
        today_trades = [t for t in trades if _parse_trade_date(t.get("opened")) == today]
        today_wins = sum(1 for t in today_trades if t.get("status") == "win")
        today_losses = sum(1 for t in today_trades if t.get("status") == "loss")
        today_pnl = sum(float(t.get("pnl", 0) or 0) for t in today_trades)
        open_positions = mt5_bridge.get_open_positions() or []
        return (
            "Signal Forge Gold overview\n"
            f"Account: {acc.label}\n"
            f"Login: {acc.login}\n"
            f"Balance: {float(account_info.get('balance', acc.balance) or 0):.2f}\n"
            f"Equity: {float(account_info.get('equity', acc.equity) or 0):.2f}\n"
            f"Today wins: {today_wins}\n"
            f"Today losses: {today_losses}\n"
            f"Today net profit: {today_pnl:.2f}\n"
            f"Open positions: {len(open_positions)}"
        )
    finally:
        try:
            _reconnect_primary()
        except Exception:
            pass


def _build_account_performance_text(acc) -> str:
    from bot.accounts import _connect_account, _reconnect_primary
    from bot import mt5_bridge

    if not acc or not acc.enabled:
        return "Account stats unavailable: target account not available."

    if not _connect_account(acc):
        return (
            "Account stats unavailable: could not connect to the account.\n"
            f"Account: {acc.label}\n"
            f"Login: {acc.login}"
        )

    try:
        account_info = mt5_bridge.get_account_info() or {}
        trades = mt5_bridge.get_trade_history(limit=500) or []
        today = datetime.now(timezone.utc).date()
        today_trades = [t for t in trades if _parse_trade_date(t.get("opened")) == today]

        total_trades = len(trades)
        wins = sum(1 for t in trades if t.get("status") == "win")
        losses = sum(1 for t in trades if t.get("status") == "loss")
        breakeven = sum(1 for t in trades if t.get("status") == "breakeven")
        net_profit = sum(float(t.get("pnl", 0) or 0) for t in trades)

        today_wins = sum(1 for t in today_trades if t.get("status") == "win")
        today_losses = sum(1 for t in today_trades if t.get("status") == "loss")
        today_net_profit = sum(float(t.get("pnl", 0) or 0) for t in today_trades)

        open_positions = mt5_bridge.get_open_positions() or []
        balance = float(account_info.get("balance", acc.balance) or 0)
        equity = float(account_info.get("equity", acc.equity) or 0)
        profit = equity - balance

        return (
            "Account summary\n"
            f"Account: {acc.label}\n"
            f"Login: {acc.login}\n"
            f"Balance: {balance:.2f}\n"
            f"Equity: {equity:.2f}\n"
            f"Floating P/L: {profit:.2f}\n"
            f"Total trades: {total_trades}\n"
            f"Wins: {wins}\n"
            f"Losses: {losses}\n"
            f"Breakeven: {breakeven}\n"
            f"Net profit: {net_profit:.2f}\n"
            f"Today wins: {today_wins}\n"
            f"Today losses: {today_losses}\n"
            f"Today net profit: {today_net_profit:.2f}\n"
            f"Open positions: {len(open_positions)}"
        )
    finally:
        try:
            _reconnect_primary()
        except Exception:
            pass


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

    if command in {"sstop", "sstart"}:
        preferred_labels = (
            "signal forge gold 5%",
            "signal forge gold funded",
            "signal forge gold demo",
            "signal forge gold",
            "the5ers funded",
        )
        for target_label in preferred_labels:
            for acc in accounts:
                label = str(getattr(acc, "label", "") or "").strip().lower()
                if label == target_label:
                    return acc
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
        chat_id = getattr(event, "chat_id", None)
        if chat_id is not None:
            try:
                send_text_alert(text, chat_id=str(chat_id))
                logger.warning(f"[TG_CMD] Inline reply failed; sent direct message instead: {exc}")
                return
            except Exception as exc2:
                logger.warning(f"[TG_CMD] Could not send direct reply: {exc2}")
                return
        logger.warning(f"[TG_CMD] Could not send inline reply: {exc}")


def _is_control_chat_allowed(chat: dict) -> bool:
    chat_type = str(chat.get("type") or "").strip().lower()
    chat_username = str(chat.get("username") or "").lstrip("@").strip().lower()
    chat_id = str(chat.get("id") or "").strip()

    allowed_chats = {
        str(item).lstrip("@").strip().lower()
        for item in (getattr(config, "TG_CHANNELS", []) or [])
        if str(item).strip()
    }
    if chat_type == "private":
        return True
    if chat_username and chat_username in allowed_chats:
        return True
    if chat_id and chat_id in allowed_chats:
        return True
    return False
def build_accounts_summary_text() -> str:
    from bot.accounts import get_all_accounts, get_account_trade_mode, _connect_account, _reconnect_primary
    from bot import mt5_bridge

    lines: list[str] = ["📊 Account Summary"]
    accounts = list(get_all_accounts() or [])
    if not accounts:
        return "📊 Account Summary\nNo accounts found."

    total_balance = 0.0
    total_equity = 0.0
    total_today_net = 0.0

    for acc in accounts:
        if not getattr(acc, "enabled", True):
            continue

        mode = get_account_trade_mode(int(acc.login))
        allowed = "ON" if mode.get("allowed") else "OFF"
        reason = str(mode.get("stop_reason_text") or mode.get("reason") or "").strip()

        balance = float(getattr(acc, "balance", 0.0) or 0.0)
        equity = float(getattr(acc, "equity", 0.0) or 0.0)
        today_wins = 0
        today_losses = 0
        today_net_profit = 0.0
        total_trades = 0
        open_positions = 0
        today_profit_amount = 0.0
        today_loss_amount = 0.0

        if _connect_account(acc):
            try:
                account_info = mt5_bridge.get_account_info() or {}
                balance = float(account_info.get("balance", balance) or balance or 0.0)
                equity = float(account_info.get("equity", equity) or equity or 0.0)
                trades = mt5_bridge.get_trade_history(limit=500) or []
                today = datetime.now(timezone.utc).date()
                today_trades = [t for t in trades if _parse_trade_date(t.get("opened")) == today]
                total_trades = len(trades)
                today_wins = sum(1 for t in today_trades if t.get("status") == "win")
                today_losses = sum(1 for t in today_trades if t.get("status") == "loss")
                today_profit_amount = sum(max(float(t.get("pnl", 0) or 0), 0.0) for t in today_trades)
                today_loss_amount = abs(sum(min(float(t.get("pnl", 0) or 0), 0.0) for t in today_trades))
                today_net_profit = today_profit_amount - today_loss_amount
                open_positions = len(mt5_bridge.get_open_positions() or [])
            finally:
                try:
                    _reconnect_primary()
                except Exception:
                    pass

        total_balance += balance
        total_equity += equity
        total_today_net += today_net_profit

        lines.append(
            f"\n{acc.label}\n"
            f"Login: {acc.login}\n"
            f"Status: {'Trading ' + allowed}\n"
            f"Today profit: {today_profit_amount:.2f}\n"
            f"Today loss: {today_loss_amount:.2f}\n"
            f"Net profit: {today_net_profit:.2f}\n"
            f"Balance: {balance:.2f}\n"
            f"Equity: {equity:.2f}\n"
            f"Total trades: {total_trades}\n"
            f"Open positions: {open_positions}"
        )
        if reason and allowed == "OFF":
            lines.append(f"Reason: {reason}")

    lines.append(
        "\nAll Accounts Total\n"
        f"Balance: {total_balance:.2f}\n"
        f"Equity: {total_equity:.2f}\n"
        f"Today net profit: {total_today_net:.2f}"
    )
    return "\n".join(lines)


def _is_private_control_allowed(sender: dict) -> bool:
    allowed_usernames = set(getattr(config, "TG_CONTROL_ALLOWED_USERNAMES", []) or [])
    allowed_ids = set(getattr(config, "TG_CONTROL_ALLOWED_IDS", []) or [])

    sender_id = str(sender.get("id", "") or "").strip()
    sender_username = str(sender.get("username", "") or "").lstrip("@").strip().lower()

    if not allowed_usernames and not allowed_ids:
        return True
    if sender_id and sender_id in allowed_ids:
        return True
    if sender_username and sender_username in allowed_usernames:
        return True
    return False


def _is_control_sender_allowed(sender: dict) -> bool:
    return _is_private_control_allowed(sender)


async def _handle_private_control_message(chat_id: str | int, text: str, sender_label: str) -> bool:
    class _PrivateReplyEvent:
        def __init__(self, target_chat_id: str | int):
            self._chat_id = str(target_chat_id)

        async def reply(self, message_text: str):
            send_text_alert(message_text, chat_id=self._chat_id)

    fake_event = _PrivateReplyEvent(chat_id)
    return await _handle_control_command(fake_event, text, sender_label)


async def _bot_control_poll_loop() -> None:
    if not getattr(config, "ADMIN_BOT_TOKEN", "").strip():
        logger.info("[TG_BOT] Control command polling disabled (no ADMIN_BOT_TOKEN).")
        return

    try:
        import httpx
    except Exception as exc:
        logger.warning(f"[TG_BOT] httpx not available for control command polling: {exc}")
        return

    token = config.ADMIN_BOT_TOKEN.strip()
    get_updates_url = f"https://api.telegram.org/bot{token}/getUpdates"
    offset: int | None = None
    logger.info("[TG_BOT] Control command polling started.")

    async with httpx.AsyncClient(timeout=40) as client:
        while True:
            try:
                params = {
                    "timeout": 30,
                    "allowed_updates": '["message","channel_post","edited_message","edited_channel_post"]',
                }
                if offset is not None:
                    params["offset"] = offset
                resp = await client.get(get_updates_url, params=params)
                resp.raise_for_status()
                payload = resp.json()
                for item in payload.get("result", []) or []:
                    try:
                        offset = int(item.get("update_id", 0)) + 1
                    except Exception:
                        continue

                    message = item.get("message") or item.get("channel_post") or item.get("edited_message") or item.get("edited_channel_post") or {}
                    if not message:
                        continue

                    chat = message.get("chat") or {}
                    if not _is_control_chat_allowed(chat):
                        continue

                    text = str(message.get("text") or "").strip()
                    if not text:
                        continue

                    sender = message.get("from") or {}
                    sender_label = str(sender.get("username") or sender.get("first_name") or sender.get("id") or "private_user")
                    if str(chat.get("type") or "").strip().lower() == "private" and not _is_control_sender_allowed(sender):
                        send_text_alert(
                            "? Not authorized to use trading control commands.",
                            chat_id=str(chat.get("id")),
                        )
                        logger.warning(f"[TG_BOT] Unauthorized private command from {sender_label}")
                        continue

                    command = _canonical_command(text)
                    if command in {"", None}:
                        continue
                    if command in {"help", "start"}:
                        send_text_alert(_build_help_text(), chat_id=str(chat.get("id")))
                        continue

                    await _handle_private_control_message(
                        chat_id=str(chat.get("id")),
                        text=text,
                        sender_label=f"{str(chat.get('type') or 'chat')}:{sender_label}",
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"[TG_BOT] Control command polling error: {exc}")
                await asyncio.sleep(max(3, int(getattr(config, "TG_RECONNECT_DELAY", 10) or 10)))
async def _handle_control_command(event, text: str, channel_name: str) -> bool:
    from bot.accounts import get_account_trade_mode, stop_account_until, start_account_now
    from bot.algo.runner import get_runner_status, start_all_strategies, stop_all_strategies

    command = _canonical_command(text)
    if command == "help":
        await _reply_control_status(event, _build_help_text())
        return True
    if command == "start":
        running_before = get_runner_status().get("running_strategies", [])
        started = []
        if not state.running:
            state.running = True
            started = start_all_strategies()
        running_after = get_runner_status().get("running_strategies", [])
        summary_text = build_accounts_summary_text()
        await _reply_control_status(
            event,
            "✅ Bot start confirmed\n"
            f"Source: @{channel_name}\n"
            f"Status: {'Bot started' if started else 'Bot already running'}\n"
            f"Running strategies: {', '.join(running_after) if running_after else 'none'}\n"
            f"Previously running: {', '.join(running_before) if running_before else 'none'}\n\n"
            f"{summary_text}"
        )
        send_text_alert(
            "Bot start confirmed\n"
            f"Source: @{channel_name}\n"
            f"Status: {'Bot started' if started else 'Bot already running'}\n"
            f"Running strategies: {', '.join(running_after) if running_after else 'none'}\n\n"
            f"{summary_text}"
        )
        return True
    if command == "stop":
        running_before = get_runner_status().get("running_strategies", [])
        state.running = False
        stop_all_strategies()
        summary_text = build_accounts_summary_text()
        await _reply_control_status(
            event,
            "🛑 Bot stop confirmed\n"
            f"Source: @{channel_name}\n"
            f"Status: Bot stopped\n"
            f"Stopped strategies: {', '.join(running_before) if running_before else 'none'}\n\n"
            f"{summary_text}"
        )
        send_text_alert(
            "Bot stop confirmed\n"
            f"Source: @{channel_name}\n"
            f"Status: Bot stopped\n"
            f"Stopped strategies: {', '.join(running_before) if running_before else 'none'}\n\n"
            f"{summary_text}"
        )
        return True
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
    auto_resume_text = "Not needed"
    control_error = ""
    if command == "sstop":
        resume_at, resume_kind = _parse_stop_until_datetime(text)
        if resume_at is None:
            await _reply_control_status(
                event,
                "❌ Stop failed\n"
                f"Account: {acc.label}\n"
                f"Reason: {resume_kind}\n"
                "Use: /signal_forge_stop 2026-07-12 18:00 or /signal_forge_stop 18:00",
            )
            return True
        if resume_at <= datetime.now(timezone.utc):
            await _reply_control_status(
                event,
                "❌ Stop failed\n"
                f"Account: {acc.label}\n"
                "Reason: stop time is in the past",
            )
            return True
        reason_code = f"telegram_{command}_{resume_kind}"
        stop_account_until(int(acc.login), resume_at, reason_code=reason_code)
        action_text = f"Stop trading until {resume_at.strftime('%Y-%m-%d %H:%M UTC')}"
        auto_resume_text = resume_at.strftime("%Y-%m-%d %H:%M UTC")
        logger.warning(
            f"[TG_CMD] Stop-until command accepted from @{channel_name} | "
            f"command={command} | account={acc.label} ({acc.login}) | resume_at={resume_at.isoformat()}"
        )
    elif command == "sstart":
        start_account_now(int(acc.login))
        action_text = "Start trading now"
        logger.warning(
            f"[TG_CMD] Start-now command accepted from @{channel_name} | "
            f"command={command} | account={acc.label} ({acc.login})"
        )
    else:
        return False

    mode = get_account_trade_mode(int(acc.login))
    if command == "sstop" and mode.get("allowed"):
        control_error = "Stop was not applied"
    if command == "sstop" and not mode.get("halt_until"):
        control_error = control_error or "No halt-until time was stored"

    if control_error:
        await _reply_control_status(
            event,
            "❌ Command failed\n"
            f"Account: {acc.label}\n"
            f"Reason: {control_error}\n"
            f"Mode: {'Trading ON' if mode.get('allowed') else 'Trading OFF'}",
        )
        return True

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
    overview_text = ""
    if command == "sstop" and _is_signal_forge_account(acc):
        overview_text = "\n\n" + _build_signal_forge_overview_text(acc)
    stats_text = "\n\n" + _build_account_performance_text(acc)
    inline_status = (
        f"✅ Command success\n"
        f"Command: {command}\n"
        f"Account: {acc.label}\n"
        f"Action: {action_text}\n"
        f"State: {'Trading ON' if mode.get('allowed') else f'Trading OFF until {auto_resume_text}'}"
        f"{overview_text}"
        f"{stats_text}"
    )
    await _reply_control_status(event, inline_status)
    send_text_alert(
        f"Command accepted\n"
        f"Account: {acc.label}\n"
        f"Login: {acc.login}\n"
        f"Action: {action_text}\n"
        f"Current state: {'Trading ON' if mode.get('allowed') else f'Trading OFF until {auto_resume_text}'}\n"
        f"Auto resume: {auto_resume_text}\n"
        f"{overview_text.strip() + chr(10) if overview_text else ''}"
        f"{stats_text.strip() + chr(10) if stats_text else ''}"
        f"Source: @{channel_name}\n"
        f"Reason: {halt_text}"
    )
    try:
        send_text_alert(build_accounts_summary_text())
    except Exception as exc:
        logger.warning(f"[TG_CMD] Could not send account summary: {exc}")
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
    bot_poll_task = asyncio.create_task(_bot_control_poll_loop(), name="TelegramBotControlPoll")

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

    monitored_chat_ids = {
        int(getattr(entity, "id", 0))
        for entity in channel_entities
        if getattr(entity, "id", None) is not None
    }

    @_client.on(events.NewMessage(chats=channel_entities))
    async def handler(event):
        chat = await event.get_chat()
        channel_name = getattr(chat, "username", None) or str(chat.id)
        logger.debug(f"[TG] Raw event received from @{channel_name}")
        await _handle_message(event)

    @_client.on(events.NewMessage())
    async def control_handler(event):
        text = (event.raw_text or "").strip()
        if not text:
            return

        command = _canonical_command(text)
        if command not in _CONTROL_COMMANDS:
            return

        chat = await event.get_chat()
        chat_id = int(getattr(chat, "id", 0) or 0)
        if chat_id in monitored_chat_ids:
            return

        sender = await event.get_sender()
        sender_dict = {
            "id": getattr(sender, "id", None),
            "username": getattr(sender, "username", None),
            "first_name": getattr(sender, "first_name", None),
        }
        if not _is_control_sender_allowed(sender_dict):
            await event.reply("❌ Not authorized to use trading control commands.")
            logger.warning(
                f"[TG_CMD] Unauthorized command in chat {chat_id} from "
                f"{sender_dict.get('username') or sender_dict.get('first_name') or sender_dict.get('id')}"
            )
            return

        channel_name = getattr(chat, "username", None) or str(chat.id)
        logger.info(f"[TG_CMD] Control command received in chat @{channel_name}: {text[:80]}")
        await _handle_control_command(event, text, channel_name)

    logger.info("Telegram listener running...")
    try:
        await _client.run_until_disconnected()
    finally:
        if bot_poll_task:
            bot_poll_task.cancel()
            try:
                await bot_poll_task
            except asyncio.CancelledError:
                pass
        state.telegram_connected = False


async def stop_listener() -> None:
    global _client
    if _client and _client.is_connected():
        await _client.disconnect()
        state.telegram_connected = False
        logger.info("Telegram listener stopped.")


def get_client() -> TelegramClient | None:
    return _client

