"""Tests for composer v2 additions: template-driven shapes, layout choices, fixed bugs."""

from __future__ import annotations

from flyer_generator.brochure.generative.models import LayoutChoice
from flyer_generator.brochure.stages.composer import compose_brochure_svgs
from flyer_generator.brochure.stages.layout import compute_panel_layout
from flyer_generator.brochure.templates import (
    EDITORIAL,
    MINIMALIST,
    PLAYFUL,
    get_template,
)
from tests.brochure.fixtures.sample_brochures import FULL_BROCHURE

_FAKE_HERO_PNG = b"\x89PNG\r\n\x1a\nfake-png-bytes"


def _render_with(template, layout_choice=None, render_guides=False):
    layout = compute_panel_layout()
    return compose_brochure_svgs(
        FULL_BROCHURE,
        layout,
        _FAKE_HERO_PNG,
        layout_choice=layout_choice,
        template=template,
        render_guides=render_guides,
    )


# ---------- Back-panel heading fix (v1 bug) ----------


def test_back_panel_kind_no_longer_renders_as_heading() -> None:
    """v1 bug: the Literal kind value 'cta' rendered as the heading. Must be mapped now."""
    outside, _ = _render_with(template=None)  # v1-compatible path
    # FULL_BROCHURE has back_panel with kind='cta'. Heading should now be human-readable.
    assert "Visit Us" in outside
    # Literal 'CTA' (uppercased) must NOT appear
    assert ">CTA<" not in outside


def test_back_panel_heading_mapping_per_kind() -> None:
    from flyer_generator.brochure.models import (
        BrochureBackPanel,
        BrochureInput,
        BrochureSection,
    )

    mappings = {
        "cta": "Visit Us",
        "bio": "About",
        "map_stub": "Find Us",
        "contact": "Contact",
    }
    for kind, expected_heading in mappings.items():
        brochure = BrochureInput(
            title="T",
            hero_concept="x",
            style_preset="photorealistic",
            color_accent="#F59E0B",
            org="Org",
            sections=[
                BrochureSection(heading="A", body="body"),
                BrochureSection(heading="B", body="body"),
            ],
            back_panel=BrochureBackPanel(kind=kind, content="content"),  # type: ignore[arg-type]
        )
        layout = compute_panel_layout()
        outside, _ = compose_brochure_svgs(brochure, layout, _FAKE_HERO_PNG)
        assert expected_heading in outside, f"kind={kind} should render heading {expected_heading}"


# ---------- Template shapes integration ----------


def test_template_shapes_render_on_playful() -> None:
    outside, inside = _render_with(template=PLAYFUL)
    # Playful template declares circle_offpage on inner panels
    assert "<circle" in inside
    # And dot_grid uses <pattern>
    assert "<pattern" in inside


def test_template_shapes_render_on_editorial() -> None:
    outside, inside = _render_with(template=EDITORIAL)
    # Editorial uses accent_bar(top) — we should see a thin rect at top of panels
    # But not decorative shapes like circles or patterns
    assert "<circle" not in inside  # no decorative circles in editorial
    assert "<pattern" not in inside  # no dot grids in editorial


def test_template_shapes_render_on_minimalist() -> None:
    outside, inside = _render_with(template=MINIMALIST)
    # Minimalist uses rotated_block — <g transform="rotate(...)"> inside
    assert "rotate(" in inside or "rotate(" in outside


def test_no_template_renders_zero_shapes() -> None:
    """Back-compat path: when template=None, no shape rendering happens."""
    outside_no_template, inside_no_template = _render_with(template=None)
    outside_playful, inside_playful = _render_with(template=PLAYFUL)
    # The playful variant should have additional shape markup not present in no-template version
    assert len(outside_playful) + len(inside_playful) > len(outside_no_template) + len(inside_no_template)


# ---------- LayoutChoice.shape_density ----------


def test_shape_density_sparse_reduces_shapes() -> None:
    sparse_choice = LayoutChoice(
        template="playful",
        shape_density="sparse",
        accent_placement="top_rule",
        cover_treatment="image_full",
    )
    dense_choice = LayoutChoice(
        template="playful",
        shape_density="dense",
        accent_placement="top_rule",
        cover_treatment="image_full",
    )
    _, inside_sparse = _render_with(template=PLAYFUL, layout_choice=sparse_choice)
    _, inside_dense = _render_with(template=PLAYFUL, layout_choice=dense_choice)
    # Dense should produce more markup than sparse
    assert len(inside_dense) > len(inside_sparse)


# ---------- Fold-line print bug fix ----------


def test_render_guides_false_is_default() -> None:
    outside, inside = compose_brochure_svgs(
        FULL_BROCHURE, compute_panel_layout(), _FAKE_HERO_PNG
    )
    assert "fold-lines" not in outside
    assert "fold-lines" not in inside


def test_render_guides_true_includes_fold_lines() -> None:
    outside, inside = compose_brochure_svgs(
        FULL_BROCHURE, compute_panel_layout(), _FAKE_HERO_PNG, render_guides=True
    )
    assert 'id="fold-lines"' in outside
    assert 'id="fold-lines"' in inside


# ---------- Still well-formed XML under all templates ----------


def test_every_template_produces_well_formed_svg() -> None:
    import xml.etree.ElementTree as ET

    for template_name in ("editorial", "minimalist", "playful", "gallery_strip", "quote_driven", "spotlight"):
        template = get_template(template_name)
        outside, inside = _render_with(template=template)
        # Must parse without raising
        ET.fromstring(outside)
        ET.fromstring(inside)


# ---------- Template-driven typography differentiation ----------


def test_templates_produce_distinct_heading_font_families() -> None:
    """Each template's declared heading_font_family must reach the rendered SVG.

    Before this wiring, every template rendered with the same module-constant
    font. Test asserts that at least 3 distinct font-family declarations appear
    across the 6 templates (serif / sans / display).
    """
    families: set[str] = set()
    for template_name in ("editorial", "minimalist", "playful", "gallery_strip", "quote_driven", "spotlight"):
        template = get_template(template_name)
        outside, _ = _render_with(template=template)
        # Extract the cover title's font-family — first <text> in outside svg
        # is the cover title (title font from template).
        assert template.heading_font_family in outside, (
            f"{template_name}: declared heading_font_family "
            f"{template.heading_font_family!r} not found in rendered outside SVG"
        )
        families.add(template.heading_font_family)

    # Sanity: templates actually declare at least 3 distinct families
    assert len(families) >= 3


def test_v1_path_still_uses_arial_black_title_font() -> None:
    """Passing template=None preserves the v1 fallback fonts."""
    outside, _ = _render_with(template=None)
    assert "'Arial Black'" in outside


def test_template_body_font_reaches_inner_panels() -> None:
    """Body text on inner panels must use template.body_font_family."""
    template = get_template("editorial")
    _, inside = _render_with(template=template)
    # EDITORIAL's body is serif
    assert template.body_font_family in inside


def test_composer_injects_font_face_defs_when_fonts_present(
    tmp_path, monkeypatch
) -> None:
    """When assets/fonts/ has matching files, @font-face rules appear in SVG defs."""
    # Redirect the fonts module's _FONTS_DIR to a test directory with a stub font.
    (tmp_path / "Playfair_Display.woff2").write_bytes(b"stub-playfair")
    monkeypatch.setattr(
        "flyer_generator.brochure.stages.fonts._FONTS_DIR",
        tmp_path,
    )

    outside, inside = _render_with(template=get_template("editorial"))
    # Both sheets must carry the @font-face rule for the matched family
    assert "@font-face" in outside
    assert "font-family:'Playfair Display'" in outside
    assert "data:font/woff2;base64," in outside
    assert "@font-face" in inside


def test_composer_no_font_defs_when_fonts_missing(tmp_path, monkeypatch) -> None:
    """Empty fonts dir → no @font-face rules (graceful fallback to system fonts)."""
    monkeypatch.setattr(
        "flyer_generator.brochure.stages.fonts._FONTS_DIR",
        tmp_path,
    )
    outside, _ = _render_with(template=get_template("editorial"))
    assert "@font-face" not in outside
