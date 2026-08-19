"""Mode 1 — Active Trade Monitor.

Entry quality, live SL/TP analysis, PnL/drawdown tracking, momentum health,
the 5-tier exit-decision engine, and the trade health score (0-100). Built
on top of bot/advisor/indicators.py - reuses those calculations rather than
re-deriving EMA/RSI/MACD/etc again.
"""
from __future__ import annotations

from typing import Any

from bot.advisor import indicators as ind
from bot.advisor import news_calendar

# ── Configurable thresholds (kept here, not buried in logic) ────────────────

SL_DANGER_ZONE_PCT = 30.0     # price within this % of SL -> WARNING
SL_CRITICAL_ZONE_PCT = 10.0   # price within this % of SL -> URGENT CLOSE
SL_EMERGENCY_ZONE_PCT = 10.0  # spec's emergency trigger, kept as its own name for clarity
TP_PARTIAL_PCT = 70.0
TP_FULL_PCT = 90.0
DRAWDOWN_WARN_PCT = 30.0
DRAWDOWN_PARTIAL_PCT = 40.0


def analyze_entry(candles: list[dict], direction: str, entry_price: float) -> dict[str, Any]:
    """Was the entry at a strong zone, confirmed by RSI + MACD, at the time
    it was taken? Uses the candles as they are now, since a snapshot is
    captured at registration time by the caller (see monitor.py)."""
    ema_r = ind.ema_trend(candles)
    rsi_r = ind.rsi(candles)
    macd_r = ind.macd(candles)
    swing_r = ind.swing_high_low(candles)
    bullish = direction == "buy"

    score = 0
    notes: list[str] = []

    if ema_r.get("available"):
        aligned = (ema_r["read"] == "bullish" and bullish) or (ema_r["read"] == "bearish" and not bullish)
        if aligned:
            score += 1
            notes.append("EMA trend aligned at entry")

    if swing_r.get("available"):
        near_support = bullish and entry_price <= swing_r["swing_low"] * 1.01
        near_resistance = (not bullish) and entry_price >= swing_r["swing_high"] * 0.99
        if near_support or near_resistance:
            score += 1
            notes.append("Entry near a key support/resistance zone")

    if rsi_r.get("available"):
        rsi_confirmed = (bullish and 45 <= rsi_r["value"] <= 70) or ((not bullish) and 30 <= rsi_r["value"] <= 55)
        if rsi_confirmed:
            score += 1
            notes.append("RSI confirmed direction at entry")

    if macd_r.get("available"):
        macd_confirmed = (bullish and macd_r["histogram"] > 0) or ((not bullish) and macd_r["histogram"] < 0)
        if macd_confirmed:
            score += 1
            notes.append("MACD confirmed direction at entry")

    if score >= 3:
        quality = "Strong"
    elif score >= 2:
        quality = "Average"
    else:
        quality = "Weak"

    return {"quality": quality, "score": score, "max_score": 4, "notes": notes}


def analyze_sl(direction: str, entry: float, sl: float | None, current_price: float) -> dict[str, Any]:
    if sl is None:
        return {"available": False}
    bullish = direction == "buy"
    total_distance = abs(entry - sl)
    remaining_distance = (current_price - sl) if bullish else (sl - current_price)
    pct_remaining = max(0.0, min(100.0, (remaining_distance / total_distance) * 100.0)) if total_distance > 0 else 100.0
    pips_away = abs(remaining_distance)

    if pct_remaining <= SL_CRITICAL_ZONE_PCT:
        status = "CRITICAL"
    elif pct_remaining <= SL_DANGER_ZONE_PCT:
        status = "DANGER"
    elif pct_remaining <= 50:
        status = "CAUTION"
    else:
        status = "SAFE"

    return {
        "available": True, "pips_away": round(pips_away, 2), "pct_remaining": round(pct_remaining, 1),
        "status": status, "sl_price": sl,
    }


def analyze_tp(direction: str, entry: float, tp: float | None, current_price: float) -> dict[str, Any]:
    if tp is None:
        return {"available": False}
    bullish = direction == "buy"
    total_distance = abs(tp - entry)
    captured_distance = (current_price - entry) if bullish else (entry - current_price)
    pct_captured = (captured_distance / total_distance) * 100.0 if total_distance > 0 else 0.0
    pips_away = abs(tp - current_price)

    if pct_captured >= TP_FULL_PCT:
        status = "ALMOST HIT"
    elif pct_captured >= TP_PARTIAL_PCT:
        status = "NEAR"
    elif pct_captured >= 30:
        status = "APPROACHING"
    else:
        status = "FAR"

    return {
        "available": True, "pips_away": round(pips_away, 2), "pct_captured": round(pct_captured, 1),
        "status": status, "tp_price": tp,
    }


def pnl_tracker(direction: str, entry: float, current_price: float, peak_price: float | None) -> dict[str, Any]:
    bullish = direction == "buy"
    pnl_price = (current_price - entry) if bullish else (entry - current_price)
    pnl_pct = (pnl_price / entry) * 100.0 if entry else 0.0

    if peak_price is None:
        peak_price = current_price
    else:
        if bullish:
            peak_price = max(peak_price, current_price)
        else:
            peak_price = min(peak_price, current_price)

    peak_pnl_price = (peak_price - entry) if bullish else (entry - peak_price)
    drawdown_price = peak_pnl_price - pnl_price
    drawdown_pct_of_peak = (drawdown_price / peak_pnl_price * 100.0) if peak_pnl_price > 0 else 0.0

    return {
        "pnl_price": round(pnl_price, 2), "pnl_pct": round(pnl_pct, 3),
        "peak_pnl_price": round(peak_pnl_price, 2), "drawdown_price": round(max(0.0, drawdown_price), 2),
        "drawdown_pct_of_peak": round(max(0.0, drawdown_pct_of_peak), 1),
        "peak_price": peak_price,
    }


def momentum_health(candles: list[dict], direction: str) -> dict[str, Any]:
    ema_r = ind.ema_trend(candles)
    rsi_r = ind.rsi(candles)
    macd_r = ind.macd(candles)
    volume_r = ind.volume_activity(candles)
    candle_r = ind.candlestick_pattern(candles)
    bullish = direction == "buy"

    ema_valid = ema_r.get("available") and ((ema_r["read"] == "bullish" and bullish) or (ema_r["read"] == "bearish" and not bullish))

    rsi_rising = None
    if len(candles) >= 16:
        rsi_prev = ind.rsi(candles[:-1])
        if rsi_r.get("available") and rsi_prev.get("available"):
            rsi_rising = rsi_r["value"] > rsi_prev["value"]

    macd_growing = macd_r.get("available") and abs(macd_r["histogram"]) >= 0 and macd_r["read"] in (
        "bullish_strengthening" if bullish else "bearish_strengthening",
        "bullish_crossover" if bullish else "bearish_crossover",
    )

    volume_supports = volume_r.get("available") and volume_r["label"] in ("Normal", "High", "Spike")

    reversal_pattern = candle_r.get("available") and candle_r["bias"] not in ("neutral",) and (
        (candle_r["bias"] == "bearish" and bullish) or (candle_r["bias"] == "bullish" and not bullish)
    )

    weakening_signals = sum([
        rsi_rising is False,
        not macd_growing,
        not volume_supports,
    ])
    if not ema_valid or reversal_pattern:
        momentum_state = "NO"
    elif weakening_signals >= 2:
        momentum_state = "WEAKENING"
    else:
        momentum_state = "YES"

    return {
        "momentum_in_direction": momentum_state,
        "ema_valid": ema_valid,
        "rsi_value": rsi_r.get("value"), "rsi_rising": rsi_rising,
        "macd_histogram": macd_r.get("histogram"), "macd_growing": macd_growing,
        "volume_label": volume_r.get("label"), "volume_supports": volume_supports,
        "reversal_pattern": candle_r.get("pattern") if reversal_pattern else None,
        "raw": {"ema": ema_r, "rsi": rsi_r, "macd": macd_r, "volume": volume_r, "candlestick": candle_r},
    }


def compute_health_score(*, momentum: dict, sl_analysis: dict, tp_analysis: dict, drawdown_pct_of_peak: float, news_status: dict) -> int:
    score = 100

    if not momentum["ema_valid"]:
        score -= 10
    if momentum["macd_histogram"] is not None and not momentum["macd_growing"]:
        score -= 10
    rsi_val = momentum.get("rsi_value")
    if rsi_val is not None and (rsi_val >= 72 or rsi_val <= 28):
        score -= 10
    if not momentum["volume_supports"] and momentum.get("volume_label") == "Spike":
        score -= 10
    if sl_analysis.get("available"):
        if sl_analysis["pct_remaining"] <= 15:
            score -= 20
        elif sl_analysis["pct_remaining"] <= 30:
            score -= 15
    if momentum.get("reversal_pattern"):
        score -= 10
    if momentum["rsi_rising"] is False:
        score -= 5
    if drawdown_pct_of_peak > 30:
        score -= 5
    if news_status["level"] == "danger":
        score -= 15
    elif news_status["level"] == "warning":
        score -= 10

    if momentum["ema_valid"]:
        score += 10
    if rsi_val is not None and (
        (50 <= rsi_val <= 65)
    ):
        score += 5
    if momentum["macd_growing"]:
        score += 5
    if momentum["volume_supports"]:
        score += 5
    if momentum["ema_valid"]:
        score += 5
    if tp_analysis.get("available") and tp_analysis["pct_captured"] >= 70:
        score += 5

    return max(0, min(100, score))


def exit_decision(*, health_score: int, sl_analysis: dict, tp_analysis: dict, momentum: dict, news_status: dict) -> dict[str, Any]:
    """Checked most-severe-first: EMERGENCY > EXIT NOW > PARTIAL > WATCH > STRONG."""

    def confidence_for(band_low: int, band_high: int, score: int) -> int:
        return max(band_low, min(band_high, score))

    reasons: list[str] = []

    # 🚨 EMERGENCY EXIT
    emergency = False
    if sl_analysis.get("available") and sl_analysis["pct_remaining"] <= 10:
        emergency = True
        reasons.append("Price within 10% of stop-loss")
    if momentum.get("volume_label") == "Spike" and not momentum["volume_supports"]:
        emergency = True
        reasons.append("Large volume spike against the trade")
    if news_status["level"] == "danger":
        emergency = True
        reasons.append(f"{news_status['event']} in {news_status['minutes_until']:.0f} min")
    if health_score < 20:
        emergency = True
        reasons.append(f"Trade health score critical ({health_score}/100)")
    if emergency:
        return {
            "decision": "EMERGENCY_EXIT", "icon": "🚨", "label": "EMERGENCY EXIT — CLOSE IMMEDIATELY",
            "confidence": confidence_for(0, 19, health_score),
            "message": "Critical risk detected — close trade right now, do not wait even 1 second",
            "reasons": reasons[:3], "telegram": "urgent", "sound": True,
        }

    # 🔴 EXIT NOW — FULL CLOSE
    exit_conditions = 0
    if momentum.get("reversal_pattern"):
        exit_conditions += 1
        reasons.append(f"{momentum['reversal_pattern']} closed against the trade")
    if not momentum["macd_growing"] and momentum["macd_histogram"] is not None:
        exit_conditions += 1
        reasons.append("MACD turned against the trade")
    rsi_val = momentum.get("rsi_value")
    if rsi_val is not None and ((rsi_val >= 70) or (rsi_val <= 30)):
        exit_conditions += 1
        reasons.append(f"RSI at extreme ({rsi_val})")
    if not momentum["ema_valid"]:
        exit_conditions += 1
        reasons.append("EMA trend broke against the trade")
    if tp_analysis.get("available") and tp_analysis["pct_captured"] >= TP_FULL_PCT:
        exit_conditions += 1
        reasons.append(f"{tp_analysis['pct_captured']}% of target captured")
    if news_status["level"] == "warning" and news_status["minutes_until"] <= 5:
        exit_conditions += 1
        reasons.append(f"{news_status['event']} in {news_status['minutes_until']:.0f} min")
    if exit_conditions >= 2:
        return {
            "decision": "EXIT_NOW", "icon": "🔴", "label": "EXIT NOW — FULL CLOSE",
            "confidence": confidence_for(20, 39, health_score),
            "message": "Momentum reversed against trade — exit now to protect profit, do not wait for SL to hit",
            "reasons": reasons[:3], "telegram": "high", "sound": False,
        }

    # 💛 PARTIAL CLOSE SUGGESTED
    partial = False
    if tp_analysis.get("available") and tp_analysis["pct_captured"] >= TP_PARTIAL_PCT:
        partial = True
        reasons.append(f"{tp_analysis['pct_captured']}% of target already captured")
    if rsi_val is not None and (rsi_val > 72 or rsi_val < 28):
        partial = True
        reasons.append(f"RSI entered extreme zone ({rsi_val})")
    if momentum.get("reversal_pattern"):
        partial = True
    if momentum.get("drawdown_flagged"):
        partial = True
    if partial:
        return {
            "decision": "PARTIAL_CLOSE", "icon": "💛", "label": "PARTIAL CLOSE SUGGESTED",
            "confidence": confidence_for(40, 60, health_score),
            "message": "Lock in 50% profit now — move SL to breakeven on rest, let remaining position run to full target",
            "reasons": reasons[:3], "telegram": "medium", "sound": False,
            "action": "Close 50% -> Move SL to entry",
        }

    # ⏳ HOLD BUT WATCH
    watch_conditions = 0
    if rsi_val is not None and ((rsi_val > 65) or (rsi_val < 35)):
        watch_conditions += 1
        reasons.append(f"RSI approaching extreme ({rsi_val})")
    if momentum["rsi_rising"] is False:
        watch_conditions += 1
        reasons.append("Momentum slightly weakening")
    if not momentum["volume_supports"]:
        watch_conditions += 1
        reasons.append("Volume dropping below average")
    if news_status["level"] in ("warning", "upcoming") and news_status["minutes_until"] and news_status["minutes_until"] <= 60:
        watch_conditions += 1
        reasons.append(f"{news_status['event']} in {news_status['minutes_until']:.0f} min")
    if sl_analysis.get("available") and sl_analysis["status"] in ("CAUTION", "DANGER"):
        watch_conditions += 1
        reasons.append(f"SL zone: {sl_analysis['status']}")
    if watch_conditions >= 2:
        return {
            "decision": "HOLD_WATCH", "icon": "⏳", "label": "HOLD BUT WATCH",
            "confidence": confidence_for(55, 79, health_score),
            "message": "Momentum slightly weakening — move SL to breakeven, watch next 3 candles closely",
            "reasons": reasons[:3], "telegram": "none", "sound": False,
            "action": "Suggest move SL to breakeven",
        }

    # ✅ HOLD STRONG (fallback - everything checked out)
    return {
        "decision": "HOLD_STRONG", "icon": "🟢", "label": "HOLD STRONG",
        "confidence": confidence_for(80, 100, health_score),
        "message": "All signals aligned — stay in trade, target reachable",
        "reasons": ["EMA aligned", "Momentum healthy", "No danger signals"], "telegram": "none", "sound": False,
    }


def analyze_active_trade(
    *, candles: list[dict], direction: str, entry: float, current_price: float,
    stop_loss: float | None, target: float | None, peak_price: float | None,
    entry_snapshot: dict | None = None, now_utc=None,
) -> dict[str, Any]:
    """Full Mode 1 analysis for one open trade."""
    sl_r = analyze_sl(direction, entry, stop_loss, current_price)
    tp_r = analyze_tp(direction, entry, target, current_price)
    pnl_r = pnl_tracker(direction, entry, current_price, peak_price)
    momentum = momentum_health(candles, direction)
    momentum["drawdown_flagged"] = pnl_r["drawdown_pct_of_peak"] >= DRAWDOWN_PARTIAL_PCT
    news_status = news_calendar.news_status(now_utc)

    health = compute_health_score(
        momentum=momentum, sl_analysis=sl_r, tp_analysis=tp_r,
        drawdown_pct_of_peak=pnl_r["drawdown_pct_of_peak"], news_status=news_status,
    )
    decision = exit_decision(health_score=health, sl_analysis=sl_r, tp_analysis=tp_r, momentum=momentum, news_status=news_status)

    return {
        "mode": 1,
        "trade": {"direction": direction, "entry": entry, "current_price": current_price, "stop_loss": stop_loss, "target": target},
        "entry_analysis": entry_snapshot or analyze_entry(candles, direction, entry),
        "sl_analysis": sl_r, "tp_analysis": tp_r, "pnl": pnl_r,
        "momentum": momentum, "news": news_status,
        "health_score": health, "decision": decision,
        "peak_price": pnl_r["peak_price"],
    }
