"""
Order Block + Fair Value Gap Strategy — Backtrader Backtest
===========================================================

SECTION 1: Strategy Summary
----------------------------
- Detects Fair Value Gaps (FVG) in 3-candle patterns
- Identifies Order Blocks (OB) as the candle before the explosive move
- Entry at 50% retracement into the Order Block zone
- Trend filter: EMA-50 (only trade with trend)
- Volatility filter: ATR-14 must be above 50% of average ATR
- Stop Loss: Below OB low (bullish) / Above OB high (bearish)
- Take Profit: 1:2 Risk-Reward ratio
- Timeframe: 15-minute candles

SECTION 2: Clean Trading Rules
--------------------------------
BUY:
  1. Detect bullish FVG: candle[1] body_ratio >= 0.6, candle[1] is bullish
     gap = candle[2].low > candle[0].high
  2. Order Block = candle[0] (high/low/midpoint)
  3. Price must be above EMA-50 (trend filter)
  4. ATR >= 50% of average ATR (volatility filter)
  5. Entry: price retraces to OB zone (OB.low to OB.midpoint)
     AND current close > OB.midpoint (confirmation)
  6. SL = OB.low - 10% of OB range
  7. TP = entry + (entry - SL) * 2.0

SELL:
  1. Detect bearish FVG: candle[1] body_ratio >= 0.6, candle[1] is bearish
     gap = candle[0].low > candle[2].high
  2. Order Block = candle[0] (high/low/midpoint)
  3. Price must be below EMA-50 (trend filter)
  4. ATR >= 50% of average ATR (volatility filter)
  5. Entry: price retraces to OB zone (OB.midpoint to OB.high)
     AND current close < OB.midpoint (confirmation)
  6. SL = OB.high + 10% of OB range
  7. TP = entry - (SL - entry) * 2.0

SECTION 3: Assumptions Made
-----------------------------
- FVG explosive candle body_ratio threshold: 0.6 (60% of candle range is body)
- OB invalidated if price closes beyond OB boundary before entry
- Max 1 open position at a time
- Starting capital: $10,000
- Commission: 0.0001 (1 pip per side, typical forex spread)
- Position size: 1% risk per trade
- Data: MT5 XAUUSD M15 (or CSV fallback for offline testing)

Run:
  python -m bot.algo.backtest                    # uses MT5 live data
  python -m bot.algo.backtest --csv data.csv     # uses CSV file
  python -m bot.algo.backtest --plot             # show chart
"""

from __future__ import annotations

import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

import backtrader as bt
import backtrader.analyzers as btanalyzers
import pandas as pd


# ── Strategy ──────────────────────────────────────────────────────────────────

class OrderBlockStrategy(bt.Strategy):
    """
    Order Block + Fair Value Gap strategy implemented in Backtrader.
    """

    params = (
        ("fvg_body_ratio", 0.6),      # min body/range ratio for explosive candle
        ("ema_period", 50),            # EMA period for trend filter
        ("atr_period", 14),            # ATR period for volatility filter
        ("atr_min_ratio", 0.5),        # min ATR as fraction of average ATR
        ("risk_reward", 2.0),          # take profit R:R ratio
        ("risk_pct", 0.01),            # risk 1% of portfolio per trade
        ("ob_lookback", 3),            # candles to look back for OB detection
        ("max_ob_age", 20),            # max candles an OB stays active
        ("sl_buffer", 0.1),            # SL buffer beyond OB boundary (10% of OB range)
        ("verbose", True),             # print trade details
    )

    def __init__(self):
        # Indicators
        self.ema = bt.indicators.EMA(self.data.close, period=self.p.ema_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)

        # Track active order blocks: list of dicts
        self.active_obs = []

        # Trade tracking
        self.order = None
        self.trade_sl = None   # stop loss price
        self.trade_tp = None   # take profit price
        self.trade_side = None # "buy" or "sell"

        # Stats
        self.trade_count = 0
        self.win_count = 0
        self.loss_count = 0
        self.total_pnl = 0.0

    def log(self, msg: str, dt=None):
        if self.p.verbose:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"[{dt}] {msg}")

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            if order.isbuy():
                self.log(
                    f"BUY EXECUTED | Price: {order.executed.price:.5f} | "
                    f"Size: {order.executed.size:.4f} | "
                    f"Cost: {order.executed.value:.2f} | "
                    f"Comm: {order.executed.comm:.4f}"
                )
            elif order.issell():
                self.log(
                    f"SELL EXECUTED | Price: {order.executed.price:.5f} | "
                    f"Size: {order.executed.size:.4f}"
                )

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"Order Canceled/Margin/Rejected: {order.status}")

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.trade_count += 1
        self.total_pnl += trade.pnl

        if trade.pnl > 0:
            self.win_count += 1
            result = "WIN"
        else:
            self.loss_count += 1
            result = "LOSS"

        self.log(
            f"TRADE CLOSED [{result}] | "
            f"PnL: {trade.pnl:.2f} | "
            f"Net PnL: {trade.pnlcomm:.2f} | "
            f"Total trades: {self.trade_count}"
        )
        # Reset SL/TP tracking
        self.trade_sl = None
        self.trade_tp = None
        self.trade_side = None

    def _detect_fvg(self, idx: int):
        """
        Detect FVG at position idx (idx=0 is current, idx=-1 is previous, etc.)
        Returns (direction, ob_high, ob_low, fvg_top, fvg_bottom) or None
        """
        # Need at least 3 candles: c1=idx-2, c2=idx-1, c3=idx
        if len(self.data) < 3:
            return None

        # c1 = 2 bars ago, c2 = 1 bar ago, c3 = current
        c1_high = self.data.high[-2]
        c1_low = self.data.low[-2]
        c1_open = self.data.open[-2]
        c1_close = self.data.close[-2]

        c2_high = self.data.high[-1]
        c2_low = self.data.low[-1]
        c2_open = self.data.open[-1]
        c2_close = self.data.close[-1]

        c3_high = self.data.high[0]
        c3_low = self.data.low[0]

        # Check if c2 is explosive
        c2_body = abs(c2_close - c2_open)
        c2_range = c2_high - c2_low
        if c2_range == 0:
            return None
        c2_body_ratio = c2_body / c2_range

        if c2_body_ratio < self.p.fvg_body_ratio:
            return None

        ob_high = c1_high
        ob_low = c1_low
        ob_mid = (ob_high + ob_low) / 2

        if c2_close > c2_open:  # bullish explosive candle
            # Bullish FVG: gap between c1.high and c3.low
            fvg_bottom = c1_high
            fvg_top = c3_low
            if fvg_top > fvg_bottom:
                return {
                    "direction": "bullish",
                    "ob_high": ob_high,
                    "ob_low": ob_low,
                    "ob_mid": ob_mid,
                    "fvg_top": fvg_top,
                    "fvg_bottom": fvg_bottom,
                    "age": 0,
                    "bar": len(self.data),
                }

        elif c2_close < c2_open:  # bearish explosive candle
            # Bearish FVG: gap between c1.low and c3.high
            fvg_top = c1_low
            fvg_bottom = c3_high
            if fvg_top > fvg_bottom:
                return {
                    "direction": "bearish",
                    "ob_high": ob_high,
                    "ob_low": ob_low,
                    "ob_mid": ob_mid,
                    "fvg_top": fvg_top,
                    "fvg_bottom": fvg_bottom,
                    "age": 0,
                    "bar": len(self.data),
                }

        return None

    def _calculate_size(self, entry: float, sl: float) -> float:
        """Calculate position size based on risk %."""
        portfolio_value = self.broker.getvalue()
        risk_amount = portfolio_value * self.p.risk_pct
        sl_distance = abs(entry - sl)
        if sl_distance == 0:
            return 0.01
        size = risk_amount / sl_distance
        return max(0.01, size)

    def next(self):
        # Skip if order pending
        if self.order:
            return

        current_price = self.data.close[0]
        current_bar = len(self.data)

        # ── Manage open position SL/TP ─────────────────────────────────────────
        if self.position and self.trade_sl is not None:
            if self.trade_side == "buy":
                if self.data.low[0] <= self.trade_sl:
                    self.log(f"SL HIT (BUY) | Price: {self.data.low[0]:.5f} | SL: {self.trade_sl:.5f}")
                    self.order = self.close()
                    return
                if self.data.high[0] >= self.trade_tp:
                    self.log(f"TP HIT (BUY) | Price: {self.data.high[0]:.5f} | TP: {self.trade_tp:.5f}")
                    self.order = self.close()
                    return
            elif self.trade_side == "sell":
                if self.data.high[0] >= self.trade_sl:
                    self.log(f"SL HIT (SELL) | Price: {self.data.high[0]:.5f} | SL: {self.trade_sl:.5f}")
                    self.order = self.close()
                    return
                if self.data.low[0] <= self.trade_tp:
                    self.log(f"TP HIT (SELL) | Price: {self.data.low[0]:.5f} | TP: {self.trade_tp:.5f}")
                    self.order = self.close()
                    return
            return  # still in trade, wait

        # ── Detect new Order Blocks ────────────────────────────────────────────
        ob = self._detect_fvg(0)
        if ob:
            # Apply trend filter
            trend_ok = False
            if ob["direction"] == "bullish" and current_price > self.ema[0]:
                trend_ok = True
            elif ob["direction"] == "bearish" and current_price < self.ema[0]:
                trend_ok = True

            # Apply volatility filter
            atr_vals = [self.atr[-i] for i in range(min(self.p.atr_period, len(self.atr)))]
            avg_atr = sum(atr_vals) / len(atr_vals) if atr_vals else self.atr[0]
            vol_ok = self.atr[0] >= avg_atr * self.p.atr_min_ratio

            if trend_ok and vol_ok:
                self.active_obs.append(ob)
                self.log(
                    f"New {ob['direction'].upper()} OB detected | "
                    f"Zone: {ob['ob_low']:.5f}-{ob['ob_high']:.5f} | "
                    f"50%: {ob['ob_mid']:.5f}"
                )

        # ── Age out old OBs ────────────────────────────────────────────────────
        self.active_obs = [
            o for o in self.active_obs
            if (current_bar - o["bar"]) <= self.p.max_ob_age
        ]

        # ── Check entry signals (only if no position) ──────────────────────────
        if not self.position:
            for ob in self.active_obs[:]:
                direction = ob["direction"]
                ob_high = ob["ob_high"]
                ob_low = ob["ob_low"]
                ob_mid = ob["ob_mid"]

                # Invalidate if price blew through OB
                if direction == "bullish" and current_price < ob_low:
                    self.active_obs.remove(ob)
                    continue
                if direction == "bearish" and current_price > ob_high:
                    self.active_obs.remove(ob)
                    continue

                prev_price = self.data.close[-1]

                if direction == "bullish":
                    in_zone = self.data.low[0] <= ob_mid and self.data.low[0] >= ob_low
                    confirmed = current_price > ob_mid and prev_price <= ob_mid

                    if in_zone and confirmed:
                        entry = current_price
                        sl_buffer = (ob_high - ob_low) * self.p.sl_buffer
                        sl = ob_low - sl_buffer
                        tp = entry + (entry - sl) * self.p.risk_reward
                        size = self._calculate_size(entry, sl)

                        self.log(
                            f"BUY SIGNAL | Entry: {entry:.5f} | "
                            f"SL: {sl:.5f} | TP: {tp:.5f} | "
                            f"Size: {size:.4f} | R:R 1:{self.p.risk_reward}"
                        )

                        self.trade_sl = sl
                        self.trade_tp = tp
                        self.trade_side = "buy"
                        self.order = self.buy(size=size)
                        self.active_obs.remove(ob)
                        break

                elif direction == "bearish":
                    in_zone = self.data.high[0] >= ob_mid and self.data.high[0] <= ob_high
                    confirmed = current_price < ob_mid and prev_price >= ob_mid

                    if in_zone and confirmed:
                        entry = current_price
                        sl_buffer = (ob_high - ob_low) * self.p.sl_buffer
                        sl = ob_high + sl_buffer
                        tp = entry - (sl - entry) * self.p.risk_reward
                        size = self._calculate_size(entry, sl)

                        self.log(
                            f"SELL SIGNAL | Entry: {entry:.5f} | "
                            f"SL: {sl:.5f} | TP: {tp:.5f} | "
                            f"Size: {size:.4f} | R:R 1:{self.p.risk_reward}"
                        )

                        self.trade_sl = sl
                        self.trade_tp = tp
                        self.trade_side = "sell"
                        self.order = self.sell(size=size)
                        self.active_obs.remove(ob)
                        break

    def stop(self):
        win_rate = (self.win_count / self.trade_count * 100) if self.trade_count > 0 else 0
        print("\n" + "=" * 60)
        print("  BACKTEST RESULTS — Order Block Strategy")
        print("=" * 60)
        print(f"  Total Trades:     {self.trade_count}")
        print(f"  Wins:             {self.win_count}")
        print(f"  Losses:           {self.loss_count}")
        print(f"  Win Rate:         {win_rate:.1f}%")
        print(f"  Total PnL:        {self.total_pnl:.2f}")
        print(f"  Final Portfolio:  {self.broker.getvalue():.2f}")
        print("=" * 60)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_mt5_data(symbol: str = "XAUUSD", days: int = 90) -> Optional[pd.DataFrame]:
    """Fetch historical data from MT5."""
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            print("MT5 initialize failed")
            return None

        from_date = datetime.now() - timedelta(days=days)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, from_date, datetime.now())
        mt5.shutdown()

        if rates is None or len(rates) == 0:
            print(f"No data returned for {symbol}")
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        df.rename(columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "tick_volume": "Volume",
        }, inplace=True)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        print(f"Loaded {len(df)} candles from MT5 ({symbol} M15, last {days} days)")
        return df

    except ImportError:
        print("MetaTrader5 not available")
        return None
    except Exception as e:
        print(f"MT5 data load error: {e}")
        return None


def generate_sample_data(n: int = 2000) -> pd.DataFrame:
    """
    Generate synthetic XAUUSD-like price data for offline testing.
    Uses random walk with realistic gold price characteristics.
    """
    import numpy as np
    np.random.seed(42)

    dates = pd.date_range(start="2024-01-01", periods=n, freq="15min")
    price = 2000.0
    prices = []

    for i in range(n):
        # Random walk with slight upward drift
        change = np.random.normal(0.02, 0.8)
        price = max(1800, min(2500, price + change))
        prices.append(price)

    prices = pd.Series(prices)

    # Build OHLCV
    opens = prices.copy()
    closes = prices + pd.Series(np.random.normal(0, 0.3, n))
    highs = pd.concat([opens, closes], axis=1).max(axis=1) + abs(pd.Series(np.random.normal(0, 0.5, n)))
    lows = pd.concat([opens, closes], axis=1).min(axis=1) - abs(pd.Series(np.random.normal(0, 0.5, n)))
    volumes = pd.Series(np.random.randint(100, 1000, n), dtype=float)

    df = pd.DataFrame({
        "Open": opens.values,
        "High": highs.values,
        "Low": lows.values,
        "Close": closes.values,
        "Volume": volumes.values,
    }, index=dates)

    print(f"Generated {len(df)} synthetic candles for offline testing")
    return df


# ── Main runner ───────────────────────────────────────────────────────────────

def run_backtest(
    symbol: str = "XAUUSD",
    days: int = 90,
    initial_cash: float = 10000.0,
    commission: float = 0.0001,
    risk_reward: float = 2.0,
    risk_pct: float = 0.01,
    fvg_body_ratio: float = 0.6,
    ema_period: int = 50,
    csv_file: Optional[str] = None,
    show_plot: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Run the Order Block backtest.

    Returns dict with performance metrics.
    """
    print("\n" + "=" * 60)
    print("  Order Block + FVG Strategy — Backtest")
    print(f"  Symbol: {symbol} | Timeframe: M15")
    print(f"  Capital: ${initial_cash:,.0f} | Risk/Trade: {risk_pct*100:.1f}%")
    print(f"  R:R: 1:{risk_reward} | FVG threshold: {fvg_body_ratio}")
    print("=" * 60 + "\n")

    # ── Load data ──────────────────────────────────────────────────────────────
    if csv_file and os.path.exists(csv_file):
        print(f"Loading data from CSV: {csv_file}")
        df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
        df.columns = [c.capitalize() for c in df.columns]
    else:
        df = load_mt5_data(symbol, days)
        if df is None:
            print("MT5 unavailable — using synthetic data for demonstration")
            df = generate_sample_data(2000)

    if df is None or len(df) < 100:
        print("ERROR: Not enough data to run backtest")
        return {}

    # ── Setup Backtrader ───────────────────────────────────────────────────────
    cerebro = bt.Cerebro()

    # Add strategy
    cerebro.addstrategy(
        OrderBlockStrategy,
        fvg_body_ratio=fvg_body_ratio,
        ema_period=ema_period,
        risk_reward=risk_reward,
        risk_pct=risk_pct,
        verbose=verbose,
    )

    # Add data feed
    data_feed = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data_feed)

    # Broker settings
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)

    # Analyzers
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.02)
    cerebro.addanalyzer(btanalyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(btanalyzers.Returns, _name="returns")
    cerebro.addanalyzer(btanalyzers.SQN, _name="sqn")

    # ── Run ────────────────────────────────────────────────────────────────────
    start_value = cerebro.broker.getvalue()
    print(f"Starting Portfolio Value: ${start_value:,.2f}")

    results = cerebro.run()
    strat = results[0]

    end_value = cerebro.broker.getvalue()
    total_return = ((end_value - start_value) / start_value) * 100

    # ── Extract analyzer results ───────────────────────────────────────────────
    sharpe = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trades = strat.analyzers.trades.get_analysis()
    sqn = strat.analyzers.sqn.get_analysis()

    total_trades = trades.get("total", {}).get("total", 0)
    won_trades = trades.get("won", {}).get("total", 0)
    lost_trades = trades.get("lost", {}).get("total", 0)
    win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0

    avg_win = trades.get("won", {}).get("pnl", {}).get("average", 0)
    avg_loss = trades.get("lost", {}).get("pnl", {}).get("average", 0)
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    max_dd = drawdown.get("max", {}).get("drawdown", 0)
    sharpe_ratio = sharpe.get("sharperatio", 0) or 0
    sqn_value = sqn.get("sqn", 0) or 0

    # ── Print results ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  PERFORMANCE REPORT")
    print("=" * 60)
    print(f"  Starting Capital:   ${start_value:>10,.2f}")
    print(f"  Final Portfolio:    ${end_value:>10,.2f}")
    print(f"  Total Return:       {total_return:>10.2f}%")
    print(f"  Max Drawdown:       {max_dd:>10.2f}%")
    print(f"  Sharpe Ratio:       {sharpe_ratio:>10.3f}")
    print(f"  SQN:                {sqn_value:>10.3f}")
    print("-" * 60)
    print(f"  Total Trades:       {total_trades:>10}")
    print(f"  Winning Trades:     {won_trades:>10}")
    print(f"  Losing Trades:      {lost_trades:>10}")
    print(f"  Win Rate:           {win_rate:>10.1f}%")
    print(f"  Avg Win:            ${avg_win:>10.2f}")
    print(f"  Avg Loss:           ${avg_loss:>10.2f}")
    print(f"  Profit Factor:      {profit_factor:>10.2f}")
    print("=" * 60)

    # SQN interpretation
    if sqn_value >= 2.0:
        rating = "GOOD"
    elif sqn_value >= 1.6:
        rating = "AVERAGE"
    elif sqn_value >= 1.0:
        rating = "BELOW AVERAGE"
    else:
        rating = "POOR"
    print(f"\n  Strategy Rating: {rating} (SQN: {sqn_value:.2f})")
    print("  (SQN >= 2.0 = Good, >= 1.6 = Average, < 1.0 = Poor)\n")

    metrics = {
        "start_value": start_value,
        "end_value": end_value,
        "total_return_pct": total_return,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": sharpe_ratio,
        "sqn": sqn_value,
        "total_trades": total_trades,
        "win_rate_pct": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "rating": rating,
    }

    # ── Plot ───────────────────────────────────────────────────────────────────
    if show_plot:
        try:
            cerebro.plot(style="candlestick", barup="green", bardown="red")
        except Exception as e:
            print(f"Plot error: {e}")

    return metrics


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Order Block + FVG Backtest")
    parser.add_argument("--symbol", default="XAUUSD", help="Trading symbol")
    parser.add_argument("--days", type=int, default=90, help="Days of history")
    parser.add_argument("--cash", type=float, default=10000.0, help="Starting capital")
    parser.add_argument("--rr", type=float, default=2.0, help="Risk:Reward ratio")
    parser.add_argument("--risk", type=float, default=0.01, help="Risk per trade (0.01 = 1%)")
    parser.add_argument("--fvg", type=float, default=0.6, help="FVG body ratio threshold")
    parser.add_argument("--ema", type=int, default=50, help="EMA period for trend filter")
    parser.add_argument("--csv", default=None, help="Path to CSV data file")
    parser.add_argument("--plot", action="store_true", help="Show chart")
    parser.add_argument("--quiet", action="store_true", help="Suppress trade logs")

    args = parser.parse_args()

    run_backtest(
        symbol=args.symbol,
        days=args.days,
        initial_cash=args.cash,
        risk_reward=args.rr,
        risk_pct=args.risk,
        fvg_body_ratio=args.fvg,
        ema_period=args.ema,
        csv_file=args.csv,
        show_plot=args.plot,
        verbose=not args.quiet,
    )
