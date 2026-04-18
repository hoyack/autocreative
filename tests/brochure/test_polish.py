"""Polish phase tests: shape/text collision fixes + spot-image compositing."""

from __future__ import annotations

import re

from flyer_generator.brochure.models import (
    BrochureBackPanel,
    BrochureInput,
    BrochureSection,
)
from flyer_generator.brochure.shapes import circle_offpage, rotated_block
from flyer_generator.brochure.stages.composer import compose_brochure_svgs
from flyer_generator.brochure.stages.layout import compute_panel_layout
from flyer_generator.brochure.templates import PLAYFUL
from tests.brochure.fixtures.sample_brochures import FULL_BROCHURE

_FAKE_HERO = b"\x89PNG\r\n\x1a\nfake"


# ------------ Shape position fixes ------------


def test_large_rotated_block_sits_in_bottom_third() -> None:
    """Decorative blocks should anchor below the heading zone."""
    panel = compute_panel_layout().inside_panels[0]  # inner_left
    sx, sy, sw, sh = panel.safe_rect

    # Large block (height > 20)
    out = rotated_block(panel, "#FF0000", seed=1, angle=-5, width=300, height=80)
    y_match = re.search(r'<rect x="\d+" y="(\d+)"', out)
    assert y_match
    y = int(y_match.group(1))
    # Bottom third = y >= sy + sh * 0.66
    assert y >= sy + int(sh * 0.66), f"Large block y={y} should be in bottom third (>= {sy + int(sh*0.66)})"


def test_thin_rotated_block_sits_above_heading() -> None:
    """Thin accent bars (height <= 20) stay near the top as an accent line."""
    panel = compute_panel_layout().inside_panels[0]
    sx, sy, _, _ = panel.safe_rect

    out = rotated_block(panel, "#FF0000", seed=1, angle=0, width=120, height=8)
    y_match = re.search(r'<rect x="\d+" y="(-?\d+)"', out)
    assert y_match
    y = int(y_match.group(1))
    # Thin bar should sit around sy - 16 (just above the safe zone top)
    assert y < sy, f"Thin bar y={y} should be above safe zone top ({sy})"


def test_circle_offpage_top_has_reduced_protrusion() -> None:
    """A top-* circle's visible portion should be small (<=30% of panel height)."""
    panel = compute_panel_layout().inside_panels[0]
    _, by, _, bh = panel.bleed_rect

    out = circle_offpage(panel, "#FF0000", seed=1, offset_direction="top-left", size=240)
    cy_match = re.search(r'<circle cx="[-\d]+" cy="([-\d]+)"', out)
    assert cy_match
    cy = int(cy_match.group(1))
    # With protrude_vert=25%, the visible cap into the panel is ≤ size*0.5 (radius)
    # Circle bottom = cy + radius. Its max extent into panel from top (by) should be reasonable.
    visible_into_panel = (cy + 120) - by  # cy + radius - panel top
    assert 0 < visible_into_panel <= int(bh * 0.25), (
        f"Top-offset circle protrudes {visible_into_panel}px; expected small peek (≤25% of panel)"
    )


# ------------ Spot-image compositing ------------


def _brochure_with_section_headings(headings: list[str]) -> BrochureInput:
    assert 2 <= len(headings) <= 5
    return BrochureInput(
        title="Spot Test",
        hero_concept="x",
        style_preset="photorealistic",
        color_accent="#7BB661",
        org="org",
        sections=[BrochureSection(heading=h, body=f"body for {h}") for h in headings],
    )


def test_spot_images_embedded_in_matching_panels() -> None:
    brochure = _brochure_with_section_headings(["Cover", "Classes", "Pricing", "Visit"])
    # sections[1..3] = Classes / Pricing / Visit go to inner panels
    spot = b"\x89PNG\r\n\x1a\nfake-spot-image"
    spot_images = {"Classes": spot}

    layout = compute_panel_layout()
    _, inside = compose_brochure_svgs(
        brochure, layout, _FAKE_HERO, spot_images=spot_images
    )

    # Spot image must appear as base64 <image> element on the inside sheet.
    import base64
    b64 = base64.b64encode(spot).decode()
    assert f"data:image/png;base64,{b64}" in inside


def test_no_spot_image_when_dict_empty() -> None:
    brochure = _brochure_with_section_headings(["A", "B"])
    layout = compute_panel_layout()
    _, inside_empty = compose_brochure_svgs(brochure, layout, _FAKE_HERO, spot_images={})
    _, inside_none = compose_brochure_svgs(brochure, layout, _FAKE_HERO, spot_images=None)

    # Both should render identically; no <image> elements on inside sheet.
    count_empty = inside_empty.count("<image")
    count_none = inside_none.count("<image")
    assert count_empty == count_none == 0


def test_spot_image_does_not_overlap_heading() -> None:
    brochure = _brochure_with_section_headings(["Cover", "Classes"])
    spot = b"\x89PNG\r\n\x1a\nfake-spot"
    spot_images = {"Classes": spot}

    layout = compute_panel_layout()
    _, inside = compose_brochure_svgs(
        brochure, layout, _FAKE_HERO, spot_images=spot_images
    )

    # The heading "Classes" on inside sheet should appear BELOW the image.
    # Find image y + height, and heading text y.
    image_match = re.search(r'<image x="\d+" y="(\d+)" width="\d+" height="(\d+)"', inside)
    heading_match = re.search(r'<text x="\d+" y="(\d+)"[^>]*>Classes</text>', inside)
    assert image_match and heading_match
    image_y = int(image_match.group(1))
    image_h = int(image_match.group(2))
    heading_y = int(heading_match.group(1))
    assert heading_y > image_y + image_h, (
        f"Heading y={heading_y} should be below image bottom ({image_y + image_h})"
    )


def test_spot_image_keyed_by_nonexistent_heading_is_ignored() -> None:
    """Keys that don't match any section heading should be silently dropped."""
    brochure = _brochure_with_section_headings(["A", "B"])
    # spot_images references a heading that's not in the brochure
    spot_images = {"ZZZ": b"\x89PNG-fake"}

    layout = compute_panel_layout()
    _, inside = compose_brochure_svgs(
        brochure, layout, _FAKE_HERO, spot_images=spot_images
    )
    assert "<image" not in inside


def test_v1_tests_still_pass_without_spot_images_kwarg() -> None:
    """Backward compat — calling composer without spot_images still works."""
    layout = compute_panel_layout()
    outside, inside = compose_brochure_svgs(FULL_BROCHURE, layout, _FAKE_HERO)
    # Both SVGs should parse fine
    import xml.etree.ElementTree as ET
    ET.fromstring(outside)
    ET.fromstring(inside)


def test_spot_image_renders_on_tuck_flap_when_section_landed_there() -> None:
    """Phase 16 change: tuck flap shows sections[3] when present. Spot keyed there renders."""
    brochure = _brochure_with_section_headings(["A", "B", "C", "TuckOne"])
    spot = b"\x89PNG-spot-bytes"
    spot_images = {"TuckOne": spot}

    layout = compute_panel_layout()
    outside, _ = compose_brochure_svgs(
        brochure, layout, _FAKE_HERO, spot_images=spot_images
    )

    import base64
    b64 = base64.b64encode(spot).decode()
    assert f"data:image/png;base64,{b64}" in outside


def test_spot_image_composes_with_template_shapes() -> None:
    """Spot images + template shapes should coexist without breaking SVG."""
    brochure = _brochure_with_section_headings(["Cover", "Classes"])
    spot_images = {"Classes": b"\x89PNG-fake"}

    layout = compute_panel_layout()
    _, inside = compose_brochure_svgs(
        brochure, layout, _FAKE_HERO, template=PLAYFUL, spot_images=spot_images
    )

    # Must contain both the image AND a shape element (circle or pattern from PLAYFUL)
    assert "<image" in inside
    assert "<circle" in inside or "<pattern" in inside
    # Well-formed XML
    import xml.etree.ElementTree as ET
    ET.fromstring(inside)
