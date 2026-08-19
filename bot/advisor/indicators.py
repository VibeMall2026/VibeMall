"""Technical indicator calculations for the XAUUSD Trade Advisor.

Every function takes plain OHLC candle data (list of dicts with
time/open/high/low/close/tick_volume, oldest first - the same shape
MT5's copy_rates_from_pos returns) and returns a small, explainable
result: a value plus a plain-language read. No numpy dependency, kept
consistent with the plain-list style already used in
bot/algo/signal_forge.py and bot/algo/smart_money.py.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


# ── Basic series helpers ─────────────────────────────────────────────────────

def closes(candles: list[dict]) -> list[float]:
    return [float(c["close"]) for c in candles]


def highs(candles: list[dict]) -> list[float]:
    return [float(c["high"]) for c in candles]


def lows(candles: list[dict]) -> list[float]:
    return [float(c["low"]) for c in candles]


def _ema_series(values: list[float], length: int) -> list[float]:
    if not values:
        return []
    k = 2.0 / (length + 1.0)
    out = [values[0]]
    for v in values[1:]:
        out.append((v * k) + (out[-1] * (1.0 - k)))
    return out


def _sma(values: list[float], length: int) -> float | None:
    if length <= 0 or len(values) < length:
        return None
    window = values[-length:]
    return sum(window) / len(window)


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


# ── Base indicators (1-6) ────────────────────────────────────────────────────

def ema_trend(candles: list[dict]) -> dict[str, Any]:
    """EMA 20/50/200 - is price aligned with the short/medium/long trend?"""
    c = closes(candles)
    if len(c) < 200:
        return {"available": False, "reason": "need 200+ candles"}
    ema20 = _ema_series(c, 20)[-1]
    ema50 = _ema_series(c, 50)[-1]
    ema200 = _ema_series(c, 200)[-1]
    price = c[-1]

    bullish_stack = price > ema20 > ema50 > ema200
    bearish_stack = price < ema20 < ema50 < ema200
    if bullish_stack:
        read = "bullish"
    elif bearish_stack:
        read = "bearish"
    elif price > ema200:
        read = "mixed_above_200"
    else:
        read = "mixed_below_200"

    return {
        "available": True,
        "ema20": round(ema20, 2), "ema50": round(ema50, 2), "ema200": round(ema200, 2),
        "price": round(price, 2), "read": read,
    }


def rsi(candles: list[dict], length: int = 14) -> dict[str, Any]:
    c = closes(candles)
    if len(c) < length + 2:
        return {"available": False, "reason": f"need {length + 2}+ candles"}
    gains, losses = [], []
    for i in range(1, len(c)):
        change = c[i] - c[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[-length:]) / length
    avg_loss = sum(losses[-length:]) / length
    rs = (avg_gain / avg_loss) if avg_loss > 0 else float("inf")
    value = 100.0 - (100.0 / (1.0 + rs)) if avg_loss > 0 else 100.0

    if value >= 70:
        read = "overbought"
    elif value <= 30:
        read = "oversold"
    elif value >= 55:
        read = "bullish_momentum"
    elif value <= 45:
        read = "bearish_momentum"
    else:
        read = "neutral"
    return {"available": True, "value": round(value, 1), "read": read}


def macd(candles: list[dict], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, Any]:
    c = closes(candles)
    if len(c) < slow + signal:
        return {"available": False, "reason": f"need {slow + signal}+ candles"}
    ema_fast = _ema_series(c, fast)
    ema_slow = _ema_series(c, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = _ema_series(macd_line, signal)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]

    hist_now, hist_prev = histogram[-1], histogram[-2] if len(histogram) > 1 else histogram[-1]
    crossed_bullish = histogram[-2] <= 0 < histogram[-1] if len(histogram) > 1 else False
    crossed_bearish = histogram[-2] >= 0 > histogram[-1] if len(histogram) > 1 else False
    growing = abs(hist_now) > abs(hist_prev)

    if crossed_bullish:
        read = "bullish_crossover"
    elif crossed_bearish:
        read = "bearish_crossover"
    elif hist_now > 0:
        read = "bullish_strengthening" if growing else "bullish_fading"
    else:
        read = "bearish_strengthening" if growing else "bearish_fading"

    return {
        "available": True,
        "macd": round(macd_line[-1], 4), "signal": round(signal_line[-1], 4),
        "histogram": round(hist_now, 4), "read": read,
    }


def atr(candles: list[dict], length: int = 14) -> dict[str, Any]:
    h, l, c = highs(candles), lows(candles), closes(candles)
    if len(c) < length + 1:
        return {"available": False, "reason": f"need {length + 1}+ candles"}
    trs = []
    for i in range(1, len(c)):
        trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    value = sum(trs[-length:]) / length
    return {"available": True, "value": round(value, 3)}


def bollinger_bands(candles: list[dict], length: int = 20, mult: float = 2.0) -> dict[str, Any]:
    c = closes(candles)
    if len(c) < length:
        return {"available": False, "reason": f"need {length}+ candles"}
    window = c[-length:]
    mid = sum(window) / length
    sd = _stdev(window)
    upper = mid + mult * sd
    lower = mid - mult * sd
    price = c[-1]

    band_width = upper - lower
    position_pct = ((price - lower) / band_width * 100.0) if band_width > 0 else 50.0
    if price >= upper:
        read = "at_or_above_upper"
    elif price <= lower:
        read = "at_or_below_lower"
    else:
        read = "inside"
    return {
        "available": True, "upper": round(upper, 2), "mid": round(mid, 2), "lower": round(lower, 2),
        "position_pct": round(position_pct, 1), "read": read,
    }


def swing_high_low(candles: list[dict], lookback: int = 30) -> dict[str, Any]:
    if len(candles) < lookback:
        return {"available": False, "reason": f"need {lookback}+ candles"}
    window = candles[-lookback:]
    swing_high = max(float(x["high"]) for x in window)
    swing_low = min(float(x["low"]) for x in window)
    return {"available": True, "swing_high": round(swing_high, 2), "swing_low": round(swing_low, 2), "lookback": lookback}


# ── New indicator 1: Candlestick pattern recognition ─────────────────────────

def _body(c: dict) -> float:
    return abs(float(c["close"]) - float(c["open"]))


def _range(c: dict) -> float:
    return float(c["high"]) - float(c["low"])


def _is_bullish(c: dict) -> bool:
    return float(c["close"]) > float(c["open"])


def candlestick_pattern(candles: list[dict]) -> dict[str, Any]:
    """Looks at the latest 3 candles for a recognizable pattern."""
    if len(candles) < 3:
        return {"available": False, "reason": "need 3+ candles"}
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]  # oldest -> newest of the 3

    rng3 = _range(c3)
    body3 = _body(c3)
    upper_wick3 = float(c3["high"]) - max(float(c3["open"]), float(c3["close"]))
    lower_wick3 = min(float(c3["open"]), float(c3["close"])) - float(c3["low"])

    # Doji: body is a tiny fraction of the range.
    if rng3 > 0 and body3 / rng3 < 0.1:
        return {"available": True, "pattern": "Doji", "bias": "neutral"}

    # Pin bar: one wick dominates the candle (rejection).
    if rng3 > 0 and body3 / rng3 < 0.35:
        if lower_wick3 > body3 * 2 and lower_wick3 > upper_wick3:
            return {"available": True, "pattern": "Pin Bar (bullish rejection)", "bias": "bullish"}
        if upper_wick3 > body3 * 2 and upper_wick3 > lower_wick3:
            return {"available": True, "pattern": "Pin Bar (bearish rejection)", "bias": "bearish"}

    # Engulfing: candle 3's body fully engulfs candle 2's body, opposite direction.
    o2, cl2 = float(c2["open"]), float(c2["close"])
    o3, cl3 = float(c3["open"]), float(c3["close"])
    if _is_bullish(c3) and not _is_bullish(c2) and cl3 >= o2 and o3 <= cl2:
        return {"available": True, "pattern": "Bullish Engulfing", "bias": "bullish"}
    if (not _is_bullish(c3)) and _is_bullish(c2) and o3 >= cl2 and cl3 <= o2:
        return {"available": True, "pattern": "Bearish Engulfing", "bias": "bearish"}

    # Morning/Evening star: big down/up candle, small-body middle candle, big reversal candle.
    body1, body2 = _body(c1), _body(c2)
    if body1 > 0 and body2 / max(body1, 1e-9) < 0.4:
        if (not _is_bullish(c1)) and _is_bullish(c3) and cl3 > (float(c1["open"]) + float(c1["close"])) / 2:
            return {"available": True, "pattern": "Morning Star", "bias": "bullish"}
        if _is_bullish(c1) and (not _is_bullish(c3)) and cl3 < (float(c1["open"]) + float(c1["close"])) / 2:
            return {"available": True, "pattern": "Evening Star", "bias": "bearish"}

    # Inside bar: candle 3 fully contained within candle 2's range (consolidation).
    if float(c3["high"]) <= float(c2["high"]) and float(c3["low"]) >= float(c2["low"]):
        return {"available": True, "pattern": "Inside Bar (consolidation)", "bias": "neutral"}

    return {"available": True, "pattern": "No clear pattern", "bias": "neutral"}


# ── New indicator 2: Fibonacci retracement ────────────────────────────────────

FIB_LEVELS = (0.236, 0.382, 0.5, 0.618, 0.786)


def fibonacci_retracement(candles: list[dict], direction: str, lookback: int = 30) -> dict[str, Any]:
    """Auto-drawn from the recent swing. For a BUY, measured low->high of the
    up-leg; for a SELL, high->low of the down-leg - retracement % is how far
    price has pulled back against the trade from that swing extreme."""
    sw = swing_high_low(candles, lookback)
    if not sw.get("available"):
        return {"available": False, "reason": sw.get("reason")}
    swing_high, swing_low = sw["swing_high"], sw["swing_low"]
    price = closes(candles)[-1]
    span = swing_high - swing_low
    if span <= 0:
        return {"available": False, "reason": "no range"}

    if direction.lower() == "buy":
        # retracement measured down from the swing high
        retrace_pct = (swing_high - price) / span
    else:
        retrace_pct = (price - swing_low) / span

    levels = {f"{int(l * 1000) / 10}%": round(
        (swing_high - l * span) if direction.lower() == "buy" else (swing_low + l * span), 2
    ) for l in FIB_LEVELS}

    nearest_level = min(FIB_LEVELS, key=lambda l: abs(l - retrace_pct))
    return {
        "available": True,
        "retrace_pct": round(retrace_pct * 100, 1),
        "nearest_level_pct": round(nearest_level * 100, 1),
        "levels": levels,
        "swing_high": swing_high, "swing_low": swing_low,
    }


# ── New indicator 3: Session clock ────────────────────────────────────────────

def session_clock(now_utc: datetime | None = None) -> dict[str, Any]:
    now_utc = now_utc or datetime.now(timezone.utc)
    hour = now_utc.hour

    in_asian = 0 <= hour < 8
    in_london = 8 <= hour < 16
    in_ny = 13 <= hour < 21
    in_overlap = 13 <= hour < 16

    if in_overlap:
        session, volatility = "London/New York Overlap", "High"
    elif in_ny:
        session, volatility = "New York", "High"
    elif in_london:
        session, volatility = "London", "Medium-High"
    elif in_asian:
        session, volatility = "Asian", "Low"
    else:
        session, volatility = "Between sessions", "Low"

    return {"available": True, "session": session, "volatility": volatility, "hour_utc": hour}


# ── New indicator 4: Economic news filter ─────────────────────────────────────
# See bot/advisor/news_calendar.py - kept separate since it has no candle
# dependency and is reused by the live monitor independently.


# ── New indicator 5: Volume / tick activity ───────────────────────────────────

def volume_activity(candles: list[dict], lookback: int = 20) -> dict[str, Any]:
    """MT5 forex/metals feeds report tick volume (number of price updates),
    not true traded volume - there is no central exchange for XAUUSD CFDs,
    so this is a proxy for activity, not literal contract volume. Labeled
    honestly as such rather than implying it's true market volume."""
    if len(candles) < lookback + 1:
        return {"available": False, "reason": f"need {lookback + 1}+ candles"}
    vols = [float(c.get("tick_volume", 0) or 0) for c in candles]
    current = vols[-1]
    avg = sum(vols[-(lookback + 1):-1]) / lookback
    if avg <= 0:
        return {"available": False, "reason": "no volume data from broker"}
    ratio = current / avg

    if ratio >= 2.5:
        label = "Spike"
    elif ratio >= 1.4:
        label = "High"
    elif ratio >= 0.7:
        label = "Normal"
    else:
        label = "Low"
    return {"available": True, "label": label, "current": current, "average_20": round(avg, 1), "ratio": round(ratio, 2), "is_proxy": True}


# ── New indicator 6: Live Risk:Reward tracker ─────────────────────────────────

def risk_reward_tracker(direction: str, entry: float, stop_loss: float | None, target: float | None, current_price: float) -> dict[str, Any]:
    direction = direction.lower()
    sign = 1 if direction == "buy" else -1

    pnl_price = (current_price - entry) * sign

    result: dict[str, Any] = {
        "available": True,
        "pnl_price": round(pnl_price, 2),
        "has_sl": stop_loss is not None,
        "has_target": target is not None,
    }

    if target is not None:
        target_dist = (target - entry) * sign
        if target_dist > 0:
            pct_captured = max(0.0, min(150.0, (pnl_price / target_dist) * 100.0))
            result["pct_target_captured"] = round(pct_captured, 1)

    if stop_loss is not None:
        sl_dist = (entry - stop_loss) * sign  # positive number = distance to SL
        if sl_dist > 0:
            remaining_to_sl = sl_dist + pnl_price  # pnl_price negative when losing
            pct_sl_remaining = max(0.0, min(100.0, (remaining_to_sl / sl_dist) * 100.0))
            result["pct_sl_remaining"] = round(pct_sl_remaining, 1)

    if stop_loss is not None and target is not None:
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)
        if risk > 0:
            result["planned_rr"] = round(reward / risk, 2)
        current_risk = abs(entry - stop_loss)
        current_reward = pnl_price
        if current_risk > 0:
            result["live_rr"] = round(current_reward / current_risk, 2)

    return result
