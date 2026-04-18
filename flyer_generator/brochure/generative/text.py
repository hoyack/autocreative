"""Stage 2: Per-section text generation.

Given a BrochureOutline, ask the LLM to write the final body for each section.
Runs N calls in parallel (one per section).
"""

from __future__ import annotations

import asyncio

from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    SectionSpec,
    SectionText,
    TargetLength,
)
from flyer_generator.brochure.llm_client import TextClient

TEXT_SYSTEM_PROMPT = """You are writing one section of a tri-fold brochure. \
Output the body prose ONLY — no heading, no markdown fences, no extra commentary. \
Follow the target length. Use short paragraphs or bullet lines starting with "- " \
for lists."""

_LENGTH_TARGETS = {
    "short": 25,
    "medium": 50,
    "long": 80,
}


def _target_words(length: TargetLength) -> int:
    return _LENGTH_TARGETS[length]


def _build_section_prompt(
    outline: BrochureOutline,
    spec: SectionSpec,
    target_length: TargetLength,
) -> str:
    target = _target_words(target_length)
    return f"""Brochure tone: {outline.tone}
Section heading: {spec.heading}
Section direction: {spec.body_brief}
Panel role: {spec.panel_role}
Target: about {target} words.

Write only the body prose for this section. No heading, no markdown fences. \
Keep to one short paragraph, or 2-4 bullet lines starting with "- "."""


async def _generate_one(
    outline: BrochureOutline,
    spec: SectionSpec,
    text_client: TextClient,
    target_length: TargetLength,
) -> SectionText:
    body = await text_client.complete(
        system=TEXT_SYSTEM_PROMPT,
        user=_build_section_prompt(outline, spec, target_length),
        response_format="text",
    )
    return SectionText(
        heading=spec.heading,
        body=body.strip(),
        image_hint=spec.image_hint,
    )


async def generate_section_texts(
    outline: BrochureOutline,
    text_client: TextClient,
    target_length: TargetLength = "medium",
) -> list[SectionText]:
    """Generate final body prose for each section in the outline, in parallel.

    Preserves outline order in the returned list.
    """
    tasks = [
        _generate_one(outline, spec, text_client, target_length)
        for spec in outline.sections
    ]
    return list(await asyncio.gather(*tasks))
