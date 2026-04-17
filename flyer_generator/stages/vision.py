"""Vision evaluation stage — sends backgrounds to Claude for approval and zone placement."""

from __future__ import annotations

import base64
import json
import re
from typing import get_args

import structlog
from anthropic import APIError, AsyncAnthropic
from pydantic import ValidationError

from flyer_generator.config import Settings
from flyer_generator.errors import VisionAPIError, VisionResponseParseError
from flyer_generator.models import EventInput, GeneratedBackground, LayoutZones, VisionVerdict
from flyer_generator.zones import ZoneName

logger = structlog.get_logger()

# D-17: Verbatim from n8n Build Vision Payload node
VISION_SYSTEM_PROMPT = """You are a professional graphic designer evaluating AI-generated background images for event flyers. Your job has two parts:

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

_VALID_ZONE_NAMES = set(get_args(ZoneName))


class VisionEvaluator:
    """Sends generated backgrounds to Claude vision for approval and zone placement."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.vision_timeout_seconds,
        )

    async def evaluate(
        self,
        background: GeneratedBackground,
        event: EventInput,
    ) -> VisionVerdict:
        """Evaluate a background image for flyer suitability.

        Sends the image + event context to Claude vision, parses the response,
        applies confidence gating and zone validation. Retries once on parse failure.
        """
        user_text = (
            f"Event: {event.title}\n"
            f"Date: {event.date}\n"
            f"Time: {event.time}\n"
            f"Venue: {event.location_name}\n"
            f"Address: {event.location_address}\n"
            f"Fees: {event.fees}\n"
            f"Organizer: {event.org}\n"
            f"Style: {event.style_concept}"
        )

        # D-18: encode at point of use, don't store
        img_b64 = base64.b64encode(background.image_bytes).decode()

        user_content: list[dict[str, object]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            },
            {"type": "text", "text": user_text},
        ]

        try:
            response = await self._client.messages.create(
                model=self._settings.vision_model,
                max_tokens=self._settings.vision_max_tokens,
                system=VISION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
        except APIError as exc:
            raise VisionAPIError(str(exc)) from exc

        raw_text = response.content[0].text

        try:
            verdict = self._parse_and_validate(raw_text)
        except VisionResponseParseError:
            # D-20: one retry with follow-up prompt
            logger.warning("vision_parse_retry", raw_preview=raw_text[:200])
            try:
                retry_response = await self._client.messages.create(
                    model=self._settings.vision_model,
                    max_tokens=self._settings.vision_max_tokens,
                    system=VISION_SYSTEM_PROMPT,
                    messages=[
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": raw_text},
                        {"role": "user", "content": "Return valid JSON only, no prose."},
                    ],
                )
            except APIError as exc:
                raise VisionAPIError(str(exc)) from exc

            raw_text_retry = retry_response.content[0].text
            verdict = self._parse_and_validate(raw_text_retry)

        logger.info(
            "vision_evaluated",
            approved=verdict.approved,
            confidence=verdict.confidence,
        )
        return verdict

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

        # Step 5: zone validation (D-22)
        if data.get("approved"):
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
                    data.setdefault("rejection_reasons", []).append(
                        f"Invalid zone names: {', '.join(invalid_zones)}"
                    )

        # Step 6: Pydantic validation
        try:
            return VisionVerdict(**data, raw_response=raw_text[:500])
        except ValidationError as exc:
            raise VisionResponseParseError(
                f"VisionVerdict validation failed: {exc}"
            ) from exc
