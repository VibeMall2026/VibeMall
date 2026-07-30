"""
Duplicate detection
===================

Suppliers resend the same product — a repost, a nudge, the same item forwarded
from two channels. Publishing it twice splits reviews and stock across two
listings, so a draft that looks like an existing product is flagged rather
than queued for approval.

Signals, strongest first:

===================  ======  =====================================================
Signal               Weight  Notes
===================  ======  =====================================================
Matching SKU            1.0  Conclusive on its own — SKU is unique on ``Product``
Near-identical image    0.8  Perceptual hash within a small Hamming distance
Very similar name       0.5  Token overlap, not exact string equality
Same price              0.2  Weak alone; meaningful as corroboration
Similar description     0.3  Token overlap on the long description
===================  ======  =====================================================

A combined score at or above :data:`DUPLICATE_THRESHOLD` marks the draft
``DUPLICATE``. The admin still sees it and can publish anyway — this warns, it
does not silently discard.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from .images import DUPLICATE_HAMMING_THRESHOLD, hamming

logger = logging.getLogger(__name__)

DUPLICATE_THRESHOLD = 0.8

#: Words too common in apparel titles to carry signal.
_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'for', 'with', 'in', 'of', 'to', 'new',
    'premium', 'designer', 'women', 'womens', 'men', 'mens', 'ladies', 'girls',
    'beautiful', 'latest', 'stylish', 'fancy', 'party', 'wear', 'set', 'piece',
}


@dataclass
class DuplicateMatch:
    """A candidate existing product, with why we think it matches."""

    product: Any
    score: float
    reasons: list[str] = field(default_factory=list)

    @property
    def is_duplicate(self) -> bool:
        return self.score >= DUPLICATE_THRESHOLD


def _tokens(text: str) -> set[str]:
    words = re.findall(r'[a-z0-9]+', (text or '').lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _similarity(a: str, b: str) -> float:
    """Jaccard overlap of significant tokens."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _to_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _candidate_products(record: dict[str, Any]) -> Any:
    """
    Narrow the search before scoring.

    Comparing against the whole catalogue would not scale to hundreds of
    products a day, so candidates are limited to products sharing a
    significant name token, plus any exact SKU match.
    """
    from django.db.models import Q

    from Hub.models import Product

    query = Q()
    for token in list(_tokens(record.get('name', '')))[:6]:
        query |= Q(name__icontains=token)

    sku = (record.get('sku') or '').strip()
    if sku:
        query |= Q(sku__iexact=sku)

    if not query:
        return Product.objects.none()

    return Product.objects.filter(query).only(
        'id', 'name', 'sku', 'price', 'description', 'slug', 'image'
    )[:60]


def _image_match(draft: Any, product: Any) -> bool:
    """True if any staged image is a near-duplicate of one of the product's images."""
    from Hub.models import ProductImage

    draft_hashes = [h for h in draft.images.values_list('phash', flat=True) if h]
    if not draft_hashes:
        return False

    # ProductImage rows do not store a hash, so hash the existing files on
    # demand. Bounded to keep the check cheap.
    from .images import difference_hash

    existing_paths: list[str] = []
    try:
        if product.image:
            existing_paths.append(product.image.path)
    except (ValueError, OSError):
        pass

    for image in ProductImage.objects.filter(product=product, is_active=True)[:8]:
        try:
            existing_paths.append(image.image.path)
        except (ValueError, OSError):
            continue

    for path in existing_paths[:9]:
        existing_hash = difference_hash(path)
        if not existing_hash:
            continue
        for draft_hash in draft_hashes:
            if hamming(draft_hash, existing_hash) <= DUPLICATE_HAMMING_THRESHOLD:
                return True
    return False


def find_duplicate(draft: Any, record: dict[str, Any]) -> DuplicateMatch | None:
    """
    Score the draft against existing products.

    Returns the best match when it clears the threshold, otherwise ``None``.
    """
    sku = (record.get('sku') or '').strip()
    name = record.get('name') or ''
    description = record.get('description') or ''
    price = _to_decimal(record.get('price'))

    best: DuplicateMatch | None = None

    for product in _candidate_products(record):
        score = 0.0
        reasons: list[str] = []

        if sku and product.sku and sku.lower() == product.sku.lower():
            score += 1.0
            reasons.append(f'Identical SKU "{product.sku}"')

        name_similarity = _similarity(name, product.name)
        if name_similarity >= 0.6:
            score += 0.5
            reasons.append(f'Name {int(name_similarity * 100)}% similar to "{product.name}"')

        description_similarity = _similarity(description, product.description or '')
        if description_similarity >= 0.55:
            score += 0.3
            reasons.append(f'Description {int(description_similarity * 100)}% similar')

        if price is not None and product.price is not None:
            product_price = _to_decimal(product.price)
            if product_price is not None and product_price == price:
                score += 0.2
                reasons.append(f'Same price (₹{price})')

        # Image hashing touches the filesystem, so only run it once the
        # cheap signals suggest this is worth checking.
        if score >= 0.3 and _image_match(draft, product):
            score += 0.8
            reasons.append('Near-identical product image')

        if score > 0 and (best is None or score > best.score):
            best = DuplicateMatch(product=product, score=round(score, 2), reasons=reasons)

    if best and best.is_duplicate:
        logger.info(
            '[duplicates] Draft %s matches product %s (score %.2f)',
            draft.pk, best.product.pk, best.score,
        )
        return best
    return None
