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


# ---------- Tuck-flap tagline (N<4 sections) ----------


def test_tuck_flap_renders_tagline_when_fewer_than_four_sections() -> None:
    """N=3 (or 2) brochures must render org name + tagline on tuck flap."""
    from flyer_generator.brochure.models import BrochureInput, BrochureSection

    brochure_n3 = BrochureInput(
        title="Three Section Brochure",
        hero_concept="abstract background",
        style_preset="photorealistic",
        color_accent="#2E8B57",
        org="Evergreen Studio",
        sections=[
            BrochureSection(heading=f"Section {i}", body=f"Body for section {i}.")
            for i in range(3)
        ],
    )
    layout = compute_panel_layout()
    outside, _ = compose_brochure_svgs(
        brochure_n3, layout, _FAKE_HERO_PNG, template=get_template("editorial")
    )
    # Tuck flap tagline uses uppercase org — the org name must appear upper-cased
    assert "EVERGREEN STUDIO" in outside


def test_tuck_flap_tagline_skipped_when_section_assigned() -> None:
    """N>=4 brochures use the tuck flap for sections[3] — no tagline duplication."""
    outside, _ = _render_with(template=get_template("editorial"))
    # FULL_BROCHURE has 5 sections; tuck flap gets sections[3] ("Evenings").
    # Org-upper shouldn't appear as the tuck-flap tagline.
    assert "DEV COLLECTIVE" not in outside


def test_tuck_flap_no_tagline_when_org_empty(tmp_path) -> None:
    """Empty org string → tagline helper returns empty; no crash."""
    from flyer_generator.brochure.models import BrochureInput, BrochureSection

    brochure = BrochureInput(
        title="No Org",
        hero_concept="c",
        style_preset="photorealistic",
        color_accent="#2E8B57",
        org="",  # empty
        sections=[
            BrochureSection(heading=f"S{i}", body=f"b{i}") for i in range(3)
        ],
    )
    layout = compute_panel_layout()
    outside, _ = compose_brochure_svgs(
        brochure, layout, _FAKE_HERO_PNG, template=get_template("editorial")
    )
    # No crash; no upper-cased tagline injected either
    import xml.etree.ElementTree as ET

    ET.fromstring(outside)  # still well-formed


# ---------- Aspect-aware spot image cropping ----------


def _png_of_size(w: int, h: int) -> bytes:
    """Helper: return a tiny valid PNG of the given dimensions."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (128, 128, 128)).save(buf, "PNG")
    return buf.getvalue()


def test_spot_image_landscape_uses_center_crop() -> None:
    from flyer_generator.brochure.models import (
        BrochureInput,
        BrochureSection,
    )

    landscape = _png_of_size(400, 200)
    brochure = BrochureInput(
        title="Landscape Test",
        hero_concept="c",
        style_preset="photorealistic",
        color_accent="#2E8B57",
        org="Org",
        sections=[
            BrochureSection(heading="Keynotes", body="body text"),
            BrochureSection(heading="Workshops", body="body text"),
        ],
    )
    layout = compute_panel_layout()
    _, inside = compose_brochure_svgs(
        brochure,
        layout,
        _FAKE_HERO_PNG,
        template=get_template("editorial"),
        spot_images={"Keynotes": landscape},
    )
    # Landscape image → xMidYMid slice (center)
    assert 'preserveAspectRatio="xMidYMid slice"' in inside


def test_spot_image_portrait_uses_top_crop() -> None:
    from flyer_generator.brochure.models import (
        BrochureInput,
        BrochureSection,
    )

    portrait = _png_of_size(200, 400)  # h/w = 2.0 → portrait
    brochure = BrochureInput(
        title="Portrait Test",
        hero_concept="c",
        style_preset="photorealistic",
        color_accent="#2E8B57",
        org="Org",
        sections=[
            BrochureSection(heading="Tall One", body="body text"),
            BrochureSection(heading="Other", body="body text"),
        ],
    )
    layout = compute_panel_layout()
    _, inside = compose_brochure_svgs(
        brochure,
        layout,
        _FAKE_HERO_PNG,
        template=get_template("editorial"),
        spot_images={"Tall One": portrait},
    )
    # Portrait → xMidYMin slice (top-aligned crop)
    assert 'preserveAspectRatio="xMidYMin slice"' in inside


def test_spot_image_unparseable_bytes_fall_back_to_center_crop() -> None:
    """Garbage bytes must not crash — default center crop."""
    from flyer_generator.brochure.models import (
        BrochureInput,
        BrochureSection,
    )

    brochure = BrochureInput(
        title="Garbage",
        hero_concept="c",
        style_preset="photorealistic",
        color_accent="#2E8B57",
        org="Org",
        sections=[
            BrochureSection(heading="S0", body="b"),
            BrochureSection(heading="S1", body="b"),
        ],
    )
    layout = compute_panel_layout()
    _, inside = compose_brochure_svgs(
        brochure,
        layout,
        _FAKE_HERO_PNG,
        template=get_template("editorial"),
        spot_images={"S0": b"not-an-image"},
    )
    # Default fallback preserves center crop
    assert 'preserveAspectRatio="xMidYMid slice"' in inside
