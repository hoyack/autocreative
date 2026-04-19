"""Schema model validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flyer_generator.brochure.schema_renderer.schema_model import (
    BulletsElement,
    GradientStop,
    LinearGradientFill,
    RadialGradientFill,
    ShapeElement,
    SolidFill,
    TemplateSchema,
    TextElement,
)


def _minimal_template() -> dict:
    return {
        "schema_version": "1",
        "name": "test_template",
        "description": "test",
        "canvas": {"width": 1100, "height": 2550},
        "palette": {"accent_default": "#1E3A5F"},
        "panels": {
            "front_cover": {"elements": []},
            "back_cover": {"elements": []},
            "tuck_flap": {"elements": []},
            "inner_left": {"elements": []},
            "inner_center": {"elements": []},
            "inner_right": {"elements": []},
        },
    }


class TestTemplateSchema:
    def test_minimal_template_loads(self):
        t = TemplateSchema.model_validate(_minimal_template())
        assert t.name == "test_template"
        assert t.canvas.width == 1100
        assert len(t.panels) == 6

    def test_missing_panel_rejected(self):
        data = _minimal_template()
        del data["panels"]["tuck_flap"]
        with pytest.raises(ValidationError, match="missing panels"):
            TemplateSchema.model_validate(data)

    def test_schema_version_must_be_1(self):
        data = _minimal_template()
        data["schema_version"] = "2"
        with pytest.raises(ValidationError):
            TemplateSchema.model_validate(data)

    def test_name_must_be_snake_case(self):
        data = _minimal_template()
        data["name"] = "BadName"
        with pytest.raises(ValidationError):
            TemplateSchema.model_validate(data)

    def test_palette_rejects_invalid_hex(self):
        data = _minimal_template()
        data["palette"]["accent_default"] = "not-a-color"
        with pytest.raises(ValidationError):
            TemplateSchema.model_validate(data)


class TestShapeElement:
    def test_rect_with_solid_fill(self):
        el = ShapeElement(
            kind="rect",
            rect=(0, 0, 100, 50),
            fill=SolidFill(color="#123456"),
        )
        assert el.kind == "rect"
        assert el.fill.type == "solid"

    def test_polygon_with_points(self):
        el = ShapeElement(
            kind="polygon",
            points=[(0, 0), (100, 0), (50, 100)],
        )
        assert len(el.points) == 3

    def test_linear_gradient_fill(self):
        fill = LinearGradientFill(
            stops=[
                GradientStop(offset=0, color="#FF0000", opacity=1.0),
                GradientStop(offset=1, color="#00FF00", opacity=0.5),
            ],
            angle=45,
        )
        assert fill.type == "linear_gradient"
        assert len(fill.stops) == 2

    def test_radial_gradient_fill(self):
        fill = RadialGradientFill(
            stops=[
                GradientStop(offset=0, color="#FFFFFF"),
                GradientStop(offset=1, color="#000000"),
            ],
            center=(0.5, 0.5),
            radius=0.75,
        )
        assert fill.type == "radial_gradient"

    def test_gradient_needs_at_least_two_stops(self):
        with pytest.raises(ValidationError):
            LinearGradientFill(stops=[GradientStop(offset=0, color="#000000")])

    def test_bleed_accepts_literals(self):
        for bleed in (True, False, "all", "left", "right", "top", "bottom"):
            el = ShapeElement(kind="rect", rect=(0, 0, 10, 10), bleed=bleed)
            assert el.bleed == bleed


class TestTextElement:
    def test_text_with_content_key(self):
        el = TextElement(
            bbox=(10, 20, 500, 100),
            role="body",
            content_key="sections[0].heading",
        )
        assert el.role == "body"

    def test_static_text_variant(self):
        el = TextElement(
            bbox=(0, 0, 100, 50),
            role="static",
            static_text="ESTABLISHED 1999",
        )
        assert el.static_text == "ESTABLISHED 1999"

    def test_opacity_in_bounds(self):
        with pytest.raises(ValidationError):
            TextElement(
                bbox=(0, 0, 100, 50), role="body", content_key="x", opacity=1.5
            )


class TestBulletsElement:
    def test_valid_bullets(self):
        el = BulletsElement(
            bbox=(0, 0, 500, 300),
            content_key="sections[0].bullets",
            section_index=0,
            bullet_style="dash",
        )
        assert el.bullet_style == "dash"

    def test_bullet_color_validated(self):
        with pytest.raises(ValidationError):
            BulletsElement(
                bbox=(0, 0, 500, 300),
                content_key="x",
                bullet_color="not-hex",
            )
