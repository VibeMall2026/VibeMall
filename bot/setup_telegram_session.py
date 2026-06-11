from __future__ import annotations

import asyncio
import re
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from bot import config


def _upsert_env_value(env_path: Path, key: str, value: str) -> None:
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    line = f"{key}={value}"
    if re.search(rf"(?m)^{re.escape(key)}=.*$", text):
        text = re.sub(rf"(?m)^{re.escape(key)}=.*$", line, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
    env_path.write_text(text, encoding="utf-8")


async def main() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    client = TelegramClient(StringSession(), config.TG_API_ID, config.TG_API_HASH)
    await client.start(phone=config.TG_PHONE)
    session_string = client.session.save()
    await client.disconnect()
    _upsert_env_value(env_path, "TG_SESSION_STRING", session_string)
    print("TG_SESSION_STRING saved to bot/.env")


if __name__ == "__main__":
    asyncio.run(main())
