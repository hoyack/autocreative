"""Postcard template loader tests."""

from __future__ import annotations

import json

import pytest

from flyer_generator.postcard.schema_renderer.loader import (
    list_templates,
    load_template,
)

STARTERS = ["classic_portrait", "modern_landscape"]


def test_list_templates_returns_list():
    """Smoke test — returns a list."""
    result = list_templates()
    assert isinstance(result, list)


def test_list_templates_includes_starters():
    """Both shipped starter templates discoverable."""
    names = set(list_templates())
    assert {"classic_portrait", "modern_landscape"} <= names


def test_load_unknown_raises():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_template("nonexistent_template_xyz")


def test_load_by_path(tmp_path):
    """Loader accepts absolute file paths (branch on .endswith('.json'))."""
    doc = {
        "schema_version": "1",
        "name": "loaded_from_path",
        "description": "test",
        "canvas": {"width": 1200, "height": 1800},
        "palette": {"accent_default": "#1E3A5F"},
        "panels": {
            "front": {"elements": []},
            "back": {"elements": []},
        },
    }
    path = tmp_path / "loaded_from_path.json"
    path.write_text(json.dumps(doc))
    t = load_template(str(path))
    assert t.name == "loaded_from_path"
    assert t.canvas.width == 1200


def test_malformed_json_rejected(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text('{"schema_version": "1", "name": "x"}')
    with pytest.raises(Exception):
        load_template(str(bad))


@pytest.mark.parametrize("name", STARTERS)
def test_load_each_template(name: str):
    """Each shipped template validates."""
    t = load_template(name)
    assert t.name == name
    assert "front" in t.panels
    assert "back" in t.panels


def test_classic_portrait_canvas_dims():
    t = load_template("classic_portrait")
    assert (t.canvas.width, t.canvas.height) == (1200, 1800)


def test_modern_landscape_canvas_dims():
    t = load_template("modern_landscape")
    assert (t.canvas.width, t.canvas.height) == (1800, 1200)


@pytest.mark.parametrize("name", STARTERS)
def test_each_template_has_front_and_back_panels(name: str):
    t = load_template(name)
    assert "front" in t.panels
    assert "back" in t.panels
    # both panels non-empty
    assert len(t.panels["front"].elements) > 0
    assert len(t.panels["back"].elements) > 0


@pytest.mark.parametrize("name", STARTERS)
def test_each_template_front_has_image_placeholder_hero_slot(name: str):
    t = load_template(name)
    elements = t.panels["front"].elements
    image_placeholders = [
        el for el in elements if getattr(el, "type", None) == "image_placeholder"
    ]
    assert any(getattr(el, "slot", None) == "hero" for el in image_placeholders), (
        f"Template {name} front panel must contain an image_placeholder with slot='hero'"
    )


@pytest.mark.parametrize("name", STARTERS)
def test_each_template_front_has_headline_text_key(name: str):
    t = load_template(name)
    elements = t.panels["front"].elements
    text_keys = [
        getattr(el, "content_key", None)
        for el in elements
        if getattr(el, "type", None) == "text"
    ]
    assert "headline" in text_keys, (
        f"Template {name} front panel must reference content_key='headline'"
    )


@pytest.mark.parametrize("name", STARTERS)
def test_each_template_back_has_address_block_text_keys(name: str):
    t = load_template(name)
    elements = t.panels["back"].elements
    text_keys = {
        getattr(el, "content_key", None)
        for el in elements
        if getattr(el, "type", None) == "text"
    }
    required = {
        "body",
        "address_block.recipient_name",
        "address_block.street",
        "address_block.city_state_zip",
    }
    missing = required - text_keys
    assert not missing, (
        f"Template {name} back panel missing content_keys: {sorted(missing)}"
    )
