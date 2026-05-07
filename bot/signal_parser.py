"""
Telegram signal parser.

Supports multiple formats:

Format 1 (standard):
  XAUUSD BUY
  Entry: 1920.00
  SL: 1915.00
  TP1: 1930.00
  TP2: 1940.00

Format 2 (inline entry):
  XAUUSD BUY @ 1920 SL 1915 TP 1930

Format 3 (@BENGOLDTRADER style):
  Sell Gold @4590-4600
  Sl :4605
  Tp1:4586
  Tp2:4580

Format 4 (@TFXC_FREE style with emojis):
  SELL XAUUSD 4546.2
  🤑TP1: 4544.2
  🔴SL: 4558.2

Format 5 (inline entry on symbol line):
  SELL XAUUSD 4546.2   ← price after symbol = entry
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

_PRICE_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _strip_emojis(text: str) -> str:
    """Remove emoji characters so regex word boundaries work correctly."""
    # Remove all non-ASCII and emoji unicode ranges
    return re.sub(
        r"[\U00010000-\U0010ffff"   # supplementary multilingual plane (emojis)
        r"\U00002600-\U000027BF"    # misc symbols
        r"\U0001F300-\U0001F9FF"    # emoticons, transport, etc.
        r"\u2600-\u27BF"            # misc symbols BMP
        r"]",
        "",
        text,
        flags=re.UNICODE,
    )


def _price(text: str, take: str = "first") -> Optional[float]:
    matches = _PRICE_RE.findall(text.replace(",", "."))
    if not matches:
        return None
    value = matches[0] if take == "first" else matches[-1]
    return float(value)


def _price_after(label_pattern: str, text: str) -> Optional[float]:
    """Extract first price after a label pattern in a line."""
    normalized = text.replace(",", ".")
    match = re.search(
        rf"(?:{label_pattern})\s*[:\s]\s*([\d]+(?:\.\d+)?)",
        normalized,
        re.IGNORECASE,
    )
    if match:
        return float(match.group(1))
    # Fallback: any number in the line
    return _price(normalized, take="first")


def _find_prices(label_pattern: str, text: str) -> list[float]:
    """Find all prices after a label (e.g. TP1, TP2, TP) across all lines."""
    results = []
    for line in text.splitlines():
        clean = _strip_emojis(line)
        if re.search(label_pattern, clean, re.IGNORECASE):
            p = _price_after(label_pattern, clean)
            if p:
                results.append(p)
    return results


# ── Regex patterns ────────────────────────────────────────────────────────────

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

# SL label — handles: SL, Sl, sl, Stop Loss, Stop, with optional space/colon
_SL_LABEL_RE = re.compile(
    r"(?:^|[\s\U00010000-\U0010ffff\U0001F300-\U0001F9FF\u2600-\u27BF])"
    r"(sl|stop\s*loss|stop)\s*[:\s]\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE | re.MULTILINE,
)

# TP label — handles: TP, TP1, TP2, tp1, with optional emoji prefix
_TP_LABEL_RE = re.compile(
    r"(?:^|[\s\U00010000-\U0010ffff\U0001F300-\U0001F9FF\u2600-\u27BF])"
    r"(tp\d*|take\s*profit|target)\s*[:\s]\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_sl(text: str) -> Optional[float]:
    """
    Extract SL price — handles:
    - 'SL: 1915'
    - 'Sl :4605'  (space before colon)
    - '🔴SL: 4558.2'  (emoji prefix)
    - 'Stop Loss: 1915'
    """
    # Strip emojis and try line by line
    for line in text.splitlines():
        clean = _strip_emojis(line).strip()
        # Match: SL / Sl / sl / Stop Loss / Stop followed by optional space, colon, space, number
        m = re.search(
            r"\b(sl|stop\s*loss|stop)\b\s*:?\s*(\d+(?:[.,]\d+)?)",
            clean,
            re.IGNORECASE,
        )
        if m:
            return float(m.group(2).replace(",", "."))
    return None


def _extract_tps(text: str) -> list[float]:
    """
    Extract all TP prices — handles:
    - 'TP1: 1930'
    - 'Tp1:4586'
    - '🤑TP1: 4544.2'  (emoji prefix)
    - 'Take Profit: 1930'
    """
    results = []
    for line in text.splitlines():
        clean = _strip_emojis(line).strip()
        m = re.search(
            r"\b(tp\d*|take\s*profit|target)\b\s*:?\s*(\d+(?:[.,]\d+)?)",
            clean,
            re.IGNORECASE,
        )
        if m:
            val = float(m.group(2).replace(",", "."))
            if val not in results:
                results.append(val)
    return results


def _extract_entry(text: str, symbol: str, side: str) -> Optional[float]:
    """
    Extract entry price — handles:
    - 'Entry: 1920'
    - 'XAUUSD BUY @ 1920'
    - 'Sell Gold @4590-4600'  → takes first price (4590)
    - 'SELL XAUUSD 4546.2'   → price inline after symbol+side
    """
    for line in text.splitlines():
        clean = _strip_emojis(line).strip()

        # Explicit entry label
        m = re.search(
            r"\b(entry|enter|price)\b\s*:?\s*(\d+(?:[.,]\d+)?)",
            clean,
            re.IGNORECASE,
        )
        if m:
            return float(m.group(2).replace(",", "."))

        # @ sign entry (e.g. "@ 1920" or "@4590-4600")
        m = re.search(r"@\s*(\d+(?:[.,]\d+)?)", clean)
        if m:
            return float(m.group(1).replace(",", "."))

    # Inline entry: price on same line as symbol+side
    # e.g. "SELL XAUUSD 4546.2" or "Buy Gold 1920.50"
    for line in text.splitlines():
        clean = _strip_emojis(line).strip()
        has_symbol = re.search(r"\b" + re.escape(symbol) + r"\b", clean, re.IGNORECASE)
        # Also check aliases (Gold → XAUUSD)
        if not has_symbol:
            if symbol == "XAUUSD" and re.search(r"\bgold\b", clean, re.IGNORECASE):
                has_symbol = True
            elif symbol == "XAGUSD" and re.search(r"\bsilver\b", clean, re.IGNORECASE):
                has_symbol = True
        has_side = re.search(r"\b(buy|sell)\b", clean, re.IGNORECASE)
        if has_symbol and has_side:
            # Find price on this line (skip the symbol/side words)
            prices = _PRICE_RE.findall(clean.replace(",", "."))
            # Filter out prices that look like years or very small numbers
            valid_prices = [float(p) for p in prices if float(p) > 100]
            if valid_prices:
                return valid_prices[0]

    return None


# ── Main parser ───────────────────────────────────────────────────────────────

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
    sig.entry = _extract_entry(text, sig.symbol, sig.side)

    # ── SL ────────────────────────────────────────────────────────────────────
    sig.sl = _extract_sl(text)

    # ── TP ────────────────────────────────────────────────────────────────────
    sig.tp = _extract_tps(text)

    # ── Validation ────────────────────────────────────────────────────────────
    if not sig.sl:
        sig.reason = "No Stop Loss found — signal rejected"
        return sig
    if not sig.tp:
        sig.reason = "No Take Profit found — signal rejected"
        return sig

    if sig.order_type != "market" and sig.entry is None:
        sig.reason = "Pending order requires an entry price — signal rejected"
        return sig

    sig.valid = True
    sig.reason = "OK"
    return sig
