"""Tests for brochure SVG composition.

Verifies that compose_brochure_svgs() produces two well-formed SVG documents
with: correct dimensions, hero image on the front cover, accent gradients on
the other five panels, text within safe zones, and fold/crop-mark layers.
"""

from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET

import pytest

from flyer_generator.brochure.stages.composer import compose_brochure_svgs
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
    compute_panel_layout,
)
from flyer_generator.errors import CompositionError
from tests.brochure.fixtures.sample_brochures import FULL_BROCHURE, MINIMAL_BROCHURE

_FAKE_HERO_PNG = b"\x89PNG\r\n\x1a\nfake-png-bytes-for-test"


def _both_sheets(brochure=MINIMAL_BROCHURE, render_guides: bool = False) -> tuple[str, str]:
    layout = compute_panel_layout()
    return compose_brochure_svgs(
        brochure, layout, _FAKE_HERO_PNG, render_guides=render_guides
    )


def _strip_ns(elem: ET.Element) -> None:
    for e in elem.iter():
        if "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]


def _parse(svg: str) -> ET.Element:
    root = ET.fromstring(svg)
    _strip_ns(root)
    return root


# ---------- Both sheets basics ----------


def test_returns_two_svg_strings() -> None:
    outside, inside = _both_sheets()
    assert outside.startswith("<?xml")
    assert inside.startswith("<?xml")
    assert "<svg" in outside
    assert "<svg" in inside


def test_sheets_have_correct_canvas_dimensions() -> None:
    outside, inside = _both_sheets()
    for svg in (outside, inside):
        root = _parse(svg)
        assert root.attrib["width"] == str(BLEED_CANVAS_WIDTH)
        assert root.attrib["height"] == str(BLEED_CANVAS_HEIGHT)


def test_sheets_are_well_formed_xml() -> None:
    outside, inside = _both_sheets()
    # Should not raise.
    _parse(outside)
    _parse(inside)


# ---------- Front cover ----------


def test_front_cover_embeds_hero_png_as_base64() -> None:
    outside, _ = _both_sheets()
    expected_b64 = base64.b64encode(_FAKE_HERO_PNG).decode()
    assert f"data:image/png;base64,{expected_b64}" in outside


def test_front_cover_shows_uppercased_title() -> None:
    outside, _ = _both_sheets()
    assert MINIMAL_BROCHURE.title.upper() in outside


def test_subtitle_appears_when_provided() -> None:
    outside, _ = _both_sheets(FULL_BROCHURE)
    assert FULL_BROCHURE.subtitle in outside


def test_no_subtitle_rendered_when_none() -> None:
    # MINIMAL_BROCHURE has subtitle=None
    outside, _ = _both_sheets(MINIMAL_BROCHURE)
    # There should only be ONE big overlay <text> chunk on the cover region
    # (title). We check that there's no "None" string leaked.
    assert "None" not in outside


# ---------- Gradients on non-cover panels ----------


def test_outside_sheet_has_gradient_on_back_cover_and_tuck_flap() -> None:
    outside, _ = _both_sheets()
    assert 'id="grad-outside-back_cover"' in outside
    assert 'id="grad-outside-tuck_flap"' in outside
    # front_cover has hero image, not gradient
    assert 'id="grad-outside-front_cover"' not in outside


def test_inside_sheet_has_gradients_on_all_three_panels() -> None:
    _, inside = _both_sheets()
    assert 'id="grad-inside-inner_left"' in inside
    assert 'id="grad-inside-inner_center"' in inside
    assert 'id="grad-inside-inner_right"' in inside


def test_gradient_uses_accent_color() -> None:
    outside, _ = _both_sheets(FULL_BROCHURE)
    assert f'stop-color="{FULL_BROCHURE.color_accent}"' in outside


# ---------- Section text ----------


def test_inner_panels_render_section_headings_in_order() -> None:
    _, inside = _both_sheets(FULL_BROCHURE)
    # sections[1..3] assigned to inner_left, inner_center, inner_right
    assert FULL_BROCHURE.sections[1].heading in inside
    assert FULL_BROCHURE.sections[2].heading in inside
    assert FULL_BROCHURE.sections[3].heading in inside


def test_tuck_flap_shows_compressed_first_section() -> None:
    outside, _ = _both_sheets(FULL_BROCHURE)
    # Heading of sections[0] appears on tuck flap
    assert FULL_BROCHURE.sections[0].heading in outside


def test_overflow_fifth_section_appears_on_inside_right_panel() -> None:
    _, inside = _both_sheets(FULL_BROCHURE)  # has 5 sections
    assert FULL_BROCHURE.sections[4].heading in inside


def test_minimal_brochure_has_no_inside_panel_body_for_missing_sections() -> None:
    _, inside = _both_sheets(MINIMAL_BROCHURE)  # only 2 sections — inside gets sections[1] only
    # sections[1] heading should appear
    assert MINIMAL_BROCHURE.sections[1].heading in inside
    # No overflow section text
    assert "overflow" not in inside.lower()


# ---------- Back cover ----------


def test_back_cover_renders_back_panel_when_provided() -> None:
    outside, _ = _both_sheets(FULL_BROCHURE)
    # FULL_BROCHURE back_panel kind="cta" content about registration
    assert "example.com/conf" in outside


def test_back_cover_falls_back_to_org_and_contact_when_no_back_panel() -> None:
    outside, _ = _both_sheets(MINIMAL_BROCHURE)  # no back_panel
    assert MINIMAL_BROCHURE.org in outside


# ---------- Fold lines ----------


def test_fold_lines_on_dedicated_layer_when_render_guides_true() -> None:
    outside, inside = _both_sheets(render_guides=True)
    for svg in (outside, inside):
        assert 'id="fold-lines"' in svg
        assert 'data-print="false"' in svg


def test_fold_lines_hidden_by_default() -> None:
    """v1 print bug fix: fold lines must NOT render unless render_guides=True."""
    outside, inside = _both_sheets()  # render_guides defaults to False
    for svg in (outside, inside):
        assert 'id="fold-lines"' not in svg


def test_fold_lines_count_is_two_per_sheet_when_rendered() -> None:
    outside, _ = _both_sheets(render_guides=True)
    root = _parse(outside)
    fold_group = None
    for g in root.iter("g"):
        if g.attrib.get("id") == "fold-lines":
            fold_group = g
            break
    assert fold_group is not None
    lines = list(fold_group.iter("line"))
    assert len(lines) == 2


# ---------- Crop marks ----------


def test_crop_marks_on_dedicated_layer() -> None:
    outside, _ = _both_sheets()
    assert 'id="crop-marks"' in outside


def test_crop_marks_count_is_eight_lines_per_sheet() -> None:
    # Each anchor renders 2 lines (horizontal + vertical). 4 anchors per sheet = 8 lines.
    outside, _ = _both_sheets()
    root = _parse(outside)
    crop_group = None
    for g in root.iter("g"):
        if g.attrib.get("id") == "crop-marks":
            crop_group = g
            break
    assert crop_group is not None
    lines = list(crop_group.iter("line"))
    assert len(lines) == 8


# ---------- Escape + safety ----------


def test_user_supplied_strings_are_xml_escaped() -> None:
    from flyer_generator.brochure.models import (
        BrochureBackPanel,
        BrochureInput,
        BrochureSection,
    )

    evil = BrochureInput(
        title="<script>evil</script>",
        hero_concept="x",
        style_preset="photorealistic",
        color_accent="#F59E0B",
        org="Ampersand & Co",
        sections=[
            BrochureSection(heading="a > b", body="b < c & d"),
            BrochureSection(heading="quote \" and '", body="body"),
        ],
    )
    layout = compute_panel_layout()
    outside, inside = compose_brochure_svgs(evil, layout, _FAKE_HERO_PNG)

    # Title (with <script>) only appears on outside sheet; it must be escaped.
    assert "<script>" not in outside
    assert "&lt;SCRIPT&gt;" in outside  # title uppercased before escape

    # Ampersand escaping — org renders on the back cover (outside).
    assert "Ampersand &amp; Co" in outside

    # Both sheets must be well-formed: no bare ampersands outside valid escape sequences.
    for svg in (outside, inside):
        bare = re.findall(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)", svg)
        assert not bare, f"bare ampersands in SVG: {bare}"

    # sections[0] is assigned to tuck_flap on OUTSIDE; heading "a > b" and body
    # "b < c & d" must be properly escaped there.
    assert "a &gt; b" in outside
    assert "b &lt; c &amp; d" in outside

    # Both sheets must parse as XML (catches unescaped angle brackets).
    _parse(outside)
    _parse(inside)


def test_empty_hero_bytes_raises_composition_error() -> None:
    layout = compute_panel_layout()
    with pytest.raises(CompositionError):
        compose_brochure_svgs(MINIMAL_BROCHURE, layout, b"")
