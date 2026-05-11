"""
Export MT5 historical candles to CSV for repeatable backtests.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from bot import mt5_bridge

try:
    import MetaTrader5 as mt5
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"MetaTrader5 import failed: {exc}")


TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def export_csv(symbol: str, timeframe: str, days: int, output: str) -> dict:
    if timeframe not in TIMEFRAME_MAP:
        raise ValueError(f"Unsupported timeframe '{timeframe}'")

    mt5_bridge.ensure_connected()
    end = datetime.now()
    start = end - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, TIMEFRAME_MAP[timeframe], start, end)
    if rates is None or len(rates) == 0:
        raise ValueError(f"No data returned for {symbol} {timeframe}")

    df = pd.DataFrame(rates)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.rename(columns={
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "tick_volume": "volume",
    })
    df = df[["datetime", "open", "high", "low", "close", "volume"]]

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "rows": len(df),
        "start": str(df["datetime"].min()),
        "end": str(df["datetime"].max()),
        "output": str(output_path),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export MT5 candles to CSV")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", default="M15")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = export_csv(
        symbol=args.symbol,
        timeframe=args.timeframe,
        days=args.days,
        output=args.output,
    )
    print(result)
