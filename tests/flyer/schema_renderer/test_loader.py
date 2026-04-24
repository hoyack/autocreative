"""Flyer template loader tests."""

from __future__ import annotations

import json

import pytest

from flyer_generator.flyer.schema_renderer.loader import (
    list_templates,
    load_template,
)

STARTERS = [
    "bold_modern",
    "editorial_classic",
    "minimal_photo",
    "retro_poster",
    "tight_typographic",
    "zine",
]


def test_list_templates_returns_list():
    """Smoke test — returns a list."""
    result = list_templates()
    assert isinstance(result, list)


def test_list_templates_returns_all_six():
    """All six starter templates are discovered, sorted alphabetically."""
    names = list_templates()
    assert names == STARTERS


def test_load_unknown_raises():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_template("nonexistent_template_xyz")


def test_load_by_path(tmp_path):
    """Loader accepts absolute file paths (branch on .endswith('.json'))."""
    doc = {
        "schema_version": "1",
        "name": "loaded_from_path",
        "description": "test",
        "canvas": {"width": 1080, "height": 1920},
        "palette": {"accent_default": "#1E3A5F"},
        "panels": {"hero": {"elements": []}},
    }
    path = tmp_path / "loaded_from_path.json"
    path.write_text(json.dumps(doc))
    t = load_template(str(path))
    assert t.name == "loaded_from_path"
    assert t.canvas.width == 1080


def test_malformed_json_rejected(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text('{"schema_version": "1", "name": "x"}')
    with pytest.raises(Exception):
        load_template(str(bad))


@pytest.mark.parametrize("name", STARTERS)
def test_load_each_template(name: str):
    """Each of the 6 shipped templates validates + has a non-empty hero panel."""
    t = load_template(name)
    assert t.name == name
    assert t.canvas.width == 1080
    assert t.canvas.height == 1920
    assert "hero" in t.panels
    assert len(t.panels["hero"].elements) > 0


@pytest.mark.parametrize("name", STARTERS)
def test_template_declares_typography_or_scrim_or_shape(name: str):
    """FT-03 guarantee — templates must declare typography scale OR scrim
    opacity OR shape mix, not just color overrides.

    We assert AT LEAST one of the following holds per template:
    - non-default typography.cover_title_size (!= 82)
    - non-default palette.scrim_opacity_top (!= 0.75)
    - at least one non-text ShapeElement in the hero panel
    """
    t = load_template(name)
    has_custom_typography = t.typography.cover_title_size != 82
    has_custom_scrim = t.palette.scrim_opacity_top != 0.75
    has_shape = any(
        getattr(el, "type", None) == "shape" for el in t.panels["hero"].elements
    )
    assert has_custom_typography or has_custom_scrim or has_shape, (
        f"Template {name} must declare at least one of: "
        "custom typography scale, custom scrim opacity, or a shape element"
    )


def test_retro_poster_is_event_only():
    assert load_template("retro_poster").subtype_compat == ["event"]


def test_bold_modern_is_event_only():
    assert load_template("bold_modern").subtype_compat == ["event"]


def test_editorial_classic_supports_both_subtypes():
    assert set(load_template("editorial_classic").subtype_compat) == {"event", "info"}
