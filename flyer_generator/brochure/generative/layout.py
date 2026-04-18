"""Stage 3: Layout selection.

Asks the LLM to pick one of the six named layout templates based on the outline's tone + content, plus shape density, accent placement, and cover treatment.
"""

from __future__ import annotations

import json

from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    LayoutChoice,
)
from flyer_generator.brochure.llm_client import TextClient
from flyer_generator.brochure.templates import all_templates
from flyer_generator.errors import VisionResponseParseError

LAYOUT_SYSTEM_PROMPT = """You are a senior brand designer picking a layout template for a tri-fold brochure. Output JSON only — no prose, no markdown fences."""


def _build_layout_prompt(outline: BrochureOutline) -> str:
    templates_desc = "\n".join(
        f"- {t.name}: {t.description} (tone hints: {', '.join(t.tone_keywords)})"
        for t in all_templates()
    )
    sections_desc = "\n".join(
        f"  - {s.heading} (role={s.panel_role}): {s.body_brief}"
        for s in outline.sections
    )
    return f"""Brochure outline:
- Tone: {outline.tone}
- CTA intent: {outline.cta_intent}
- Sections:
{sections_desc}

Available templates:
{templates_desc}

Return JSON with this exact shape:
{{
  "template": "<one of: editorial | minimalist | playful | gallery_strip | quote_driven | spotlight>",
  "shape_density": "sparse" | "medium" | "dense",
  "accent_placement": "top_rule" | "side_band" | "corner_block",
  "cover_treatment": "image_full" | "image_half_shapes" | "shapes_only"
}}

Rules:
- Match template to the outline's tone. B2B/professional → editorial; fun/casual/events → playful; minimal-tech → minimalist; image-heavy → gallery_strip; cause-driven → quote_driven; single-product focus → spotlight.
- shape_density: conservative tone → sparse; casual/playful → dense; otherwise medium.
- cover_treatment: use image_full for most real-world subjects; shapes_only for abstract/conceptual prompts."""


_FALLBACK = LayoutChoice(
    template="editorial",
    shape_density="medium",
    accent_placement="top_rule",
    cover_treatment="image_full",
)


async def choose_layout(outline: BrochureOutline, text_client: TextClient) -> LayoutChoice:
    """Ask the LLM for a LayoutChoice.

    Falls back to a safe default ('editorial' + medium + top_rule + image_full) if the LLM output is invalid after one retry.
    """
    try:
        raw_json = await text_client.complete(
            system=LAYOUT_SYSTEM_PROMPT,
            user=_build_layout_prompt(outline),
            response_format="json",
        )
    except VisionResponseParseError:
        return _FALLBACK

    try:
        data = json.loads(raw_json)
        return LayoutChoice(**data)
    except Exception:  # ValidationError or KeyError
        return _FALLBACK
