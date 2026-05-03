"""
One-time script to generate a Telegram StringSession.

Run this ONCE on any machine:
  python generate_session.py

It will print a session string like:
  1BVtsOKABu...

Copy that string and add it to bot/.env:
  TG_SESSION_STRING=1BVtsOKABu...

After that, the bot will connect to Telegram automatically on every
restart without needing a phone code — even after reboots or IP changes.
"""

import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path("bot") / ".env")

API_ID = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH", "")
PHONE = os.getenv("TG_PHONE", "")


async def main():
    print("=" * 60)
    print("  Telegram StringSession Generator")
    print("  This runs ONCE to create a portable session string.")
    print("=" * 60)
    print()

    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        session_string = client.session.save()

        print()
        print("=" * 60)
        print("  SUCCESS! Copy the session string below:")
        print("=" * 60)
        print()
        print(session_string)
        print()
        print("=" * 60)
        print("  Add this to bot/.env:")
        print(f"  TG_SESSION_STRING={session_string}")
        print("=" * 60)
        print()
        print("After adding it, the bot will connect automatically")
        print("on every restart without needing a phone code.")


if __name__ == "__main__":
    asyncio.run(main())
