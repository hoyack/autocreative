"""Poster template loader tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flyer_generator.poster.schema_renderer.loader import (
    list_templates,
    load_template,
)

STARTERS = [
    "bold_announcement",
    "cinematic_onesheet",
    "editorial_grand",
]


def test_list_templates_returns_list():
    """Smoke test — returns a list."""
    result = list_templates()
    assert isinstance(result, list)


def test_list_templates_returns_three_starters():
    """All three starter templates are discovered, sorted alphabetically."""
    names = list_templates()
    assert names == STARTERS


def test_load_unknown_raises():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_template("nonexistent_template_xyz")


def test_load_unknown_lists_available():
    """FileNotFoundError message includes the available templates list."""
    with pytest.raises(FileNotFoundError, match="Available"):
        load_template("nonexistent_template_xyz")


def test_load_by_path(tmp_path):
    """Loader accepts absolute file paths (branch on .endswith('.json'))."""
    doc = {
        "schema_version": "1",
        "name": "loaded_from_path",
        "description": "test",
        "canvas": {"width": 5400, "height": 7200},
        "palette": {"accent_default": "#1E3A5F"},
        "panels": {"hero": {"elements": []}},
    }
    path = tmp_path / "loaded_from_path.json"
    path.write_text(json.dumps(doc))
    t = load_template(str(path))
    assert t.name == "loaded_from_path"
    assert t.canvas.width == 5400


def test_malformed_json_rejected(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text('{"schema_version": "1", "name": "x"}')
    with pytest.raises(Exception):
        load_template(str(bad))


def test_list_templates_empty_when_dir_missing(monkeypatch, tmp_path):
    """If _SCHEMAS_DIR doesn't exist, list_templates returns []."""
    from flyer_generator.poster.schema_renderer import loader as loader_mod

    nonexistent = tmp_path / "no_such_dir"
    monkeypatch.setattr(loader_mod, "_SCHEMAS_DIR", nonexistent)
    assert list_templates() == []


@pytest.mark.parametrize("name", STARTERS)
def test_load_each_template(name: str):
    """Each shipped template validates + has a non-empty hero panel."""
    t = load_template(name)
    assert t.name == name
    assert t.canvas.width == 5400
    assert t.canvas.height == 7200
    assert "hero" in t.panels
    assert len(t.panels["hero"].elements) > 0


@pytest.mark.parametrize("name", STARTERS)
def test_shipped_template_typography_print_scaled(name: str):
    """All shipped poster templates declare print-distance typography.

    cover_title_size >= 200 ensures titles are readable from across a room
    when printed at 18×24 minimum.
    """
    t = load_template(name)
    assert t.canvas.width == 5400 and t.canvas.height == 7200
    assert t.typography.cover_title_size >= 200, (
        f"{name} cover_title_size={t.typography.cover_title_size} is "
        f"too small for print-distance reading"
    )


@pytest.mark.parametrize("name", STARTERS)
def test_shipped_template_has_text_and_shape(name: str):
    """Each shipped template ships at least one text + one shape element."""
    t = load_template(name)
    elements = t.panels["hero"].elements
    has_text = any(getattr(el, "type", None) == "text" for el in elements)
    has_shape = any(getattr(el, "type", None) == "shape" for el in elements)
    assert has_text, f"{name} missing TextElement"
    assert has_shape, f"{name} missing ShapeElement"
