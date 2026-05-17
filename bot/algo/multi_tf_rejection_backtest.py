"""
Backtest: MultiTF Rejection strategy (15m S/R, 5m entries)
==========================================================

This backtest expects two CSV files:
 - M15 candles (HTF): datetime,open,high,low,close,volume
 - M5 candles  (LTF): datetime,open,high,low,close,volume

Example:
  python -m bot.algo.multi_tf_rejection_backtest ^
    --symbol XAUUSD ^
    --m15 data\\XAUUSD_M15_180d.csv ^
    --m5  data\\XAUUSD_M5_180d.csv ^
    --pip-size 0.01

Notes:
 - PnL is reported in pips (not account currency).
 - If SL and TP are both hit within the same candle, we assume SL first (conservative).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class Trade:
    side: str  # buy/sell
    entry_time: pd.Timestamp
    entry: float
    sl: float
    tp: float
    risk_pips: float
    be_applied: bool = False
    last_trail_step: int = 0

    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # SL/TP

    def pnl_pips(self, pip_size: float) -> float:
        if self.exit_price is None:
            return 0.0
        if self.side == "buy":
            return (self.exit_price - self.entry) / pip_size
        return (self.entry - self.exit_price) / pip_size


def _detect_pivots(m15: pd.DataFrame, lookback: int) -> tuple[list[float], list[float]]:
    """
    Returns (supports, resistances) as price lists, using simple swing-high/low pivots.
    """
    lb = max(2, int(lookback))
    supports: list[float] = []
    resistances: list[float] = []

    lows = m15["low"].to_list()
    highs = m15["high"].to_list()

    for i in range(lb, len(m15) - lb):
        low = lows[i]
        high = highs[i]

        if all(low < lows[j] for j in range(i - lb, i)) and all(low <= lows[j] for j in range(i + 1, i + 1 + lb)):
            supports.append(low)
        if all(high > highs[j] for j in range(i - lb, i)) and all(high >= highs[j] for j in range(i + 1, i + 1 + lb)):
            resistances.append(high)

    return supports, resistances


def _nearest_support(price: float, supports: list[float]) -> Optional[float]:
    below = [s for s in supports if s <= price]
    return max(below) if below else None


def _nearest_resistance(price: float, resistances: list[float]) -> Optional[float]:
    above = [r for r in resistances if r >= price]
    return min(above) if above else None


def run_backtest(
    symbol: str,
    m15_csv: str,
    m5_csv: str,
    pip_size: float,
    rr: float = 2.0,
    pivot_lookback: int = 3,
    special_trigger_pips: float = 20.0,
    special_sl_pips: float = 50.0,
    trail_step_pips: float = 10.0,
) -> dict:
    m15 = pd.read_csv(m15_csv)
    m5 = pd.read_csv(m5_csv)

    for df in (m15, m5):
        if "datetime" not in df.columns:
            raise ValueError("CSV must contain a 'datetime' column")
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
        df.dropna(subset=["datetime"], inplace=True)
        df.sort_values("datetime", inplace=True)
        df.reset_index(drop=True, inplace=True)

    # We will recompute pivots incrementally from M15 slices (simple, slower but OK for typical CSV sizes)
    trades: list[Trade] = []
    open_trade: Optional[Trade] = None

    special_trigger_dist = special_trigger_pips * pip_size
    special_sl_dist = special_sl_pips * pip_size
    trail_step_dist = trail_step_pips * pip_size

    for i in range(2, len(m5)):
        row = m5.iloc[i]
        prev = m5.iloc[i - 1]
        candle_time = row["datetime"]

        # Select M15 candles up to this 5m candle close
        m15_slice = m15[m15["datetime"] <= candle_time]
        if len(m15_slice) < (pivot_lookback * 2 + 10):
            continue

        supports, resistances = _detect_pivots(m15_slice, pivot_lookback)
        if not supports and not resistances:
            continue

        # Manage open trade first (simulate intrabar hits)
        if open_trade:
            high = float(row["high"])
            low = float(row["low"])

            # Conservative fill: if both SL and TP hit same bar, assume SL first
            if open_trade.side == "buy":
                if low <= open_trade.sl:
                    open_trade.exit_time = candle_time
                    open_trade.exit_price = open_trade.sl
                    open_trade.exit_reason = "SL"
                elif high >= open_trade.tp:
                    open_trade.exit_time = candle_time
                    open_trade.exit_price = open_trade.tp
                    open_trade.exit_reason = "TP"
            else:
                if high >= open_trade.sl:
                    open_trade.exit_time = candle_time
                    open_trade.exit_price = open_trade.sl
                    open_trade.exit_reason = "SL"
                elif low <= open_trade.tp:
                    open_trade.exit_time = candle_time
                    open_trade.exit_price = open_trade.tp
                    open_trade.exit_reason = "TP"

            if open_trade.exit_reason:
                trades.append(open_trade)
                open_trade = None
                continue

            # BE + trailing (apply at candle close)
            close = float(row["close"])
            if open_trade.side == "buy":
                profit_pips = (close - open_trade.entry) / pip_size
            else:
                profit_pips = (open_trade.entry - close) / pip_size

            # BE at 1R
            if (not open_trade.be_applied) and profit_pips >= open_trade.risk_pips:
                open_trade.sl = open_trade.entry
                open_trade.be_applied = True
                open_trade.last_trail_step = 0

            if open_trade.be_applied and profit_pips > open_trade.risk_pips:
                extra = profit_pips - open_trade.risk_pips
                steps = int(extra // trail_step_pips)
                if steps > open_trade.last_trail_step:
                    if open_trade.side == "buy":
                        candidate = open_trade.entry + steps * trail_step_dist
                        open_trade.sl = max(open_trade.sl, candidate)
                    else:
                        candidate = open_trade.entry - steps * trail_step_dist
                        open_trade.sl = min(open_trade.sl, candidate)
                    open_trade.last_trail_step = steps

            continue  # no new entry while trade is open

        # Entry checks (no open trade)
        close = float(row["close"])
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        prev_close = float(prev["close"])

        support = _nearest_support(close, supports)
        resistance = _nearest_resistance(close, resistances)

        # BUY
        if support is not None and low <= support and close > support:
            entry = close
            use_fixed = abs(prev_close - open_) <= special_trigger_dist
            sl = entry - special_sl_dist if use_fixed else prev_close
            if sl >= entry:
                sl = entry - special_sl_dist
            risk_dist = abs(entry - sl)
            risk_pips = risk_dist / pip_size
            tp = entry + risk_dist * rr
            open_trade = Trade("buy", candle_time, entry, sl, tp, risk_pips)
            continue

        # SELL
        if resistance is not None and high >= resistance and close < resistance:
            entry = close
            use_fixed = abs(prev_close - open_) <= special_trigger_dist
            sl = entry + special_sl_dist if use_fixed else prev_close
            if sl <= entry:
                sl = entry + special_sl_dist
            risk_dist = abs(entry - sl)
            risk_pips = risk_dist / pip_size
            tp = entry - risk_dist * rr
            open_trade = Trade("sell", candle_time, entry, sl, tp, risk_pips)
            continue

    # If trade still open, close at last close (mark-to-market)
    if open_trade:
        last = m5.iloc[-1]
        open_trade.exit_time = last["datetime"]
        open_trade.exit_price = float(last["close"])
        open_trade.exit_reason = "EOD"
        trades.append(open_trade)

    total = len(trades)
    wins = sum(1 for t in trades if t.exit_reason == "TP")
    losses = sum(1 for t in trades if t.exit_reason == "SL")
    total_pips = sum(t.pnl_pips(pip_size) for t in trades)
    win_rate = (wins / total * 100.0) if total else 0.0

    return {
        "symbol": symbol,
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 2),
        "total_pips": round(total_pips, 2),
        "avg_pips": round(total_pips / total, 2) if total else 0.0,
        "rr": rr,
        "pip_size": pip_size,
        "notes": "PnL in pips. Requires M15+M5 CSV. Conservative SL-first when both hit same candle.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--m15", required=True, help="Path to M15 CSV")
    ap.add_argument("--m5", required=True, help="Path to M5 CSV")
    ap.add_argument("--pip-size", type=float, default=0.01)
    ap.add_argument("--rr", type=float, default=2.0)
    ap.add_argument("--pivot-lookback", type=int, default=3)
    args = ap.parse_args()

    result = run_backtest(
        symbol=args.symbol,
        m15_csv=args.m15,
        m5_csv=args.m5,
        pip_size=args.pip_size,
        rr=args.rr,
        pivot_lookback=args.pivot_lookback,
    )
    print(result)


if __name__ == "__main__":
    main()

