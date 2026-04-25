"""Poster template schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flyer_generator.poster.schema_renderer.schema_model import (
    GradientStop,
    LinearGradientFill,
    PosterTemplateSchema,
    RadialGradientFill,
    ShapeElement,
    SolidFill,
    TextElement,
)


def test_import_smoke():
    """Barrel import works end-to-end for poster schema_renderer package."""
    from flyer_generator.poster.schema_renderer import (  # noqa: F401
        PosterTemplateSchema as _PTS,
        list_templates as _lt,
        load_template as _lt2,
    )


def _minimal_template() -> dict:
    return {
        "schema_version": "1",
        "name": "test_template",
        "description": "test",
        "canvas": {"width": 5400, "height": 7200},
        "palette": {"accent_default": "#1E3A5F"},
        "panels": {
            "hero": {"elements": []},
        },
    }


class TestPosterTemplateSchema:
    def test_minimal_template_loads(self):
        t = PosterTemplateSchema.model_validate(_minimal_template())
        assert t.name == "test_template"
        assert t.canvas.width == 5400
        assert t.canvas.height == 7200
        assert "hero" in t.panels

    def test_missing_hero_panel_rejected(self):
        data = _minimal_template()
        del data["panels"]["hero"]
        with pytest.raises(ValidationError, match="missing panels"):
            PosterTemplateSchema.model_validate(data)

    def test_missing_panels_dict_rejected(self):
        """No panels dict at all → ValidationError."""
        data = _minimal_template()
        data["panels"] = {}
        with pytest.raises(ValidationError, match="missing panels"):
            PosterTemplateSchema.model_validate(data)

    def test_schema_version_must_be_1(self):
        data = _minimal_template()
        data["schema_version"] = "2"
        with pytest.raises(ValidationError):
            PosterTemplateSchema.model_validate(data)

    def test_name_must_be_snake_case(self):
        data = _minimal_template()
        data["name"] = "BadName"
        with pytest.raises(ValidationError):
            PosterTemplateSchema.model_validate(data)

    def test_palette_rejects_invalid_hex(self):
        data = _minimal_template()
        data["palette"]["accent_default"] = "not-a-color"
        with pytest.raises(ValidationError):
            PosterTemplateSchema.model_validate(data)

    def test_canvas_defaults_to_5400x7200(self):
        """Canvas is optional with poster-aspect defaults (18×24 at 300 DPI)."""
        data = _minimal_template()
        del data["canvas"]
        t = PosterTemplateSchema.model_validate(data)
        assert t.canvas.width == 5400
        assert t.canvas.height == 7200

    def test_typography_defaults_print_scaled(self):
        """Typography defaults are sized for print reading distance.

        cover_title_size=300 vs flyer's 82 reflects ~3.65× linear scale.
        """
        t = PosterTemplateSchema.model_validate(_minimal_template())
        assert t.typography.cover_title_size == 300
        assert t.typography.cover_subtitle_size == 180
        assert t.typography.heading_size == 220
        assert t.typography.body_size == 120

    def test_subtype_compat_field_is_dropped(self):
        """Posters have no subtype split; the field must not exist on the model.

        extra='forbid' means setting subtype_compat in the JSON also fails.
        """
        data = _minimal_template()
        data["subtype_compat"] = ["event"]
        with pytest.raises(ValidationError):
            PosterTemplateSchema.model_validate(data)

    def test_extra_fields_forbidden(self):
        data = _minimal_template()
        data["unknown_field"] = "x"
        with pytest.raises(ValidationError):
            PosterTemplateSchema.model_validate(data)

    def test_validate_hex_color_importable(self):
        """Cross-package shared utility import smoke."""
        from flyer_generator.brochure.models import validate_hex_color  # noqa: F401


class TestShapeElement:
    def test_rect_with_solid_fill(self):
        el = ShapeElement(
            kind="rect",
            rect=(0, 0, 5400, 200),
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
            bbox=(400, 500, 4600, 1800),
            role="cover_title",
            content_key="event.title",
        )
        assert el.role == "cover_title"

    def test_static_text_variant(self):
        el = TextElement(
            bbox=(0, 0, 5400, 200),
            role="static",
            static_text="ESTABLISHED",
        )
        assert el.static_text == "ESTABLISHED"
