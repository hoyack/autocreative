"""Text-only LLM clients for the generative brochure pipeline.

Two implementations share a `TextClient` Protocol so upstream stages (outline, text, layout, fit, verify-critique) are backend-agnostic.

- `OllamaTextClient` — OpenAI-compatible /v1/chat/completions endpoint, uses `ollama_text_model` from settings.
- `AnthropicTextClient` — Anthropic Messages API, uses `vision_model` (same Claude for both text and vision in Anthropic mode).

Caller picks backend via `settings.vision_provider` and a factory helper.
"""

from __future__ import annotations

import json
import re
from typing import Literal, Protocol

import httpx
from anthropic import APIError, AsyncAnthropic

from flyer_generator.config import Settings
from flyer_generator.errors import VisionAPIError, VisionResponseParseError


class TextClient(Protocol):
    """Protocol for text-only LLM calls. Both Ollama and Anthropic implement this."""

    async def complete(
        self,
        *,
        system: str,
        user: str,
        response_format: Literal["text", "json"] = "text",
    ) -> str:
        """Return the model's response as a string.

        When `response_format == "json"`, retry once on parse failure and return
        the cleaned JSON body (still as a string; caller does json.loads).
        """
        ...


def _extract_json(raw: str) -> str:
    """Strip markdown fences and return the first {...} JSON object as text.

    Raises VisionResponseParseError if no balanced object is present *or* the
    extracted candidate fails to parse. Parse failures are wrapped so callers
    need only catch VisionResponseParseError.
    """
    cleaned = re.sub(r"```json\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first < 0 or last <= first:
        raise VisionResponseParseError(f"No JSON object found in: {raw[:200]}")
    candidate = cleaned[first : last + 1]
    # Validate parseability; raise a wrapped error so callers can retry uniformly.
    try:
        json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise VisionResponseParseError(
            f"Malformed JSON from model: {exc}. Preview: {candidate[:200]}"
        ) from exc
    return candidate


class OllamaTextClient:
    """Ollama / OpenAI-compatible text completion via httpx."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=settings.ollama_base_url.rstrip("/"),
            timeout=settings.vision_timeout_seconds,
            follow_redirects=True,
            headers={
                "Authorization": f"Bearer {settings.ollama_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
        )

    async def complete(
        self,
        *,
        system: str,
        user: str,
        response_format: Literal["text", "json"] = "text",
    ) -> str:
        raw = await self._call(system=system, user=user)
        if response_format == "json":
            try:
                return _extract_json(raw)
            except VisionResponseParseError:
                # One retry with a nudge.
                raw = await self._call(
                    system=system,
                    user=user + "\n\nReturn ONLY valid JSON. No prose, no markdown fences.",
                )
                return _extract_json(raw)
        return raw.strip()

    async def _call(self, *, system: str, user: str) -> str:
        from flyer_generator.errors import LLMAPIError
        from flyer_generator.stages.llm_retry import _call_with_retry

        payload = {
            "max_tokens": self._settings.text_max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        primary = self._settings.ollama_text_model
        chain = [primary, *self._settings.ollama_text_model_fallbacks]
        data = await _call_with_retry(
            self._http,
            "/v1/chat/completions",
            payload,
            model_chain=chain,
            max_attempts=self._settings.llm_retry_max_attempts,
            base_delay=self._settings.llm_retry_base_delay,
            max_delay=self._settings.llm_retry_max_delay,
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMAPIError(
                f"Unexpected Ollama response format: {json.dumps(data)[:200]}"
            ) from exc

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()


class AnthropicTextClient:
    """Anthropic Messages API text completion."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.vision_timeout_seconds,
        )

    async def complete(
        self,
        *,
        system: str,
        user: str,
        response_format: Literal["text", "json"] = "text",
    ) -> str:
        raw = await self._call(system=system, user=user)
        if response_format == "json":
            try:
                return _extract_json(raw)
            except VisionResponseParseError:
                raw = await self._call(
                    system=system,
                    user=user + "\n\nReturn ONLY valid JSON. No prose, no markdown fences.",
                )
                return _extract_json(raw)
        return raw.strip()

    async def _call(self, *, system: str, user: str) -> str:
        try:
            response = await self._client.messages.create(
                model=self._settings.vision_model,
                max_tokens=self._settings.text_max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except APIError as exc:
            raise VisionAPIError(str(exc)) from exc
        return response.content[0].text


def build_text_client(settings: Settings) -> TextClient:
    """Factory: return an OllamaTextClient or AnthropicTextClient based on settings."""
    if settings.vision_provider == "ollama":
        return OllamaTextClient(settings)
    return AnthropicTextClient(settings)
