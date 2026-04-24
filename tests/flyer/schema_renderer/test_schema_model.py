"""Flyer template schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flyer_generator.flyer.schema_renderer.schema_model import (
    FlyerTemplateSchema,
    GradientStop,
    LinearGradientFill,
    RadialGradientFill,
    ShapeElement,
    SolidFill,
    TextElement,
)


def test_import_smoke():
    """Test 1 of behavior block — barrel import works end-to-end."""
    from flyer_generator.flyer.schema_renderer import (  # noqa: F401
        FlyerTemplateSchema as _FTS,
        list_templates as _lt,
        load_template as _lt2,
    )


def _minimal_template() -> dict:
    return {
        "schema_version": "1",
        "name": "test_template",
        "description": "test",
        "canvas": {"width": 1080, "height": 1920},
        "palette": {"accent_default": "#1E3A5F"},
        "panels": {
            "hero": {"elements": []},
        },
    }


class TestFlyerTemplateSchema:
    def test_minimal_template_loads(self):
        t = FlyerTemplateSchema.model_validate(_minimal_template())
        assert t.name == "test_template"
        assert t.canvas.width == 1080
        assert t.canvas.height == 1920
        assert "hero" in t.panels

    def test_missing_hero_panel_rejected(self):
        data = _minimal_template()
        del data["panels"]["hero"]
        with pytest.raises(ValidationError, match="missing panels"):
            FlyerTemplateSchema.model_validate(data)

    def test_schema_version_must_be_1(self):
        data = _minimal_template()
        data["schema_version"] = "2"
        with pytest.raises(ValidationError):
            FlyerTemplateSchema.model_validate(data)

    def test_name_must_be_snake_case(self):
        data = _minimal_template()
        data["name"] = "BadName"
        with pytest.raises(ValidationError):
            FlyerTemplateSchema.model_validate(data)

    def test_palette_rejects_invalid_hex(self):
        data = _minimal_template()
        data["palette"]["accent_default"] = "not-a-color"
        with pytest.raises(ValidationError):
            FlyerTemplateSchema.model_validate(data)

    def test_subtype_compat_defaults_to_both(self):
        t = FlyerTemplateSchema.model_validate(_minimal_template())
        assert set(t.subtype_compat) == {"event", "info"}

    def test_subtype_compat_event_only(self):
        data = _minimal_template()
        data["subtype_compat"] = ["event"]
        t = FlyerTemplateSchema.model_validate(data)
        assert t.subtype_compat == ["event"]

    def test_canvas_defaults_to_1080x1920(self):
        """Canvas is optional with flyer-aspect defaults."""
        data = _minimal_template()
        del data["canvas"]
        t = FlyerTemplateSchema.model_validate(data)
        assert t.canvas.width == 1080
        assert t.canvas.height == 1920

    def test_validate_hex_color_importable(self):
        """Cross-package shared utility import smoke (22-PATTERNS line 151)."""
        from flyer_generator.brochure.models import validate_hex_color  # noqa: F401


class TestShapeElement:
    def test_rect_with_solid_fill(self):
        el = ShapeElement(
            kind="rect",
            rect=(0, 0, 100, 50),
            fill=SolidFill(color="#123456"),
        )
        assert el.kind == "rect"
        assert el.fill is not None
        assert el.fill.type == "solid"

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


class TestTextElement:
    def test_text_with_content_key(self):
        el = TextElement(
            bbox=(10, 20, 500, 100),
            role="body",
            content_key="event.title",
        )
        assert el.role == "body"

    def test_static_text_variant(self):
        el = TextElement(
            bbox=(0, 0, 100, 50),
            role="static",
            static_text="ESTABLISHED",
        )
        assert el.static_text == "ESTABLISHED"
