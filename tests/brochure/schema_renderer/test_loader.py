"""Schema loader tests."""

from __future__ import annotations

import json

import pytest

from flyer_generator.brochure.schema_renderer.loader import (
    list_templates,
    load_template,
)


def test_list_templates_contains_starters():
    names = list_templates()
    assert "editorial_classic" in names
    assert "geometric_bold" in names
    assert "quote_center" in names


def test_load_editorial_classic():
    t = load_template("editorial_classic")
    assert t.name == "editorial_classic"
    assert t.canvas.width == 1100
    # All 6 panels have at least one element
    for panel in t.panels.values():
        assert len(panel.elements) > 0


def test_load_geometric_bold():
    t = load_template("geometric_bold")
    assert t.name == "geometric_bold"


def test_load_quote_center():
    t = load_template("quote_center")
    assert t.name == "quote_center"


def test_load_unknown_raises():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_template("nonexistent_template_xyz")


def test_load_by_path(tmp_path):
    # Round-trip: serialize a known template, reload from path
    t = load_template("editorial_classic")
    path = tmp_path / "copy.json"
    path.write_text(t.model_dump_json())
    t2 = load_template(str(path))
    assert t2.name == t.name


def test_malformed_json_rejected(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text('{"schema_version": "1", "name": "x"}')
    with pytest.raises(Exception):
        load_template(str(bad))
