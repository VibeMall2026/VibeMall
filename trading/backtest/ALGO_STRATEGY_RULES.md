# Order Block + Fair Value Gap (FVG) Algo Strategy — Rules

## Strategy Overview
ICT/Smart Money Concepts based algorithmic strategy running on XAUUSD (Gold).
- **Analysis Timeframe:** 15-minute candles (Order Block detection)
- **Execution Timeframe:** 5-minute candles (Entry confirmation)
- **Risk:Reward:** 1:2 minimum

---

## Rules Added to the Strategy

### 1. TREND IDENTIFICATION
- **EMA 50** calculated on analysis timeframe (15m)
- **BUY trades only** when price is **above EMA 50** (uptrend)
- **SELL trades only** when price is **below EMA 50** (downtrend)

### 2. FAIR VALUE GAP (FVG) DETECTION
3-candle pattern:
- Candle 2 must be **explosive** (body/range ratio ≥ 0.6)
- **Bullish FVG:** Gap between candle[1].high and candle[3].low
- **Bearish FVG:** Gap between candle[1].low and candle[3].high

### 3. ORDER BLOCK (OB) IDENTIFICATION
- OB = candle **before** the explosive FVG candle
- **Bullish OB:** high/low of that candle when followed by bullish FVG
- **Bearish OB:** high/low of that candle when followed by bearish FVG
- **Key level = 50% midpoint** of the order block

### 4. ENTRY RULES
**BUY Entry:**
- Price retraces into bullish OB zone (between OB low and OB midpoint)
- Last candle closes **above OB midpoint** (confirmation)
- Previous candle closed **at or below** OB midpoint

**SELL Entry:**
- Price retraces into bearish OB zone (between OB midpoint and OB high)
- Last candle closes **below OB midpoint** (confirmation)
- Previous candle closed **at or above** OB midpoint

### 5. VOLATILITY FILTER
- **ATR (14)** calculated on analysis timeframe
- Trade only when ATR is **above minimum threshold**
- Avoids trading in dead/choppy low-volatility markets

### 6. TREND STRENGTH FILTER
- EMA 50 and EMA 200 separation must be **> 0.5 × ATR**
- Prevents trading in ranging/sideways markets

### 7. OB INVALIDATION
- **Bullish OB invalidated** if price drops below OB low
- **Bearish OB invalidated** if price rises above OB high
- Invalidated OBs are removed from tracking

### 8. MAX ACTIVE ORDER BLOCKS
- Maximum **5 active OBs** tracked at once
- Oldest OBs removed when limit reached
- Only most recent OBs kept (sorted by time)

### 9. MAX OPEN POSITIONS
- Maximum **2 simultaneous algo positions**
- No new trades if 2 algo positions already open

### 10. POSITION SIZING (1% Risk Model)
```
size = (account_equity × 1%) / stop_loss_distance
```
- Risk exactly **1% of account balance** per trade
- Stop loss distance determines position size

### 11. STOP LOSS
- **Bullish trade SL:** OB low − (OB range × 10%) — just below OB
- **Bearish trade SL:** OB high + (OB range × 10%) — just above OB

### 12. TAKE PROFIT (R:R Based)
```
TP = entry + (SL_distance × risk_reward_ratio)
```
- Default **1:2 R:R** (configurable via API)
- TP = entry ± (|entry − SL| × 2.0)

### 13. TRADE COMMENT TAGGING
- All algo trades tagged with comment: `ALGO:OB:{ob_id[:8]}`
- Allows filtering algo trades from manual/telegram trades in history

### 14. OB RE-ENTRY LOGIC
- If an OB's position is **manually closed**, OB resets
- Allows re-entry on same OB zone if price returns
- Prevents missing re-entry opportunities

### 15. SCAN INTERVAL
- Strategy scans for new setups every **60 seconds**
- Runs in background thread (non-blocking)

### 16. ALGO ENABLE/DISABLE
- **Enabled mode:** Executes real trades
- **Disabled mode:** Scan only, no trade execution
- Controllable via dashboard (Enable/Disable Trading buttons)

---

## Risk Management Summary

| Parameter | Value |
|---|---|
| Risk per trade | 1% of equity |
| Max open positions | 2 |
| Min R:R ratio | 1:2 |
| SL placement | Below/above OB boundary |
| TP placement | 2× SL distance |

---

## API Endpoints (Configurable at Runtime)

| Endpoint | Action |
|---|---|
| `POST /algo/start` | Start algo thread |
| `POST /algo/stop` | Stop algo thread |
| `POST /algo/enable` | Enable live trading |
| `POST /algo/disable` | Scan only mode |
| `PUT /algo/config` | Update symbol, R:R, risk%, timeframes |
| `GET /algo/status` | View active OBs and config |
| `GET /algo/trades` | View all algo trade history |

---

## What Was Added vs Original Order Block Strategy

1. ✅ **EMA 50 trend filter** — only trade in trend direction
2. ✅ **ATR volatility filter** — avoid low-volatility periods
3. ✅ **Trend strength filter** — EMA separation check
4. ✅ **OB invalidation logic** — remove stale OBs
5. ✅ **Max position limit** — prevent overexposure
6. ✅ **1% risk position sizing** — professional risk management
7. ✅ **Trade comment tagging** — track algo trades separately
8. ✅ **OB re-entry after manual close** — flexible management
9. ✅ **Runtime config updates** — change params without restart
10. ✅ **Session-aware scanning** — 60s interval background thread
