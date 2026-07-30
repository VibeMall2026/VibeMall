"""
Ollama provider (local models)
==============================

Runs extraction and copywriting against a self-hosted Ollama instance, so no
API key, quota or per-token cost is involved.

Exposes the same surface as the Claude and Gemini clients — ``complete_json``,
``model``, ``total_tokens`` — so prompts, schema, merge logic and every caller
stay exactly as they are.

Two things differ from the hosted providers, and both are handled here rather
than pushed onto callers:

* **Vision is model-dependent.** ``qwen3:8b`` is text-only. :attr:`supports_vision`
  is resolved from the model's own metadata, and the pipeline skips the image
  pass when it is false instead of sending images a model cannot read.
* **Local inference is slow.** On CPU an 8B model takes minutes for a long
  structured response, so the default timeout is minutes, not seconds.

Structured output uses Ollama's ``format`` parameter, which constrains
generation to a JSON schema — the same guarantee ``output_config.format`` gives
on Claude and ``responseSchema`` on Gemini.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = 'http://127.0.0.1:11434'
DEFAULT_MODEL = 'qwen3:8b'

#: Local generation is slow; this is a ceiling, not an expectation.
DEFAULT_TIMEOUT = 900

#: Model families Ollama reports for multimodal models.
VISION_FAMILIES = {'clip', 'mllama', 'qwen2vl', 'qwen2.5vl', 'gemma3', 'llava'}

#: Reasoning models can wrap their thinking in tags. With `format` set the
#: output is normally clean JSON, but stripping is cheap insurance.
_THINK_BLOCK = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)
_JSON_OBJECT = re.compile(r'\{.*\}', re.DOTALL)


def base_url() -> str:
    return str(getattr(settings, 'OLLAMA_BASE_URL', DEFAULT_BASE_URL) or DEFAULT_BASE_URL).rstrip('/')


def model_name() -> str:
    return str(getattr(settings, 'AUTOMATION_OLLAMA_MODEL', DEFAULT_MODEL) or DEFAULT_MODEL).strip()


def is_configured() -> bool:
    """
    True when an Ollama server is reachable.

    Unlike the hosted providers there is no key to check, so availability is
    the configuration — a stopped ``ollama serve`` is the equivalent of a
    missing key, and the pipeline should fall back to rules rather than fail.
    """
    try:
        response = requests.get(f'{base_url()}/api/tags', timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False


def list_models() -> list[str]:
    """Model names available on the server — used by ``telegram_doctor``."""
    try:
        response = requests.get(f'{base_url()}/api/tags', timeout=10)
        response.raise_for_status()
        return [str(m.get('name', '')) for m in response.json().get('models', [])]
    except requests.RequestException as exc:
        logger.warning('[ollama] Could not list models: %s', exc)
        return []


class OllamaUnavailable(RuntimeError):
    """Raised when the local model cannot be used."""


class OllamaClient:
    """Wraps Ollama's chat API with schema-constrained JSON output."""

    def __init__(
        self,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        max_retries: int = 2,
        timeout: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url()
        self.model = model or model_name()
        self.max_tokens = max_tokens or int(getattr(settings, 'AUTOMATION_AI_MAX_TOKENS', 8000))
        self.timeout = timeout or int(getattr(settings, 'AUTOMATION_OLLAMA_TIMEOUT', DEFAULT_TIMEOUT))
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.last_usage: dict[str, int] = {}
        self._supports_vision: bool | None = None

    # -- Capabilities -------------------------------------------------------

    @property
    def supports_vision(self) -> bool:
        """
        Whether the configured model can read images.

        Asked of the server rather than assumed, so swapping to a multimodal
        model (llava, qwen2.5vl, gemma3) enables the image pass with no code
        change. Result is cached for the client's lifetime.
        """
        if self._supports_vision is not None:
            return self._supports_vision

        override = getattr(settings, 'AUTOMATION_OLLAMA_VISION', None)
        if override is not None:
            self._supports_vision = bool(override)
            return self._supports_vision

        self._supports_vision = False
        try:
            response = self.session.post(
                f'{self.base_url}/api/show', json={'model': self.model}, timeout=20
            )
            if response.status_code == 200:
                payload = response.json()
                families = {
                    str(f).lower()
                    for f in (payload.get('details', {}).get('families') or [])
                }
                capabilities = {str(c).lower() for c in (payload.get('capabilities') or [])}
                self._supports_vision = bool(
                    families & VISION_FAMILIES or 'vision' in capabilities
                )
        except requests.RequestException as exc:
            logger.warning('[ollama] Could not read model capabilities: %s', exc)

        if not self._supports_vision:
            logger.info(
                '[ollama] %s has no vision support; image classification will use '
                'the positional fallback.', self.model,
            )
        return self._supports_vision

    # -- Core call ----------------------------------------------------------

    def complete_json(
        self,
        *,
        system: str,
        content: list[dict[str, Any]],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Run one schema-constrained request and return the parsed object."""
        text_parts, images = self._split_content(content)

        message: dict[str, Any] = {'role': 'user', 'content': '\n\n'.join(text_parts)}
        if images and self.supports_vision:
            message['images'] = images

        body = {
            'model': self.model,
            'messages': [{'role': 'system', 'content': system}, message],
            'stream': False,
            'format': schema,
            # Reasoning models otherwise spend the whole token budget thinking
            # before emitting the JSON.
            'think': False,
            'options': {
                'temperature': 0.4,
                'num_predict': self.max_tokens,
                'num_ctx': int(getattr(settings, 'AUTOMATION_OLLAMA_CONTEXT', 8192)),
            },
        }

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.post(
                    f'{self.base_url}/api/chat', json=body, timeout=self.timeout
                )
            except requests.Timeout as exc:
                last_error = exc
                logger.warning(
                    '[ollama] Timed out after %ss on attempt %d/%d — a local model on CPU '
                    'may need a longer AUTOMATION_OLLAMA_TIMEOUT.',
                    self.timeout, attempt, self.max_retries,
                )
            except requests.RequestException as exc:
                last_error = exc
                logger.warning('[ollama] Request failed on attempt %d/%d: %s', attempt, self.max_retries, exc)
            else:
                if response.status_code == 404:
                    raise OllamaUnavailable(
                        f"Model '{self.model}' is not present on the Ollama server. "
                        f'Pull it first:  ollama pull {self.model}'
                    )
                if response.status_code != 200:
                    detail = response.text[:200]
                    # `think` is rejected by older Ollama builds; retry without it
                    # rather than failing the draft over a version difference.
                    if 'think' in detail.lower() and 'think' in body:
                        logger.info('[ollama] Server rejected "think"; retrying without it.')
                        body.pop('think', None)
                        continue
                    raise OllamaUnavailable(f'Ollama returned {response.status_code}: {detail}')

                try:
                    return self._parse(response.json())
                except ValueError as exc:
                    last_error = exc
                    logger.warning('[ollama] Bad response on attempt %d: %s', attempt, exc)

            if attempt < self.max_retries:
                time.sleep(3)

        raise OllamaUnavailable(f'Ollama request failed after {self.max_retries} attempts: {last_error}')

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _split_content(content: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        """
        Flatten Anthropic-shaped content blocks into Ollama's shape.

        Ollama takes one text string plus a separate list of base64 images,
        rather than interleaved blocks.
        """
        texts: list[str] = []
        images: list[str] = []

        for block in content:
            kind = block.get('type')
            if kind == 'text':
                text = (block.get('text') or '').strip()
                if text:
                    texts.append(text)
            elif kind == 'image':
                source = block.get('source') or {}
                if source.get('type') == 'base64' and source.get('data'):
                    images.append(source['data'])

        return texts, images

    def _parse(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_usage = {
            'input_tokens': int(payload.get('prompt_eval_count') or 0),
            'output_tokens': int(payload.get('eval_count') or 0),
        }

        text = ((payload.get('message') or {}).get('content') or '').strip()
        if not text:
            raise ValueError(f"Empty response (done_reason={payload.get('done_reason')}).")

        text = _THINK_BLOCK.sub('', text).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # A model that ignores the schema sometimes wraps JSON in prose.
            match = _JSON_OBJECT.search(text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError as exc:
                    raise ValueError(f'Response was not valid JSON: {exc}') from exc
            raise ValueError('Response contained no JSON object.')

    @property
    def total_tokens(self) -> int:
        return sum(self.last_usage.get(k, 0) for k in ('input_tokens', 'output_tokens'))
