"""
Google Gemini provider
======================

A free-tier alternative to Claude, exposing the same interface as
:class:`~Hub.automation.ai.client.ClaudeClient` so nothing downstream changes.

Why plain HTTP rather than an SDK: ``requests`` is already a dependency of this
project, so switching providers needs no ``pip install`` on the server. The
Gemini REST API is small enough that a wrapper is cheaper than a new package.

Two translations happen here, and they are the whole job:

* **Content blocks.** Callers build Anthropic-shaped blocks
  (``{"type": "image", "source": {...}}``); Gemini wants
  ``{"inline_data": {...}}``.
* **JSON schema.** Gemini uses an OpenAPI subset — upper-case type names, no
  ``additionalProperties``. :func:`to_gemini_schema` converts the shared schema
  so both providers are driven from one definition.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_ROOT = 'https://generativelanguage.googleapis.com/v1beta'

#: Free-tier default.
#:
#: Measured against this project's own extraction prompt: a full product
#: record in **3.6s**, with the right category at high confidence. The
#: full-size Flash aliases (`gemini-flash-latest`, `gemini-2.0-flash-lite`)
#: return 429 almost immediately on the free tier, which is what "Gemini only
#: gives a few tries" actually was — the wrong model, not an exhausted key.
DEFAULT_MODEL = 'gemini-3.1-flash-lite'

#: Free-tier quota is counted **per model**, not per key: the 429 detail names
#: ``GenerateRequestsPerMinutePerProjectPerModel-FreeTier``. Measured at 15
#: requests/minute per model, after which Google asks for a ~39s wait.
#:
#: So when one model is rate limited the cheapest response is not to sleep —
#: it is to ask a different model, which has its own untouched bucket. These
#: are the lite-class models that answer on the free tier, in preference
#: order; each one added roughly multiplies the sustainable throughput.
FALLBACK_MODELS = [
    'gemini-3.1-flash-lite',
    'gemini-flash-lite-latest',
    'gemini-2.0-flash-lite',
    'gemini-flash-latest',
]

DEFAULT_MAX_TOKENS = 8192

_TYPE_MAP = {
    'object': 'OBJECT',
    'array': 'ARRAY',
    'string': 'STRING',
    'integer': 'INTEGER',
    'number': 'NUMBER',
    'boolean': 'BOOLEAN',
}


def api_key() -> str:
    import os

    return (
        getattr(settings, 'GEMINI_API_KEY', '')
        or os.getenv('GEMINI_API_KEY', '')
        or os.getenv('GOOGLE_API_KEY', '')
        or ''
    ).strip()


def is_configured() -> bool:
    return bool(api_key())


def to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a JSON Schema to Gemini's OpenAPI subset.

    Unsupported keywords are dropped rather than approximated — the values they
    guarded are re-validated in :mod:`Hub.automation.ai.extraction` anyway, so
    losing them costs nothing and keeps the request valid.
    """
    if not isinstance(schema, dict):
        return {}

    converted: dict[str, Any] = {}

    raw_type = schema.get('type')
    if isinstance(raw_type, str):
        converted['type'] = _TYPE_MAP.get(raw_type.lower(), raw_type.upper())

    if schema.get('description'):
        converted['description'] = schema['description']

    # Gemini rejects an empty-string enum member, which the shared schema uses
    # to mean "no category fits". Drop it and let post-validation handle the
    # model picking something invalid.
    if isinstance(schema.get('enum'), list):
        values = [v for v in schema['enum'] if isinstance(v, str) and v.strip()]
        if values:
            converted['enum'] = values

    if isinstance(schema.get('properties'), dict):
        converted['properties'] = {
            name: to_gemini_schema(sub) for name, sub in schema['properties'].items()
        }
        # propertyOrdering makes output order deterministic, which keeps
        # responses stable between runs.
        converted['propertyOrdering'] = list(schema['properties'].keys())

    if isinstance(schema.get('required'), list):
        converted['required'] = list(schema['required'])

    if isinstance(schema.get('items'), dict):
        converted['items'] = to_gemini_schema(schema['items'])

    return converted


def to_gemini_parts(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate Anthropic-shaped content blocks into Gemini parts."""
    parts: list[dict[str, Any]] = []

    for block in content:
        kind = block.get('type')
        if kind == 'text':
            text = block.get('text') or ''
            if text:
                parts.append({'text': text})
        elif kind == 'image':
            source = block.get('source') or {}
            if source.get('type') == 'base64':
                parts.append(
                    {
                        'inline_data': {
                            'mime_type': source.get('media_type', 'image/jpeg'),
                            'data': source.get('data', ''),
                        }
                    }
                )
        # Any other block type is ignored rather than sent malformed.

    return parts


class GeminiUnavailable(RuntimeError):
    """Raised when Gemini cannot be used."""


class GeminiClient:
    """Gemini wrapper with the same surface as ``ClaudeClient``."""

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
            raise GeminiUnavailable(
                'GEMINI_API_KEY is not set. Create a free key at '
                'https://aistudio.google.com/apikey and add it to .env'
            )

        self._key = key
        # An unset AUTOMATION_GEMINI_MODEL arrives as '' rather than missing, so
        # a plain getattr default would hand back the empty string and DEFAULT_MODEL
        # would never apply.
        self.model = (
            model
            or (getattr(settings, 'AUTOMATION_GEMINI_MODEL', '') or '').strip()
            or DEFAULT_MODEL
        )
        self.max_tokens = max_tokens or int(
            getattr(settings, 'AUTOMATION_AI_MAX_TOKENS', DEFAULT_MAX_TOKENS)
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
        body = {
            'contents': [{'role': 'user', 'parts': to_gemini_parts(content)}],
            'systemInstruction': {'parts': [{'text': system}]},
            'generationConfig': {
                'responseMimeType': 'application/json',
                'responseSchema': to_gemini_schema(schema),
                'maxOutputTokens': self.max_tokens,
                # Low but non-zero: catalogue copy should vary between products
                # without drifting from the supplied facts.
                'temperature': 0.4,
            },
        }

        rotation = self.model_rotation()
        last_error: Exception | None = None
        quota_delay = 20

        for attempt in range(1, self.max_retries + 1):
            rate_limited = 0

            for model in rotation:
                outcome, payload = self._call(model, body)

                if outcome == 'ok':
                    # Report the model that actually answered, so the draft's
                    # audit trail names the one that produced the copy.
                    self.model = model
                    return payload

                if outcome == 'quota':
                    # This model's per-minute bucket is empty. Another model has
                    # its own, so try that before spending 39 seconds asleep.
                    rate_limited += 1
                    # A retired model reports 0; it must not shorten the wait a
                    # genuinely rate-limited model asked for.
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
                        '[gemini] All %d models rate limited on attempt %d/%d; waiting %ss',
                        len(rotation), attempt, self.max_retries, quota_delay,
                    )
                    time.sleep(quota_delay)
                continue

            if attempt < self.max_retries:
                time.sleep(min(5 * attempt, 30))

        raise GeminiUnavailable(f'Gemini request failed after {self.max_retries} attempts: {last_error}')

    def model_rotation(self) -> list[str]:
        """The configured model first, then the other free-tier lite models."""
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
                f'{API_ROOT}/models/{model}:generateContent',
                params={'key': self._key},
                json=body,
                timeout=180,
                headers={'Content-Type': 'application/json'},
            )
        except requests.RequestException as exc:
            logger.warning('[gemini] Network error on %s: %s', model, exc)
            return 'retry', exc

        if response.status_code == 200:
            try:
                return 'ok', self._parse(response.json())
            except ValueError as exc:
                logger.warning('[gemini] Bad response from %s: %s', model, exc)
                return 'retry', exc

        if response.status_code == 429:
            logger.info('[gemini] %s is rate limited; trying the next model.', model)
            return 'quota', self._retry_delay(response)

        if response.status_code == 404:
            # Google retires model aliases for new keys. Treat it like an empty
            # bucket so the rotation simply moves on instead of failing.
            logger.info('[gemini] %s is unavailable on this key; skipping.', model)
            return 'quota', 0

        if response.status_code in (500, 503):
            return 'retry', RuntimeError(f'Server error {response.status_code} from {model}.')

        # 400/403 will not fix themselves — surface immediately.
        return 'fatal', GeminiUnavailable(
            f'Gemini rejected the request ({response.status_code}): {self._error_detail(response)}'
        )

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _retry_delay(response: requests.Response, default: int = 20) -> int:
        """Seconds to wait, taken from Google's ``RetryInfo`` when present."""
        try:
            for detail in response.json().get('error', {}).get('details', []):
                if detail.get('@type', '').endswith('RetryInfo'):
                    raw = str(detail.get('retryDelay', '')).rstrip('s')
                    # A couple of seconds of headroom: the quota window is
                    # per-minute and the boundary is not ours to measure.
                    return min(max(int(float(raw)) + 2, 5), 90)
        except (ValueError, TypeError, AttributeError):
            pass
        return default

    @staticmethod
    def _error_detail(response: requests.Response) -> str:
        try:
            return str(response.json().get('error', {}).get('message', ''))[:300]
        except Exception:
            return response.text[:200]

    def _parse(self, payload: dict[str, Any]) -> dict[str, Any]:
        usage = payload.get('usageMetadata') or {}
        self.last_usage = {
            'input_tokens': int(usage.get('promptTokenCount') or 0),
            'output_tokens': int(usage.get('candidatesTokenCount') or 0),
        }

        candidates = payload.get('candidates') or []
        if not candidates:
            feedback = payload.get('promptFeedback') or {}
            raise ValueError(f'No candidates returned (feedback: {feedback}).')

        candidate = candidates[0]
        reason = candidate.get('finishReason')
        if reason in ('SAFETY', 'PROHIBITED_CONTENT', 'BLOCKLIST'):
            raise GeminiUnavailable(f'Gemini blocked this content ({reason}).')

        parts = ((candidate.get('content') or {}).get('parts')) or []
        text = ''.join(part.get('text', '') for part in parts).strip()
        if not text:
            raise ValueError(f'Empty response (finishReason={reason}).')

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            if reason == 'MAX_TOKENS':
                raise ValueError('Response truncated — raise AUTOMATION_AI_MAX_TOKENS.') from exc
            raise ValueError(f'Response was not valid JSON: {exc}') from exc

    @property
    def total_tokens(self) -> int:
        return sum(self.last_usage.get(k, 0) for k in ('input_tokens', 'output_tokens'))


def list_models() -> list[str]:
    """Model names available to this key — used by ``telegram_doctor``."""
    key = api_key()
    if not key:
        return []
    try:
        response = requests.get(f'{API_ROOT}/models', params={'key': key}, timeout=30)
        response.raise_for_status()
        names = []
        for model in response.json().get('models', []):
            if 'generateContent' in (model.get('supportedGenerationMethods') or []):
                names.append(str(model.get('name', '')).replace('models/', ''))
        return names
    except Exception as exc:
        logger.warning('[gemini] Could not list models: %s', exc)
        return []
