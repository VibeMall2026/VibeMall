"""
AI provider selection
=====================

The pipeline calls :func:`is_configured` and :func:`get_client` and never names
a vendor. Four providers are supported:

``ollama``
    A local model — no API key, no quota, no per-token cost. Vision depends on
    the model: ``qwen3:8b`` is text-only, so the image pass is skipped;
    a multimodal model (llava, qwen2.5vl, gemma3) enables it automatically.

``claude``
    Anthropic. Highest quality; needs a paid API key.

``gemini``
    Google. Free tier with vision; key from https://aistudio.google.com/apikey

``groq``
    Free, fast, text-only (no vision model on the free tier at the time this
    was written — pair it with ``gemini`` if images need analysing too). Key
    from https://console.groq.com/keys

Selection follows ``AUTOMATION_AI_PROVIDER``. The default, ``auto``, prefers a
reachable Ollama server (it costs nothing per request), then Claude, then
Gemini, then Groq.

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
from .groq import GroqClient, GroqUnavailable
from .groq import is_configured as groq_configured
from .ollama import OllamaClient, OllamaUnavailable
from .ollama import base_url as ollama_base_url
from .ollama import is_configured as ollama_configured
from .ollama import model_name as ollama_model_name

logger = logging.getLogger(__name__)

__all__ = [
    'AIUnavailable',
    'ClaudeClient',
    'GeminiClient',
    'GroqClient',
    'OllamaClient',
    'active_provider',
    'get_client',
    'get_vision_client',
    'is_configured',
    'provider_status',
]

PROVIDER_CLAUDE = 'claude'
PROVIDER_GEMINI = 'gemini'
PROVIDER_GROQ = 'groq'
PROVIDER_OLLAMA = 'ollama'

#: Values that switch AI off deliberately, rather than for want of a key.
#: The pipeline then runs purely on the rule-based extractor — which is also
#: what the test suite wants, so a test run can never call a live model.
PROVIDER_OFF = {'none', 'off', 'disabled', 'rules'}


def _configured_provider() -> str:
    """
    ``SiteSettings.ai_provider_override`` wins when set - it's how the admin
    panel's AI usage widget switches providers without a deploy, for when a
    quota runs out mid-day and waiting for a restart isn't an option. Falls
    through to the .env default when empty, which is what runs before the
    site settings row even exists (e.g. management commands, tests).
    """
    try:
        from Hub.models import SiteSettings
        override = (SiteSettings.get_settings().ai_provider_override or '').strip().lower()
        if override:
            return override
    except Exception:
        # Migrations not yet run, DB unreachable, or a test context with no
        # database at all - the .env value is always a safe fallback.
        pass
    return (getattr(settings, 'AUTOMATION_AI_PROVIDER', 'auto') or 'auto').strip().lower()


def active_provider() -> str:
    """Which provider will actually be used, or ``''`` if none can be."""
    choice = _configured_provider()

    if choice in PROVIDER_OFF:
        return ''
    if choice == PROVIDER_OLLAMA:
        return PROVIDER_OLLAMA if ollama_configured() else ''
    if choice == PROVIDER_CLAUDE:
        return PROVIDER_CLAUDE if claude_configured() else ''
    if choice == PROVIDER_GEMINI:
        return PROVIDER_GEMINI if gemini_configured() else ''
    if choice == PROVIDER_GROQ:
        return PROVIDER_GROQ if groq_configured() else ''

    # auto: a reachable local model first — it has no key, quota or per-request
    # cost — then the hosted providers.
    if ollama_configured():
        return PROVIDER_OLLAMA
    if claude_configured():
        return PROVIDER_CLAUDE
    if gemini_configured():
        return PROVIDER_GEMINI
    if groq_configured():
        return PROVIDER_GROQ
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

    if provider == PROVIDER_GROQ:
        try:
            return GroqClient(**kwargs)
        except GroqUnavailable as exc:
            raise AIUnavailable(str(exc)) from exc

    choice = _configured_provider()
    if choice in PROVIDER_OFF:
        raise AIUnavailable(
            f'AI is switched off (AUTOMATION_AI_PROVIDER={choice}). Drafts are '
            'extracted by the rule-based parser only.'
        )
    if choice == PROVIDER_OLLAMA:
        raise AIUnavailable(
            f'AUTOMATION_AI_PROVIDER=ollama but no server answered at '
            f'{ollama_base_url()}. Start it with:  ollama serve'
        )
    if choice == PROVIDER_CLAUDE:
        raise AIUnavailable('AUTOMATION_AI_PROVIDER=claude but ANTHROPIC_API_KEY is not set.')
    if choice == PROVIDER_GEMINI:
        raise AIUnavailable('AUTOMATION_AI_PROVIDER=gemini but GEMINI_API_KEY is not set.')
    if choice == PROVIDER_GROQ:
        raise AIUnavailable('AUTOMATION_AI_PROVIDER=groq but GROQ_API_KEY is not set.')
    raise AIUnavailable(
        'No AI provider available. Start Ollama (ollama serve), or set '
        'GEMINI_API_KEY, GROQ_API_KEY or ANTHROPIC_API_KEY in .env'
    )


#: Preference order for the vision step specifically, tried whenever the
#: active text provider cannot see images (Groq today). Not every entry has
#: to be configured — the first one that is wins.
_VISION_FALLBACK_ORDER = (PROVIDER_GEMINI, PROVIDER_CLAUDE, PROVIDER_OLLAMA)


def get_vision_client(**kwargs: Any):
    """
    Build a client for the image-analysis step.

    Extraction and vision do not have to share a provider — Groq is fast and
    free but text-only, so a Groq-primary setup still wants a real vision
    pass. This returns the active provider's own client when it already
    supports vision (unchanged from before this function existed), and only
    reaches for a different, vision-capable provider when it does not.
    """
    client = get_client(**kwargs)
    if getattr(client, 'supports_vision', True):
        return client

    for provider in _VISION_FALLBACK_ORDER:
        if provider == PROVIDER_GEMINI and gemini_configured():
            try:
                return GeminiClient(**kwargs)
            except GeminiUnavailable:
                continue
        if provider == PROVIDER_CLAUDE and claude_configured():
            return ClaudeClient(**kwargs)
        if provider == PROVIDER_OLLAMA and ollama_configured():
            try:
                candidate = OllamaClient(**kwargs)
            except OllamaUnavailable:
                continue
            if candidate.supports_vision:
                return candidate

    # Nothing else can see images either — the caller already handles a
    # text-only client by falling back to the positional image ordering.
    return client


def active_model() -> str:
    """Model name for the active provider."""
    provider = active_provider()
    if provider == PROVIDER_OLLAMA:
        return ollama_model_name()
    if provider == PROVIDER_CLAUDE:
        return getattr(settings, 'AUTOMATION_AI_MODEL', '')
    if provider == PROVIDER_GEMINI:
        return getattr(settings, 'AUTOMATION_GEMINI_MODEL', '')
    if provider == PROVIDER_GROQ:
        return getattr(settings, 'AUTOMATION_GROQ_MODEL', '')
    return ''


def provider_status() -> dict[str, Any]:
    """Summary for diagnostics."""
    return {
        'configured': _configured_provider(),
        'active': active_provider(),
        'claude_key': claude_configured(),
        'gemini_key': gemini_configured(),
        'groq_key': groq_configured(),
        'ollama_up': ollama_configured(),
        'ollama_url': ollama_base_url(),
        'model': active_model(),
    }
