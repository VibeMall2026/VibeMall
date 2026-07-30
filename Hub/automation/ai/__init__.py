"""
AI provider selection
=====================

The pipeline calls :func:`is_configured` and :func:`get_client` and never names
a vendor. Three providers are supported:

``ollama``
    A local model — no API key, no quota, no per-token cost. Vision depends on
    the model: ``qwen3:8b`` is text-only, so the image pass is skipped;
    a multimodal model (llava, qwen2.5vl, gemma3) enables it automatically.

``claude``
    Anthropic. Highest quality; needs a paid API key.

``gemini``
    Google. Free tier with vision; key from https://aistudio.google.com/apikey

Selection follows ``AUTOMATION_AI_PROVIDER``. The default, ``auto``, prefers a
reachable Ollama server (it costs nothing per request), then Claude, then
Gemini.

Every client exposes the same surface: ``complete_json(system, content,
schema)``, ``.model`` and ``.total_tokens``, plus an optional
``supports_vision``. Adding a provider means one more class and one branch here
— prompts, schema and merge logic never change.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from .client import AIUnavailable, ClaudeClient
from .client import is_configured as claude_configured
from .gemini import GeminiClient, GeminiUnavailable
from .gemini import is_configured as gemini_configured
from .ollama import OllamaClient, OllamaUnavailable
from .ollama import base_url as ollama_base_url
from .ollama import is_configured as ollama_configured
from .ollama import model_name as ollama_model_name

logger = logging.getLogger(__name__)

__all__ = [
    'AIUnavailable',
    'ClaudeClient',
    'GeminiClient',
    'OllamaClient',
    'active_provider',
    'get_client',
    'is_configured',
    'provider_status',
]

PROVIDER_CLAUDE = 'claude'
PROVIDER_GEMINI = 'gemini'
PROVIDER_OLLAMA = 'ollama'


def _configured_provider() -> str:
    return (getattr(settings, 'AUTOMATION_AI_PROVIDER', 'auto') or 'auto').strip().lower()


def active_provider() -> str:
    """Which provider will actually be used, or ``''`` if none can be."""
    choice = _configured_provider()

    if choice == PROVIDER_OLLAMA:
        return PROVIDER_OLLAMA if ollama_configured() else ''
    if choice == PROVIDER_CLAUDE:
        return PROVIDER_CLAUDE if claude_configured() else ''
    if choice == PROVIDER_GEMINI:
        return PROVIDER_GEMINI if gemini_configured() else ''

    # auto: a reachable local model first — it has no key, quota or per-request
    # cost — then the hosted providers.
    if ollama_configured():
        return PROVIDER_OLLAMA
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

    if provider == PROVIDER_OLLAMA:
        try:
            return OllamaClient(**kwargs)
        except OllamaUnavailable as exc:
            # Callers only handle AIUnavailable, so normalise the exception type.
            raise AIUnavailable(str(exc)) from exc

    if provider == PROVIDER_CLAUDE:
        return ClaudeClient(**kwargs)

    if provider == PROVIDER_GEMINI:
        try:
            return GeminiClient(**kwargs)
        except GeminiUnavailable as exc:
            raise AIUnavailable(str(exc)) from exc

    choice = _configured_provider()
    if choice == PROVIDER_OLLAMA:
        raise AIUnavailable(
            f'AUTOMATION_AI_PROVIDER=ollama but no server answered at '
            f'{ollama_base_url()}. Start it with:  ollama serve'
        )
    if choice == PROVIDER_CLAUDE:
        raise AIUnavailable('AUTOMATION_AI_PROVIDER=claude but ANTHROPIC_API_KEY is not set.')
    if choice == PROVIDER_GEMINI:
        raise AIUnavailable('AUTOMATION_AI_PROVIDER=gemini but GEMINI_API_KEY is not set.')
    raise AIUnavailable(
        'No AI provider available. Start Ollama (ollama serve), or set '
        'GEMINI_API_KEY or ANTHROPIC_API_KEY in .env'
    )


def active_model() -> str:
    """Model name for the active provider."""
    provider = active_provider()
    if provider == PROVIDER_OLLAMA:
        return ollama_model_name()
    if provider == PROVIDER_CLAUDE:
        return getattr(settings, 'AUTOMATION_AI_MODEL', '')
    if provider == PROVIDER_GEMINI:
        return getattr(settings, 'AUTOMATION_GEMINI_MODEL', '')
    return ''


def provider_status() -> dict[str, Any]:
    """Summary for diagnostics."""
    return {
        'configured': _configured_provider(),
        'active': active_provider(),
        'claude_key': claude_configured(),
        'gemini_key': gemini_configured(),
        'ollama_up': ollama_configured(),
        'ollama_url': ollama_base_url(),
        'model': active_model(),
    }
