# Trading Bot — Setup & Deployment Guide

## Architecture

```
Windows PC (24/7)          Ubuntu VPS
─────────────────          ──────────────────────────────
MetaTrader 5          ←──  Trading Bot (bot/main.py)
  terminal64.exe            - Telegram listener (Telethon)
                            - Signal parser
                            - MT5 bridge (via MetaTrader5 lib)
                            - FastAPI server (:8000)
                       ←──  Django Dashboard (VibeMall)
                            - /trading/ dashboard
                            - /trading/settings/
```

> **Note:** MetaTrader5 Python library only works on Windows.
> On Ubuntu VPS, the bot runs the Telegram listener and API server,
> but MT5 trade execution requires the Windows PC to be running MT5
> and the bot to be run there (or via SSH tunnel).

---

## Option A — Run bot on Windows PC (Recommended for MT5)

### 1. Install Python 3.11+ on Windows PC

### 2. Install dependencies
```cmd
cd bot
pip install -r requirements.txt
```

### 3. Copy .env
```cmd
copy .env.example .env
# Edit .env with your credentials
```

### 4. First run (Telegram login — one time only)
```cmd
python -m bot.main
# Enter your phone number when prompted
# Enter the OTP code Telegram sends you
# Session saved to sessions/telegram_to_mt5.session
```

### 5. Run as Windows Service (optional)
Use NSSM (Non-Sucking Service Manager):
```cmd
nssm install TradingBot "C:\Python311\python.exe" "-m bot.main"
nssm set TradingBot AppDirectory "C:\path\to\VibeMall"
nssm start TradingBot
```

---

## Option B — Run bot on Ubuntu VPS (API + Telegram only, no MT5)

### 1. SSH into VPS
```bash
ssh user@your-vps-ip
cd /path/to/VibeMall
```

### 2. Install dependencies
```bash
pip install -r bot/requirements.txt
# Note: MetaTrader5 will fail to install on Linux — that's OK
pip install telethon fastapi uvicorn python-dotenv pydantic pydantic-settings loguru
```

### 3. Copy .env
```bash
cp bot/.env.example bot/.env
nano bot/.env   # Fill in credentials
```

### 4. First Telegram login (interactive — do this once)
```bash
python -m bot.main
# Follow prompts for Telegram OTP
```

### 5. Run as systemd service
```bash
sudo nano /etc/systemd/system/tradingbot.service
```

```ini
[Unit]
Description=Trading Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/VibeMall
ExecStart=/usr/bin/python3 -m bot.main
Restart=always
RestartSec=10
Environment=PYTHONPATH=/path/to/VibeMall

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable tradingbot
sudo systemctl start tradingbot
sudo systemctl status tradingbot
```

### 6. View logs
```bash
sudo journalctl -u tradingbot -f
# or
tail -f logs/bot.log
```

---

## Django Dashboard Connection

The Django `trading/` app connects to the bot API at:
- Default: `http://127.0.0.1:8001`
- Set in `.env`: `BOT_API_URL=http://127.0.0.1:8001`

If bot runs on same server as Django → use `127.0.0.1`
If bot runs on Windows PC → use SSH tunnel:

```bash
# On Ubuntu VPS, create SSH tunnel to Windows PC
ssh -L 8001:localhost:8000 user@windows-pc-ip -N
```

Then Django dashboard at `/trading/` will show live data.

---

## Telegram Session (First Time)

When you run the bot for the first time, Telethon will ask:
1. Your phone number (already in .env as TG_PHONE)
2. The OTP code Telegram sends to your phone/app
3. If 2FA enabled: your Telegram password

After this, `sessions/telegram_to_mt5.session` is created.
**Never delete this file** — it's your login session.

---

## Signal Format Supported

```
XAUUSD BUY
Entry: 1920.00
SL: 1915.00
TP1: 1930.00
TP2: 1940.00
```

Or inline:
```
EURUSD SELL @ 1.0850 SL 1.0880 TP 1.0820
```

---

## API Endpoints (port 8000)

All require header: `X-API-Key: Paladiya@2023`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /status | Bot + MT5 + Telegram status |
| GET | /stats | Full stats (account, performance, daily) |
| GET | /open-trades | Current open MT5 positions |
| GET | /trades | Trade history |
| GET | /signals | Recent signal log |
| GET | /settings | Current settings |
| PUT | /settings | Update settings |
| POST | /channels | Add Telegram channel |
| DELETE | /channels | Remove Telegram channel |
| PUT | /positions/{id} | Modify SL/TP |
| POST | /parse-signal | Test signal parsing |
| POST | /control | start/stop/restart/weekend_shutdown |
