"""
AI provider selection
=====================

The pipeline calls :func:`is_configured` and :func:`get_client` and never names
a vendor. Two providers are supported today:

``claude``
    Anthropic. Highest quality; needs a paid API key.

``gemini``
    Google. Has a **free tier** with vision and no credit card required —
    create a key at https://aistudio.google.com/apikey

Selection follows ``AUTOMATION_AI_PROVIDER``. The default, ``auto``, uses
whichever key is present, preferring Claude when both are — so adding a Claude
key later switches providers with no code or config change.

Both clients expose the same three things: ``complete_json(system, content,
schema)``, ``.model`` and ``.total_tokens``. Adding a third provider means one
more class with that surface plus a branch here.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from .client import AIUnavailable, ClaudeClient
from .client import is_configured as claude_configured
from .gemini import GeminiClient, GeminiUnavailable
from .gemini import is_configured as gemini_configured

logger = logging.getLogger(__name__)

__all__ = [
    'AIUnavailable',
    'ClaudeClient',
    'GeminiClient',
    'active_provider',
    'get_client',
    'is_configured',
    'provider_status',
]

PROVIDER_CLAUDE = 'claude'
PROVIDER_GEMINI = 'gemini'


def _configured_provider() -> str:
    return (getattr(settings, 'AUTOMATION_AI_PROVIDER', 'auto') or 'auto').strip().lower()


def active_provider() -> str:
    """Which provider will actually be used, or ``''`` if none can be."""
    choice = _configured_provider()

    if choice == PROVIDER_CLAUDE:
        return PROVIDER_CLAUDE if claude_configured() else ''
    if choice == PROVIDER_GEMINI:
        return PROVIDER_GEMINI if gemini_configured() else ''

    # auto: prefer Claude when available, otherwise fall back to Gemini.
    if claude_configured():
        return PROVIDER_CLAUDE
    if gemini_configured():
        return PROVIDER_GEMINI
    return ''


def is_configured() -> bool:
    """True when some provider is usable."""
    return bool(active_provider())


def get_client(**kwargs: Any):
    """Build a client for the active provider."""
    provider = active_provider()

    if provider == PROVIDER_CLAUDE:
        return ClaudeClient(**kwargs)

    if provider == PROVIDER_GEMINI:
        try:
            return GeminiClient(**kwargs)
        except GeminiUnavailable as exc:
            # Callers only handle AIUnavailable, so normalise the exception type.
            raise AIUnavailable(str(exc)) from exc

    choice = _configured_provider()
    if choice == PROVIDER_CLAUDE:
        raise AIUnavailable('AUTOMATION_AI_PROVIDER=claude but ANTHROPIC_API_KEY is not set.')
    if choice == PROVIDER_GEMINI:
        raise AIUnavailable('AUTOMATION_AI_PROVIDER=gemini but GEMINI_API_KEY is not set.')
    raise AIUnavailable(
        'No AI key configured. Set GEMINI_API_KEY (free — aistudio.google.com/apikey) '
        'or ANTHROPIC_API_KEY in .env'
    )


def provider_status() -> dict[str, Any]:
    """Summary for diagnostics."""
    return {
        'configured': _configured_provider(),
        'active': active_provider(),
        'claude_key': claude_configured(),
        'gemini_key': gemini_configured(),
        'model': (
            getattr(settings, 'AUTOMATION_AI_MODEL', '')
            if active_provider() == PROVIDER_CLAUDE
            else getattr(settings, 'AUTOMATION_GEMINI_MODEL', 'gemini-2.0-flash')
        ),
    }
