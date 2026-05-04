"""
Main entry point for the Trading Bot.

Usage:
  python -m bot.main          # Start bot + API server
  python -m bot.main --api    # Start API server only (no Telegram)
"""
import asyncio
import os
import sys
import threading
import uvicorn
from loguru import logger

from bot import config
from bot.state import state
from bot import mt5_bridge
from bot.api_server import app


def start_api_server() -> None:
    """Run FastAPI in a background thread."""
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level=config.LOG_LEVEL.lower(),
    )


async def start_bot() -> None:
    """Connect MT5 and start Telegram listener."""
    # Connect MT5
    logger.info("Connecting to MT5...")
    if mt5_bridge.connect():
        state.mt5_connected = True
        logger.success("MT5 connected.")
    else:
        logger.warning("MT5 not connected — running without trade execution.")

    # Start Telegram listener
    logger.info("Starting Telegram listener...")
    from bot.telegram_listener import start_listener
    state.running = True
    try:
        await start_listener()
    except Exception as e:
        logger.error(f"Telegram listener error: {e}")
    finally:
        state.running = False
        state.telegram_connected = False
        mt5_bridge.disconnect()


def main() -> None:
    api_only = "--api" in sys.argv

    logger.info("=" * 60)
    logger.info("  Trading Bot Starting")
    logger.info(f"  API: http://{config.API_HOST}:{config.API_PORT}")
    logger.info(f"  MT5 Login: {config.MT5_LOGIN} @ {config.MT5_SERVER}")
    logger.info(f"  Channels: {', '.join(config.TG_CHANNELS) or 'none'}")
    logger.info("=" * 60)

    # Kill any process holding the port before starting
    import subprocess, re
    try:
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if f":{config.API_PORT}" in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit() and int(pid) != os.getpid():
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                    logger.info(f"Freed port {config.API_PORT} (killed PID {pid})")
                    import time; time.sleep(1)
    except Exception:
        pass

    # Initialize state channels from config
    from bot.state import state as _state
    if not _state.channels:
        _state.channels = list(config.TG_CHANNELS)

    # Start API server in background thread
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()
    logger.info(f"API server started on port {config.API_PORT}")

    # Start algo strategy thread (scan-only by default, enable via API)
    from bot.algo.order_block import start_algo
    start_algo()

    if api_only:
        logger.info("Running in API-only mode (no Telegram listener).")
        api_thread.join()
        return

    # Run bot (blocking)
    asyncio.run(start_bot())


if __name__ == "__main__":
    main()
