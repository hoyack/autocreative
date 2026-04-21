"""Contrast module: ratio math, AA/AAA classification, remediation strategies,
and ContrastPair/ContrastReport round-trip.

Per checker B1: DIRECT-MODULE imports only
(`from flyer_generator.brand_kit.contrast import ...`) so this plan never
touches the package-root `__init__.py`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flyer_generator.brand_kit.contrast import (
    ContrastPair,
    ContrastReport,
    _hex_to_floats,
    classify_level,
    ensure_aa,
    passes_aa,
    passes_aaa,
    remediate,
    wcag_ratio,
)


# ---- _hex_to_floats -----------------------------------------------------


def test_hex_to_floats_black() -> None:
    assert _hex_to_floats("#000000") == (0.0, 0.0, 0.0)


def test_hex_to_floats_white() -> None:
    assert _hex_to_floats("#FFFFFF") == (1.0, 1.0, 1.0)


def test_hex_to_floats_accepts_lowercase() -> None:
    a = _hex_to_floats("#1e3a5f")
    b = _hex_to_floats("#1E3A5F")
    assert a == b


def test_hex_to_floats_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        _hex_to_floats("not-a-color")


# ---- wcag_ratio known pairs ---------------------------------------------


def test_black_on_white_is_21() -> None:
    assert abs(wcag_ratio("#000000", "#FFFFFF") - 21.0) < 1e-6


def test_white_on_black_is_21_symmetric() -> None:
    assert abs(wcag_ratio("#FFFFFF", "#000000") - 21.0) < 1e-6


def test_same_color_is_1() -> None:
    assert wcag_ratio("#808080", "#808080") == 1.0


def test_dark_blue_on_white_is_high() -> None:
    # #1E3A5F on white should be ~11.50 (verified empirically via wcag-contrast-ratio 0.9)
    r = wcag_ratio("#1E3A5F", "#FFFFFF")
    assert r > 10.0


# ---- AA / AAA classification --------------------------------------------


def test_passes_aa_body() -> None:
    assert passes_aa("#1E3A5F", "#FFFFFF") is True
    assert passes_aa("#CCCCCC", "#FFFFFF") is False


def test_passes_aa_large_text_lower_bar() -> None:
    # Ratio ~3.03 for #949494 on white -- fails body (4.5) but passes large (3.0)
    assert passes_aa("#949494", "#FFFFFF") is False
    assert passes_aa("#949494", "#FFFFFF", large_text=True) is True


def test_passes_aaa() -> None:
    # Black on white passes AAA (ratio 21.0)
    assert passes_aaa("#000000", "#FFFFFF") is True
    # #666666 on white: ratio ~5.74 -- passes AA but fails AAA (7.0 body threshold).
    # (Plan's draft used #555555 which empirically scores ~7.46 and would pass AAA;
    # corrected to #666666 per Rule 1 auto-fix.)
    assert passes_aaa("#666666", "#FFFFFF") is False


def test_classify_level_extremes() -> None:
    assert classify_level("#000000", "#FFFFFF") == "AAA"
    assert classify_level("#CCCCCC", "#FFFFFF") == "FAIL"


def test_classify_level_midrange_is_aa_not_aaa() -> None:
    # #737373 on white ratio ~4.74 -- between 4.5 (AA) and 7.0 (AAA).
    assert classify_level("#737373", "#FFFFFF") == "AA"


# ---- Remediation --------------------------------------------------------


def test_remediate_already_passing_returns_unchanged() -> None:
    fg, note = remediate("#1E3A5F", "#FFFFFF", neutrals=("#111111", "#F7F7F5"))
    assert fg == "#1E3A5F"
    assert note == "pass"


def test_remediate_swaps_to_opposite_neutral_for_dark_bg() -> None:
    # Medium-gray fg on dark bg fails AA (ratio ~2.53), remediate should swap
    # to the light neutral.
    # (Plan's draft used #808080 which actually passes on #111111 (ratio ~4.78);
    # corrected to #555555 per Rule 1 auto-fix so remediation actually fires.)
    fg, note = remediate("#555555", "#111111", neutrals=("#111111", "#F7F7F5"))
    assert passes_aa(fg, "#111111") is True
    assert "neutral_light" in note or "OKLCH" in note


def test_remediate_swaps_to_opposite_neutral_for_light_bg() -> None:
    fg, note = remediate("#AAAAAA", "#FAFAF7", neutrals=("#111111", "#F7F7F5"))
    assert passes_aa(fg, "#FAFAF7") is True


def test_remediate_returns_fail_note_when_no_solution() -> None:
    # Pathological case: bg is mid-gray; neutrals near mid-gray can't pass.
    fg, note = remediate(
        "#7F7F7F",
        "#808080",
        neutrals=("#777777", "#888888"),
    )
    # Either the OKLCH search found a passing value OR returned FAIL -- both
    # acceptable. Hard assert: if FAIL, returned fg is the original.
    if note.startswith("FAIL"):
        assert fg == "#7F7F7F"
    else:
        # OKLCH must have actually passed AA
        assert passes_aa(fg, "#808080") is True


# ---- ensure_aa wrapper --------------------------------------------------


def test_ensure_aa_returns_none_note_on_pass() -> None:
    fg, note = ensure_aa("#1E3A5F", "#FFFFFF", palette_neutrals=("#111111", "#F7F7F5"))
    assert fg == "#1E3A5F"
    assert note is None


def test_ensure_aa_returns_note_on_remediation() -> None:
    fg, note = ensure_aa(
        "#AAAAAA", "#FAFAF7", palette_neutrals=("#111111", "#F7F7F5")
    )
    assert passes_aa(fg, "#FAFAF7") is True
    assert note is not None


# ---- ContrastPair / ContrastReport -------------------------------------


def test_contrast_pair_valid() -> None:
    p = ContrastPair(fg="#000000", bg="#FFFFFF", ratio=21.0, level="AAA")
    assert p.level == "AAA"


def test_contrast_pair_hex_normalized() -> None:
    p = ContrastPair(fg="#1e3a5f", bg="#ffffff", ratio=11.2, level="AAA")
    assert p.fg == "#1E3A5F"
    assert p.bg == "#FFFFFF"


def test_contrast_pair_rejects_invalid_hex() -> None:
    with pytest.raises(ValidationError):
        ContrastPair(fg="#000", bg="#FFFFFF", ratio=10.0, level="AA")


def test_contrast_pair_ratio_bounds() -> None:
    # Below 1.0 or above 21.0 -> ValidationError
    with pytest.raises(ValidationError):
        ContrastPair(fg="#000000", bg="#FFFFFF", ratio=0.5, level="FAIL")
    with pytest.raises(ValidationError):
        ContrastPair(fg="#000000", bg="#FFFFFF", ratio=22.0, level="AAA")


def test_contrast_report_overall_pass_all_aa() -> None:
    rep = ContrastReport(
        pairs=[
            ContrastPair(fg="#000000", bg="#FFFFFF", ratio=21.0, level="AAA"),
            ContrastPair(fg="#1E3A5F", bg="#FFFFFF", ratio=11.5, level="AAA"),
        ]
    )
    assert rep.overall_aa_pass is True
    assert rep.fails() == []


def test_contrast_report_overall_fail_on_any_fail() -> None:
    rep = ContrastReport(
        pairs=[
            ContrastPair(fg="#000000", bg="#FFFFFF", ratio=21.0, level="AAA"),
            ContrastPair(fg="#CCCCCC", bg="#FFFFFF", ratio=1.6, level="FAIL"),
        ]
    )
    assert rep.overall_aa_pass is False
    assert len(rep.fails()) == 1


def test_contrast_report_roundtrip() -> None:
    rep = ContrastReport(
        pairs=[
            ContrastPair(
                fg="#000000",
                bg="#FFFFFF",
                ratio=21.0,
                level="AAA",
                panel="front_cover",
                content_key="title",
            )
        ]
    )
    loaded = ContrastReport.model_validate_json(rep.model_dump_json())
    assert loaded.model_dump() == rep.model_dump()
