"""Tests for the PLF-04 vision downsample helper + integration.

Phase 24.1 plan 03 — closes PLF-04 at the unit/integration layer.

Background: poster vision was timing out because the pipeline shipped the
full upscaled (5400×7200 / 7200×10800 / 8100×12000) PNG to the LLM —
encoding to ~25–50 MB of base64 in the request body. The fix introduces
a ``_downsample_for_vision`` helper that caps the long edge at 1920 px
before base64 encoding, while preserving the original ``image_bytes`` on
``GeneratedBackground`` for the rest of the pipeline (composer / rasterizer).

Six tests:

1. ``test_downsample_caps_long_edge_at_1920`` — synthesizes a 5400×7200
   PNG, decodes the helper output, asserts long edge ≤ 1920 and aspect
   ratio is preserved within ±1 px.

2. ``test_downsample_noop_when_under_threshold`` — synthesizes a
   1080×1920 PNG, asserts the returned bytes are identical (the no-op
   short-circuit, so flyer/brochure paths stay byte-identical).

3. ``test_downsample_re_encodes_as_png`` — synthesizes an 8000×6000
   PNG, asserts the output starts with the PNG magic header (so the
   ``media_type: "image/png"`` field on Anthropic / Ollama stays
   correct).

4. ``test_evaluate_passes_downsampled_bytes_to_anthropic`` — patches
   ``_call_anthropic`` with ``AsyncMock``, captures the ``img_b64``
   passed in, decodes it and asserts the long edge ≤ 1920 px when the
   input is a 5400×7200 background.

5. ``test_evaluate_passes_full_resolution_for_small_inputs`` — same
   shape with a 1080×1920 background; asserts the captured img_b64
   decodes back to long edge == 1920 (no-op path flows through).

6. ``test_evaluate_does_not_mutate_background_image_bytes`` — calls
   ``evaluate(background, event)`` with a 5400×7200 background and
   asserts ``background.image_bytes`` is byte-identical before and
   after. This is the locked CONTEXT.md contract: "preserve original
   image_bytes for the rest of the pipeline."
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from flyer_generator.config import Settings
from flyer_generator.models import (
    ComfyJob,
    FlyerInput,
    GeneratedBackground,
)
from flyer_generator.stages.vision import VisionEvaluator, _downsample_for_vision

# ---------------------------------------------------------------------------
# Synthetic input helpers
# ---------------------------------------------------------------------------


def _make_png(width: int, height: int, color: str = "red") -> bytes:
    """Build a real PNG of the given dimensions and return its bytes."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_background(width: int, height: int) -> GeneratedBackground:
    """Wrap a synthesized PNG in a ``GeneratedBackground`` model."""
    return GeneratedBackground(
        image_bytes=_make_png(width, height),
        source_dimensions=(832, 1472),
        final_dimensions=(width, height),
        comfy_job=ComfyJob(
            prompt_id="plf04-test",
            submitted_at=datetime.now(timezone.utc),
            positive_prompt="",
            negative_prompt="",
            seed=42,
            attempt_number=1,
        ),
    )


def _flyer_input() -> FlyerInput:
    """Minimal FlyerInput for evaluator tests."""
    return FlyerInput(
        title="Test",
        org="Test",
        style_concept="x",
        style_preset="photorealistic",
    )


_APPROVED_RAW = (
    '{"approved": true, "confidence": 0.9, '
    '"zones": {"title": "TOP_CENTER", "details": "MIDDLE_CENTER", '
    '"fee_badge": "BOTTOM_RIGHT", "org_credit": "BOTTOM_CENTER"}, '
    '"text_color": "white"}'
)


# ---------------------------------------------------------------------------
# 1. Helper unit tests
# ---------------------------------------------------------------------------


def test_downsample_caps_long_edge_at_1920() -> None:
    """A 5400×7200 PNG must be downsampled so long edge ≤ 1920 px."""
    src = _make_png(5400, 7200)
    out = _downsample_for_vision(src, max_long_edge=1920)

    img = Image.open(io.BytesIO(out))
    w, h = img.size
    assert max(w, h) <= 1920, f"long edge not capped: got {(w, h)}"

    # Aspect ratio preserved within ±1 px (rounding tolerance).
    src_ratio = 5400 / 7200
    out_ratio = w / h
    assert abs(src_ratio - out_ratio) < (1 / max(w, h)) + 1e-3, (
        f"aspect ratio drifted: src={src_ratio:.6f} out={out_ratio:.6f}"
    )


def test_downsample_noop_when_under_threshold() -> None:
    """A 1080×1920 PNG already fits — bytes must be returned unchanged.

    This preserves byte-identical behavior for flyer / brochure paths
    (1080×1920 backgrounds) and avoids a round-trip re-encode.
    """
    src = _make_png(1080, 1920, color="blue")
    out = _downsample_for_vision(src, max_long_edge=1920)
    assert out == src, "no-op short-circuit broken: bytes were re-encoded"


def test_downsample_re_encodes_as_png() -> None:
    """Output must always be PNG so ``media_type: image/png`` stays correct."""
    src = _make_png(8000, 6000)
    out = _downsample_for_vision(src, max_long_edge=1920)
    assert out.startswith(b"\x89PNG\r\n\x1a\n"), (
        f"output is not PNG: header={out[:8]!r}"
    )


# ---------------------------------------------------------------------------
# 2. Integration with VisionEvaluator
# ---------------------------------------------------------------------------


@pytest.fixture
def settings() -> Settings:
    return Settings(
        vision_provider="anthropic",
        anthropic_api_key="test-key",
        vision_model="claude-sonnet-4-5",
        vision_max_tokens=1024,
        vision_timeout_seconds=30,
        vision_confidence_threshold=0.6,
    )


async def test_evaluate_passes_downsampled_bytes_to_anthropic(
    settings: Settings,
) -> None:
    """``evaluate()`` must downsample large inputs before the Anthropic call."""
    evaluator = VisionEvaluator(settings)
    background = _make_background(5400, 7200)
    event = _flyer_input()

    captured: dict[str, str] = {}

    async def _capture(
        img_b64: str, user_text: str, *, system_prompt: str | None = None
    ) -> str:
        captured["img_b64"] = img_b64
        return _APPROVED_RAW

    with patch.object(
        evaluator,
        "_call_anthropic",
        new=AsyncMock(side_effect=_capture),
    ):
        verdict = await evaluator.evaluate(background, event)

    # Verdict shape parsed correctly through the existing pipeline.
    assert verdict.approved is True
    assert verdict.zones is not None
    assert verdict.zones.title == "TOP_CENTER"

    # Decode captured base64 — assert downsampled.
    assert "img_b64" in captured, "_call_anthropic was not invoked"
    decoded = base64.b64decode(captured["img_b64"])
    img = Image.open(io.BytesIO(decoded))
    w, h = img.size
    assert max(w, h) <= 1920, (
        f"vision call received non-downsampled image: {(w, h)}"
    )


async def test_evaluate_passes_full_resolution_for_small_inputs(
    settings: Settings,
) -> None:
    """1080×1920 backgrounds flow through the no-op path unchanged."""
    evaluator = VisionEvaluator(settings)
    background = _make_background(1080, 1920)
    event = _flyer_input()

    captured: dict[str, str] = {}

    async def _capture(
        img_b64: str, user_text: str, *, system_prompt: str | None = None
    ) -> str:
        captured["img_b64"] = img_b64
        return _APPROVED_RAW

    with patch.object(
        evaluator,
        "_call_anthropic",
        new=AsyncMock(side_effect=_capture),
    ):
        await evaluator.evaluate(background, event)

    decoded = base64.b64decode(captured["img_b64"])
    img = Image.open(io.BytesIO(decoded))
    w, h = img.size
    # No-op path: long edge stays at the original 1920.
    assert max(w, h) == 1920, f"unexpected resize on small input: {(w, h)}"
    assert (w, h) == (1080, 1920), (
        f"no-op path mutated dimensions: got {(w, h)} expected (1080, 1920)"
    )


async def test_evaluate_does_not_mutate_background_image_bytes(
    settings: Settings,
) -> None:
    """``background.image_bytes`` must be byte-identical before/after evaluate.

    Locked CONTEXT.md contract: downsampling is local to the vision call,
    NOT to ``GeneratedBackground``. The composer/rasterizer downstream
    still need the full canvas.
    """
    evaluator = VisionEvaluator(settings)
    background = _make_background(5400, 7200)
    event = _flyer_input()

    pre_bytes = background.image_bytes
    pre_id = id(pre_bytes)

    with patch.object(
        evaluator,
        "_call_anthropic",
        new=AsyncMock(return_value=_APPROVED_RAW),
    ):
        await evaluator.evaluate(background, event)

    post_bytes = background.image_bytes
    assert post_bytes == pre_bytes, "background.image_bytes was mutated"
    assert id(post_bytes) == pre_id, (
        "background.image_bytes was reassigned (identity changed)"
    )
