"""
Telegram signal parser.

Supports common formats:
  XAUUSD BUY
  Entry: 1920.00
  SL: 1915.00
  TP1: 1930.00
  TP2: 1940.00

  or inline:  XAUUSD BUY @ 1920 SL 1915 TP 1930
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedSignal:
    symbol: str = ""
    side: str = ""          # "buy" | "sell"
    order_type: str = "market"
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: list[float] = field(default_factory=list)
    raw: str = ""
    valid: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "valid": self.valid,
            "reason": self.reason,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

_PRICE_RE = re.compile(r"[\d]+(?:[.,]\d+)?")


def _price(text: str, take: str = "first") -> Optional[float]:
    matches = _PRICE_RE.findall(text.replace(",", "."))
    if not matches:
        return None
    value = matches[0] if take == "first" else matches[-1]
    return float(value)


def _price_after(label_pattern: str, text: str) -> Optional[float]:
    normalized = text.replace(",", ".")
    match = re.search(rf"(?:{label_pattern})[^\d]*([\d]+(?:\.\d+)?)", normalized, re.IGNORECASE)
    if match:
        return float(match.groups()[-1])
    return _price(normalized, take="last")


def _find_prices(label_pattern: str, text: str) -> list[float]:
    """Find all prices after a label (e.g. TP1, TP2, TP)."""
    results = []
    for line in text.splitlines():
        if re.search(label_pattern, line, re.IGNORECASE):
            p = _price_after(label_pattern, line)
            if p:
                results.append(p)
    return results


# ── Main parser ───────────────────────────────────────────────────────────────

# Common forex/gold symbols
_SYMBOLS = [
    "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "NZDUSD", "USDCAD", "EURGBP", "EURJPY", "GBPJPY",
    "BTCUSD", "ETHUSD", "US30", "NAS100", "SPX500", "GER40",
    "GOLD", "SILVER", "OIL", "USOIL", "UKOIL",
]

_SYMBOL_RE = re.compile(
    r"\b(" + "|".join(_SYMBOLS) + r")\b",
    re.IGNORECASE,
)

_SIDE_RE = re.compile(
    r"\b(buy\s*limit|sell\s*limit|buy\s*stop|sell\s*stop|buy|sell)\b",
    re.IGNORECASE,
)


def parse_signal(text: str) -> ParsedSignal:
    sig = ParsedSignal(raw=text)

    if not text or not text.strip():
        sig.reason = "Empty message"
        return sig

    # ── Symbol ────────────────────────────────────────────────────────────────
    sym_match = _SYMBOL_RE.search(text)
    if not sym_match:
        sig.reason = "No recognisable symbol found"
        return sig
    raw_sym = sym_match.group(1).upper()
    # Normalise aliases
    sig.symbol = {"GOLD": "XAUUSD", "SILVER": "XAGUSD"}.get(raw_sym, raw_sym)

    # ── Side ──────────────────────────────────────────────────────────────────
    side_match = _SIDE_RE.search(text)
    if not side_match:
        sig.reason = "No BUY/SELL direction found"
        return sig
    raw_side = side_match.group(1).lower().replace(" ", "")
    if "buylimit" in raw_side or "buystop" in raw_side:
        sig.side = "buy"
        sig.order_type = raw_side
    elif "selllimit" in raw_side or "sellstop" in raw_side:
        sig.side = "sell"
        sig.order_type = raw_side
    else:
        sig.side = raw_side  # "buy" or "sell"
        sig.order_type = "market"

    # ── Entry ─────────────────────────────────────────────────────────────────
    for line in text.splitlines():
        if re.search(r"\b(entry|enter|price)\b|@", line, re.IGNORECASE):
            p = _price_after(r"\b(entry|enter|price)\b|@", line)
            if p:
                sig.entry = p
                break

    # ── SL ────────────────────────────────────────────────────────────────────
    for line in text.splitlines():
        if re.search(r"\bsl\b|\bstop\s*loss\b|\bstop\b", line, re.IGNORECASE):
            p = _price_after(r"\bsl\b|\bstop\s*loss\b|\bstop\b", line)
            if p:
                sig.sl = p
                break

    # ── TP ────────────────────────────────────────────────────────────────────
    sig.tp = _find_prices(r"\btp\d*\b|\btake\s*profit\b|\btarget\b", text)

    # ── Validation ────────────────────────────────────────────────────────────
    if not sig.sl:
        sig.reason = "No Stop Loss found — signal rejected"
        return sig
    if not sig.tp:
        sig.reason = "No Take Profit found — signal rejected"
        return sig

    if sig.order_type != "market" and sig.entry is None:
        sig.reason = "Pending order requires an entry price â€” signal rejected"
        return sig

    sig.valid = True
    sig.reason = "OK"
    return sig
