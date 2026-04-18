"""Phase 16 quality tests: section distribution, heading accent rules, verify regen."""

from __future__ import annotations

import re

import pytest
from pydantic import SecretStr

from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    SectionSpec,
    SectionText,
)
from flyer_generator.brochure.generative.pipeline import _assemble_brochure_input
from flyer_generator.brochure.models import (
    BrochureInput,
    BrochureSection,
)
from flyer_generator.brochure.stages.composer import compose_brochure_svgs
from flyer_generator.brochure.stages.layout import compute_panel_layout
from flyer_generator.brochure.generative.models import BrochurePrompt


_FAKE_HERO = b"\x89PNG\r\n\x1a\nfake"


# ----------- Section distribution (1) -----------


def _outline_with(sections_spec: list[tuple[str, str, str | None]]) -> BrochureOutline:
    """Build an outline from (heading, panel_role, image_hint) triples."""
    sections = [
        SectionSpec(heading=h, body_brief=f"direction for {h}", image_hint=hint, panel_role=role)  # type: ignore[arg-type]
        for h, role, hint in sections_spec
    ]
    return BrochureOutline(
        sections=sections,
        tone="warm",
        cta_intent="visit us",
        suggested_preset="photorealistic",
        suggested_accent="#7BB661",
    )


def _texts_for(outline: BrochureOutline) -> list[SectionText]:
    return [SectionText(heading=s.heading, body=f"body for {s.heading}", image_hint=s.image_hint) for s in outline.sections]


def test_assembly_keeps_all_feature_and_detail_sections() -> None:
    """Before: features could be dropped. Now: every non-cover section stays visible."""
    outline = _outline_with(
        [
            ("Cover", "cover", None),
            ("Feature A", "feature", "image a"),
            ("Feature B", "feature", None),
            ("Detail C", "detail", None),
            ("Visit", "cta", None),
        ]
    )
    bi = _assemble_brochure_input(BrochurePrompt(prompt="x"), outline, _texts_for(outline))
    headings = [s.heading for s in bi.sections]
    # All 3 non-cover-non-cta sections preserved
    assert "Feature A" in headings
    assert "Feature B" in headings
    assert "Detail C" in headings
    # CTA section in back_panel, not in sections
    assert "Visit" not in headings
    assert bi.back_panel is not None


def test_assembly_sorts_features_before_details() -> None:
    """Features land first so image_hint-bearing sections get priority placement."""
    outline = _outline_with(
        [
            ("Cover", "cover", None),
            ("Detail C", "detail", None),
            ("Feature A", "feature", "hint"),
            ("Feature B", "feature", None),
        ]
    )
    bi = _assemble_brochure_input(BrochurePrompt(prompt="x"), outline, _texts_for(outline))
    headings = [s.heading for s in bi.sections]
    # Feature A (index 0) goes to tuck flap — it has the image_hint, good spot
    assert headings[0] == "Feature A"
    assert headings[1] == "Feature B"
    assert headings[2] == "Detail C"


def test_assembly_promotes_cta_when_content_sparse() -> None:
    """Only 1 feature + cta → cta becomes content, back_panel=None."""
    outline = _outline_with(
        [
            ("Cover", "cover", None),
            ("Feature A", "feature", None),
            ("Visit", "cta", None),
        ]
    )
    bi = _assemble_brochure_input(BrochurePrompt(prompt="x"), outline, _texts_for(outline))
    headings = [s.heading for s in bi.sections]
    assert len(bi.sections) >= 2
    assert "Visit" in headings  # promoted
    assert bi.back_panel is None


def test_assembly_pads_when_too_few_sections() -> None:
    """Worst case: only cover + 1 feature — pads with cta_intent as 'About' section."""
    outline = _outline_with(
        [
            ("Cover", "cover", None),
            ("OnlyFeature", "feature", None),
        ]
    )
    bi = _assemble_brochure_input(BrochurePrompt(prompt="x"), outline, _texts_for(outline))
    assert len(bi.sections) >= 2
    # The padding section uses "About" heading
    assert any(s.heading == "About" for s in bi.sections)


# ----------- Heading accent rules (2) -----------


def _brochure(n_sections: int = 4) -> BrochureInput:
    headings = ["Classes", "Pricing", "Schedule", "Enrollment"][:n_sections]
    return BrochureInput(
        title="Q",
        hero_concept="x",
        style_preset="photorealistic",
        color_accent="#2E8B57",
        org="Acme",
        sections=[BrochureSection(heading=h, body="body") for h in headings],
    )


def test_section_headings_have_accent_rule_beneath() -> None:
    """Every visible section heading should have a thin accent rect under it."""
    outside, inside = compose_brochure_svgs(_brochure(n_sections=4), compute_panel_layout(), _FAKE_HERO)
    # 4 sections: sections[0]→tuck flap, sections[1..3]→inner panels. Every visible heading gets an accent rule.
    combined = outside + inside
    accent_rects = re.findall(r'<rect[^>]*height="3"[^>]*fill="#2E8B57"', combined)
    # At least 4 section accent rules (1 tuck flap + 3 inner) + 1 back cover fallback = >=5
    assert len(accent_rects) >= 4, f"expected >=4 accent rules, got {len(accent_rects)}"


def test_back_panel_heading_also_has_accent_rule() -> None:
    """Back-cover heading (Visit Us / About) gets the same accent rule treatment."""
    from flyer_generator.brochure.models import BrochureBackPanel

    brochure = BrochureInput(
        title="Q",
        hero_concept="x",
        style_preset="photorealistic",
        color_accent="#2E8B57",
        org="Acme",
        sections=[
            BrochureSection(heading="S1", body="b"),
            BrochureSection(heading="S2", body="b"),
        ],
        back_panel=BrochureBackPanel(kind="cta", content="Book now"),
    )
    outside, _ = compose_brochure_svgs(brochure, compute_panel_layout(), _FAKE_HERO)
    # Back panel heading "Visit Us" should be followed by an accent rule (height=3, accent color)
    accent_rects = re.findall(r'<rect[^>]*height="3"[^>]*fill="#2E8B57"', outside)
    assert len(accent_rects) >= 1


# ----------- Cover title treatment (2 cont'd) -----------


def test_cover_title_uses_drop_shadow_filter_not_stroke() -> None:
    """The cover title should use an SVG filter for drop shadow (softer)."""
    outside, _ = compose_brochure_svgs(_brochure(), compute_panel_layout(), _FAKE_HERO)
    assert "<filter" in outside  # filter defined
    assert "feGaussianBlur" in outside
    # Title text uses filter reference (not hard stroke)
    title_block = re.search(r'<text[^>]*>Q</text>', outside)
    assert title_block is not None
    assert 'filter="url(#' in title_block.group(0)


# ----------- Verify regen seed variation (3) -----------


def test_repeated_compose_with_same_title_is_deterministic() -> None:
    """Sanity: same input produces same output (so iteration 1 is stable)."""
    brochure = _brochure()
    layout = compute_panel_layout()
    a, _ = compose_brochure_svgs(brochure, layout, _FAKE_HERO)
    b, _ = compose_brochure_svgs(brochure, layout, _FAKE_HERO)
    assert a == b


def test_title_mutation_shifts_shape_positions() -> None:
    """The verify-regen trick uses a title nudge to force different shape seeds."""
    from flyer_generator.brochure.templates import PLAYFUL

    base = _brochure()
    nudged = base.model_copy(update={"title": base.title + "\u200b"})
    layout = compute_panel_layout()
    _, inside_a = compose_brochure_svgs(base, layout, _FAKE_HERO, template=PLAYFUL)
    _, inside_b = compose_brochure_svgs(nudged, layout, _FAKE_HERO, template=PLAYFUL)
    # Shapes should differ somewhere (e.g. rotated_block jitter position x)
    assert inside_a != inside_b
