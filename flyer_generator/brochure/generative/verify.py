"""Stage 7: Verification.

Scores the composed brochure on a 5-dimension rubric using a vision LLM. Returns a VerificationVerdict naming the weakest stage for regen loop.
"""

from __future__ import annotations

import json
from typing import Literal

from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    VerificationVerdict,
)
from flyer_generator.brochure.llm_client import TextClient
from flyer_generator.config import Settings
from flyer_generator.errors import VisionAPIError, VisionResponseParseError
from flyer_generator.stages.vision import VisionEvaluator

VERIFY_SYSTEM_PROMPT = """You are a senior brand designer reviewing a tri-fold \
brochure. Score it on a 5-dimension rubric. Output JSON only — no prose, no markdown fences."""


_DIMENSIONS = ("content_fit", "visual_balance", "text_legibility", "layout_coherence", "print_readiness")


class BrochureVerificationError(Exception):
    """Raised when verification fails to produce a valid verdict."""


def _extract_rubric_json(raw: str) -> dict | None:
    """Pull the first JSON object out of a raw LLM response and return it if it has rubric shape.

    Returns None if parse fails, no object found, or object lacks `dimension_scores`.
    """
    if not raw:
        return None
    first = raw.find("{")
    last = raw.rfind("}")
    if first < 0 or last <= first:
        return None
    try:
        data = json.loads(raw[first : last + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "dimension_scores" not in data:
        return None
    dims = data.get("dimension_scores")
    if not isinstance(dims, dict) or not dims:
        return None
    return data


def _verdict_from_rubric(data: dict, *, iteration: int, critique_prefix: str = "") -> VerificationVerdict:
    """Build a VerificationVerdict from a parsed rubric dict."""
    dims_raw = data["dimension_scores"]
    dims: dict[str, int] = {}
    for key, value in dims_raw.items():
        try:
            dims[key] = int(value)
        except (TypeError, ValueError):
            continue
    if not dims:
        raise BrochureVerificationError("Rubric dimension_scores contained no numeric values")
    score = int(sum(dims.values()) / len(dims))
    critique = str(data.get("critique", ""))
    if critique_prefix:
        critique = f"{critique_prefix}{critique}" if critique else critique_prefix
    weakest_raw = data.get("weakest_stage")
    weakest: Literal["outline", "text", "layout", "imagery", "compose"] | None = None
    if weakest_raw in ("outline", "text", "layout", "imagery", "compose"):
        weakest = weakest_raw  # type: ignore[assignment]
    return VerificationVerdict(
        score=score,
        dimension_scores=dims,
        critique=critique,
        weakest_stage=weakest,
        iteration=iteration,
    )


def _outline_summary(outline: BrochureOutline) -> str:
    bullets = "\n".join(
        f"- {s.heading} ({s.panel_role}): {s.body_brief}"
        for s in outline.sections
    )
    return f"Tone: {outline.tone}\nCTA intent: {outline.cta_intent}\nSections:\n{bullets}"


def _build_user_prompt(original_prompt: str, outline: BrochureOutline) -> str:
    return f"""Original user prompt: {original_prompt}

Outline summary:
{_outline_summary(outline)}

Score each dimension 0-100:
1. content_fit — does the copy match the prompt's intent and tone?
2. visual_balance — are panel weights visually even? Any panel cramped or empty?
3. text_legibility — does text fit safely? Any overflow/clipping? Adequate contrast?
4. layout_coherence — does the template suit the content tone?
5. print_readiness — crop marks present? No fold-line bleed? Bleed coverage OK?

Return JSON with this exact shape (all keys required):
{{
  "approved": true|false,
  "confidence": 0.0-1.0,
  "dimension_scores": {{
    "content_fit": 0-100, "visual_balance": 0-100,
    "text_legibility": 0-100, "layout_coherence": 0-100,
    "print_readiness": 0-100
  }},
  "critique": "2-3 sentences explaining the lowest-scoring dimension",
  "weakest_stage": "outline" | "text" | "layout" | "imagery" | "compose" | null
}}

Derive approved + confidence from the dimension scores:
- approved = (all dimensions >= 70)
- confidence = (mean of dimension_scores) / 100  (0.0-1.0)

Map the weakest dimension to a stage:
- content_fit low → "text" or "outline"
- visual_balance low → "layout" or "compose"
- text_legibility low → "text" (too long) or "compose" (rendering)
- layout_coherence low → "layout"
- print_readiness low → "compose"
- If all dimensions >= 70: set weakest_stage to null."""


def _fallback_verdict_from_vision(
    verdict,  # VisionVerdict
    *,
    iteration: int,
) -> VerificationVerdict:
    """Build a rubric-shaped verdict from a VisionVerdict when rubric JSON is absent."""
    score = int(verdict.confidence * 100)
    dimension_scores = {dim: score for dim in _DIMENSIONS}
    weakest: Literal["outline", "text", "layout", "imagery", "compose"] | None = None
    if score < 70:
        weakest = "compose" if verdict.approved else "text"
    critique = verdict.refinement_hint or (", ".join(verdict.rejection_reasons) or "No critique")
    return VerificationVerdict(
        score=score,
        dimension_scores=dimension_scores,
        critique=critique,
        weakest_stage=weakest,
        iteration=iteration,
    )


def _merge_sheet_verdicts(
    outside: VerificationVerdict,
    inside: VerificationVerdict,
    *,
    iteration: int,
) -> VerificationVerdict:
    """Average two per-sheet verdicts into one combined verdict.

    - dimension_scores averaged per key (shared keys only; unique keys carried over at half weight).
    - score = mean of averaged dimensions.
    - critique concatenates both with sheet labels (drops empty critiques).
    - weakest_stage picked from the lower-scoring sheet; null only if both agree on null.
    """
    keys = set(outside.dimension_scores) | set(inside.dimension_scores)
    merged: dict[str, int] = {}
    for k in keys:
        o = outside.dimension_scores.get(k)
        i = inside.dimension_scores.get(k)
        if o is not None and i is not None:
            merged[k] = (o + i) // 2
        else:
            merged[k] = o if o is not None else i  # type: ignore[assignment]
    score = int(sum(merged.values()) / len(merged)) if merged else 0

    parts = []
    if outside.critique:
        parts.append(f"[outside] {outside.critique}")
    if inside.critique:
        parts.append(f"[inside] {inside.critique}")
    critique = " ".join(parts) or "No critique"

    if outside.score <= inside.score:
        worse_weakest = outside.weakest_stage
    else:
        worse_weakest = inside.weakest_stage

    return VerificationVerdict(
        score=score,
        dimension_scores=merged,
        critique=critique,
        weakest_stage=worse_weakest,
        iteration=iteration,
    )


async def _score_one_sheet(
    vision_evaluator: VisionEvaluator,
    png_bytes: bytes,
    user_text: str,
    sheet_label: str,
    iteration: int,
) -> VerificationVerdict:
    """Score a single sheet and return a VerificationVerdict (rubric or fallback).

    Critiques are NOT sheet-labeled here; _merge_sheet_verdicts adds labels only
    when merging two sheets. Single-sheet calls keep the legacy critique format.
    """
    try:
        verdict = await vision_evaluator.evaluate_cover(
            image_bytes=png_bytes,
            concept=user_text,
        )
    except (VisionAPIError, VisionResponseParseError) as exc:
        raise BrochureVerificationError(
            f"Verification vision call failed on {sheet_label} sheet: {exc}"
        ) from exc

    rubric = _extract_rubric_json(verdict.raw_response)
    if rubric is not None:
        return _verdict_from_rubric(rubric, iteration=iteration)
    return _fallback_verdict_from_vision(verdict, iteration=iteration)


async def verify_brochure(
    outside_png_bytes: bytes,
    inside_png_bytes: bytes,
    original_prompt: str,
    outline: BrochureOutline,
    settings: Settings,
    *,
    vision_evaluator: VisionEvaluator | None = None,
    iteration: int = 1,
    verify_inside_sheet: bool = True,
) -> VerificationVerdict:
    """Score the composed brochure and return a VerificationVerdict.

    When `verify_inside_sheet` is True (default) and inside PNG bytes are
    non-empty, both sheets are scored independently and averaged — the worse-
    scoring sheet drives `weakest_stage`. Set False or pass empty inside bytes
    to score outside only (halves the vision API cost).

    Vision backend comes from settings.vision_provider.
    """
    if vision_evaluator is None:
        vision_evaluator = VisionEvaluator(
            settings,
            system_prompt=VERIFY_SYSTEM_PROMPT,
            require_zones=False,
        )

    user_text = _build_user_prompt(original_prompt, outline)

    outside_verdict = await _score_one_sheet(
        vision_evaluator, outside_png_bytes, user_text, "outside", iteration
    )

    if not verify_inside_sheet or not inside_png_bytes:
        return outside_verdict

    inside_verdict = await _score_one_sheet(
        vision_evaluator, inside_png_bytes, user_text, "inside", iteration
    )
    return _merge_sheet_verdicts(outside_verdict, inside_verdict, iteration=iteration)


async def verify_with_text_critique(
    outside_png_bytes: bytes,
    inside_png_bytes: bytes,
    original_prompt: str,
    outline: BrochureOutline,
    text_client: TextClient,
) -> VerificationVerdict:
    """Alternative verification: pure text LLM rubric (no vision).

    Used when vision is unavailable or too expensive. Relies on prompt + outline summary only — less accurate but deterministic.
    """
    user_text = _build_user_prompt(original_prompt, outline) + (
        "\n\nNote: you cannot see the rendered brochure. Score based on content quality + layout coherence only. "
        "Assume print_readiness and visual_balance are both 70 unless outline indicates issues."
    )
    raw = await text_client.complete(
        system=VERIFY_SYSTEM_PROMPT,
        user=user_text,
        response_format="json",
    )
    try:
        data = json.loads(raw)
        dims = data["dimension_scores"]
        score = int(sum(dims.values()) / len(dims))
        return VerificationVerdict(
            score=score,
            dimension_scores=dims,
            critique=data.get("critique", ""),
            weakest_stage=data.get("weakest_stage"),
            iteration=1,
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise BrochureVerificationError(f"Text verification JSON malformed: {exc}") from exc
