"""Postcard template schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flyer_generator.postcard.schema_renderer.schema_model import (
    GradientStop,
    LinearGradientFill,
    PostcardTemplateSchema,
    RadialGradientFill,
    ShapeElement,
    SolidFill,
    TextElement,
)


def test_import_smoke():
    """Test 1 of behavior block — barrel import works end-to-end."""
    from flyer_generator.postcard.schema_renderer import (  # noqa: F401
        PostcardTemplateSchema as _PTS,
        list_templates as _lt,
        load_template as _lt2,
    )


def _minimal_template_dict() -> dict:
    return {
        "schema_version": "1",
        "name": "minimal_pc",
        "description": "minimal",
        "canvas": {"width": 1200, "height": 1800},
        "palette": {"accent_default": "#FF0000"},
        "panels": {
            "front": {"elements": []},
            "back": {"elements": []},
        },
    }


class TestPostcardTemplateSchema:
    def test_minimal_template_loads(self):
        t = PostcardTemplateSchema.model_validate(_minimal_template_dict())
        assert t.name == "minimal_pc"
        assert t.canvas.width == 1200
        assert t.canvas.height == 1800
        assert "front" in t.panels
        assert "back" in t.panels

    def test_missing_front_panel_rejected(self):
        data = _minimal_template_dict()
        del data["panels"]["front"]
        with pytest.raises(ValidationError, match="missing panels"):
            PostcardTemplateSchema.model_validate(data)

    def test_missing_back_panel_rejected(self):
        data = _minimal_template_dict()
        del data["panels"]["back"]
        with pytest.raises(ValidationError, match="missing panels"):
            PostcardTemplateSchema.model_validate(data)

    def test_schema_version_must_be_1(self):
        data = _minimal_template_dict()
        data["schema_version"] = "2"
        with pytest.raises(ValidationError):
            PostcardTemplateSchema.model_validate(data)

    def test_name_must_be_snake_case(self):
        data = _minimal_template_dict()
        data["name"] = "BadName"
        with pytest.raises(ValidationError):
            PostcardTemplateSchema.model_validate(data)

    def test_extra_top_level_keys_rejected(self):
        """extra='forbid' enforces strict schema at the top level."""
        data = _minimal_template_dict()
        data["foo"] = "bar"
        with pytest.raises(ValidationError):
            PostcardTemplateSchema.model_validate(data)

    def test_palette_rejects_invalid_hex(self):
        data = _minimal_template_dict()
        data["palette"]["accent_default"] = "not-a-color"
        with pytest.raises(ValidationError):
            PostcardTemplateSchema.model_validate(data)

    def test_canvas_required_no_defaults(self):
        """Postcards always declare canvas explicitly (4x6 vs 6x4 differ)."""
        data = _minimal_template_dict()
        del data["canvas"]
        with pytest.raises(ValidationError):
            PostcardTemplateSchema.model_validate(data)

    def test_canvas_zero_dim_rejected(self):
        data = _minimal_template_dict()
        data["canvas"] = {"width": 0, "height": 1800}
        with pytest.raises(ValidationError):
            PostcardTemplateSchema.model_validate(data)

    def test_palette_keeps_scrim_opacity_defaults(self):
        """Front panel may compose scrim over hero — defaults preserved from flyer."""
        t = PostcardTemplateSchema.model_validate(_minimal_template_dict())
        assert t.palette.scrim_opacity_top == 0.75
        assert t.palette.scrim_opacity_bottom == 0.85

    def test_validate_hex_color_importable(self):
        """Cross-package shared utility import smoke."""
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
            content_key="body",
        )
        assert el.role == "body"

    def test_static_text_variant(self):
        el = TextElement(
            bbox=(0, 0, 100, 50),
            role="static",
            static_text="STAMP",
        )
        assert el.static_text == "STAMP"
