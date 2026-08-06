"""
AI marketing copy for the daily creative banner.

Reuses the same provider-agnostic AI layer as the product-intake pipeline
(``Hub.automation.ai`` — currently resolves to Groq's free tier on
production). If no provider is configured or the call fails, falls back to
a deterministic rule-based caption so the pipeline never blocks on AI.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

COPY_SCHEMA: dict[str, Any] = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['headline', 'caption', 'hashtags', 'cta'],
    'properties': {
        'headline': {
            'type': 'string',
            'description': 'Punchy banner headline, 4-8 words, no hashtags or emoji.',
        },
        'caption': {
            'type': 'string',
            'description': (
                'Instagram caption for this post, 2-4 short sentences, warm and '
                'exciting tone, may include 1-3 emoji. No hashtags in this field.'
            ),
        },
        'hashtags': {
            'type': 'array',
            'items': {'type': 'string'},
            'description': '8-12 relevant Instagram hashtags, no # symbol, no spaces.',
        },
        'cta': {
            'type': 'string',
            'description': 'Short call-to-action button phrase, 2-4 words, e.g. "Shop Now".',
        },
    },
}

SYSTEM_PROMPT = (
    'You are a senior fashion e-commerce copywriter for VibeMall, an Indian '
    'online fashion store. Write copy that feels premium, exciting and '
    'trustworthy - never generic, never overhyped, no false urgency. Prices '
    'are in Indian Rupees. Match the energy to the discount: a small discount '
    'gets a confident tone, a large discount can be more urgent.'
)


def _fallback_copy(product) -> dict[str, Any]:
    """Deterministic copy used when no AI provider is configured or the
    call fails - the pipeline must never block on this."""
    name = product.name.strip()
    return {
        'headline': name[:60],
        'caption': f"{name} just landed. Grab yours before it's gone!",
        'hashtags': ['fashion', 'style', 'vibemall', 'onlineshopping', 'trending', 'ootd', 'instafashion', 'sale'],
        'cta': 'Shop Now',
    }


def generate_copy(product) -> dict[str, Any]:
    """Returns {'headline','caption','hashtags','cta','provider'}."""
    from Hub.automation.ai import active_provider, get_client, is_configured

    if not is_configured():
        result = _fallback_copy(product)
        result['provider'] = ''
        return result

    old_price = getattr(product, 'old_price', None)
    discount = int(getattr(product, 'discount_percent', 0) or 0)
    facts = [
        f'Product name: {product.name}',
        f'Category: {product.get_category_display() if product.category else "Fashion"}',
        f'Price: Rs {int(product.price)}',
    ]
    if old_price and old_price > product.price:
        facts.append(f'Original price: Rs {int(old_price)}')
    if discount:
        facts.append(f'Discount: {discount}% off')
    if getattr(product, 'brand', ''):
        facts.append(f'Brand: {product.brand}')
    if getattr(product, 'rating', 0):
        facts.append(f'Customer rating: {product.rating}/5')

    try:
        client = get_client()
        result = client.complete_json(
            system=SYSTEM_PROMPT,
            content=[{'type': 'text', 'text': '\n'.join(facts)}],
            schema=COPY_SCHEMA,
        )
        headline = str(result.get('headline') or '').strip()[:200]
        caption = str(result.get('caption') or '').strip()
        hashtags = [str(h).strip().lstrip('#') for h in (result.get('hashtags') or []) if str(h).strip()]
        cta = str(result.get('cta') or '').strip()[:100] or 'Shop Now'
        if not headline or not caption or not hashtags:
            raise ValueError('AI returned incomplete copy')
        return {
            'headline': headline,
            'caption': caption,
            'hashtags': hashtags[:12],
            'cta': cta,
            'provider': active_provider(),
        }
    except Exception as exc:
        logger.warning('[marketing_copy] AI copy generation failed for product %s: %s', product.id, exc)
        result = _fallback_copy(product)
        result['provider'] = ''
        return result
