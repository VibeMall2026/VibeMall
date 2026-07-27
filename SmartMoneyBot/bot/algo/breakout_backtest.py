"""
Breakout strategy backtest.

Designed to mirror the live breakout module as closely as practical while
remaining simple to run on CSV data.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass
class BacktestConfig:
    initial_cash: float = 10_000.0
    risk_pct: float = 0.01
    risk_reward: float = 2.0
    breakout_lookback: int = 20
    ema_period: int = 50
    atr_period: int = 14
    atr_min_multiplier: float = 0.6
    range_min_atr_multiplier: float = 1.2
    breakout_buffer_atr: float = 0.10
    retest_tolerance_atr: float = 0.15
    min_breakout_body_ratio: float = 0.55
    min_volume_multiplier: float = 1.20
    max_setup_age: int = 12
    sl_buffer_pct: float = 0.15


def load_csv(csv_file: str) -> pd.DataFrame:
    path = Path(csv_file)
    df = pd.read_csv(path)
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
        df = df.set_index("datetime")
    else:
        df.index = pd.to_datetime(df.index, utc=True)

    rename_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    df = df.rename(columns=rename_map)
    needed = ["Open", "High", "Low", "Close"]
    if "Volume" not in df.columns:
        df["Volume"] = 0.0
    df = df[needed + ["Volume"]].copy()
    return df.sort_index()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def run_backtest(csv_file: str, config: BacktestConfig) -> dict:
    df = load_csv(csv_file)
    if len(df) < max(config.ema_period, config.breakout_lookback) + 10:
        raise ValueError("Not enough rows for backtest")

    df["EMA"] = ema(df["Close"], config.ema_period)
    df["ATR"] = atr(df, config.atr_period)
    df["AVG_ATR"] = df["ATR"].rolling(config.atr_period).mean()
    df["AVG_VOL"] = df["Volume"].rolling(10).mean()
    df["BODY"] = (df["Close"] - df["Open"]).abs()
    df["RANGE"] = (df["High"] - df["Low"]).replace(0, pd.NA)
    df["BODY_RATIO"] = (df["BODY"] / df["RANGE"]).fillna(0.0)

    cash = config.initial_cash
    equity_curve: list[float] = []
    peak_equity = cash
    max_drawdown = 0.0

    setup: Optional[dict] = None
    trade: Optional[dict] = None
    trades: list[dict] = []

    start = max(config.ema_period, config.breakout_lookback, config.atr_period * 2)

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
                    exit_reason = "sl_tp_same_bar"
                    exit_price = trade["sl"]
                elif sl_hit:
                    exit_reason = "sl"
                    exit_price = trade["sl"]
                elif tp_hit:
                    exit_reason = "tp"
                    exit_price = trade["tp"]
            else:
                sl_hit = row["High"] >= trade["sl"]
                tp_hit = row["Low"] <= trade["tp"]
                if sl_hit and tp_hit:
                    exit_reason = "sl_tp_same_bar"
                    exit_price = trade["sl"]
                elif sl_hit:
                    exit_reason = "sl"
                    exit_price = trade["sl"]
                elif tp_hit:
                    exit_reason = "tp"
                    exit_price = trade["tp"]

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

        if trade is None and setup is not None:
            if i - setup["index"] > config.max_setup_age:
                setup = None
            else:
                tolerance = (row["ATR"] if pd.notna(row["ATR"]) else setup["range_size"]) * config.retest_tolerance_atr
                if setup["direction"] == "bullish":
                    touched = row["Low"] <= setup["breakout_level"] + tolerance
                    confirmed = row["Close"] > setup["breakout_level"] and row["Close"] >= df.iloc[i - 1]["Close"]
                    invalidated = row["Close"] < setup["range_low"]
                    if invalidated:
                        setup = None
                    elif touched and confirmed:
                        entry = row["Close"]
                        sl = setup["range_low"] - setup["range_size"] * config.sl_buffer_pct
                        risk_per_unit = entry - sl
                        if risk_per_unit > 0:
                            risk_amount = cash * config.risk_pct
                            size = risk_amount / risk_per_unit
                            trade = {
                                "side": "buy",
                                "entry_time": timestamp,
                                "entry": entry,
                                "sl": sl,
                                "tp": entry + risk_per_unit * config.risk_reward,
                                "size": size,
                            }
                            setup = None
                else:
                    touched = row["High"] >= setup["breakout_level"] - tolerance
                    confirmed = row["Close"] < setup["breakout_level"] and row["Close"] <= df.iloc[i - 1]["Close"]
                    invalidated = row["Close"] > setup["range_high"]
                    if invalidated:
                        setup = None
                    elif touched and confirmed:
                        entry = row["Close"]
                        sl = setup["range_high"] + setup["range_size"] * config.sl_buffer_pct
                        risk_per_unit = sl - entry
                        if risk_per_unit > 0:
                            risk_amount = cash * config.risk_pct
                            size = risk_amount / risk_per_unit
                            trade = {
                                "side": "sell",
                                "entry_time": timestamp,
                                "entry": entry,
                                "sl": sl,
                                "tp": entry - risk_per_unit * config.risk_reward,
                                "size": size,
                            }
                            setup = None

        if trade is None:
            if pd.isna(row["ATR"]) or pd.isna(row["AVG_ATR"]) or pd.isna(row["EMA"]):
                equity_curve.append(cash)
                continue

            window = df.iloc[i - config.breakout_lookback:i]
            range_high = window["High"].max()
            range_low = window["Low"].min()
            range_size = range_high - range_low

            if range_size <= 0:
                equity_curve.append(cash)
                continue
            if range_size < row["ATR"] * config.range_min_atr_multiplier:
                equity_curve.append(cash)
                continue
            if row["ATR"] < row["AVG_ATR"] * config.atr_min_multiplier:
                equity_curve.append(cash)
                continue

            avg_vol = row["AVG_VOL"]
            volume_ok = True if pd.isna(avg_vol) or avg_vol <= 0 else row["Volume"] >= avg_vol * config.min_volume_multiplier
            body_ok = row["BODY_RATIO"] >= config.min_breakout_body_ratio
            buffer = row["ATR"] * config.breakout_buffer_atr

            if (
                row["Close"] > row["EMA"]
                and row["Close"] > range_high + buffer
                and row["Close"] > row["Open"]
                and body_ok
                and volume_ok
            ):
                setup = {
                    "index": i,
                    "direction": "bullish",
                    "breakout_level": range_high,
                    "range_high": range_high,
                    "range_low": range_low,
                    "range_size": range_size,
                }
            elif (
                row["Close"] < row["EMA"]
                and row["Close"] < range_low - buffer
                and row["Close"] < row["Open"]
                and body_ok
                and volume_ok
            ):
                setup = {
                    "index": i,
                    "direction": "bearish",
                    "breakout_level": range_low,
                    "range_high": range_high,
                    "range_low": range_low,
                    "range_size": range_size,
                }

        marked_equity = cash
        if trade is not None:
            if trade["side"] == "buy":
                marked_equity += (row["Close"] - trade["entry"]) * trade["size"]
            else:
                marked_equity += (trade["entry"] - row["Close"]) * trade["size"]
        equity_curve.append(marked_equity)
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


def print_report(metrics: dict) -> None:
    print("\n" + "=" * 60)
    print("  BREAKOUT STRATEGY BACKTEST")
    print("=" * 60)
    print(f"  Data:              {metrics['csv_file']}")
    print(f"  Bars:              {metrics['bars']}")
    print(f"  Period:            {metrics['start']} -> {metrics['end']}")
    print("-" * 60)
    print(f"  Starting Capital:  ${metrics['initial_cash']:,.2f}")
    print(f"  Final Capital:     ${metrics['final_cash']:,.2f}")
    print(f"  Total Return:      {metrics['total_return_pct']:.2f}%")
    print(f"  Max Drawdown:      {metrics['max_drawdown_pct']:.2f}%")
    print("-" * 60)
    print(f"  Total Trades:      {metrics['total_trades']}")
    print(f"  Wins / Losses:     {metrics['wins']} / {metrics['losses']}")
    print(f"  Win Rate:          {metrics['win_rate_pct']:.2f}%")
    print(f"  Profit Factor:     {metrics['profit_factor']:.2f}")
    print(f"  Avg Win:           ${metrics['avg_win']:.2f}")
    print(f"  Avg Loss:          ${metrics['avg_loss']:.2f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Breakout strategy backtest")
    parser.add_argument("--csv", required=True, help="CSV file with OHLCV data")
    parser.add_argument("--cash", type=float, default=10_000.0)
    parser.add_argument("--rr", type=float, default=2.0)
    parser.add_argument("--risk", type=float, default=0.01)
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--ema", type=int, default=50)
    args = parser.parse_args()

    cfg = BacktestConfig(
        initial_cash=args.cash,
        risk_reward=args.rr,
        risk_pct=args.risk,
        breakout_lookback=args.lookback,
        ema_period=args.ema,
    )
    results = run_backtest(args.csv, cfg)
    print_report(results)
