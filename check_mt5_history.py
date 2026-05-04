import MetaTrader5 as mt5
from datetime import datetime, timezone

mt5.initialize()

# Use UTC to match MT5 server time
now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
from_date = datetime(2026, 4, 1)  # UTC

deals = mt5.history_deals_get(from_date, now_utc)
print(f"April-May deals: {len(deals) if deals else 0}")

if deals:
    recent = sorted(deals, key=lambda x: x.time, reverse=True)
    for d in recent:
        dt = datetime.utcfromtimestamp(d.time).strftime("%Y-%m-%d %H:%M UTC")
        comment = (d.comment or "")[:25]
        print(f"{dt} | {d.symbol} | profit={round(d.profit,2)} | entry={d.entry} | {comment}")

mt5.shutdown()
