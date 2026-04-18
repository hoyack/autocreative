"""Stage 5: Fit optimization.

Per section: estimate rendered text capacity vs the panel's safe zone. If the section body overflows by >15% or underflows by >40%, ask the LLM to rewrite it to hit target.
"""

from __future__ import annotations

import asyncio

from flyer_generator.brochure.generative.models import SectionText, TargetLength
from flyer_generator.brochure.llm_client import TextClient
from flyer_generator.brochure.templates import LayoutTemplate

FIT_SYSTEM_PROMPT = """You are rewriting one section of a tri-fold brochure body so it fits a specific layout. Preserve the key facts, tone, and voice. Output the revised body ONLY — no heading, no commentary, no markdown fences."""

_LENGTH_TARGETS = {
    "short": 25,
    "medium": 50,
    "long": 80,
}


def estimate_body_capacity(template: LayoutTemplate, *, panel_safe_height_px: int = 2400) -> int:
    """Approximate how many characters the body prose can use on an inner panel.

    Heuristic: subtract heading height + gap from the panel, divide remaining height by line height, multiply by chars-per-line.
    """
    heading_block = template.heading_font_size + 24  # heading + gap after
    available_px = max(0, panel_safe_height_px - heading_block)
    available_lines = max(1, available_px // template.body_line_height)
    return available_lines * template.body_max_chars_per_line


def _target_words_for(length: TargetLength) -> int:
    return _LENGTH_TARGETS[length]


def _char_target(template: LayoutTemplate, length: TargetLength) -> int:
    """Intended body character count.

    'short' target is word-count-driven (a short blurb should be a blurb regardless of panel size).
    'medium' and 'long' are capacity-driven (fill the template's intended share of the panel)
    so we don't ship v1's sparse-panel look on templates with generous capacity.
    """
    capacity = estimate_body_capacity(template)
    if length == "short":
        return _target_words_for("short") * 5  # ~125 chars
    capacity_fraction = {"medium": 0.5, "long": 0.85}[length]
    return int(capacity * capacity_fraction)


def needs_rewrite(body: str, template: LayoutTemplate, length: TargetLength) -> tuple[bool, int]:
    """Return (needs_rewrite, target_chars).

    Rewrite triggers:
    - body longer than target by >15%
    - body shorter than target by >40% AND target_length != 'short'
    """
    target = _char_target(template, length)
    current = len(body)
    if current > target * 1.15:
        return True, target
    if length != "short" and current < target * 0.6:
        return True, target
    return False, target


async def _rewrite(
    body: str,
    target_chars: int,
    heading: str,
    text_client: TextClient,
) -> str:
    """One LLM call: rewrite `body` to hit `target_chars` (±15%). Returns stripped text."""
    target_words = max(10, target_chars // 5)
    user = (
        f"Section heading (for context only, do not output): {heading}\n\n"
        f"Current body:\n{body}\n\n"
        f"Rewrite to about {target_words} words (roughly {target_chars} characters). "
        "Preserve key facts and tone. Output the revised body only — no heading, no commentary."
    )
    revised = await text_client.complete(
        system=FIT_SYSTEM_PROMPT,
        user=user,
        response_format="text",
    )
    return revised.strip()


async def optimize_fit(
    texts: list[SectionText],
    template: LayoutTemplate,
    text_client: TextClient,
    target_length: TargetLength = "medium",
    *,
    max_rewrites: int = 2,
) -> list[SectionText]:
    """Rewrite sections whose bodies overflow/underflow the template's capacity.

    Runs up to `max_rewrites` rewrites per section. Each rewrite tightens the
    target by 10% so the LLM converges when its first pass was too timid.
    Sections already in range pass through unchanged. Rewrites run in parallel
    across sections via asyncio.gather.
    """

    async def _maybe_rewrite(t: SectionText) -> SectionText:
        body = t.body
        for attempt in range(max_rewrites):
            needs, target = needs_rewrite(body, template, target_length)
            if not needs:
                break
            # Tighten 10% per retry — subsequent passes squeeze the target.
            tightened = int(target * (0.9 ** attempt))
            tightened = max(1, tightened)
            body = await _rewrite(body, tightened, t.heading, text_client)
        if body is t.body:
            return t
        return SectionText(heading=t.heading, body=body, image_hint=t.image_hint)

    return list(await asyncio.gather(*(_maybe_rewrite(t) for t in texts)))
