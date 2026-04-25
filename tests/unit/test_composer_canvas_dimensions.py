"""Tests for PosterComposer's parameterized canvas_width kwarg.

Phase 24-02: PosterComposer must accept an optional `canvas_width`
constructor kwarg so the poster pipeline can render at larger canvas
sizes. The default (1080) preserves Phase 21–23 byte-identical flyer
output. Margin scales proportionally (60/1080 of canvas_width) so the
visual relationship between margin and canvas stays constant across
sizes.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

from flyer_generator.models import (
    ComfyJob,
    EventInput,
    GeneratedBackground,
    LayoutZones,
    ResolvedLayout,
    VisionVerdict,
)
from flyer_generator.stages import composer as composer_module
from flyer_generator.stages.composer import PosterComposer
from flyer_generator.zones import ZONE_COORDS


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/test_composer.py shapes)
# ---------------------------------------------------------------------------


def _make_event(**overrides: object) -> EventInput:
    defaults = dict(
        title="Summer Fest",
        date="June 15, 2026",
        time="8:00 PM",
        location_name="Central Park",
        location_address="123 Main St",
        fees="$25",
        org="Events Co",
        style_concept="summer",
        style_preset="photorealistic",
        color_accent="#F59E0B",
    )
    defaults.update(overrides)
    return EventInput(**defaults)  # type: ignore[arg-type]


def _make_background() -> GeneratedBackground:
    job = ComfyJob(
        prompt_id="test-canvas",
        submitted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        positive_prompt="test",
        negative_prompt="test",
        seed=42,
        attempt_number=1,
    )
    return GeneratedBackground(
        image_bytes=b"PNG_FAKE",
        source_dimensions=(832, 1472),
        final_dimensions=(1080, 1920),
        comfy_job=job,
    )


def _make_verdict() -> VisionVerdict:
    return VisionVerdict(
        approved=True,
        confidence=0.9,
        zones=LayoutZones(
            title="TOP_CENTER",
            details="BOTTOM_LEFT",
            fee_badge="BOTTOM_RIGHT",
        ),
        text_color="white",
        raw_response="test",
    )


def _make_layout() -> ResolvedLayout:
    return ResolvedLayout(
        title=ZONE_COORDS["TOP_CENTER"],
        details=ZONE_COORDS["BOTTOM_LEFT"],
        fee_badge=ZONE_COORDS["BOTTOM_RIGHT"],
        org_credit=ZONE_COORDS["BOTTOM_CENTER"],
    )


# ---------------------------------------------------------------------------
# Tests — instance-level canvas_width / margin_px
# ---------------------------------------------------------------------------


class TestDefaultConstructor:
    def test_default_constructor_canvas_width_1080(self) -> None:
        composer = PosterComposer()
        assert composer._canvas_width == 1080
        assert composer._margin_px == 60

    def test_default_constructor_emits_1080_svg(self) -> None:
        """Back-compat: PosterComposer() emits the legacy 1080-wide SVG."""
        composer = PosterComposer()
        svg = composer.compose(
            event=_make_event(),
            background=_make_background(),
            verdict=_make_verdict(),
            layout=_make_layout(),
        )
        # Existing assertions from tests/test_composer.py must still hold.
        assert 'width="1080"' in svg
        assert 'viewBox="0 0 1080 1920"' in svg
        # Accent stripe at design y=1908 (back-compat)
        assert 'y="1908"' in svg
        # Org credit at design y=1840
        assert 'y="1840"' in svg


class TestProportionalMarginScaling:
    """Margin scales as 60/1080 of canvas_width — keeps visual ratio constant."""

    def test_canvas_width_5400_margin_300(self) -> None:
        composer = PosterComposer(canvas_width=5400)
        assert composer._canvas_width == 5400
        assert composer._margin_px == 300

    def test_canvas_width_7200_margin_400(self) -> None:
        composer = PosterComposer(canvas_width=7200)
        assert composer._canvas_width == 7200
        assert composer._margin_px == 400

    def test_canvas_width_8100_margin_450(self) -> None:
        composer = PosterComposer(canvas_width=8100)
        assert composer._canvas_width == 8100
        assert composer._margin_px == 450


class TestSvgWidthAttribute:
    """`<svg width="...">` reflects the constructor's canvas_width."""

    def test_compose_emits_svg_with_canvas_width_5400(self) -> None:
        composer = PosterComposer(canvas_width=5400)
        svg = composer.compose(
            event=_make_event(),
            background=_make_background(),
            verdict=_make_verdict(),
            layout=_make_layout(),
        )
        # The outer <svg> must declare width="5400"
        assert 'width="5400"' in svg

    def test_compose_emits_svg_with_canvas_width_7200(self) -> None:
        composer = PosterComposer(canvas_width=7200)
        svg = composer.compose(
            event=_make_event(),
            background=_make_background(),
            verdict=_make_verdict(),
            layout=_make_layout(),
        )
        assert 'width="7200"' in svg


class TestModuleConstantsRemoved:
    """Module-level _CANVAS_WIDTH / _MARGIN_PX moved to instance attributes."""

    def test_module_level_canvas_width_constant_removed(self) -> None:
        # The module must no longer expose `_CANVAS_WIDTH` as a module attribute.
        assert not hasattr(composer_module, "_CANVAS_WIDTH"), (
            "_CANVAS_WIDTH should be moved from module-level to PosterComposer "
            "instance attribute (self._canvas_width)."
        )

    def test_module_level_margin_constant_removed(self) -> None:
        assert not hasattr(composer_module, "_MARGIN_PX"), (
            "_MARGIN_PX should be moved from module-level to PosterComposer "
            "instance attribute (self._margin_px)."
        )

    def test_composer_constructor_accepts_canvas_width_kwarg(self) -> None:
        sig = inspect.signature(PosterComposer.__init__)
        assert "canvas_width" in sig.parameters, (
            "PosterComposer.__init__ must accept canvas_width kwarg."
        )
        # Default must be 1080 for back-compat
        assert sig.parameters["canvas_width"].default == 1080
