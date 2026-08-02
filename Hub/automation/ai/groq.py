"""
Groq provider
=============

A fast, free-tier alternative for the text-only extraction step, exposing the
same interface as :class:`~Hub.automation.ai.client.ClaudeClient` so nothing
downstream changes. Groq's API is OpenAI-compatible, so this is a much
thinner translation than :mod:`Hub.automation.ai.gemini` needs — the shared
schema already satisfies Groq's ``strict`` requirements (every property
``required``, ``additionalProperties: false``) because that is also what
Claude's structured outputs demand.

No vision model is available on the free tier at the time this was written,
so this provider is wired for text-only extraction; image analysis stays on
Gemini. See :mod:`Hub.automation.ai` for how the two are split.

Quota is per model, not per key (mirrors Gemini), so
:meth:`GroqClient.model_rotation` tries the next model rather than sleeping
when one is exhausted — each model added roughly adds its own daily budget.
Only ``openai/gpt-oss-120b`` and ``openai/gpt-oss-20b`` support Groq's strict
mode (guaranteed schema-valid JSON); ``llama-3.1-8b-instant`` is listed last
and runs in best-effort mode as a last-resort overflow — occasionally
malformed output there still lands on the same rule-based fallback that
covers every other provider's failures.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_ROOT = 'https://api.groq.com/openai/v1'

DEFAULT_MODEL = 'openai/gpt-oss-120b'

#: In preference order. The first two support Groq's strict structured-output
#: mode (schema-guaranteed JSON); the third does not and is a last-resort
#: overflow once both strict-mode models are rate limited for the day.
FALLBACK_MODELS = [
    'openai/gpt-oss-120b',
    'openai/gpt-oss-20b',
    'llama-3.1-8b-instant',
]

#: https://console.groq.com/docs/structured-outputs — strict mode is only
#: honoured on these; every other model gets best-effort JSON mode instead.
STRICT_CAPABLE_MODELS = {'openai/gpt-oss-120b', 'openai/gpt-oss-20b'}

#: Deliberately far below AUTOMATION_AI_MAX_TOKENS (Claude's 8000 default,
#: shared with Gemini). Groq's per-minute limit is charged against *max*
#: completion tokens requested, not what the model actually returns - the
#: strict-mode gpt-oss models cap at 8K TPM total, so asking for an 8192
#: completion budget alone blows the whole window before a single prompt
#: token is counted. A product record's JSON runs a few hundred tokens; this
#: leaves comfortable headroom without eating the rate limit.
DEFAULT_MAX_TOKENS = 2048


def api_key() -> str:
    import os

    return (
        getattr(settings, 'GROQ_API_KEY', '')
        or os.getenv('GROQ_API_KEY', '')
        or ''
    ).strip()


def is_configured() -> bool:
    return bool(api_key())


def to_groq_content(content: list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    """
    Translate Anthropic-shaped content blocks into an OpenAI-style user
    message ``content`` value.

    Text-only input collapses to a plain string — Groq accepts either shape,
    and a string is what every extraction call actually sends today. Images
    only appear here if a future vision-capable model is added; encoded as a
    data URI, the OpenAI-compatible shape.
    """
    if all(block.get('type') == 'text' for block in content):
        return '\n\n'.join(block.get('text') or '' for block in content)

    parts: list[dict[str, Any]] = []
    for block in content:
        kind = block.get('type')
        if kind == 'text':
            text = block.get('text') or ''
            if text:
                parts.append({'type': 'text', 'text': text})
        elif kind == 'image':
            source = block.get('source') or {}
            if source.get('type') == 'base64':
                media_type = source.get('media_type', 'image/jpeg')
                data = source.get('data', '')
                parts.append({
                    'type': 'image_url',
                    'image_url': {'url': f'data:{media_type};base64,{data}'},
                })
    return parts


class GroqUnavailable(RuntimeError):
    """Raised when Groq cannot be used."""


class GroqClient:
    """Groq wrapper with the same surface as ``ClaudeClient``."""

    #: No vision model is available on the free tier at the time this was
    #: written — pipeline.py reads this to skip straight to the positional
    #: fallback instead of sending images nowhere.
    supports_vision = False

    def __init__(
        self,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        key = api_key()
        if not key:
            raise GroqUnavailable(
                'GROQ_API_KEY is not set. Create a free key at '
                'https://console.groq.com/keys and add it to .env'
            )

        self._key = key
        self.model = (
            model
            or (getattr(settings, 'AUTOMATION_GROQ_MODEL', '') or '').strip()
            or DEFAULT_MODEL
        )
        # A dedicated setting, not AUTOMATION_AI_MAX_TOKENS - that one is
        # shared with Claude/Gemini, defaults to 8000, and would reintroduce
        # the TPM problem DEFAULT_MAX_TOKENS above exists to avoid.
        self.max_tokens = max_tokens or int(
            getattr(settings, 'AUTOMATION_GROQ_MAX_TOKENS', 0) or DEFAULT_MAX_TOKENS
        )
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.last_usage: dict[str, int] = {}

    # -- Core call ----------------------------------------------------------

    def complete_json(
        self,
        *,
        system: str,
        content: list[dict[str, Any]],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Run one schema-constrained request and return the parsed object."""
        user_content = to_groq_content(content)

        rotation = self.model_rotation()
        last_error: Exception | None = None
        quota_delay = 20

        for attempt in range(1, self.max_retries + 1):
            rate_limited = 0

            for model in rotation:
                body = {
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': system},
                        {'role': 'user', 'content': user_content},
                    ],
                    'max_completion_tokens': self.max_tokens,
                    # Low but non-zero: catalogue copy should vary between
                    # products without drifting from the supplied facts.
                    'temperature': 0.4,
                    'response_format': {
                        'type': 'json_schema',
                        'json_schema': {
                            'name': 'product_extraction',
                            'strict': model in STRICT_CAPABLE_MODELS,
                            'schema': schema,
                        },
                    },
                }

                outcome, payload = self._call(model, body)

                if outcome == 'ok':
                    # Report the model that actually answered, so the draft's
                    # audit trail names the one that produced the copy.
                    self.model = model
                    return payload

                if outcome == 'quota':
                    # This model's daily/per-minute bucket is empty. Another
                    # model has its own, so try that before sleeping.
                    rate_limited += 1
                    if payload:
                        quota_delay = max(quota_delay, payload) if rate_limited > 1 else payload
                    continue

                if outcome == 'fatal':
                    raise payload

                last_error = payload
                break  # network or server-side: back off rather than hammer

            if rate_limited == len(rotation):
                last_error = RuntimeError('Free-tier quota exceeded on every model.')
                if attempt < self.max_retries:
                    logger.warning(
                        '[groq] All %d models rate limited on attempt %d/%d; waiting %ss',
                        len(rotation), attempt, self.max_retries, quota_delay,
                    )
                    time.sleep(quota_delay)
                continue

            if attempt < self.max_retries:
                time.sleep(min(5 * attempt, 30))

        raise GroqUnavailable(f'Groq request failed after {self.max_retries} attempts: {last_error}')

    def model_rotation(self) -> list[str]:
        """The configured model first, then the other free-tier models."""
        ordered = [self.model]
        for name in FALLBACK_MODELS:
            if name not in ordered:
                ordered.append(name)
        return ordered

    def _call(self, model: str, body: dict[str, Any]) -> tuple[str, Any]:
        """
        One request to one model.

        Returns ``(outcome, payload)`` where outcome is ``ok`` (parsed record),
        ``quota`` (seconds to wait), ``fatal`` (exception to raise) or
        ``retry`` (exception, worth another attempt).
        """
        try:
            response = self.session.post(
                f'{API_ROOT}/chat/completions',
                json=body,
                timeout=180,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self._key}',
                },
            )
        except requests.RequestException as exc:
            logger.warning('[groq] Network error on %s: %s', model, exc)
            return 'retry', exc

        if response.status_code == 200:
            try:
                return 'ok', self._parse(response.json())
            except ValueError as exc:
                logger.warning('[groq] Bad response from %s: %s', model, exc)
                return 'retry', exc

        if response.status_code == 429:
            logger.info('[groq] %s is rate limited; trying the next model.', model)
            return 'quota', self._retry_delay(response)

        if response.status_code == 404:
            # A model name Groq has retired or this key cannot see. Treat it
            # like an empty bucket so the rotation simply moves on.
            logger.info('[groq] %s is unavailable on this key; skipping.', model)
            return 'quota', 0

        if response.status_code in (500, 502, 503):
            return 'retry', RuntimeError(f'Server error {response.status_code} from {model}.')

        detail = self._error_detail(response)

        # Strict mode's constrained decoding failed to produce output
        # matching the schema on THIS model for THIS input - Groq's own
        # wording is "Failed to generate JSON... see 'failed_generation'".
        # That is a property of the model, not the request: gpt-oss-20b (also
        # strict) or llama-3.1-8b-instant (best-effort, no constrained
        # decoding to fail) can still succeed on the exact same body. Treated
        # as fatal, this used to abort the whole rotation on attempt one and
        # fall the caller straight through to the rule-based extractor -
        # which is how three real products got published with a placeholder
        # description ("Full details to be reviewed before publishing")
        # despite two working fallback models sitting right there unused.
        if response.status_code == 400 and 'failed to generate json' in detail.lower():
            logger.info('[groq] %s could not satisfy strict mode; trying the next model.', model)
            return 'quota', 0

        # Every other 400/401/403 will not fix themselves — surface immediately.
        return 'fatal', GroqUnavailable(
            f'Groq rejected the request ({response.status_code}): {detail}'
        )

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _retry_delay(response: requests.Response, default: int = 20) -> int:
        """Seconds to wait — Groq's ``Retry-After`` header when present."""
        header = response.headers.get('Retry-After')
        if header:
            try:
                return min(max(int(float(header)) + 2, 5), 90)
            except (ValueError, TypeError):
                pass
        return default

    @staticmethod
    def _error_detail(response: requests.Response) -> str:
        try:
            return str(response.json().get('error', {}).get('message', ''))[:300]
        except Exception:
            return response.text[:200]

    def _parse(self, payload: dict[str, Any]) -> dict[str, Any]:
        usage = payload.get('usage') or {}
        self.last_usage = {
            'input_tokens': int(usage.get('prompt_tokens') or 0),
            'output_tokens': int(usage.get('completion_tokens') or 0),
        }

        choices = payload.get('choices') or []
        if not choices:
            raise ValueError('No choices returned.')

        choice = choices[0]
        reason = choice.get('finish_reason')
        text = ((choice.get('message') or {}).get('content') or '').strip()
        if not text:
            raise ValueError(f'Empty response (finish_reason={reason}).')

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            if reason == 'length':
                raise ValueError('Response truncated — raise AUTOMATION_GROQ_MAX_TOKENS.') from exc
            raise ValueError(f'Response was not valid JSON: {exc}') from exc

    @property
    def total_tokens(self) -> int:
        return sum(self.last_usage.get(k, 0) for k in ('input_tokens', 'output_tokens'))
