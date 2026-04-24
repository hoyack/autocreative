"""Vision evaluation stage — sends backgrounds to an LLM for approval and zone placement.

Resilience behavior (see flyer_generator.stages.llm_retry):
Ollama calls retry transient failures (429/500/502/503/timeouts) with exponential
backoff + jitter, honor Retry-After on 429, and fall through to
`settings.ollama_vision_model_fallbacks` on 404/model-unavailable. 4xx client
errors (400/401/403) raise immediately without retry or fallback.
"""

from __future__ import annotations

import base64
import json
import re
from typing import get_args

import httpx
import structlog
from anthropic import APIError, AsyncAnthropic
from pydantic import ValidationError

from flyer_generator.config import Settings
from flyer_generator.errors import VisionAPIError, VisionResponseParseError
from flyer_generator.models import FlyerInput, GeneratedBackground, LayoutZones, VisionVerdict
from flyer_generator.zones import ZoneName

logger = structlog.get_logger()

# D-17: Verbatim from n8n Build Vision Payload node
VISION_SYSTEM_PROMPT_EVENT = """You are a professional graphic designer evaluating AI-generated background images for event flyers. Your job has two parts:

1. APPROPRIATENESS: Determine if the image is suitable for the given event. Consider subject match, mood/tone, visual quality (not blurry/deformed), and absence of unwanted elements (text, watermarks, people with distorted features).

2. LAYOUT: If approved, identify the optimal placement zones for flyer text elements. The canvas is 1080 wide x 1920 tall (9:16 portrait). Classify zones using a 3x3 grid:
   - Rows: TOP (0-640px), MIDDLE (640-1280px), BOTTOM (1280-1920px)
   - Cols: LEFT (0-360px), CENTER (360-720px), RIGHT (720-1080px)

For each text element, pick the ZONE with the cleanest visual area (smooth, low-detail, good contrast for white text).

Text elements to place:
- TITLE (largest, 3-4 lines max): the event name
- DETAILS (date, time, venue): supporting info block
- FEE_BADGE (small pill): price/cost indicator
- ORG_CREDIT (tiny): presenter line at very bottom

Return ONLY valid JSON. No prose, no markdown fences. Schema:
{
  "approved": true|false,
  "confidence": 0.0-1.0,
  "rejection_reasons": [] | ["specific issue 1", ...],
  "refinement_hint": "" | "guidance for regeneration, e.g. 'more sky area at top, less visual clutter'",
  "zones": {
    "title": "TOP_CENTER" | "TOP_LEFT" | "TOP_RIGHT" | "MIDDLE_CENTER" | ...,
    "details": "BOTTOM_CENTER" | ...,
    "fee_badge": "TOP_RIGHT" | "BOTTOM_LEFT" | ...,
    "org_credit": "BOTTOM_CENTER"
  },
  "text_color": "white" | "dark",
  "mood_tags": ["warm", "energetic", ...]
}

If approved is false, zones can be omitted. Confidence below 0.6 should trigger rejection."""

# Subtype-aware prompt for informational flyers (announcements, public notices,
# educational posters, service promotions with no specific event date).
# Locked specification per Plan 22-02: TITLE + DESCRIPTION + ORG_CREDIT only;
# zones.details and zones.fee_badge MUST be null in the verdict.
VISION_SYSTEM_PROMPT_INFO = """You are a professional graphic designer evaluating AI-generated background images for informational flyers (announcements, public notices, educational posters, service promotions with no specific event date).

Unlike event flyers, informational flyers have NO date/time/venue/fees — they communicate a message, not an event.

Evaluate the image for informational-flyer use. Return ONLY valid JSON matching this schema:
{
  "approved": bool,
  "confidence": float (0.0-1.0),
  "rejection_reasons": [str, ...],
  "refinement_hint": str,
  "zones": {
    "title": "ZONE_NAME",
    "details": null,
    "fee_badge": null,
    "org_credit": "ZONE_NAME"
  },
  "text_color": "white" | "dark",
  "mood_tags": [str, ...]
}

Zone names: TOP_LEFT, TOP_CENTER, TOP_RIGHT, MIDDLE_LEFT, MIDDLE_CENTER, MIDDLE_RIGHT, BOTTOM_LEFT, BOTTOM_CENTER, BOTTOM_RIGHT.

Text elements to place on the image:
- TITLE (largest): the headline
- DESCRIPTION (multi-line body): the core message (rendered near or under the title; the composer handles placement using the TITLE zone's region + layout heuristics — DO NOT return a DESCRIPTION zone key; set details to null)
- ORG_CREDIT (tiny): sponsor/issuer line, typically at very bottom

zones.details and zones.fee_badge MUST be null. Only zones.title and zones.org_credit should name real zone keys.
"""

# Back-compat alias for any direct importers of the original constant.
# Prefer VISION_SYSTEM_PROMPT_EVENT in new code.
VISION_SYSTEM_PROMPT = VISION_SYSTEM_PROMPT_EVENT

_VALID_ZONE_NAMES = set(get_args(ZoneName))


class VisionEvaluator:
    """Sends generated backgrounds to a vision LLM for approval and zone placement.

    Supports two backends via settings.vision_provider:
    - "anthropic" (default): Anthropic Claude via the official SDK
    - "ollama": Any OpenAI-compatible endpoint (Ollama Cloud, local Ollama, etc.)
    """

    def __init__(
        self,
        settings: Settings,
        *,
        system_prompt: str | None = None,
        require_zones: bool = True,
    ) -> None:
        self._settings = settings
        self._system_prompt = system_prompt or VISION_SYSTEM_PROMPT
        self._require_zones = require_zones
        if settings.vision_provider == "ollama":
            self._anthropic_client: AsyncAnthropic | None = None
            self._httpx_client: httpx.AsyncClient | None = httpx.AsyncClient(
                base_url=settings.ollama_base_url.rstrip("/"),
                timeout=settings.vision_timeout_seconds,
                follow_redirects=True,
                headers={
                    "Authorization": f"Bearer {settings.ollama_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
            )
        else:
            self._anthropic_client = AsyncAnthropic(
                api_key=settings.anthropic_api_key.get_secret_value(),
                timeout=settings.vision_timeout_seconds,
            )
            self._httpx_client = None

    async def evaluate(
        self,
        background: GeneratedBackground,
        event: FlyerInput,
    ) -> VisionVerdict:
        """Evaluate a background image for flyer suitability.

        Sends the image + flyer context to the configured vision LLM, parses
        the response, applies confidence gating and zone validation. Retries
        once on parse failure.

        Branches system prompt + user context on ``event.subtype``:
          - ``"event"``: TITLE + DETAILS + FEE_BADGE + ORG_CREDIT zones.
          - ``"info"``:  TITLE + ORG_CREDIT zones; details/fee_badge null.
        """
        if event.subtype == "info":
            system_prompt = VISION_SYSTEM_PROMPT_INFO
            user_text = (
                f"Headline: {event.title}\n"
                f"Description: {event.description or ''}\n"
                f"Call to action: {event.call_to_action or ''}\n"
                f"Organizer: {event.org}\n"
                f"Style: {event.style_concept}"
            )
        else:
            system_prompt = VISION_SYSTEM_PROMPT_EVENT
            user_text = (
                f"Event: {event.title}\n"
                f"Date: {event.date or ''}\n"
                f"Time: {event.time or ''}\n"
                f"Venue: {event.location_name or ''}\n"
                f"Address: {event.location_address or ''}\n"
                f"Fees: {event.fees or ''}\n"
                f"Organizer: {event.org}\n"
                f"Style: {event.style_concept}"
            )
        return await self._call_backend(
            background=background,
            user_text=user_text,
            system_prompt=system_prompt,
        )

    async def _call_backend(
        self,
        *,
        background: GeneratedBackground,
        user_text: str,
        system_prompt: str | None = None,
    ) -> VisionVerdict:
        """Backend entry point that threads a per-call system-prompt override.

        Thin wrapper around ``_evaluate_with_text`` that accepts a
        ``GeneratedBackground`` (rather than raw bytes) so the subtype-aware
        ``evaluate()`` path and test patches have a clean seam. Direct byte
        callers (e.g. brochure ``evaluate_cover``) continue to use
        ``_evaluate_with_text`` without going through this method.
        """
        return await self._evaluate_with_text(
            background.image_bytes,
            user_text,
            system_prompt=system_prompt,
        )

    async def evaluate_cover(
        self,
        image_bytes: bytes,
        concept: str,
        style_preset: str = "",
    ) -> VisionVerdict:
        """Evaluate a hero image for brochure cover suitability.

        Concept-only (no date/venue/etc.), no zone assignment expected. Requires
        the evaluator to have been constructed with `require_zones=False` and a
        brochure-specific `system_prompt`.
        """
        user_text = f"Brochure cover concept: {concept}"
        if style_preset:
            user_text += f"\nStyle preset: {style_preset}"
        return await self._evaluate_with_text(image_bytes, user_text)

    async def _evaluate_with_text(
        self,
        image_bytes: bytes,
        user_text: str,
        *,
        system_prompt: str | None = None,
    ) -> VisionVerdict:
        """Shared vision evaluation path: send image + text, parse, validate, retry once.

        ``system_prompt`` is an optional per-call override. When ``None``, falls
        back to ``self._system_prompt`` (the evaluator default — typically
        ``VISION_SYSTEM_PROMPT_EVENT`` or a brochure-specific prompt).
        """
        img_b64 = base64.b64encode(image_bytes).decode()
        effective_system = system_prompt or self._system_prompt

        if self._settings.vision_provider == "ollama":
            raw_text = await self._call_ollama(img_b64, user_text, system_prompt=effective_system)
        else:
            raw_text = await self._call_anthropic(
                img_b64, user_text, system_prompt=effective_system
            )

        try:
            verdict = self._parse_and_validate(raw_text)
        except VisionResponseParseError:
            logger.warning("vision_parse_retry", raw_preview=raw_text[:200])
            if self._settings.vision_provider == "ollama":
                raw_text_retry = await self._call_ollama_retry(
                    img_b64, user_text, raw_text, system_prompt=effective_system
                )
            else:
                raw_text_retry = await self._call_anthropic_retry(
                    img_b64, user_text, raw_text, system_prompt=effective_system
                )
            verdict = self._parse_and_validate(raw_text_retry)

        logger.info(
            "vision_evaluated",
            approved=verdict.approved,
            confidence=verdict.confidence,
        )
        return verdict

    # ── Anthropic backend ──

    async def _call_anthropic(
        self,
        img_b64: str,
        user_text: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Call Anthropic Claude vision API.

        ``system_prompt`` overrides ``self._system_prompt`` for this call only.
        """
        assert self._anthropic_client is not None
        effective_system = system_prompt or self._system_prompt
        user_content: list[dict[str, object]] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": img_b64},
            },
            {"type": "text", "text": user_text},
        ]
        try:
            response = await self._anthropic_client.messages.create(
                model=self._settings.vision_model,
                max_tokens=self._settings.vision_max_tokens,
                system=effective_system,
                messages=[{"role": "user", "content": user_content}],
            )
        except APIError as exc:
            raise VisionAPIError(str(exc)) from exc
        return response.content[0].text

    async def _call_anthropic_retry(
        self,
        img_b64: str,
        user_text: str,
        raw_text: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Retry Anthropic call with conversation history."""
        assert self._anthropic_client is not None
        effective_system = system_prompt or self._system_prompt
        user_content: list[dict[str, object]] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": img_b64},
            },
            {"type": "text", "text": user_text},
        ]
        try:
            response = await self._anthropic_client.messages.create(
                model=self._settings.vision_model,
                max_tokens=self._settings.vision_max_tokens,
                system=effective_system,
                messages=[
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": raw_text},
                    {"role": "user", "content": "Return valid JSON only, no prose."},
                ],
            )
        except APIError as exc:
            raise VisionAPIError(str(exc)) from exc
        return response.content[0].text

    # ── Ollama / OpenAI-compatible backend ──

    async def _call_ollama(
        self,
        img_b64: str,
        user_text: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Call Ollama-compatible vision API via OpenAI /v1/chat/completions."""
        assert self._httpx_client is not None
        effective_system = system_prompt or self._system_prompt
        payload = {
            "model": self._settings.ollama_vision_model,
            "max_tokens": self._settings.vision_max_tokens,
            "messages": [
                {"role": "system", "content": effective_system},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                        },
                        {"type": "text", "text": user_text},
                    ],
                },
            ],
        }
        return await self._post_ollama(payload)

    async def _call_ollama_retry(
        self,
        img_b64: str,
        user_text: str,
        raw_text: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Retry Ollama call with conversation history."""
        assert self._httpx_client is not None
        effective_system = system_prompt or self._system_prompt
        payload = {
            "model": self._settings.ollama_vision_model,
            "max_tokens": self._settings.vision_max_tokens,
            "messages": [
                {"role": "system", "content": effective_system},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                        },
                        {"type": "text", "text": user_text},
                    ],
                },
                {"role": "assistant", "content": raw_text},
                {"role": "user", "content": "Return valid JSON only, no prose."},
            ],
        }
        return await self._post_ollama(payload)

    async def _post_ollama(self, payload: dict) -> str:
        """Send a request to the Ollama OpenAI-compatible endpoint with retry + model-fallback."""
        from flyer_generator.errors import LLMAPIError
        from flyer_generator.stages.llm_retry import _call_with_retry

        assert self._httpx_client is not None
        primary = self._settings.ollama_vision_model
        chain = [primary, *self._settings.ollama_vision_model_fallbacks]
        data = await _call_with_retry(
            self._httpx_client,
            "/v1/chat/completions",
            payload,
            model_chain=chain,
            max_attempts=self._settings.llm_retry_max_attempts,
            base_delay=self._settings.llm_retry_base_delay,
            max_delay=self._settings.llm_retry_max_delay,
            log=logger,
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMAPIError(
                f"Unexpected Ollama response format: {json.dumps(data)[:200]}"
            ) from exc

    # ── Shared parsing ──

    def _parse_and_validate(self, raw_text: str) -> VisionVerdict:
        """Parse raw LLM text into a validated VisionVerdict.

        Steps:
        1. Strip markdown fences
        2. Extract first { to last }
        3. JSON parse
        4. Confidence gate (D-21)
        5. Zone validation (D-22)
        6. Pydantic validation into VisionVerdict
        """
        # Step 1: strip markdown fences
        cleaned = re.sub(r"```json\s*", "", raw_text, flags=re.IGNORECASE)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()

        # Step 2: extract first {...} block
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace < 0 or last_brace <= first_brace:
            raise VisionResponseParseError(f"No JSON object found in: {raw_text[:200]}")
        json_str = cleaned[first_brace : last_brace + 1]

        # Step 3: parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise VisionResponseParseError(f"Invalid JSON: {exc}") from exc

        # Step 4: confidence gate (D-21)
        if data.get("approved") and isinstance(data.get("confidence"), (int, float)):
            if data["confidence"] < self._settings.vision_confidence_threshold:
                data["approved"] = False
                data.setdefault("rejection_reasons", []).append(
                    f"Low confidence: {data['confidence']}"
                )

        # Step 5: zone validation (D-22) — flyer-mode only
        if self._require_zones and data.get("approved"):
            zones = data.get("zones")
            if zones is None:
                data["approved"] = False
                data.setdefault("rejection_reasons", []).append(
                    "Zones missing for approved verdict"
                )
            elif isinstance(zones, dict):
                invalid_zones = [
                    f"{k}={v}" for k, v in zones.items() if v not in _VALID_ZONE_NAMES
                ]
                if invalid_zones:
                    data["approved"] = False
                    data["zones"] = None
                    data.setdefault("rejection_reasons", []).append(
                        f"Invalid zone names: {', '.join(invalid_zones)}"
                    )
        elif not self._require_zones:
            # Brochure / non-zone mode: drop zones entirely to avoid spurious validation
            data.pop("zones", None)

        # Step 6: Pydantic validation
        try:
            return VisionVerdict(**data, raw_response=raw_text[:4000])
        except ValidationError as exc:
            raise VisionResponseParseError(
                f"VisionVerdict validation failed: {exc}"
            ) from exc
