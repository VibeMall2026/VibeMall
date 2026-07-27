"""
Order Block + FVG + Breakout confluence backtest.

The setup requires:
1. A valid Order Block + Fair Value Gap pattern.
2. The same impulse to also break a recent range in the same direction.
3. A retest entry into the OB zone with directional confirmation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import pandas as pd

from bot.algo.breakout_backtest import atr, ema, load_csv, print_report


@dataclass
class ConfluenceConfig:
    initial_cash: float = 10_000.0
    risk_pct: float = 0.01
    risk_reward: float = 2.0
    breakout_lookback: int = 15
    ema_period: int = 30
    atr_period: int = 14
    atr_min_multiplier: float = 0.5
    breakout_buffer_atr: float = 0.10
    fvg_body_ratio: float = 0.60
    max_setup_age: int = 20
    sl_buffer_pct: float = 0.10


def run_backtest(csv_file: str, config: ConfluenceConfig) -> dict:
    df = load_csv(csv_file)
    min_rows = max(config.ema_period, config.atr_period * 2, config.breakout_lookback + 3) + 5
    if len(df) < min_rows:
        raise ValueError("Not enough rows for confluence backtest")

    df["EMA"] = ema(df["Close"], config.ema_period)
    df["ATR"] = atr(df, config.atr_period)
    df["AVG_ATR"] = df["ATR"].rolling(config.atr_period).mean()
    df["BODY"] = (df["Close"] - df["Open"]).abs()
    df["RANGE"] = (df["High"] - df["Low"]).replace(0, pd.NA)
    df["BODY_RATIO"] = (df["BODY"] / df["RANGE"]).fillna(0.0)

    cash = config.initial_cash
    peak_equity = cash
    max_drawdown = 0.0
    trades: list[dict] = []
    trade = None
    active_setups: list[dict] = []

    start = min_rows
    for i in range(start, len(df)):
        row = df.iloc[i]
        timestamp = df.index[i]

        if trade is not None:
            exit_reason = None
            exit_price = None
            if trade["side"] == "buy":
                sl_hit = row["Low"] <= trade["sl"]
                tp_hit = row["High"] >= trade["tp"]
                if sl_hit and tp_hit:
                    exit_reason, exit_price = "sl_tp_same_bar", trade["sl"]
                elif sl_hit:
                    exit_reason, exit_price = "sl", trade["sl"]
                elif tp_hit:
                    exit_reason, exit_price = "tp", trade["tp"]
            else:
                sl_hit = row["High"] >= trade["sl"]
                tp_hit = row["Low"] <= trade["tp"]
                if sl_hit and tp_hit:
                    exit_reason, exit_price = "sl_tp_same_bar", trade["sl"]
                elif sl_hit:
                    exit_reason, exit_price = "sl", trade["sl"]
                elif tp_hit:
                    exit_reason, exit_price = "tp", trade["tp"]

            if exit_reason:
                pnl = (exit_price - trade["entry"]) * trade["size"]
                if trade["side"] == "sell":
                    pnl *= -1
                cash += pnl
                trades.append({
                    **trade,
                    "exit_time": timestamp,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "result": "win" if pnl > 0 else "loss",
                    "exit_reason": exit_reason,
                })
                trade = None

        active_setups = [s for s in active_setups if i - s["index"] <= config.max_setup_age]

        if trade is None:
            for setup in list(active_setups):
                if setup["direction"] == "bullish":
                    invalidated = row["Close"] < setup["ob_low"]
                    touched = row["Low"] <= setup["ob_mid"] and row["Low"] >= setup["ob_low"]
                    confirmed = row["Close"] > setup["ob_mid"] and df.iloc[i - 1]["Close"] <= setup["ob_mid"]
                    if invalidated:
                        active_setups.remove(setup)
                        continue
                    if touched and confirmed:
                        entry = row["Close"]
                        sl = setup["ob_low"] - setup["ob_size"] * config.sl_buffer_pct
                        risk_per_unit = entry - sl
                        if risk_per_unit > 0:
                            size = (cash * config.risk_pct) / risk_per_unit
                            trade = {
                                "side": "buy",
                                "entry_time": timestamp,
                                "entry": entry,
                                "sl": sl,
                                "tp": entry + risk_per_unit * config.risk_reward,
                                "size": size,
                                "setup_time": setup["time"],
                            }
                            active_setups.remove(setup)
                            break
                else:
                    invalidated = row["Close"] > setup["ob_high"]
                    touched = row["High"] >= setup["ob_mid"] and row["High"] <= setup["ob_high"]
                    confirmed = row["Close"] < setup["ob_mid"] and df.iloc[i - 1]["Close"] >= setup["ob_mid"]
                    if invalidated:
                        active_setups.remove(setup)
                        continue
                    if touched and confirmed:
                        entry = row["Close"]
                        sl = setup["ob_high"] + setup["ob_size"] * config.sl_buffer_pct
                        risk_per_unit = sl - entry
                        if risk_per_unit > 0:
                            size = (cash * config.risk_pct) / risk_per_unit
                            trade = {
                                "side": "sell",
                                "entry_time": timestamp,
                                "entry": entry,
                                "sl": sl,
                                "tp": entry - risk_per_unit * config.risk_reward,
                                "size": size,
                                "setup_time": setup["time"],
                            }
                            active_setups.remove(setup)
                            break

        if pd.isna(row["ATR"]) or pd.isna(row["AVG_ATR"]) or pd.isna(row["EMA"]):
            marked_equity = cash if trade is None else cash
            peak_equity = max(peak_equity, marked_equity)
            continue

        c1 = df.iloc[i - 2]
        c2 = df.iloc[i - 1]
        c3 = df.iloc[i]
        if c2["BODY_RATIO"] < config.fvg_body_ratio:
            marked_equity = cash if trade is None else cash
            peak_equity = max(peak_equity, marked_equity)
            continue

        if c3["ATR"] < c3["AVG_ATR"] * config.atr_min_multiplier:
            marked_equity = cash if trade is None else cash
            peak_equity = max(peak_equity, marked_equity)
            continue

        prior_window = df.iloc[i - config.breakout_lookback - 2:i - 2]
        if len(prior_window) < config.breakout_lookback:
            marked_equity = cash if trade is None else cash
            peak_equity = max(peak_equity, marked_equity)
            continue

        prior_high = prior_window["High"].max()
        prior_low = prior_window["Low"].min()
        buffer = c3["ATR"] * config.breakout_buffer_atr

        if (
            c2["Close"] > c2["Open"]
            and c3["Low"] > c1["High"]
            and c3["Close"] > prior_high + buffer
            and c3["Close"] > c3["EMA"]
        ):
            ob_high = c1["High"]
            ob_low = c1["Low"]
            active_setups.append({
                "index": i,
                "time": timestamp,
                "direction": "bullish",
                "ob_high": ob_high,
                "ob_low": ob_low,
                "ob_mid": (ob_high + ob_low) / 2,
                "ob_size": ob_high - ob_low,
            })

        elif (
            c2["Close"] < c2["Open"]
            and c3["High"] < c1["Low"]
            and c3["Close"] < prior_low - buffer
            and c3["Close"] < c3["EMA"]
        ):
            ob_high = c1["High"]
            ob_low = c1["Low"]
            active_setups.append({
                "index": i,
                "time": timestamp,
                "direction": "bearish",
                "ob_high": ob_high,
                "ob_low": ob_low,
                "ob_mid": (ob_high + ob_low) / 2,
                "ob_size": ob_high - ob_low,
            })

        marked_equity = cash
        if trade is not None:
            if trade["side"] == "buy":
                marked_equity += (row["Close"] - trade["entry"]) * trade["size"]
            else:
                marked_equity += (trade["entry"] - row["Close"]) * trade["size"]
        peak_equity = max(peak_equity, marked_equity)
        dd = 0.0 if peak_equity == 0 else (peak_equity - marked_equity) / peak_equity * 100
        max_drawdown = max(max_drawdown, dd)

    if trade is not None:
        final_row = df.iloc[-1]
        exit_price = final_row["Close"]
        pnl = (exit_price - trade["entry"]) * trade["size"]
        if trade["side"] == "sell":
            pnl *= -1
        cash += pnl
        trades.append({
            **trade,
            "exit_time": df.index[-1],
            "exit_price": exit_price,
            "pnl": pnl,
            "result": "win" if pnl > 0 else "loss",
            "exit_reason": "eod",
        })

    total_trades = len(trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] <= 0)
    win_rate = (wins / total_trades * 100) if total_trades else 0.0
    total_return = (cash - config.initial_cash) / config.initial_cash * 100
    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0
    avg_win = (gross_profit / wins) if wins else 0.0
    avg_loss = (-gross_loss / losses) if losses else 0.0

    return {
        "csv_file": csv_file,
        "bars": len(df),
        "start": str(df.index.min()),
        "end": str(df.index.max()),
        "initial_cash": config.initial_cash,
        "final_cash": cash,
        "total_return_pct": total_return,
        "max_drawdown_pct": max_drawdown,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": win_rate,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "sample_trades": trades[:5],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OB + FVG + Breakout confluence backtest")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--cash", type=float, default=10_000.0)
    parser.add_argument("--rr", type=float, default=2.0)
    parser.add_argument("--risk", type=float, default=0.01)
    parser.add_argument("--lookback", type=int, default=15)
    parser.add_argument("--ema", type=int, default=30)
    args = parser.parse_args()

    cfg = ConfluenceConfig(
        initial_cash=args.cash,
        risk_reward=args.rr,
        risk_pct=args.risk,
        breakout_lookback=args.lookback,
        ema_period=args.ema,
    )
    results = run_backtest(args.csv, cfg)
    print_report(results)
