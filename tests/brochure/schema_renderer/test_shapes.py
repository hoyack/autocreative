"""Shape primitive rendering tests."""

from __future__ import annotations

import pytest

from flyer_generator.brochure.schema_renderer.schema_model import (
    GradientStop,
    LinearGradientFill,
    RadialGradientFill,
    ShapeElement,
    SolidFill,
    Stroke,
)
from flyer_generator.brochure.schema_renderer.shapes import (
    apply_bleed,
    render_fill,
    render_shape,
)

_CANVAS = (0, 0, 3300, 2550)


def test_solid_rect_contains_color():
    el = ShapeElement(kind="rect", rect=(0, 0, 100, 50), fill=SolidFill(color="#123456"))
    svg = render_shape(el, _CANVAS, "t")
    assert "<rect" in svg
    assert 'x="0' in svg  # 0 or 0.0
    assert 'width="100' in svg
    assert 'fill="#123456"' in svg


def test_rounded_rect_emits_rx_ry():
    el = ShapeElement(
        kind="rounded_rect",
        rect=(0, 0, 100, 50),
        fill=SolidFill(color="#123456"),
        path_params={"corner_radius": 16},
    )
    svg = render_shape(el, _CANVAS, "t")
    assert 'rx="16' in svg
    assert 'ry="16' in svg


def test_circle_uses_min_dimension():
    el = ShapeElement(
        kind="circle",
        rect=(10, 10, 80, 200),  # width 80 < height 200
        fill=SolidFill(color="#000000"),
    )
    svg = render_shape(el, _CANVAS, "t")
    assert 'r="40.0"' in svg  # min(80, 200)/2 = 40


def test_ellipse_uses_both_radii():
    el = ShapeElement(
        kind="ellipse",
        rect=(0, 0, 200, 100),
        fill=SolidFill(color="#000000"),
    )
    svg = render_shape(el, _CANVAS, "t")
    assert 'rx="100.0"' in svg
    assert 'ry="50.0"' in svg


def test_polygon_emits_points():
    el = ShapeElement(
        kind="polygon",
        points=[(0, 0), (100, 0), (50, 100)],
        fill=SolidFill(color="#FFFFFF"),
    )
    svg = render_shape(el, _CANVAS, "t")
    assert "<polygon" in svg
    # Points list should contain all three
    assert 'points="0' in svg
    assert ",100" in svg


def test_triangle_with_orient_down():
    el = ShapeElement(
        kind="triangle",
        rect=(0, 0, 100, 100),
        path_params={"orient": "down"},
        fill=SolidFill(color="#FFFFFF"),
    )
    svg = render_shape(el, _CANVAS, "t")
    assert "<polygon" in svg
    # Down-oriented triangle: apex at (50, 100)
    assert "50" in svg and "100" in svg


def test_ribbon_produces_four_points():
    el = ShapeElement(
        kind="ribbon",
        rect=(0, 0, 200, 100),
        path_params={"skew": 40},
        fill=SolidFill(color="#000000"),
    )
    svg = render_shape(el, _CANVAS, "t")
    assert "<polygon" in svg
    # Ribbon emits 4 point pairs; polygon points= should have 4 comma-separated
    # pairs (3 spaces between).
    import re
    m = re.search(r'points="([^"]+)"', svg)
    assert m is not None
    assert m.group(1).count(" ") >= 3


def test_wave_emits_path_with_sine_samples():
    el = ShapeElement(
        kind="wave",
        rect=(0, 0, 3000, 200),
        fill=SolidFill(color="#000000"),
    )
    svg = render_shape(el, _CANVAS, "t")
    assert "<path" in svg
    assert svg.count(" L ") > 20  # lots of sine samples


def test_line_uses_stroke_not_fill():
    el = ShapeElement(
        kind="line",
        points=[(0, 0), (100, 100)],
        stroke=Stroke(color="#FF0000", width=3),
    )
    svg = render_shape(el, _CANVAS, "t")
    assert "<line" in svg
    assert 'stroke="#FF0000"' in svg
    assert 'x2="100' in svg
    assert 'y2="100' in svg


def test_linear_gradient_emits_defs_and_url():
    fill = LinearGradientFill(
        stops=[
            GradientStop(offset=0, color="#FF0000", opacity=1.0),
            GradientStop(offset=1, color="#00FF00", opacity=0.5),
        ],
        angle=90,
    )
    defs, fill_val = render_fill(fill, "salt1")
    assert "<linearGradient" in defs
    assert 'id="grad-lin-salt1"' in defs
    assert fill_val == "url(#grad-lin-salt1)"
    assert "#FF0000" in defs
    assert "#00FF00" in defs


def test_radial_gradient_emits_defs_and_url():
    fill = RadialGradientFill(
        stops=[
            GradientStop(offset=0, color="#FFFFFF"),
            GradientStop(offset=1, color="#000000"),
        ],
        center=(0.5, 0.5),
        radius=0.8,
    )
    defs, fill_val = render_fill(fill, "s")
    assert "<radialGradient" in defs
    assert fill_val.startswith("url(#")


def test_solid_fill_returns_color_directly():
    fill = SolidFill(color="#ABCDEF", opacity=0.5)
    defs, fill_val = render_fill(fill, "s")
    assert defs == ""
    assert fill_val == "#ABCDEF"


def test_stroke_dash_rendering():
    el = ShapeElement(
        kind="rect",
        rect=(0, 0, 100, 50),
        fill=SolidFill(color="#000000"),
        stroke=Stroke(color="#FF0000", width=2, dash=[4, 2]),
    )
    svg = render_shape(el, _CANVAS, "t")
    assert "stroke-dasharray" in svg
    assert "4" in svg
    assert "2" in svg


class TestBleed:
    def test_bleed_top(self):
        out = apply_bleed((100, 200, 400, 300), "top", (0, 0, 3300, 2550))
        assert out == (100, 0, 400, 500)  # height grows by 200

    def test_bleed_bottom(self):
        out = apply_bleed((100, 100, 400, 300), "bottom", (0, 0, 3300, 2550))
        # y=100, h grows to reach 2550 → h=2450
        assert out == (100, 100, 400, 2450)

    def test_bleed_right(self):
        out = apply_bleed((1000, 500, 400, 200), "right", (0, 0, 3300, 2550))
        assert out == (1000, 500, 2300, 200)

    def test_bleed_all(self):
        out = apply_bleed((100, 100, 400, 300), "all", (0, 0, 3300, 2550))
        assert out == (0, 0, 3300, 2550)

    def test_no_bleed_unchanged(self):
        rect = (100, 100, 400, 300)
        assert apply_bleed(rect, False, (0, 0, 3300, 2550)) == rect


class TestTextureSlot:
    """Phase 4 stretch — texture_slot fill resolves to a tiled <pattern>."""

    def _png(self, rgb=(200, 150, 80)) -> bytes:
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (64, 64), color=rgb).save(buf, format="PNG")
        return buf.getvalue()

    def test_texture_slot_without_textures_falls_back_to_solid(self):
        from flyer_generator.brochure.schema_renderer.schema_model import (
            TextureSlotFill,
        )

        fill = TextureSlotFill(slot="grain", fallback=SolidFill(color="#BADA55"))
        defs, val = render_fill(fill, "t")
        assert defs == ""
        assert val == "#BADA55"

    def test_texture_slot_emits_pattern_when_slot_supplied(self):
        from flyer_generator.brochure.schema_renderer.schema_model import (
            TextureSlotFill,
        )

        fill = TextureSlotFill(slot="grain", fallback=SolidFill(color="#BADA55"))
        png = self._png()
        defs, val = render_fill(fill, "salt-1", textures={"grain": png})
        assert "<pattern" in defs
        assert "patternUnits=\"userSpaceOnUse\"" in defs
        assert "data:image/png;base64," in defs
        assert val == "url(#tex-grain-salt-1)"

    def test_texture_slot_missing_slot_falls_back(self):
        from flyer_generator.brochure.schema_renderer.schema_model import (
            GradientStop,
            LinearGradientFill,
            TextureSlotFill,
        )

        fallback = LinearGradientFill(
            stops=[
                GradientStop(offset=0.0, color="#111111"),
                GradientStop(offset=1.0, color="#EEEEEE"),
            ],
            angle=45,
        )
        fill = TextureSlotFill(slot="wanted_slot", fallback=fallback)
        # Different slot name supplied → falls back to gradient.
        defs, val = render_fill(fill, "s", textures={"other_slot": self._png()})
        assert "<linearGradient" in defs
        assert val.startswith("url(#grad-lin-")

    def test_shape_with_texture_slot_fill_uses_pattern_end_to_end(self):
        from flyer_generator.brochure.schema_renderer.schema_model import (
            TextureSlotFill,
        )

        el = ShapeElement(
            kind="rect",
            rect=(0, 0, 1000, 800),
            fill=TextureSlotFill(slot="grain", fallback=SolidFill(color="#BADA55")),
        )
        svg = render_shape(el, _CANVAS, "e2e", textures={"grain": self._png()})
        # Shape fills via the pattern; no solid color leaked through.
        assert "fill=\"url(#tex-grain-e2e)\"" in svg
        assert "<pattern" in svg
