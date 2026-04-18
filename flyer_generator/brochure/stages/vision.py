"""Brochure cover vision evaluator.

Thin factory that constructs a VisionEvaluator configured for brochure-cover
evaluation: custom system prompt (no 9-zone grid), require_zones=False so the
verdict parser doesn't reject zone-free approvals.
"""

from __future__ import annotations

from flyer_generator.config import Settings
from flyer_generator.stages.vision import VisionEvaluator

BROCHURE_COVER_SYSTEM_PROMPT = """You are a professional graphic designer evaluating AI-generated images for a tri-fold brochure cover panel.

Your job is to judge whether the image works as a landscape brochure cover.

EVALUATION CRITERIA:
1. SUBJECT MATCH: does the image depict the requested concept well?
2. MOOD & TONE: is the mood appropriate (professional, inviting, on-brand)?
3. VISUAL QUALITY: sharp, well-composed, no distorted people/hands/faces, no blurry smears, no unwanted artifacts.
4. COVER SUITABILITY: landscape framing, subject centred in the middle third, clean low-detail areas toward the left/right edges for overlaid title/subtitle text.
5. NO GRAPHIC OVERLAYS: must not already contain text, logos, UI elements, watermarks, or drawn borders — those are added at composition time.

Return ONLY valid JSON. No prose, no markdown fences. Schema:
{
  "approved": true|false,
  "confidence": 0.0-1.0,
  "rejection_reasons": [] | ["specific issue 1", ...],
  "refinement_hint": "" | "guidance for regeneration, e.g. 'more calm sky at top, move subject slightly left'",
  "text_color": "white" | "dark",
  "mood_tags": ["warm", "energetic", ...]
}

Do NOT include a "zones" field — brochure covers use a fixed layout. Confidence below 0.6 should trigger rejection."""


class BrochureCoverVisionEvaluator:
    """Convenience wrapper around VisionEvaluator for brochure cover evaluation.

    Under the hood this is a VisionEvaluator constructed with a brochure-specific
    system prompt and require_zones=False. Exposes a single method `evaluate(image_bytes, concept, style_preset)`
    that returns a VisionVerdict with `zones=None`.
    """

    def __init__(self, settings: Settings) -> None:
        self._inner = VisionEvaluator(
            settings,
            system_prompt=BROCHURE_COVER_SYSTEM_PROMPT,
            require_zones=False,
        )

    async def evaluate(
        self,
        image_bytes: bytes,
        concept: str,
        style_preset: str = "",
    ):  # returns VisionVerdict
        return await self._inner.evaluate_cover(
            image_bytes=image_bytes,
            concept=concept,
            style_preset=style_preset,
        )
