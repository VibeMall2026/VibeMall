"""Mode 2 — Solo Market Analyzer.

Runs when the algo has no open trade. Scans market structure, scores BUY vs
SELL setups against a 12-point checklist each, and builds a full trade plan
(entry zone, SL, TP, R:R) when a high-quality opportunity appears. Built on
bot/advisor/indicators.py - reuses those calculations, does not re-derive them.
"""
from __future__ import annotations

from typing import Any

from bot.advisor import indicators as ind
from bot.advisor import news_calendar

MIN_OPPORTUNITY_PCT = 65.0
MIN_ACCEPTABLE_RR = 2.0


def market_structure(candles: list[dict], lookback: int = 30) -> dict[str, Any]:
    ema_r = ind.ema_trend(candles)
    swing_r = ind.swing_high_low(candles, lookback)

    if ema_r.get("available"):
        if ema_r["read"] == "bullish":
            trend, strength = "UP", "Strong"
        elif ema_r["read"] == "bearish":
            trend, strength = "DOWN", "Strong"
        elif ema_r["read"] == "mixed_above_200":
            trend, strength = "UP", "Moderate"
        elif ema_r["read"] == "mixed_below_200":
            trend, strength = "DOWN", "Moderate"
        else:
            trend, strength = "SIDEWAYS", "Weak"
    else:
        trend, strength = "SIDEWAYS", "Weak"

    # Market phase from the last few swing points: compare the two halves of
    # the lookback window's highs/lows for a simple higher-highs/lower-lows read.
    phase = "RANGING"
    if len(candles) >= lookback:
        window = candles[-lookback:]
        first_half, second_half = window[: lookback // 2], window[lookback // 2 :]
        fh_high = max(float(c["high"]) for c in first_half)
        fh_low = min(float(c["low"]) for c in first_half)
        sh_high = max(float(c["high"]) for c in second_half)
        sh_low = min(float(c["low"]) for c in second_half)
        if sh_high > fh_high and sh_low > fh_low:
            phase = "BULLISH STRUCTURE"
        elif sh_high < fh_high and sh_low < fh_low:
            phase = "BEARISH STRUCTURE"

    price = ind.closes(candles)[-1] if candles else None
    at_support = swing_r.get("available") and price is not None and price <= swing_r["swing_low"] * 1.005
    at_resistance = swing_r.get("available") and price is not None and price >= swing_r["swing_high"] * 0.995

    return {
        "trend": trend, "trend_strength": strength, "phase": phase,
        "support": swing_r.get("swing_low"), "resistance": swing_r.get("swing_high"),
        "distance_to_support": round(price - swing_r["swing_low"], 2) if (swing_r.get("available") and price) else None,
        "distance_to_resistance": round(swing_r["swing_high"] - price, 2) if (swing_r.get("available") and price) else None,
        "at_support": at_support, "at_resistance": at_resistance,
        "price": price,
    }


def _signal_checklist(candles: list[dict], direction: str, structure: dict, session: dict, news_status: dict) -> dict[str, Any]:
    ema_r = ind.ema_trend(candles)
    rsi_r = ind.rsi(candles)
    macd_r = ind.macd(candles)
    bb_r = ind.bollinger_bands(candles)
    atr_r = ind.atr(candles)
    volume_r = ind.volume_activity(candles)
    candle_r = ind.candlestick_pattern(candles)

    bullish = direction == "buy"
    checks: list[tuple[str, bool]] = []

    checks.append(("EMA stack", ema_r.get("available") and ema_r["read"] == ("bullish" if bullish else "bearish")))

    rsi_ok = False
    if rsi_r.get("available"):
        if bullish:
            rsi_ok = 45 <= rsi_r["value"] <= 65
        else:
            rsi_ok = 35 <= rsi_r["value"] <= 55
    checks.append(("RSI in range", rsi_ok))

    macd_ok = macd_r.get("available") and (
        (bullish and macd_r["histogram"] > 0 and macd_r["read"] in ("bullish_crossover", "bullish_strengthening"))
        or ((not bullish) and macd_r["histogram"] < 0 and macd_r["read"] in ("bearish_crossover", "bearish_strengthening"))
    )
    checks.append(("MACD histogram", macd_ok))

    price = structure.get("price")
    checks.append(("Price vs EMA20", ema_r.get("available") and price is not None and (
        (price > ema_r["ema20"]) if bullish else (price < ema_r["ema20"])
    )))

    near_level = structure["at_support"] if bullish else structure["at_resistance"]
    checks.append(("At key level", bool(near_level)))

    candle_ok = candle_r.get("available") and candle_r["bias"] == ("bullish" if bullish else "bearish")
    checks.append(("Candle pattern", candle_ok))

    checks.append(("ATR active", atr_r.get("available") and atr_r["value"] > 0))

    bb_ok = bb_r.get("available") and bb_r["read"] == ("at_or_above_upper" if bullish else "at_or_below_lower")
    checks.append(("Bollinger squeeze break", bb_ok))

    checks.append(("Volume above average", volume_r.get("available") and volume_r["label"] in ("High", "Spike")))

    checks.append(("Active session", session["session"] in ("London", "New York", "London/New York Overlap")))

    checks.append(("No high-impact news soon", news_status["level"] not in ("danger", "warning")))

    last_candle_bullish = len(candles) >= 1 and float(candles[-1]["close"]) > float(candles[-1]["open"])
    checks.append(("Previous candle closed " + ("bullish" if bullish else "bearish"), last_candle_bullish == bullish))

    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    score_pct = round((passed / total) * 100.0, 1) if total else 0.0

    return {"checks": [{"label": label, "passed": ok} for label, ok in checks], "passed": passed, "total": total, "score_pct": score_pct}


def _confidence_label(score_pct: float) -> dict[str, str]:
    if score_pct >= 85:
        return {"label": "HIGH CONFIDENCE", "icon": "🔥", "tier": "high"}
    if score_pct >= 75:
        return {"label": "STRONG SETUP", "icon": "🟢", "tier": "strong"}
    if score_pct >= MIN_OPPORTUNITY_PCT:
        return {"label": "MODERATE SETUP", "icon": "🟡", "tier": "moderate"}
    return {"label": "", "icon": "", "tier": "none"}


def _build_trade_setup(direction: str, structure: dict, price: float) -> dict[str, Any]:
    bullish = direction == "buy"
    support, resistance = structure.get("support"), structure.get("resistance")
    if support is None or resistance is None:
        return {"available": False}

    if bullish:
        entry_low, entry_high = min(price, support), max(price, support * 1.002)
        stop_loss = support - abs(support * 0.0003) * 20  # small buffer below swing low
        take_profit = resistance
    else:
        entry_low, entry_high = min(price, resistance * 0.998), max(price, resistance)
        stop_loss = resistance + abs(resistance * 0.0003) * 20
        take_profit = support

    entry_ref = price
    risk = abs(entry_ref - stop_loss)
    reward = abs(take_profit - entry_ref)
    rr = round(reward / risk, 2) if risk > 0 else 0.0
    weak = rr < MIN_ACCEPTABLE_RR

    return {
        "available": True,
        "entry_zone_low": round(min(entry_low, entry_high), 2), "entry_zone_high": round(max(entry_low, entry_high), 2),
        "stop_loss": round(stop_loss, 2), "take_profit": round(take_profit, 2),
        "risk_pips": round(risk, 2), "reward_pips": round(reward, 2),
        "rr_ratio": rr, "weak_setup": weak,
    }


def scan_market(candles: list[dict], now_utc=None) -> dict[str, Any]:
    """Full Mode 2 analysis - scores both directions and returns whichever
    (if either) clears the opportunity bar, plus the full checklist for both."""
    structure = market_structure(candles)
    session = ind.session_clock(now_utc)
    news_status = news_calendar.news_status(now_utc)

    buy_checklist = _signal_checklist(candles, "buy", structure, session, news_status)
    sell_checklist = _signal_checklist(candles, "sell", structure, session, news_status)

    news_override = news_status["level"] in ("danger", "warning")

    opportunity = None
    direction = None
    if not news_override:
        if buy_checklist["score_pct"] >= MIN_OPPORTUNITY_PCT and buy_checklist["score_pct"] > sell_checklist["score_pct"]:
            direction, opportunity = "buy", buy_checklist
        elif sell_checklist["score_pct"] >= MIN_OPPORTUNITY_PCT and sell_checklist["score_pct"] > buy_checklist["score_pct"]:
            direction, opportunity = "sell", sell_checklist

    result: dict[str, Any] = {
        "mode": 2,
        "structure": structure, "session": session, "news": news_status,
        "buy_score": buy_checklist, "sell_score": sell_checklist,
        "news_override": news_override,
        "opportunity": None,
        "generated_at_utc": (now_utc or __import__("datetime").datetime.now(__import__("datetime").timezone.utc)).isoformat(),
    }

    if direction is None:
        missing = [c["label"] for c in (buy_checklist if buy_checklist["score_pct"] >= sell_checklist["score_pct"] else sell_checklist)["checks"] if not c["passed"]]
        result["decision"] = {
            "signal": "WAIT", "icon": "⏳", "message": "No high-quality setup right now",
            "missing": missing[:4], "news_override": news_override,
        }
        return result

    confidence = _confidence_label(opportunity["score_pct"])
    setup = _build_trade_setup(direction, structure, structure["price"])

    result["opportunity"] = {
        "direction": direction, "confidence_pct": opportunity["score_pct"],
        "confidence_label": confidence["label"], "confidence_icon": confidence["icon"], "confidence_tier": confidence["tier"],
        "setup": setup,
        "top_reasons": [c["label"] for c in opportunity["checks"] if c["passed"]][:4],
    }
    result["decision"] = {
        "signal": "BUY" if direction == "buy" else "SELL",
        "icon": "📈" if direction == "buy" else "📉",
        "message": f"{direction.upper()} OPPORTUNITY DETECTED",
    }
    return result
