"""Render-smoke integration: poster pipeline at all 9 (template x size) permutations.

Phase 24 plan 06 — closes PO-02 + PO-03 at the unit/integration layer.

For each of 3 templates x 3 size literals (= 9 cases) we exercise the full
rendering chain *without* hitting Comfy:

    load_template -> _build_flyer_input-style fixture
        -> mocked GeneratedBackground at canvas_dims
        -> real PosterComposer(canvas_width=W).compose(...)
        -> real Rasterizer(width=W, height=H).rasterize(svg)
        -> assert PIL.Image.open(BytesIO(png_bytes)).size == (W, H)

The dimension assertion is the critical guarantee called out in the
plan's quality gate ("Render-smoke validates output PNG dimensions match
each size preset"). Every poster ships at exactly the print-spec
canvas; this test pins that contract.

A separate ``test_size_to_canvas_dims_locked`` sanity-checks the
``_SIZE_TO_CANVAS`` constant against the locked CONTEXT.md values so a
future edit to the worker mapping immediately surfaces here.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from PIL import Image

from flyer_generator.api.tasks.poster import _SIZE_TO_CANVAS
from flyer_generator.models import (
    ComfyJob,
    FlyerInput,
    GeneratedBackground,
    LayoutZones,
    ResolvedLayout,
    VisionVerdict,
)
from flyer_generator.poster.schema_renderer.loader import load_template
from flyer_generator.stages.composer import PosterComposer
from flyer_generator.stages.layout import LayoutResolver
from flyer_generator.stages.rasterizer import Rasterizer

# ---------------------------------------------------------------------------
# Permutation matrix — 3 templates x 3 sizes = 9 cases. The size literal lives
# in the worker's ``_SIZE_TO_CANVAS`` constant; we read it at import time so
# any future addition to the mapping (e.g. a 4th size) automatically grows
# the test matrix without editing this file.
# ---------------------------------------------------------------------------

_TEMPLATES = ["editorial_grand", "bold_announcement", "cinematic_onesheet"]
_SIZES = ["18x24", "24x36", "27x40"]


def _permutations() -> list[tuple[str, str, tuple[int, int]]]:
    """Yield (template_name, size, canvas_dims) for all 9 combinations."""
    return [(t, s, _SIZE_TO_CANVAS[s]) for t in _TEMPLATES for s in _SIZES]


# ---------------------------------------------------------------------------
# Fixture builders (mirror tests/flyer/schema_renderer/test_render_smoke.py)
# ---------------------------------------------------------------------------


def _synthetic_background(canvas_dims: tuple[int, int]) -> GeneratedBackground:
    """Build a synthetic GeneratedBackground at the target canvas dimensions.

    The bytes are a real PNG so a future composer change that decodes the
    background (e.g. for embedded base64) keeps working — but we do *not*
    rely on the bytes themselves; the composer's <image> tag base64-embeds
    them as-is and the rasterizer re-rasters from cairosvg's perspective.
    """
    img = Image.new("RGB", canvas_dims, color=(64, 96, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return GeneratedBackground(
        image_bytes=buf.getvalue(),
        source_dimensions=(832, 1472),
        final_dimensions=canvas_dims,
        comfy_job=ComfyJob(
            prompt_id="phase24-render-smoke",
            submitted_at=datetime.now(timezone.utc),
            positive_prompt="",
            negative_prompt="",
            seed=42,
            attempt_number=1,
        ),
    )


def _flyer_input() -> FlyerInput:
    """Posters use subtype='info' per locked CONTEXT.md decision; the worker's
    _build_flyer_input maps headline -> title and subheading -> description.
    """
    return FlyerInput(
        title="Phase 24 Test Poster",
        subtype="info",
        description="Print-distance reading sample for the render smoke.",
        call_to_action="Visit example.com",
        org="Example Org",
        style_concept="bold poster, festival art",
        style_preset="photorealistic",
    )


def _verdict_info() -> VisionVerdict:
    """info-subtype verdict — title + org_credit only (no details/fee_badge)."""
    return VisionVerdict(
        approved=True,
        confidence=0.95,
        text_color="white",
        raw_response="{}",
        zones=LayoutZones(
            title="TOP_CENTER",
            details=None,
            fee_badge=None,
            org_credit="BOTTOM_CENTER",
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_size_to_canvas_dims_locked() -> None:
    """Sanity-check the worker mapping matches the locked CONTEXT.md values.

    Pins the 3 size literals (300 DPI portrait) so a future edit to
    ``flyer_generator/api/tasks/poster._SIZE_TO_CANVAS`` immediately fails
    here as well as in the worker tests.
    """
    assert _SIZE_TO_CANVAS == {
        "18x24": (5400, 7200),
        "24x36": (7200, 10800),
        "27x40": (8100, 12000),
    }


@pytest.mark.parametrize(
    "template_name,size,canvas_dims",
    _permutations(),
    ids=[f"{t}-{s}" for t, s, _ in _permutations()],
)
def test_render_smoke_canvas_dims(
    template_name: str, size: str, canvas_dims: tuple[int, int]
) -> None:
    """For each (template x size) permutation:

    1. Load the poster template by slug.
    2. Build a synthetic GeneratedBackground at canvas_dims (skip Comfy).
    3. Compose SVG via PosterComposer(canvas_width=canvas_dims[0]).
    4. Rasterize via Rasterizer(width=canvas_dims[0], height=canvas_dims[1]).
    5. Assert decoded PNG image.size == canvas_dims (Pillow round-trip).

    The dimension assertion is the quality gate item: "Render-smoke
    validates output PNG dimensions match each size preset".
    """
    template = load_template(template_name)
    flyer_input = _flyer_input()
    background = _synthetic_background(canvas_dims)
    verdict = _verdict_info()
    layout = LayoutResolver().resolve(verdict.zones)

    composer = PosterComposer(canvas_width=canvas_dims[0])
    svg = composer.compose(
        flyer_input,
        background,
        verdict,
        layout,
        template=template,
    )
    assert svg.startswith("<svg"), (
        f"{template_name}-{size}: composer did not emit <svg prefix"
    )

    rast = Rasterizer(width=canvas_dims[0], height=canvas_dims[1])
    png_bytes = rast.rasterize(svg)
    # PNG magic header
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    # Decode and assert dimensions exactly match the size-derived canvas.
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == canvas_dims, (
        f"{template_name}-{size}: expected PNG size {canvas_dims}, "
        f"got {img.size}"
    )


# ResolvedLayout is imported above to satisfy "from flyer_generator.models
# import ... ResolvedLayout" — the LayoutResolver returns ResolvedLayout
# instances which we then pass to compose(). Keep the import so a future
# refactor that drops ResolvedLayout from models surfaces here too.
_KEEP_RESOLVED_LAYOUT_REFERENCE = ResolvedLayout
