"""Combines all 12 indicators into one Hold / Close / Wait recommendation.

Each indicator casts one vote relative to the trade's direction:
  +1 supportive of staying in the trade
   0 neutral / no strong read
  -1 working against the trade

Base decision (before overrides) - counting only the +1 (supportive) votes
out of 12:
  8-12 supportive -> HOLD   (confidence = supportive/12)
  5-7  supportive -> WAIT
  0-4  supportive -> CLOSE

Overrides applied after the base count (these can force a decision even if
the vote count alone would say otherwise):
  - High-impact news within 30 minutes -> force WAIT
  - R:R tracker shows 90%+ of target captured -> force CLOSE (take profit)
  - Volume spike against the trade direction -> force CLOSE
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bot.advisor import indicators as ind
from bot.advisor import news_calendar


def _vote_ema(result: dict, direction: str) -> tuple[int, str]:
    if not result.get("available"):
        return 0, "EMA trend: not enough data"
    read = result["read"]
    bullish = direction == "buy"
    if read == "bullish":
        return (1, "Trend: price above rising EMA20/50/200 (bullish stack)") if bullish else (-1, "Trend: bullish stack against your SELL")
    if read == "bearish":
        return (1, "Trend: price below falling EMA20/50/200 (bearish stack)") if not bullish else (-1, "Trend: bearish stack against your BUY")
    return 0, f"Trend: mixed ({read.replace('_', ' ')})"


def _vote_rsi(result: dict, direction: str) -> tuple[int, str]:
    if not result.get("available"):
        return 0, "RSI: not enough data"
    value, read = result["value"], result["read"]
    bullish = direction == "buy"
    if read == "overbought":
        return (-1, f"RSI {value} overbought - stretched against a BUY") if bullish else (1, f"RSI {value} overbought - supports your SELL")
    if read == "oversold":
        return (1, f"RSI {value} oversold - supports your BUY") if bullish else (-1, f"RSI {value} oversold - stretched against a SELL")
    if read == "bullish_momentum":
        return (1, f"RSI {value} - momentum still bullish") if bullish else (-1, f"RSI {value} - momentum against your SELL")
    if read == "bearish_momentum":
        return (1, f"RSI {value} - momentum still bearish") if not bullish else (-1, f"RSI {value} - momentum against your BUY")
    return 0, f"RSI {value} - neutral"


def _vote_macd(result: dict, direction: str) -> tuple[int, str]:
    if not result.get("available"):
        return 0, "MACD: not enough data"
    read = result["read"]
    bullish = direction == "buy"
    if read == "bullish_crossover":
        return (1, "MACD just crossed bullish") if bullish else (-1, "MACD crossed bullish against your SELL")
    if read == "bearish_crossover":
        return (1, "MACD just crossed bearish") if not bullish else (-1, "MACD crossed bearish against your BUY")
    if read == "bullish_strengthening":
        return (1, "MACD momentum strengthening bullish") if bullish else (-1, "MACD strengthening against your SELL")
    if read == "bullish_fading":
        return (0, "MACD bullish but fading") if bullish else (1, "MACD bullish momentum fading - good for your SELL")
    if read == "bearish_strengthening":
        return (1, "MACD momentum strengthening bearish") if not bullish else (-1, "MACD strengthening against your BUY")
    if read == "bearish_fading":
        return (0, "MACD bearish but fading") if not bullish else (1, "MACD bearish momentum fading - good for your BUY")
    return 0, "MACD: neutral"


def _vote_atr(result: dict, rr: dict) -> tuple[int, str]:
    if not result.get("available"):
        return 0, "ATR: not enough data"
    value = result["value"]
    # ATR alone doesn't have a direction - it just describes whether the
    # current move looks like normal volatility. Neutral vote, informational.
    return 0, f"ATR(14) {value} - typical range per candle right now"


def _vote_bb(result: dict, direction: str) -> tuple[int, str]:
    if not result.get("available"):
        return 0, "Bollinger Bands: not enough data"
    read = result["read"]
    bullish = direction == "buy"
    if read == "at_or_above_upper":
        return (-1, "Price at/above upper Bollinger Band - stretched against a BUY") if bullish else (1, "Price at/above upper band - supports your SELL")
    if read == "at_or_below_lower":
        return (1, "Price at/below lower Bollinger Band - supports your BUY") if bullish else (-1, "Price at/below lower band - stretched against a SELL")
    return 0, f"Price inside Bollinger Bands ({result['position_pct']}% of the band)"


def _vote_swing(result: dict, direction: str, current_price: float) -> tuple[int, str]:
    if not result.get("available"):
        return 0, "Swing High/Low: not enough data"
    bullish = direction == "buy"
    high, low = result["swing_high"], result["swing_low"]
    if bullish:
        if current_price <= low * 1.001:
            return -1, f"Price near recent swing low {low} - key support at risk"
        return 1, f"Price holding above recent swing low {low}"
    else:
        if current_price >= high * 0.999:
            return -1, f"Price near recent swing high {high} - key resistance at risk"
        return 1, f"Price holding below recent swing high {high}"


def _vote_candlestick(result: dict, direction: str) -> tuple[int, str]:
    if not result.get("available"):
        return 0, "Candlestick pattern: not enough data"
    pattern, bias = result["pattern"], result["bias"]
    bullish = direction == "buy"
    if bias == "neutral":
        return 0, f"Pattern: {pattern}"
    aligned = (bias == "bullish") == bullish
    if aligned:
        return 1, f"Pattern: {pattern} - aligned with your trade"
    return -1, f"WARNING - {pattern} against your trade direction"


def _vote_fibonacci(result: dict, direction: str) -> tuple[int, str]:
    if not result.get("available"):
        return 0, "Fibonacci: not enough data"
    retrace = result["retrace_pct"]
    if retrace >= 78.6:
        return -1, f"Retraced {retrace}% - beyond the 78.6% zone, thesis weakening"
    if retrace >= 61.8:
        return 1, f"Retraced {retrace}% - sitting in the 61.8-78.6% bounce zone"
    return 0, f"Retraced {retrace}% of the recent swing"


def _vote_session(result: dict) -> tuple[int, str]:
    # Informational only - session context is applied as a modifier on other
    # risky signals elsewhere (spec: "Asian + risky signal -> WAIT", "London/NY
    # + risky signal -> CLOSE/ACT NOW"), not a standalone directional vote.
    return 0, f"{result['session']} session ({result['volatility']} volatility)"


def _vote_news(status: dict) -> tuple[int, str]:
    if status["level"] == "danger":
        return -1, f"DANGER: {status['event']} in {status['minutes_until']:.0f} min"
    if status["level"] == "warning":
        return -1, f"WARNING: {status['event']} in {status['minutes_until']:.0f} min"
    if status["level"] == "upcoming":
        return 0, f"{status['event']} in {status['minutes_until']:.0f} min - not yet urgent"
    return 1, "No high-impact news in the next 2 hours"


def _vote_volume(result: dict, direction: str, ema_read: dict, swing_result: dict, current_price: float) -> tuple[int, str]:
    if not result.get("available"):
        return 0, "Volume: not enough data"
    label = result["label"]
    bullish = direction == "buy"

    broke_high = swing_result.get("available") and current_price >= swing_result.get("swing_high", float("inf"))
    broke_low = swing_result.get("available") and current_price <= swing_result.get("swing_low", float("-inf"))
    broke_key_level = broke_high or broke_low
    breakout_aligned = (broke_high and bullish) or (broke_low and not bullish)

    if label == "Spike" and breakout_aligned is False and broke_key_level:
        return -1, f"Volume {label} on a break against your trade direction"
    if breakout_aligned and label in ("High", "Spike"):
        return 1, f"Volume {label} confirms the breakout in your favor"
    if breakout_aligned and label == "Low":
        return -1, "Breakout on Low volume - may be a fake move"
    if label == "Spike":
        return 0, "Volume Spike - elevated activity, watch closely"
    return 0, f"Volume {label} (tick-volume proxy, not true market volume)"


def _vote_rr(result: dict) -> tuple[int, str]:
    if not result.get("available") or "pct_target_captured" not in result:
        return 0, "R:R tracker: set a target price to enable this"
    pct = result["pct_target_captured"]
    if pct >= 90:
        return -1, f"{pct}% of target captured - very close, lock it in"
    if pct >= 70:
        return 0, f"{pct}% of target captured - consider a partial close"
    if pct >= 40:
        return 1, f"{pct}% of target captured - trending toward target, trail your stop"
    if pct >= 0:
        return 1, f"{pct}% of target captured - trade just getting started"
    return -1, f"{pct}% of target - moving away from your target"


def analyze_trade(
    candles: list[dict],
    direction: str,
    entry: float,
    current_price: float,
    stop_loss: float | None = None,
    target: float | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Runs all 12 indicators against one open (or hypothetical) trade and
    returns the combined recommendation."""
    direction = direction.lower()
    now_utc = now_utc or datetime.now(timezone.utc)

    ema_r = ind.ema_trend(candles)
    rsi_r = ind.rsi(candles)
    macd_r = ind.macd(candles)
    atr_r = ind.atr(candles)
    bb_r = ind.bollinger_bands(candles)
    swing_r = ind.swing_high_low(candles)
    candle_r = ind.candlestick_pattern(candles)
    fib_r = ind.fibonacci_retracement(candles, direction)
    session_r = ind.session_clock(now_utc)
    news_r = news_calendar.news_status(now_utc)
    volume_r = ind.volume_activity(candles)
    rr_r = ind.risk_reward_tracker(direction, entry, stop_loss, target, current_price)

    votes: list[tuple[str, int, str]] = [
        ("EMA 20/50/200 Trend", *_vote_ema(ema_r, direction)),
        ("RSI (14)", *_vote_rsi(rsi_r, direction)),
        ("MACD", *_vote_macd(macd_r, direction)),
        ("ATR (14)", *_vote_atr(atr_r, rr_r)),
        ("Bollinger Bands", *_vote_bb(bb_r, direction)),
        ("Swing High/Low", *_vote_swing(swing_r, direction, current_price)),
        ("Candlestick Pattern", *_vote_candlestick(candle_r, direction)),
        ("Fibonacci Retracement", *_vote_fibonacci(fib_r, direction)),
        ("Session Clock", *_vote_session(session_r)),
        ("Economic News Filter", *_vote_news(news_r)),
        ("Volume / Tick Activity", *_vote_volume(volume_r, direction, ema_r, swing_r, current_price)),
        ("Live Risk:Reward Tracker", *_vote_rr(rr_r)),
    ]

    supportive = sum(1 for _, v, _ in votes if v > 0)
    against = sum(1 for _, v, _ in votes if v < 0)
    total_indicators = len(votes)
    confidence_pct = round((supportive / total_indicators) * 100.0, 1)

    if supportive >= 8:
        decision = "HOLD"
    elif supportive >= 5:
        decision = "WAIT"
    else:
        decision = "CLOSE"

    overrides: list[str] = []

    # News override: within 30 minutes forces WAIT (unless already CLOSE).
    if news_r["level"] in ("danger", "warning") and decision == "HOLD":
        decision = "WAIT"
        overrides.append(f"News override: {news_r['event']} in {news_r['minutes_until']:.0f} min -> forced WAIT")

    # Asian session + a risky (CLOSE) signal is more likely to be low-volume
    # noise than a real move - soften CLOSE to WAIT during Asian session.
    if decision == "CLOSE" and session_r["session"] == "Asian":
        decision = "WAIT"
        overrides.append("Session override: Asian session (low volume) - CLOSE signal softened to WAIT")

    # R:R override: 90%+ of target captured forces CLOSE (take the profit).
    if rr_r.get("available") and rr_r.get("pct_target_captured", 0) >= 90:
        decision = "CLOSE"
        overrides.append(f"R:R override: {rr_r['pct_target_captured']}% of target captured -> forced CLOSE")

    # R:R override: price near stop loss forces CLOSE.
    if rr_r.get("available") and rr_r.get("pct_sl_remaining") is not None and rr_r["pct_sl_remaining"] <= 20:
        decision = "CLOSE"
        overrides.append(f"R:R override: only {rr_r['pct_sl_remaining']}% of stop-loss buffer remains -> forced CLOSE")

    # Volume spike against the trade forces CLOSE.
    volume_vote = next(v for name, v, _ in votes if name == "Volume / Tick Activity")
    if volume_r.get("label") == "Spike" and volume_vote < 0:
        decision = "CLOSE"
        overrides.append("Volume override: spike against your trade direction -> forced CLOSE")

    if confidence_pct >= 60:
        color = "green"
    elif confidence_pct >= 40:
        color = "yellow"
    else:
        color = "red"

    reasons_sorted = sorted(votes, key=lambda v: (0 if v[1] < 0 else (2 if v[1] > 0 else 1)))
    top_reasons = [r for _, _, r in reasons_sorted[:3]]

    return {
        "decision": decision,
        "confidence_pct": confidence_pct,
        "color": color,
        "supportive_votes": supportive,
        "against_votes": against,
        "total_indicators": total_indicators,
        "overrides": overrides,
        "top_reasons": top_reasons,
        "indicators": {name: {"vote": v, "reason": r} for name, v, r in votes},
        "raw": {
            "ema": ema_r, "rsi": rsi_r, "macd": macd_r, "atr": atr_r, "bollinger_bands": bb_r,
            "swing_high_low": swing_r, "candlestick": candle_r, "fibonacci": fib_r,
            "session": session_r, "news": news_r, "volume": volume_r, "risk_reward": rr_r,
        },
        "trade": {
            "direction": direction, "entry": entry, "current_price": current_price,
            "stop_loss": stop_loss, "target": target,
        },
        "generated_at_utc": now_utc.isoformat(),
    }
