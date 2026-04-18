"""Stage 1: Outline generation.

Given a BrochurePrompt, return a BrochureOutline with 2-5 sections, tone, CTA intent, and suggested preset/accent.
"""

from __future__ import annotations

import json

from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    BrochurePrompt,
)
from flyer_generator.brochure.llm_client import TextClient
from flyer_generator.errors import VisionResponseParseError

OUTLINE_SYSTEM_PROMPT = """You are a senior brochure copywriter. Your job is to \
produce a structured outline for a US Letter tri-fold brochure based on a user \
prompt. Output JSON only — no prose, no markdown fences."""


def _build_user_prompt(p: BrochurePrompt) -> str:
    ctx_lines = []
    if p.audience:
        ctx_lines.append(f"Audience/tone: {p.audience}")
    if p.style_preset:
        ctx_lines.append(f"Style preset (locked): {p.style_preset}")
    if p.color_accent:
        ctx_lines.append(f"Accent color (locked): {p.color_accent}")
    ctx_lines.append(f"Target section length: {p.target_length}")
    ctx = "\n".join(ctx_lines) if ctx_lines else "No additional context."

    return f"""User prompt: {p.prompt}

Context:
{ctx}

Return JSON with this exact shape:
{{
  "sections": [
    {{"heading": "...", "body_brief": "one-sentence direction", "image_hint": "...|null", "panel_role": "cover|feature|detail|cta", "cover_image_concept": "...|null"}},
    ...
  ],
  "tone": "short phrase describing overall tone",
  "cta_intent": "one sentence describing the back-panel call to action",
  "suggested_preset": "photorealistic|anime|western_cartoon|scifi|watercolor|retro_poster",
  "suggested_accent": "#RRGGBB"
}}

Rules:
- 2 to 5 sections total.
- Exactly ONE section must have panel_role="cover" (the hero section).
- image_hint may be non-null on at most 3 sections total.
- If user specified style_preset or color_accent above, echo them in suggested_preset / suggested_accent.
- suggested_accent must be a 6-digit hex color like #2E8B57.
- body_brief should be a one-sentence direction for a copywriter, NOT the final body text.
- cover_image_concept is REQUIRED on the cover section and must describe a concrete VISUAL scene to render (e.g. "sunlit yoga studio with potted plants and a folded mat"). Keep it to one sentence with concrete nouns + adjectives. Set it to null on non-cover sections."""


class BrochureOutlineError(Exception):
    """Raised when outline generation fails validation after retries."""


async def generate_outline(prompt: BrochurePrompt, text_client: TextClient) -> BrochureOutline:
    """Ask the LLM for a structured outline and return a validated BrochureOutline.

    Raises BrochureOutlineError if the LLM returns unparseable or invalid JSON
    after one retry.
    """
    user_text = _build_user_prompt(prompt)
    try:
        raw_json = await text_client.complete(
            system=OUTLINE_SYSTEM_PROMPT,
            user=user_text,
            response_format="json",
        )
    except VisionResponseParseError as exc:
        raise BrochureOutlineError(f"Outline JSON could not be parsed: {exc}") from exc

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise BrochureOutlineError(f"Outline JSON decode error: {exc}") from exc

    # Echo user-supplied overrides onto the outline so downstream stages see a
    # single source of truth.
    if prompt.style_preset:
        data["suggested_preset"] = prompt.style_preset
    if prompt.color_accent:
        data["suggested_accent"] = prompt.color_accent

    try:
        outline = BrochureOutline(**data)
    except Exception as exc:  # Pydantic ValidationError
        raise BrochureOutlineError(f"Outline failed validation: {exc}") from exc

    # Sanity: exactly one cover role, image_hint cap ≤ 3.
    cover_count = sum(1 for s in outline.sections if s.panel_role == "cover")
    if cover_count != 1:
        raise BrochureOutlineError(
            f"Outline must have exactly one section with panel_role='cover', got {cover_count}"
        )
    hinted = sum(1 for s in outline.sections if s.image_hint)
    if hinted > 3:
        raise BrochureOutlineError(
            f"Outline has {hinted} image_hints; max 3 allowed"
        )

    return outline
