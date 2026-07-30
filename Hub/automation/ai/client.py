"""
Anthropic client wrapper
========================

A thin, dependency-optional layer over the ``anthropic`` SDK.

Two design choices worth knowing:

* **Graceful degradation.** If the SDK is not installed or ``ANTHROPIC_API_KEY``
  is unset, :func:`is_configured` returns ``False`` and the pipeline falls back
  to rule-based extraction only. Missing AI degrades draft quality; it never
  fails an import.
* **Structured output.** Extraction uses ``output_config.format`` with a JSON
  schema, so the model returns validated JSON rather than prose we have to
  parse. That removes an entire class of parsing bugs.

Model behaviour follows current Anthropic guidance: ``claude-opus-5`` with
adaptive thinking. Sampling parameters (``temperature`` / ``top_p``) are not
accepted on this model and are deliberately absent.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'claude-opus-5'
DEFAULT_MAX_TOKENS = 8000


class AIUnavailable(RuntimeError):
    """Raised when an AI call is attempted without a working configuration."""


def _sdk():
    """Import the SDK lazily so the app boots without it installed."""
    try:
        import anthropic  # noqa: PLC0415
    except ImportError:
        return None
    return anthropic


def is_configured() -> bool:
    """True when both the SDK and an API key are available."""
    return bool(_sdk()) and bool(_api_key())


def _api_key() -> str:
    import os

    return (getattr(settings, 'ANTHROPIC_API_KEY', '') or os.getenv('ANTHROPIC_API_KEY', '') or '').strip()


class ClaudeClient:
    """Wraps the Messages API with retries and JSON-schema enforcement."""

    def __init__(
        self,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        effort: str | None = None,
        max_retries: int = 3,
    ) -> None:
        sdk = _sdk()
        if sdk is None:
            raise AIUnavailable(
                "The 'anthropic' package is not installed. Run: pip install anthropic"
            )
        key = _api_key()
        if not key:
            raise AIUnavailable('ANTHROPIC_API_KEY is not set. Add it to your .env file.')

        self._sdk = sdk
        # The SDK already retries 429/5xx; ours covers the whole call including
        # schema-validation failures.
        self.client = sdk.Anthropic(api_key=key, max_retries=2)
        self.model = model or getattr(settings, 'AUTOMATION_AI_MODEL', DEFAULT_MODEL)
        self.max_tokens = max_tokens or int(getattr(settings, 'AUTOMATION_AI_MAX_TOKENS', DEFAULT_MAX_TOKENS))
        self.effort = effort or getattr(settings, 'AUTOMATION_AI_EFFORT', 'medium')
        self.max_retries = max_retries
        self.last_usage: dict[str, int] = {}

    # -- Core call ----------------------------------------------------------

    def complete_json(
        self,
        *,
        system: str,
        content: list[dict[str, Any]],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Run one request constrained to ``schema`` and return the parsed object.

        ``content`` is a Messages API content-block list, so callers can mix
        text and images freely.
        """
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    thinking={'type': 'adaptive'},
                    output_config={
                        'effort': self.effort,
                        'format': {'type': 'json_schema', 'schema': schema},
                    },
                    system=system,
                    messages=[{'role': 'user', 'content': content}],
                )
            except self._sdk.APIStatusError as exc:
                last_error = exc
                # 4xx other than rate limiting will not fix themselves.
                if exc.status_code < 500 and exc.status_code != 429:
                    logger.error('[ai] Non-retryable API error %s: %s', exc.status_code, exc)
                    raise
                logger.warning('[ai] API error %s on attempt %d/%d', exc.status_code, attempt, self.max_retries)
            except self._sdk.APIConnectionError as exc:
                last_error = exc
                logger.warning('[ai] Connection error on attempt %d/%d: %s', attempt, self.max_retries, exc)
            else:
                if response.stop_reason == 'refusal':
                    raise AIUnavailable(
                        'Claude declined this request '
                        f'({getattr(response.stop_details, "category", "unknown")}).'
                    )

                self._record_usage(response)

                text = next((b.text for b in response.content if b.type == 'text'), '')
                if not text.strip():
                    last_error = ValueError('Model returned an empty response.')
                else:
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError as exc:
                        # output_config.format makes this very unlikely, but a
                        # max_tokens truncation can still produce partial JSON.
                        last_error = exc
                        logger.warning(
                            '[ai] Invalid JSON on attempt %d/%d (stop_reason=%s)',
                            attempt, self.max_retries, response.stop_reason,
                        )

            if attempt < self.max_retries:
                time.sleep(min(2 ** attempt, 10))

        raise AIUnavailable(f'Claude request failed after {self.max_retries} attempts: {last_error}')

    def _record_usage(self, response: Any) -> None:
        usage = getattr(response, 'usage', None)
        if not usage:
            return
        self.last_usage = {
            'input_tokens': getattr(usage, 'input_tokens', 0) or 0,
            'output_tokens': getattr(usage, 'output_tokens', 0) or 0,
            'cache_read_input_tokens': getattr(usage, 'cache_read_input_tokens', 0) or 0,
        }

    @property
    def total_tokens(self) -> int:
        return sum(self.last_usage.get(k, 0) for k in ('input_tokens', 'output_tokens'))


def get_client(**kwargs: Any) -> ClaudeClient:
    """Build a client, raising :class:`AIUnavailable` if it cannot be configured."""
    return ClaudeClient(**kwargs)
