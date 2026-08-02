"""
AI usage stats
==============

Token spend is already recorded per draft (``ai_model``, ``ai_tokens_used`` -
see pipeline.py), so this module only aggregates it: today's and this
month's totals, against the free-tier ceiling for whichever model actually
answered most recently.

Limits below are read from each provider's published free-tier documentation
at the time they were added (Groq: console.groq.com/docs/rate-limits;
Gemini: ai.google.dev/gemini-api/docs/rate-limits) — not queried live, so a
provider changing its own limits will only show up here once someone updates
this table. Gemini has no clean *daily* token ceiling to show (its free tier
is a per-minute request count, not a token budget), so it reports a request
count instead of a token percentage.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

#: Daily token ceiling per model, free tier. Absent models (Claude, Ollama,
#: Gemini) fall through to "no published daily limit" rather than a guess.
DAILY_TOKEN_LIMITS: dict[str, int] = {
    'openai/gpt-oss-120b': 200_000,
    'openai/gpt-oss-20b': 200_000,
    'openai/gpt-oss-safeguard-20b': 200_000,
    'llama-3.1-8b-instant': 500_000,
    'llama-3.3-70b-versatile': 100_000,
    'qwen/qwen3.6-27b': 200_000,
}

#: Gemini's free tier is 15 requests/minute per model, not a daily token
#: budget - shown as a request ceiling instead when the active model is one
#: of these.
GEMINI_RPM_LIMIT = 15


def _is_gemini_model(model: str) -> bool:
    return model.startswith('gemini')


def _default_model_for(provider: str) -> str:
    """The client's own fallback default, for when no draft has run yet today."""
    if provider == 'groq':
        from .groq import DEFAULT_MODEL
        return DEFAULT_MODEL
    if provider == 'gemini':
        from .gemini import DEFAULT_MODEL
        return DEFAULT_MODEL
    from . import active_model
    return active_model()


def usage_summary() -> dict[str, Any]:
    """Everything the AI usage widget needs, in one query pass."""
    from django.db.models import Sum, Count

    from Hub.models import ProductDraft
    from . import active_provider

    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)

    today_agg = (
        ProductDraft.objects.filter(updated_at__gte=today_start, ai_tokens_used__gt=0)
        .aggregate(total=Sum('ai_tokens_used'))
    )
    month_agg = (
        ProductDraft.objects.filter(updated_at__gte=month_start, ai_tokens_used__gt=0)
        .aggregate(total=Sum('ai_tokens_used'))
    )
    tokens_today = today_agg['total'] or 0
    tokens_month = month_agg['total'] or 0

    requests_today = ProductDraft.objects.filter(
        updated_at__gte=today_start, ai_model__gt='',
    ).aggregate(n=Count('id'))['n'] or 0

    provider = active_provider()

    # Groq rotates between three models on quota, so "the configured model"
    # can be stale mid-day - the model that actually answered most recently
    # is the truthful answer to "what's running right now".
    latest = (
        ProductDraft.objects.filter(ai_model__gt='')
        .order_by('-updated_at')
        .values_list('ai_model', flat=True)
        .first()
    )
    model = latest or _default_model_for(provider)

    limit = DAILY_TOKEN_LIMITS.get(model)
    percent_used = None
    tokens_remaining_today = None
    limit_kind = 'none'
    if limit:
        percent_used = min(100, round(tokens_today / limit * 100, 1))
        tokens_remaining_today = max(0, limit - tokens_today)
        limit_kind = 'tokens'
    elif _is_gemini_model(model):
        limit = GEMINI_RPM_LIMIT
        limit_kind = 'rpm'

    return {
        'provider': provider or 'none',
        'model': model or '—',
        'tokens_today': tokens_today,
        'tokens_month': tokens_month,
        'requests_today': requests_today,
        'daily_limit': limit,
        # No provider here publishes a *monthly* token ceiling (Groq and
        # Gemini's free tiers are both per-minute/per-day only) - there is
        # nothing to compute a monthly percentage or remainder against, so
        # this stays a running total rather than inventing a number.
        'tokens_remaining_today': tokens_remaining_today,
        'limit_kind': limit_kind,  # 'tokens' | 'rpm' | 'none'
        'percent_used': percent_used,
        'is_near_limit': bool(percent_used is not None and percent_used >= 80),
        'is_at_limit': bool(percent_used is not None and percent_used >= 100),
        'as_of': now.strftime('%H:%M'),
    }
