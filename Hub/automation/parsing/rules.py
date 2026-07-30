"""
Rule-based extraction
=====================

Regex/heuristic pass over the supplier message. It serves two purposes:

1. **Grounding.** Prices and sizes are the fields where a hallucination is most
   expensive, so we extract them deterministically and pass the result to the
   model as verified context rather than letting it infer them from prose.
2. **Fallback.** If the Anthropic API is unavailable or the key is unset, this
   alone still produces a usable draft — the admin gets something to approve
   instead of a failed job.

Nothing here is keyword-exhaustive by design; suppliers write in free form and
the AI layer handles the long tail. These rules cover the patterns that recur
across Indian apparel suppliers: ``₹799``, ``799/-``, ``Rs. 1,299``,
``M L XL XXL``, ``M-38 L-40``, and the ``FABRIC DETAILS / Top / Bottom /
Dupatta`` block layout.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

# --- Sizes -------------------------------------------------------------------

#: Alphabetic sizes, longest-first so "XXL" wins over "XL" when scanning.
LETTER_SIZES = ['XXXL', '3XL', 'XXL', '2XL', '4XL', '5XL', 'XL', 'XS', 'S', 'M', 'L']

# The optional trailing group captures chest measurements written either as
# "L-40" or bare as "L 40". \b after \d{2} stops "999" yielding a "99" size.
_SIZE_TOKEN = re.compile(
    r'\b(XS|S|M|L|XL|XXL|XXXL|[2-5]XL|FREE\s*SIZE|FREESIZE)\b(?:\s*[-–:]?\s*(\d{2})\b)?',
    re.IGNORECASE,
)
_NUMERIC_SIZE = re.compile(r'\b(2[6-9]|[3-5]\d)\b')
_SIZE_LINE_HINT = re.compile(r'\b(size|sizes|available\s+in|avl|अवेलेबल)\b', re.IGNORECASE)

# --- Prices ------------------------------------------------------------------

# The trailing (?!\d) is load-bearing: without it the comma-grouped branch
# matches only the first three digits of "1299" and the price becomes 129.
_MONEY = r'(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?!\d)'
_PRICE_PATTERNS = [
    re.compile(rf'₹\s*{_MONEY}'),
    re.compile(rf'\b(?:rs\.?|inr)\s*{_MONEY}', re.IGNORECASE),
    re.compile(rf'{_MONEY}\s*/-'),
    re.compile(rf'\bprice\b\s*[:\-]?\s*{_MONEY}', re.IGNORECASE),
]
_ORIGINAL_PRICE_PATTERNS = [
    re.compile(rf'\b(?:mrp|m\.r\.p\.?|retail|original|was)\b\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*{_MONEY}', re.IGNORECASE),
]
_SELLING_PRICE_PATTERNS = [
    re.compile(rf'\b(?:offer|sale|deal|now|selling|our)\s*price\b\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*{_MONEY}', re.IGNORECASE),
]

# --- Fabric ------------------------------------------------------------------

# Trailing \w* matters: suppliers write "Bottomwear Fabric: Georgette", and a
# strict \bbottom\b never matches inside "Bottomwear".
_FABRIC_COMPONENTS = {
    'top_fabric': re.compile(r'\b(top|topwear|kurti|kurta|shirt|upper|blouse)\w*\b', re.IGNORECASE),
    'bottom_fabric': re.compile(
        r'\b(bottom|bottomwear|pant|palazzo|plazo|salwar|sharara|lehenga|lower|skirt)\w*\b',
        re.IGNORECASE,
    ),
    'dupatta_fabric': re.compile(r'\b(dupatta|duppatta|stole|scarf)\w*\b', re.IGNORECASE),
    'inner_fabric': re.compile(r'\b(inner|lining|slip)\w*\b', re.IGNORECASE),
}

#: Common fabric names. Used to recognise a bare word on its own line as a fabric.
KNOWN_FABRICS = [
    'cotton', 'rayon', 'chiffon', 'georgette', 'silk', 'satin', 'crepe', 'linen',
    'denim', 'net', 'velvet', 'organza', 'chanderi', 'muslin', 'viscose', 'modal',
    'polyester', 'lycra', 'khadi', 'jacquard', 'brasso', 'tussar', 'banarasi',
    'cotton blend', 'poly cotton', 'blended', 'wool', 'nylon', 'spandex', 'tafeta',
    'taffeta', 'schiffli', 'dola silk', 'art silk', 'raw silk', 'pure cotton',
]

_FABRIC_LABEL = re.compile(r'\b(fabric|material|cloth|kapda)\b\s*[:\-]?\s*(.+)', re.IGNORECASE)

# --- Colours -----------------------------------------------------------------

#: Compound names must appear here too, otherwise "Navy Blue" is recorded as
#: two separate colours ("Navy" and "Blue") and produces two bogus variants.
KNOWN_COLORS = [
    'red', 'blue', 'navy blue', 'navy', 'sky blue', 'royal blue', 'dark green',
    'light green', 'bottle green', 'black', 'white', 'off white', 'cream',
    'green', 'olive', 'mint', 'yellow', 'mustard', 'orange', 'peach', 'pink',
    'rani pink', 'baby pink', 'magenta', 'purple', 'lavender', 'wine', 'maroon',
    'grey', 'gray', 'brown', 'beige', 'gold', 'golden', 'silver', 'rust',
    'teal', 'turquoise', 'coral', 'mauve', 'multicolor', 'multicolour',
]
_COLOR_LABEL = re.compile(r'\b(colou?rs?|shades?)\b\s*[:\-]?\s*(.+)', re.IGNORECASE)

# --- Misc --------------------------------------------------------------------

_STOCK = re.compile(r'\b(?:stock|qty|quantity|pieces?|pcs)\b\s*[:\-]?\s*(\d{1,5})', re.IGNORECASE)
_SKU = re.compile(r'\b(?:sku|style\s*(?:code|no\.?|number)|design\s*(?:code|no\.?)|code)\b\s*[:\-]?\s*([A-Za-z0-9\-_/]{3,30})', re.IGNORECASE)
_WEIGHT = re.compile(r'\b(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|gms|gram|grams)\b', re.IGNORECASE)


@dataclass
class RuleExtraction:
    """Everything the deterministic pass could establish. Empty values mean 'unknown'."""

    name: str = ''
    price: Decimal | None = None
    old_price: Decimal | None = None
    sizes: list[str] = field(default_factory=list)
    size_measurements: dict[str, str] = field(default_factory=dict)
    colors: list[str] = field(default_factory=list)
    fabric: str = ''
    fabric_components: dict[str, str] = field(default_factory=dict)
    stock: int | None = None
    sku: str = ''
    weight: str = ''

    def as_context(self) -> dict:
        """Compact dict handed to the model as verified ground truth."""
        return {
            'name_guess': self.name,
            'price': str(self.price) if self.price is not None else None,
            'old_price': str(self.old_price) if self.old_price is not None else None,
            'sizes': self.sizes,
            'size_measurements': self.size_measurements,
            'colors': self.colors,
            'fabric': self.fabric,
            'fabric_components': self.fabric_components,
            'stock': self.stock,
            'sku': self.sku,
            'weight': self.weight,
        }


def _to_decimal(raw: str) -> Decimal | None:
    try:
        value = Decimal(raw.replace(',', '').strip())
    except (InvalidOperation, AttributeError):
        return None
    # Reject implausible apparel prices — usually a phone number or a year.
    if value <= 0 or value > Decimal('1000000'):
        return None
    return value


def _extract_prices(text: str) -> tuple[Decimal | None, Decimal | None]:
    """
    Return ``(selling_price, original_price)``.

    Labelled values win. Otherwise, when several bare amounts appear, the
    lowest is treated as the selling price and the highest as the original —
    which is how suppliers almost always write "999 1499".
    """
    explicit_old = None
    for pattern in _ORIGINAL_PRICE_PATTERNS:
        match = pattern.search(text)
        if match:
            explicit_old = _to_decimal(match.group(1))
            break

    explicit_new = None
    for pattern in _SELLING_PRICE_PATTERNS:
        match = pattern.search(text)
        if match:
            explicit_new = _to_decimal(match.group(1))
            break

    found: list[Decimal] = []
    for pattern in _PRICE_PATTERNS:
        for match in pattern.finditer(text):
            value = _to_decimal(match.group(1))
            if value is not None and value not in found:
                found.append(value)

    if explicit_new is not None and explicit_old is not None:
        return explicit_new, explicit_old
    if explicit_new is not None:
        candidates = [v for v in found if v > explicit_new]
        return explicit_new, (max(candidates) if candidates else explicit_old)
    if explicit_old is not None:
        candidates = [v for v in found if v < explicit_old]
        return (min(candidates) if candidates else None), explicit_old

    if not found:
        return None, None

    if len(found) == 1:
        # A single unlabelled price in a supplier message is the supplier's own
        # price — i.e. the MRP / original price, not what we sell at. The
        # selling price is a margin decision the admin makes at approval, so
        # it is deliberately left empty rather than guessed.
        if supplier_price_is_mrp():
            return None, found[0]
        return found[0], None

    lowest, highest = min(found), max(found)
    # Two identical values, or a spread so wide it is probably not a discount pair.
    if highest == lowest or highest > lowest * 20:
        return (None, lowest) if supplier_price_is_mrp() else (lowest, None)
    return lowest, highest


def supplier_price_is_mrp() -> bool:
    """
    Whether an unlabelled supplier price means MRP rather than selling price.

    Defaults to True: suppliers quote their own price, and the store sets its
    own selling price per product.
    """
    from django.conf import settings

    return bool(getattr(settings, 'AUTOMATION_SUPPLIER_PRICE_IS_MRP', True))


#: Matches a whole line that is essentially just a price statement.
_PRICE_LINE = re.compile(
    r'^\s*(?:(?:offer|sale|deal|selling|our|net|final|mrp|m\.r\.p\.?|retail|original)\s*)?'
    r'price\b.*$|^\s*(?:₹|rs\.?|inr)\s*[\d,]+.*$|^\s*[\d,]+\s*/-\s*$',
    re.IGNORECASE,
)


def strip_price_mentions(text: str) -> str:
    """
    Remove prices from copy that will be shown to shoppers.

    The price belongs in the price field, not the description — a stale number
    baked into the description text outlives every repricing.
    """
    if not text:
        return ''

    lines = []
    for line in text.splitlines():
        if _PRICE_LINE.match(line.strip()):
            continue
        cleaned = line
        for pattern in _PRICE_PATTERNS + _ORIGINAL_PRICE_PATTERNS + _SELLING_PRICE_PATTERNS:
            cleaned = pattern.sub('', cleaned)
        # Tidy up punctuation left behind by the removal.
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip(' ,;:-–|')
        if cleaned:
            lines.append(cleaned)

    return '\n'.join(lines).strip()


def _normalise_size(token: str) -> str:
    cleaned = re.sub(r'\s+', '', token).upper()
    if cleaned in ('FREESIZE', 'FREE'):
        return 'Free Size'
    aliases = {'2XL': 'XXL', '3XL': 'XXXL'}
    return aliases.get(cleaned, cleaned)


def _is_size_only_line(line: str, matches: list[re.Match]) -> bool:
    """
    True when a line contains nothing but size tokens, numbers and separators.

    This is what makes single-letter sizes safe. Scanning ``\\bS\\b`` over free
    text matches the ``s`` in "Women's Premium Kurti"; restricting bare S/M/L
    to lines like ``M L XL`` or ``M 38`` removes that whole class of false
    positive while still reading the block layouts suppliers use.
    """
    remainder = line
    for match in matches:
        remainder = remainder.replace(match.group(0), ' ')
    remainder = re.sub(r'[\d\s,/&+|\-–:()\.]+', '', remainder)
    return not remainder


def _extract_sizes(text: str) -> tuple[list[str], dict[str, str]]:
    """Return ordered unique sizes plus any ``L-40`` style measurements."""
    sizes: list[str] = []
    measurements: dict[str, str] = {}

    def add(size: str) -> None:
        if size not in sizes:
            sizes.append(size)

    for line in text.splitlines():
        matches = list(_SIZE_TOKEN.finditer(line))
        if not matches:
            continue

        # Multi-character tokens (XL, XXL, XS, Free Size) are unambiguous
        # anywhere. Bare S/M/L need corroboration from the line's shape.
        permissive = bool(_SIZE_LINE_HINT.search(line)) or _is_size_only_line(line, matches)

        for match in matches:
            size = _normalise_size(match.group(1))
            if len(match.group(1).strip()) == 1 and not permissive:
                continue
            add(size)
            if match.group(2):
                measurements[size] = match.group(2)

    # Bare numeric sizes only count on a line that says "size", and only when
    # no letter sizes were found anywhere. A catalogue that already lists
    # "S M L XL" and then a chest chart ("34 36 38 40") is giving
    # measurements, not additional sizes — collecting both produced a
    # 16-entry size list on real supplier text.
    if not sizes:
        for line in text.splitlines():
            if not _SIZE_LINE_HINT.search(line):
                continue
            for match in _NUMERIC_SIZE.finditer(line):
                add(match.group(1))

    order = {s: i for i, s in enumerate(['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL', '4XL', '5XL', 'Free Size'])}
    sizes.sort(key=lambda s: order.get(s, 99))
    return sizes, measurements


def _extract_fabric(text: str) -> tuple[str, dict[str, str]]:
    """
    Pull the overall fabric plus per-component fabrics.

    Handles both inline (``Top: Cotton``) and the block layout suppliers often
    paste, where the component name and its fabric sit on consecutive lines::

        FABRIC DETAILS
        Top
        Cotton
        Bottom
        Rayon
    """
    lines = [line.strip() for line in text.splitlines()]
    components: dict[str, str] = {}

    def match_fabric_word(value: str) -> str:
        lowered = value.lower().strip(' .:-')
        for fabric in sorted(KNOWN_FABRICS, key=len, reverse=True):
            if fabric in lowered:
                return fabric.title()
        return ''

    def literal_value(value: str) -> str:
        """
        Accept the text after a ``Label:`` as the fabric even when it is not a
        name we know.

        Suppliers invent and rebrand fabric names constantly — real catalogues
        in this store list "Vichitra", "Tesla" and "Chinnon", none of which can
        be in a fixed list. Requiring a known name silently dropped them.
        """
        candidate = value.split(':')[-1].strip(' .,-–|')
        if not candidate or len(candidate) > 40:
            return ''
        # Letters and spaces only, so a stray price or size never lands here.
        if not re.fullmatch(r'[A-Za-z][A-Za-z\s/&-]*', candidate):
            return ''
        return candidate.title()

    for index, line in enumerate(lines):
        if not line:
            continue
        # The component word must OPEN the line. A product title such as
        # "Georgette Women Kurti With Dupatta & Bottomwear" mentions every
        # garment part, and a loose search let that one line define all three
        # fabrics as whatever the title happened to contain.
        stripped = line.lstrip(' *•−–-\t')
        for key, pattern in _FABRIC_COMPONENTS.items():
            if key in components or not pattern.match(stripped):
                continue

            # Inline: "Top - Cotton" or "Dupatta Fabric: Vichitra"
            tail = pattern.sub('', stripped, count=1).strip(' :-–')
            fabric = match_fabric_word(tail)
            if not fabric and ':' in stripped:
                fabric = literal_value(stripped)

            # Block layout: fabric is on the next non-empty line.
            if not fabric:
                for following in lines[index + 1:index + 3]:
                    if following:
                        fabric = match_fabric_word(following)
                        break

            if fabric:
                components[key] = fabric

    overall = ''
    label = _FABRIC_LABEL.search(text)
    if label:
        overall = match_fabric_word(label.group(2)) or literal_value(label.group(2))
    if not overall:
        overall = match_fabric_word(text)
    if not overall and components:
        overall = components.get('top_fabric', next(iter(components.values())))

    return overall, components


def _extract_colors(text: str) -> list[str]:
    colors: list[str] = []

    label = _COLOR_LABEL.search(text)
    scope = label.group(2) if label else text

    for color in sorted(KNOWN_COLORS, key=len, reverse=True):
        if re.search(rf'\b{re.escape(color)}\b', scope, re.IGNORECASE):
            title = color.title()
            if not any(title.lower() in existing.lower() for existing in colors):
                colors.append(title)

    return colors[:12]


#: Lines that are section headers rather than product names. When a supplier
#: leads with "FABRIC DETAILS", the first line is not the product.
_HEADER_LINE = re.compile(
    r'^\s*(fabric\s*details?|product\s*details?|details?|description|specifications?'
    r'|size\s*chart|sizes?|price|colou?rs?|features?|note)\s*[:\-]?\s*$',
    re.IGNORECASE,
)


#: Label prefixes suppliers put in front of the actual product name, e.g.
#: "Catalog Name:*Georgette Women Kurti*".
_NAME_LABEL = re.compile(
    r'^\s*(catalog(ue)?\s*name|product\s*name|item\s*name|name|title)\s*[:\-]\s*',
    re.IGNORECASE,
)


def _guess_name(text: str) -> str:
    """First substantive line, minus label prefixes, price noise and headers."""
    for line in text.splitlines():
        candidate = _NAME_LABEL.sub('', line)
        candidate = candidate.strip(' *_-•\t')
        if len(candidate) < 3:
            continue
        if re.fullmatch(r'[\W\d\s]+', candidate):
            continue
        if _HEADER_LINE.match(candidate):
            continue
        for pattern in _PRICE_PATTERNS:
            candidate = pattern.sub('', candidate)
        candidate = candidate.strip(' *_-•:\t')
        if len(candidate) >= 3:
            return candidate[:200]
    return ''


def extract_rules(text: str) -> RuleExtraction:
    """Run every deterministic rule over a supplier message."""
    text = text or ''
    price, old_price = _extract_prices(text)
    sizes, measurements = _extract_sizes(text)
    fabric, components = _extract_fabric(text)

    stock_match = _STOCK.search(text)
    sku_match = _SKU.search(text)
    weight_match = _WEIGHT.search(text)

    return RuleExtraction(
        name=_guess_name(text),
        price=price,
        old_price=old_price,
        sizes=sizes,
        size_measurements=measurements,
        colors=_extract_colors(text),
        fabric=fabric,
        fabric_components=components,
        stock=int(stock_match.group(1)) if stock_match else None,
        sku=sku_match.group(1).strip() if sku_match else '',
        weight=f'{weight_match.group(1)} {weight_match.group(2).lower()}' if weight_match else '',
    )
