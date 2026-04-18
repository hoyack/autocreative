"""Tests for the parameterized vector shape library."""

from __future__ import annotations

import re

import pytest

from flyer_generator.brochure.shapes import (
    SHAPE_FUNCTIONS,
    accent_bar,
    circle_offpage,
    corner_wedge,
    dot_grid,
    parse_shape_recipe,
    pullquote_frame,
    render_shape,
    rotated_block,
)
from flyer_generator.brochure.stages.layout import compute_panel_layout


@pytest.fixture
def cover_panel():
    return compute_panel_layout().outside_panels[1]  # front_cover


@pytest.fixture
def inner_panel():
    return compute_panel_layout().inside_panels[0]  # inner_left


# ---------- Recipe parser ----------


def test_parse_recipe_no_args() -> None:
    name, kwargs = parse_shape_recipe("dot_grid()")
    assert name == "dot_grid"
    assert kwargs == {}


def test_parse_recipe_simple_args() -> None:
    name, kwargs = parse_shape_recipe("accent_bar(placement=top, thickness=4)")
    assert name == "accent_bar"
    assert kwargs == {"placement": "top", "thickness": 4}


def test_parse_recipe_coerces_ints() -> None:
    _, kwargs = parse_shape_recipe("circle_offpage(size=260, offset_direction=bottom-right)")
    assert kwargs["size"] == 260
    assert kwargs["offset_direction"] == "bottom-right"


def test_parse_recipe_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_shape_recipe("not a recipe")


# ---------- Registry ----------


def test_shape_functions_registry_has_six() -> None:
    assert set(SHAPE_FUNCTIONS.keys()) == {
        "circle_offpage",
        "rotated_block",
        "accent_bar",
        "dot_grid",
        "pullquote_frame",
        "corner_wedge",
    }


# ---------- Each shape returns valid SVG-ish text ----------


def test_circle_offpage_renders_circle_element(inner_panel) -> None:
    out = circle_offpage(inner_panel, "#FF0000", seed=1, offset_direction="top-left", size=200)
    assert "<circle" in out
    assert 'fill="#FF0000"' in out


def test_rotated_block_uses_transform(inner_panel) -> None:
    out = rotated_block(inner_panel, "#0000FF", seed=1, angle=10, width=100, height=30)
    assert 'transform="rotate(10' in out
    assert "<rect" in out


def test_accent_bar_top_placement(inner_panel) -> None:
    out = accent_bar(inner_panel, "#00FF00", seed=1, placement="top", thickness=6)
    assert "<rect" in out
    # At top placement the rect spans the full trim width
    assert f'width="{inner_panel.trim_rect[2]}"' in out


def test_dot_grid_creates_pattern(inner_panel) -> None:
    out = dot_grid(inner_panel, "#112233", seed=1, density="medium")
    assert "<pattern" in out
    assert "<circle" in out  # the dot itself


def test_pullquote_frame_oval_emits_ellipse(inner_panel) -> None:
    out = pullquote_frame(inner_panel, "#888888", seed=1, shape="oval")
    assert "<ellipse" in out


def test_pullquote_frame_asym_block_emits_rect(inner_panel) -> None:
    out = pullquote_frame(inner_panel, "#888888", seed=1, shape="asym_block")
    assert "<rect" in out
    assert "rx=" in out  # rounded corners


def test_corner_wedge_emits_polygon(inner_panel) -> None:
    out = corner_wedge(inner_panel, "#AABB00", seed=1, corner="bottom-right", size=150)
    assert "<polygon" in out
    assert "points=" in out


# ---------- render_shape dispatcher ----------


def test_render_shape_dispatches_by_name(inner_panel) -> None:
    out = render_shape(
        "accent_bar(placement=top, thickness=5)", inner_panel, "#FF9900", seed=1
    )
    assert "<rect" in out


def test_render_shape_unknown_name_returns_comment(inner_panel) -> None:
    out = render_shape("nonexistent_shape()", inner_panel, "#FF9900", seed=1)
    assert "<!-- unknown shape" in out


def test_render_shape_substitutes_brief_text(inner_panel) -> None:
    out = render_shape(
        "rotated_block(angle=0, width=200, height=30, text=brief)",
        inner_panel,
        "#FF9900",
        seed=1,
        text="Here is the heading",
    )
    assert "Here is the heading" in out


# ---------- Determinism ----------


def test_shape_rendering_is_deterministic(inner_panel) -> None:
    a = rotated_block(inner_panel, "#ABC000", seed=42, angle=-5, width=200, height=20)
    b = rotated_block(inner_panel, "#ABC000", seed=42, angle=-5, width=200, height=20)
    assert a == b


def test_shape_rendering_varies_with_seed(inner_panel) -> None:
    a = rotated_block(inner_panel, "#ABC000", seed=1, angle=-5, width=200, height=20)
    b = rotated_block(inner_panel, "#ABC000", seed=2, angle=-5, width=200, height=20)
    assert a != b


# ---------- Bounds sanity ----------


def test_accent_bar_inside_trim_rect(inner_panel) -> None:
    out = accent_bar(inner_panel, "#FF0000", seed=1, placement="side", thickness=10)
    x_match = re.search(r'<rect x="(\d+)"', out)
    assert x_match is not None
    x = int(x_match.group(1))
    tx = inner_panel.trim_rect[0]
    tw = inner_panel.trim_rect[2]
    assert tx <= x < tx + tw
