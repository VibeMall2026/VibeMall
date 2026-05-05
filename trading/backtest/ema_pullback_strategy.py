"""
EMA Pullback Forex Strategy — Backtrader Implementation
=======================================================
Strategy: Trend-following pullback with R-multiple trailing stop
Author: Professional Quant System
"""

import backtrader as bt
import backtrader.indicators as btind
import datetime
import math


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM INDICATORS
# ─────────────────────────────────────────────────────────────────────────────

class SessionFilter(bt.Indicator):
    """
    Returns 1 during London (07:00–16:00 UTC) or NY (12:00–21:00 UTC) sessions.
    """
    lines = ('in_session',)
    plotinfo = dict(plot=False)

    def next(self):
        hour = self.data.datetime.time(0).hour
        london = 7 <= hour < 16
        new_york = 12 <= hour < 21
        self.lines.in_session[0] = 1.0 if (london or new_york) else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# MAIN STRATEGY
# ─────────────────────────────────────────────────────────────────────────────

class EMAPullbackStrategy(bt.Strategy):
    """
    Professional EMA Pullback Strategy with R-Multiple Trailing Stop.

    Parameters
    ----------
    ema_fast      : Fast EMA period (default 50)
    ema_slow      : Slow EMA period (default 200)
    rsi_period    : RSI period (default 14)
    atr_period    : ATR period (default 14)
    atr_threshold : Minimum ATR as fraction of price (default 0.0003 = 3 pips on 1.0 price)
    risk_pct      : Risk per trade as fraction of equity (default 0.01 = 1%)
    rr_breakeven  : R-multiple to move SL to breakeven (default 1.0)
    rr_lock       : R-multiple to lock in profit (default 2.0)
    trail_atr_mult: ATR multiplier for trailing stop beyond 2R (default 1.0)
    sl_atr_mult   : ATR multiplier for initial stop loss (default 1.5)
    pullback_atr  : Max distance from EMA50 for pullback entry (default 1.5 ATR)
    rsi_buy_max   : RSI threshold for buy entry (default 40)
    rsi_sell_min  : RSI threshold for sell entry (default 60)
    cooldown_bars : Bars to wait after trade close (default 5)
    daily_profit_limit : Stop trading if daily profit >= this (default 50.0)
    max_drawdown_pct   : Stop trading if drawdown >= this fraction (default 0.10)
    spread_pips   : Simulated spread in pips (default 2)
    pip_value     : Value of 1 pip (default 0.0001 for most pairs)
    """

    params = dict(
        ema_fast=50,
        ema_slow=200,
        rsi_period=14,
        atr_period=14,
        atr_threshold=0.0003,
        risk_pct=0.01,
        rr_breakeven=1.0,
        rr_lock=2.0,
        trail_atr_mult=1.0,
        sl_atr_mult=1.5,
        pullback_atr=1.5,
        rsi_buy_max=40,
        rsi_sell_min=60,
        cooldown_bars=5,
        daily_profit_limit=50.0,
        max_drawdown_pct=0.10,
        spread_pips=2,
        pip_value=0.0001,
    )

    def __init__(self):
        # ── Indicators ────────────────────────────────────────────────────────
        self.ema50  = btind.EMA(self.data.close, period=self.p.ema_fast)
        self.ema200 = btind.EMA(self.data.close, period=self.p.ema_slow)
        self.rsi    = btind.RSI(self.data.close, period=self.p.rsi_period)
        self.atr    = btind.ATR(self.data, period=self.p.atr_period)
        self.session = SessionFilter(self.data)

        # ── State variables ───────────────────────────────────────────────────
        self.order          = None      # pending order reference
        self.trade_open     = False
        self.entry_price    = 0.0
        self.stop_price     = 0.0
        self.one_r          = 0.0       # 1R distance
        self.trade_side     = None      # 'buy' or 'sell'
        self.r_stage        = 0         # 0=initial, 1=breakeven, 2=locked, 3=trailing
        self.cooldown_count = 0         # bars since last trade close

        # ── Daily tracking ────────────────────────────────────────────────────
        self.daily_profit   = 0.0
        self.daily_date     = None
        self.trading_halted = False     # halted for the day

        # ── Drawdown tracking ─────────────────────────────────────────────────
        self.peak_equity    = self.broker.getvalue()
        self.dd_halted      = False     # halted permanently due to drawdown

        # ── Trade log ─────────────────────────────────────────────────────────
        self.trade_log = []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _spread(self):
        """Return spread cost in price units."""
        return self.p.spread_pips * self.p.pip_value

    def _reset_daily_if_needed(self):
        """Reset daily profit counter at start of new day."""
        current_date = self.data.datetime.date(0)
        if self.daily_date != current_date:
            self.daily_date    = current_date
            self.daily_profit  = 0.0
            self.trading_halted = False  # reset daily halt

    def _check_drawdown(self):
        """Halt trading permanently if drawdown exceeds threshold."""
        equity = self.broker.getvalue()
        if equity > self.peak_equity:
            self.peak_equity = equity
        drawdown = (self.peak_equity - equity) / self.peak_equity
        if drawdown >= self.p.max_drawdown_pct:
            self.dd_halted = True
            self.log(f"⛔ MAX DRAWDOWN {drawdown:.1%} — trading halted permanently")

    def _can_trade(self):
        """Return True if all trading conditions allow a new entry."""
        if self.dd_halted:
            return False
        if self.trading_halted:
            return False
        if self.trade_open:
            return False
        if self.cooldown_count > 0:
            return False
        if not self.session.in_session[0]:
            return False
        return True

    def _position_size(self, entry, stop):
        """
        Calculate position size based on 1% risk model.
        size = (equity × risk_pct) / |entry - stop|
        """
        equity    = self.broker.getvalue()
        risk_amt  = equity * self.p.risk_pct
        sl_dist   = abs(entry - stop)
        if sl_dist == 0:
            return 0
        size = risk_amt / sl_dist
        # Round down to nearest integer lot (or fractional if broker allows)
        size = math.floor(size * 100) / 100  # 2 decimal places
        return max(size, 0.01)

    def _trend_strength_ok(self):
        """EMA separation must exceed 0.5 × ATR to avoid ranging markets."""
        gap = abs(self.ema50[0] - self.ema200[0])
        return gap > self.atr[0] * 0.5

    def _volatility_ok(self):
        """ATR must exceed minimum threshold."""
        return self.atr[0] > self.p.atr_threshold

    def _near_ema50(self, side):
        """Price must be within pullback_atr × ATR of EMA50."""
        dist = abs(self.data.close[0] - self.ema50[0])
        return dist <= self.atr[0] * self.p.pullback_atr

    def log(self, txt):
        dt = self.data.datetime.datetime(0)
        print(f"[{dt}] {txt}")

    # ── Order / Trade notifications ───────────────────────────────────────────

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status == order.Completed:
            if order.isbuy():
                self.log(f"BUY  EXEC @ {order.executed.price:.5f} | size={order.executed.size:.2f}")
            else:
                self.log(f"SELL EXEC @ {order.executed.price:.5f} | size={order.executed.size:.2f}")
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"Order FAILED: {order.status}")
        self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            pnl = trade.pnlcomm
            self.daily_profit += pnl
            self.trade_open    = False
            self.cooldown_count = self.p.cooldown_bars
            self.r_stage       = 0

            self.trade_log.append({
                'date':  self.data.datetime.datetime(0),
                'side':  self.trade_side,
                'pnl':   round(pnl, 2),
                'entry': self.entry_price,
                'exit':  trade.price,
            })

            self.log(f"TRADE CLOSED | PnL={pnl:.2f} | Daily={self.daily_profit:.2f}")

            if self.daily_profit >= self.p.daily_profit_limit:
                self.trading_halted = True
                self.log(f"✅ Daily profit limit ${self.p.daily_profit_limit} reached — halting for today")

    # ── Main logic ────────────────────────────────────────────────────────────

    def next(self):
        # ── Daily reset & drawdown check ──────────────────────────────────────
        self._reset_daily_if_needed()
        self._check_drawdown()

        # ── Cooldown countdown ────────────────────────────────────────────────
        if self.cooldown_count > 0:
            self.cooldown_count -= 1

        # ── Manage open trade (trailing stop) ─────────────────────────────────
        if self.trade_open and self.position:
            self._manage_trailing_stop()
            return

        # ── Check if we can enter ─────────────────────────────────────────────
        if not self._can_trade():
            return
        if not self._volatility_ok():
            return
        if not self._trend_strength_ok():
            return

        close = self.data.close[0]
        spread = self._spread()

        # ── BUY SETUP ─────────────────────────────────────────────────────────
        if (close > self.ema200[0]          # uptrend
                and self.ema50[0] > self.ema200[0]  # EMA alignment
                and self._near_ema50('buy')          # pullback to EMA50
                and self.rsi[0] < self.p.rsi_buy_max):  # RSI oversold

            entry = close + spread  # account for spread on buy
            stop  = entry - self.atr[0] * self.p.sl_atr_mult
            size  = self._position_size(entry, stop)
            if size <= 0:
                return

            self.entry_price = entry
            self.stop_price  = stop
            self.one_r       = entry - stop
            self.trade_side  = 'buy'
            self.trade_open  = True
            self.r_stage     = 0

            self.order = self.buy(size=size)
            self.log(f"BUY SIGNAL | entry={entry:.5f} SL={stop:.5f} 1R={self.one_r:.5f} size={size:.2f}")

        # ── SELL SETUP ────────────────────────────────────────────────────────
        elif (close < self.ema200[0]         # downtrend
                and self.ema50[0] < self.ema200[0]  # EMA alignment
                and self._near_ema50('sell')          # pullback to EMA50
                and self.rsi[0] > self.p.rsi_sell_min):  # RSI overbought

            entry = close - spread  # account for spread on sell
            stop  = entry + self.atr[0] * self.p.sl_atr_mult
            size  = self._position_size(entry, stop)
            if size <= 0:
                return

            self.entry_price = entry
            self.stop_price  = stop
            self.one_r       = stop - entry
            self.trade_side  = 'sell'
            self.trade_open  = True
            self.r_stage     = 0

            self.order = self.sell(size=size)
            self.log(f"SELL SIGNAL | entry={entry:.5f} SL={stop:.5f} 1R={self.one_r:.5f} size={size:.2f}")

    def _manage_trailing_stop(self):
        """
        R-Multiple trailing stop management.
        Stage 0 → 1: At +1R, move SL to breakeven
        Stage 1 → 2: At +2R, move SL to +1R (lock profit)
        Stage 2 → 3: Beyond +2R, trail by ATR × trail_atr_mult
        """
        close = self.data.close[0]

        if self.trade_side == 'buy':
            profit_r = (close - self.entry_price) / self.one_r if self.one_r > 0 else 0

            if profit_r >= self.p.rr_lock and self.r_stage < 2:
                # Lock in +1R profit
                new_sl = self.entry_price + self.one_r
                if new_sl > self.stop_price:
                    self.stop_price = new_sl
                    self.r_stage = 2
                    self.log(f"SL LOCKED +1R @ {new_sl:.5f}")

            elif profit_r >= self.p.rr_breakeven and self.r_stage < 1:
                # Move to breakeven
                new_sl = self.entry_price
                if new_sl > self.stop_price:
                    self.stop_price = new_sl
                    self.r_stage = 1
                    self.log(f"SL BREAKEVEN @ {new_sl:.5f}")

            if self.r_stage >= 2:
                # Trail dynamically
                trail_sl = close - self.atr[0] * self.p.trail_atr_mult
                if trail_sl > self.stop_price:
                    self.stop_price = trail_sl
                    self.r_stage = 3

            # Check if stop hit
            if close <= self.stop_price:
                self.log(f"STOP HIT (buy) @ {close:.5f} SL={self.stop_price:.5f}")
                self.close()

        elif self.trade_side == 'sell':
            profit_r = (self.entry_price - close) / self.one_r if self.one_r > 0 else 0

            if profit_r >= self.p.rr_lock and self.r_stage < 2:
                new_sl = self.entry_price - self.one_r
                if new_sl < self.stop_price:
                    self.stop_price = new_sl
                    self.r_stage = 2
                    self.log(f"SL LOCKED +1R @ {new_sl:.5f}")

            elif profit_r >= self.p.rr_breakeven and self.r_stage < 1:
                new_sl = self.entry_price
                if new_sl < self.stop_price:
                    self.stop_price = new_sl
                    self.r_stage = 1
                    self.log(f"SL BREAKEVEN @ {new_sl:.5f}")

            if self.r_stage >= 2:
                trail_sl = close + self.atr[0] * self.p.trail_atr_mult
                if trail_sl < self.stop_price:
                    self.stop_price = trail_sl
                    self.r_stage = 3

            # Check if stop hit
            if close >= self.stop_price:
                self.log(f"STOP HIT (sell) @ {close:.5f} SL={self.stop_price:.5f}")
                self.close()

    def stop(self):
        """Print final summary."""
        final_value = self.broker.getvalue()
        print("\n" + "="*60)
        print("BACKTEST COMPLETE")
        print(f"  Final Portfolio Value : ${final_value:,.2f}")
        print(f"  Total Trades          : {len(self.trade_log)}")
        wins   = [t for t in self.trade_log if t['pnl'] > 0]
        losses = [t for t in self.trade_log if t['pnl'] <= 0]
        print(f"  Wins                  : {len(wins)}")
        print(f"  Losses                : {len(losses)}")
        if self.trade_log:
            wr = len(wins) / len(self.trade_log) * 100
            print(f"  Win Rate              : {wr:.1f}%")
            total_pnl = sum(t['pnl'] for t in self.trade_log)
            print(f"  Total PnL             : ${total_pnl:,.2f}")
        print("="*60)


# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(
    csv_file: str,
    initial_cash: float = 10_000.0,
    commission: float = 0.00005,   # 0.5 pip commission per side
    plot: bool = True,
):
    """
    Run the EMA Pullback backtest.

    Parameters
    ----------
    csv_file     : Path to OHLCV CSV (columns: datetime, open, high, low, close, volume)
    initial_cash : Starting account balance
    commission   : Commission as fraction of trade value
    plot         : Whether to show Backtrader plot
    """
    cerebro = bt.Cerebro()

    # ── Data feed ─────────────────────────────────────────────────────────────
    data = bt.feeds.GenericCSVData(
        dataname=csv_file,
        dtformat='%Y-%m-%d %H:%M:%S',
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        timeframe=bt.TimeFrame.Minutes,
        compression=60,   # 1-hour bars
    )
    cerebro.adddata(data)

    # ── Strategy ──────────────────────────────────────────────────────────────
    cerebro.addstrategy(EMAPullbackStrategy)

    # ── Broker ────────────────────────────────────────────────────────────────
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)
    cerebro.broker.set_slippage_perc(0.0001)  # 1 pip slippage

    # ── Analyzers ─────────────────────────────────────────────────────────────
    cerebro.addanalyzer(bt.analyzers.SharpeRatio,  _name='sharpe',  riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.DrawDown,     _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer,_name='trades')
    cerebro.addanalyzer(bt.analyzers.Returns,      _name='returns')

    print(f"Starting Portfolio Value: ${cerebro.broker.getvalue():,.2f}")

    results = cerebro.run()
    strat   = results[0]

    # ── Print analyzer results ────────────────────────────────────────────────
    sharpe   = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trades   = strat.analyzers.trades.get_analysis()

    print("\n📊 PERFORMANCE METRICS")
    print(f"  Sharpe Ratio     : {sharpe.get('sharperatio', 'N/A')}")
    print(f"  Max Drawdown     : {drawdown.max.drawdown:.2f}%")
    print(f"  Max DD Duration  : {drawdown.max.len} bars")

    total = trades.get('total', {})
    won   = trades.get('won',   {})
    lost  = trades.get('lost',  {})
    print(f"  Total Trades     : {total.get('total', 0)}")
    print(f"  Won              : {won.get('total', 0)}")
    print(f"  Lost             : {lost.get('total', 0)}")
    if total.get('total', 0) > 0:
        wr = won.get('total', 0) / total.get('total', 1) * 100
        print(f"  Win Rate         : {wr:.1f}%")
    avg_win  = won.get('pnl',  {}).get('average', 0)
    avg_loss = lost.get('pnl', {}).get('average', 0)
    print(f"  Avg Win          : ${avg_win:.2f}")
    print(f"  Avg Loss         : ${avg_loss:.2f}")
    if avg_loss != 0:
        print(f"  Profit Factor    : {abs(avg_win / avg_loss):.2f}")

    if plot:
        cerebro.plot(style='candlestick', barup='green', bardown='red')

    return results


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    csv = sys.argv[1] if len(sys.argv) > 1 else 'EURUSD_H1.csv'
    run_backtest(
        csv_file=csv,
        initial_cash=10_000.0,
        commission=0.00005,
        plot=True,
    )
