"""
Extraction orchestration
========================

Merges the deterministic pass with the model's output into the canonical
``ProductDraft.parsed`` record.

Precedence is deliberate: **rules win on commercial facts** (price, original
price, SKU, stock), because those are the fields where being wrong is
expensive and where regex is strictly more trustworthy than inference. The
model wins everywhere else — naming, copy, attributes, SEO — because that is
work regex cannot do.

If the AI is unavailable the same record is produced from rules alone, with
generated-but-honest copy. The draft is still reviewable; it just needs more
admin editing.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any

from django.utils.text import slugify

from ..parsing.rules import (
    RuleExtraction,
    extract_rules,
    strip_price_mentions,
    supplier_price_is_mrp,
)
from .client import AIUnavailable
from .prompts import EXTRACTION_SYSTEM, build_extraction_content
from .schema import EXTENDED_ATTRIBUTE_FIELDS, build_extraction_schema

logger = logging.getLogger(__name__)

#: Every key ``parsed`` is guaranteed to carry.
STRING_FIELDS = [
    'name', 'short_description', 'description', 'brand', 'sku',
    'price', 'old_price', 'stock', 'weight', 'dimensions',
    'meta_title', 'meta_description',
    'suggested_category', 'suggested_sub_category', 'category_confidence', 'category_reasoning',
] + EXTENDED_ATTRIBUTE_FIELDS

LIST_FIELDS = [
    'highlights', 'sizes', 'colors', 'meta_keywords', 'tags',
    'inferred_fields', 'warnings',
]


def empty_record() -> dict[str, Any]:
    """A fully-populated record with every field blank."""
    record: dict[str, Any] = {field: '' for field in STRING_FIELDS}
    record.update({field: [] for field in LIST_FIELDS})
    return record


def _clean_str(value: Any, limit: int = 2000) -> str:
    if value is None:
        return ''
    return str(value).strip()[:limit]


def _clean_list(value: Any, limit: int = 30) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    seen: list[str] = []
    for item in value:
        text = _clean_str(item, 200)
        if text and text.lower() not in {s.lower() for s in seen}:
            seen.append(text)
    return seen[:limit]


def _number_str(value: Any) -> str:
    """Normalise a numeric-ish value to a bare number string, or ''."""
    text = re.sub(r'[^\d.]', '', str(value or ''))
    if not text:
        return ''
    try:
        number = Decimal(text)
    except Exception:
        return ''
    if number <= 0:
        return ''
    return str(number.quantize(Decimal('0.01')).normalize())


def category_options() -> list[tuple[str, str]]:
    """
    The categories this store actually sells under, as ``(key, label)``.

    These come from ``CategoryIcon`` — the same rows that fill the storefront
    header and the Category dropdown on the review screen. ``Product``'s
    hardcoded ``CATEGORY_CHOICES`` is a stale template list (Mobiles,
    Furniture, Auto Acc, Sports) that this shop does not use, and offering it
    to the model meant a kurti had no correct answer available: "Furniture" was
    the least-wrong pick from a menu of wrong ones, and the admin could not
    even accept it, because the dropdown lists the real categories instead.

    Falls back to the model's list only when no categories are configured.
    """
    from Hub.models import CategoryIcon, Product

    rows = [
        ((icon.category_key or '').strip(), (icon.name or '').strip())
        for icon in CategoryIcon.objects.filter(is_active=True).order_by('order', 'id')
    ]
    options = [(key, label or key) for key, label in rows if key]
    return options or list(Product.CATEGORY_CHOICES)


def category_keys() -> list[str]:
    return [key for key, _label in category_options()]


def sub_category_options() -> list[str]:
    """Sub-category labels already in use, so a suggestion is selectable."""
    from Hub.models import SubCategory

    names = (
        SubCategory.objects.filter(is_active=True)
        .order_by('category_key', 'order', 'name')
        .values_list('name', flat=True)
    )
    seen: list[str] = []
    for name in names:
        cleaned = (name or '').strip()
        if cleaned and cleaned.lower() not in {s.lower() for s in seen}:
            seen.append(cleaned)
    return seen


# --------------------------------------------------------------------------
# Fallback copy (used when the AI is unavailable)
# --------------------------------------------------------------------------

def _fallback_description(rules: RuleExtraction, raw_text: str) -> str:
    """
    Assemble an honest description from known attributes only.

    Intentionally plain: it exists so the admin has something to edit, not to
    pass as marketing copy. It never asserts anything the supplier did not say.
    """
    name = rules.name or 'This product'
    parts = [f'{name}.']

    if rules.fabric:
        parts.append(f'Made from {rules.fabric.lower()}.')
    for label, key in (('Top', 'top_fabric'), ('Bottom', 'bottom_fabric'), ('Dupatta', 'dupatta_fabric')):
        value = rules.fabric_components.get(key)
        if value:
            parts.append(f'{label}: {value}.')
    if rules.sizes:
        parts.append(f'Available in {", ".join(rules.sizes)}.')
    if rules.colors:
        parts.append(f'Offered in {", ".join(rules.colors)}.')

    parts.append('Full details to be reviewed before publishing.')
    return ' '.join(parts)


def build_from_rules(rules: RuleExtraction, raw_text: str) -> dict[str, Any]:
    """Produce a complete record without any AI involvement."""
    record = empty_record()
    name = rules.name or 'Untitled Product'

    record.update(
        {
            'name': name[:200],
            'short_description': strip_price_mentions(
                (rules.fabric and f'{name} in {rules.fabric}.' or name)
            )[:160],
            'description': strip_price_mentions(_fallback_description(rules, raw_text)),
            'sku': rules.sku,
            'price': str(rules.price) if rules.price is not None else '',
            'old_price': str(rules.old_price) if rules.old_price is not None else '',
            'stock': str(rules.stock) if rules.stock is not None else '',
            'weight': rules.weight,
            'fabric': rules.fabric,
            'meta_title': name[:60],
            'meta_description': f'Buy {name} online at VibeMall.'[:160],
            'sizes': rules.sizes,
            'colors': rules.colors,
            'category_confidence': 'low',
            'category_reasoning': 'AI categorisation unavailable — please select manually.',
            'warnings': (
                ['Generated without AI: descriptions and attributes need review.']
                + (
                    [
                        f'Supplier price Rs.{rules.old_price} was recorded as the ORIGINAL price. '
                        'Enter your selling price before approving.'
                    ]
                    if rules.old_price is not None and rules.price is None
                    else []
                )
            ),
            'tags': [t for t in [rules.fabric, *rules.colors] if t][:10],
            'meta_keywords': [t for t in [name, rules.fabric, *rules.colors] if t][:10],
        }
    )
    record.update({key: value for key, value in rules.fabric_components.items() if value})
    return record


# --------------------------------------------------------------------------
# Merge
# --------------------------------------------------------------------------

def _merge(ai: dict[str, Any], rules: RuleExtraction) -> dict[str, Any]:
    """Normalise AI output and overlay the deterministic values that win."""
    record = empty_record()

    for field in STRING_FIELDS:
        record[field] = _clean_str(ai.get(field))
    for field in LIST_FIELDS:
        record[field] = _clean_list(ai.get(field))

    # --- Commercial facts: rules are authoritative -------------------------
    record['price'] = str(rules.price) if rules.price is not None else _number_str(record['price'])
    record['old_price'] = str(rules.old_price) if rules.old_price is not None else _number_str(record['old_price'])

    # The supplier quotes MRP, not our selling price. If the deterministic pass
    # read exactly one price and treated it as MRP, do not let the model's
    # guess sneak into the selling-price field — that number is the admin's
    # margin decision, made at approval.
    if supplier_price_is_mrp() and rules.old_price is not None and rules.price is None:
        record['price'] = ''
        record['warnings'].append(
            f'Supplier price Rs.{rules.old_price} was recorded as the ORIGINAL price. '
            'Enter your selling price before approving.'
        )

    # Prices must never live inside shopper-facing copy.
    record['description'] = strip_price_mentions(record['description'])
    record['short_description'] = strip_price_mentions(record['short_description'])
    record['stock'] = str(rules.stock) if rules.stock is not None else _number_str(record['stock'])
    if rules.sku:
        record['sku'] = rules.sku

    # An "original" price below the selling price is a misread — drop it
    # rather than publish a negative discount.
    try:
        if record['old_price'] and record['price'] and Decimal(record['old_price']) <= Decimal(record['price']):
            record['warnings'].append('Original price was not above the selling price; it has been cleared.')
            record['old_price'] = ''
    except Exception:
        record['old_price'] = ''

    # --- Sizes: union, rules first -----------------------------------------
    if rules.sizes:
        merged = list(rules.sizes)
        merged += [s for s in record['sizes'] if s.upper() not in {m.upper() for m in merged}]
        record['sizes'] = merged

    # --- Field-length limits matching the Product/ProductSEO columns -------
    record['name'] = record['name'][:200] or (rules.name or 'Untitled Product')[:200]
    record['short_description'] = record['short_description'][:160]
    record['meta_title'] = record['meta_title'][:60]
    record['meta_description'] = record['meta_description'][:160]
    record['brand'] = record['brand'][:100]
    record['sku'] = record['sku'][:100]
    record['weight'] = record['weight'][:50]
    record['dimensions'] = record['dimensions'][:100]
    record['suggested_sub_category'] = record['suggested_sub_category'][:100]

    if record['category_confidence'] not in ('high', 'medium', 'low'):
        record['category_confidence'] = 'low'

    valid_categories = set(category_keys())
    if record['suggested_category'] not in valid_categories:
        record['suggested_category'] = ''

    if not record['meta_title']:
        record['meta_title'] = record['name'][:60]
    if not record['short_description']:
        record['short_description'] = record['description'][:160]

    return record


def extract(
    *,
    raw_text: str,
    client: Any | None,
    image_findings: dict[str, Any] | None = None,
    source_label: str = 'Telegram',
) -> tuple[dict[str, Any], bool]:
    """
    Build the canonical parsed record.

    Returns ``(record, used_ai)`` so the caller can log which path ran.
    """
    rules = extract_rules(raw_text)

    if client is None:
        return build_from_rules(rules, raw_text), False

    categories = category_options()

    try:
        ai_output = client.complete_json(
            system=EXTRACTION_SYSTEM,
            content=build_extraction_content(
                raw_text=raw_text,
                verified=rules.as_context(),
                image_findings=image_findings,
                source_label=source_label,
                categories=categories,
                sub_categories=sub_category_options(),
            ),
            schema=build_extraction_schema([key for key, _ in categories]),
        )
    except AIUnavailable as exc:
        logger.warning('[extraction] AI unavailable, falling back to rules: %s', exc)
        record = build_from_rules(rules, raw_text)
        record['warnings'].append(f'AI extraction failed: {exc}')
        return record, False
    except Exception as exc:
        logger.exception('[extraction] Unexpected AI failure')
        record = build_from_rules(rules, raw_text)
        record['warnings'].append(f'AI extraction error: {exc}')
        return record, False

    return _merge(ai_output, rules), True


def suggested_slug(record: dict[str, Any]) -> str:
    """SEO-friendly slug stem derived from the product name."""
    return slugify(record.get('name') or 'product')[:180] or 'product'
