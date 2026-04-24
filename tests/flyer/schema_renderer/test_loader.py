"""Flyer template loader tests."""

from __future__ import annotations

import json

import pytest

from flyer_generator.flyer.schema_renderer.loader import (
    list_templates,
    load_template,
)


def test_list_templates_returns_list():
    """Smoke test — returns a list (may be empty during Task 1)."""
    result = list_templates()
    assert isinstance(result, list)


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
