"""Tests for flyer_generator.brochure.stages.fonts — font-face SVG defs builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from flyer_generator.brochure.stages.fonts import (
    _family_to_filename,
    _primary_family_name,
    build_font_face_defs,
    load_font_as_data_uri,
)
from flyer_generator.brochure.templates import EDITORIAL, get_template


def test_primary_family_name_strips_quotes_and_picks_first() -> None:
    assert _primary_family_name("'Playfair Display', 'Times New Roman', serif") == "Playfair Display"
    assert _primary_family_name("Inter, sans-serif") == "Inter"
    assert _primary_family_name("Arial") == "Arial"


def test_family_to_filename_replaces_spaces() -> None:
    assert _family_to_filename("Playfair Display") == "Playfair_Display"
    assert _family_to_filename("Inter") == "Inter"


def test_load_font_as_data_uri_encodes_bytes(tmp_path: Path) -> None:
    font_path = tmp_path / "fake.woff2"
    font_path.write_bytes(b"\x77\x4F\x46\x32woff2-stub")  # 'wOF2' magic + suffix
    uri = load_font_as_data_uri(font_path)
    assert uri.startswith("data:font/woff2;base64,")
    import base64

    decoded = base64.b64decode(uri.split(",", 1)[1])
    assert decoded == b"\x77\x4F\x46\x32woff2-stub"


def test_build_font_face_defs_empty_when_dir_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    out = build_font_face_defs(EDITORIAL, font_dir=missing)
    assert out == ""


def test_build_font_face_defs_empty_when_no_matching_files(tmp_path: Path) -> None:
    (tmp_path / "Unrelated.woff2").write_bytes(b"stub")
    out = build_font_face_defs(EDITORIAL, font_dir=tmp_path)
    assert out == ""


def test_build_font_face_defs_inlines_matching_font(tmp_path: Path) -> None:
    # EDITORIAL declares Playfair Display + Source Serif Pro as primary families
    (tmp_path / "Playfair_Display.woff2").write_bytes(b"playfair-bytes")
    out = build_font_face_defs(EDITORIAL, font_dir=tmp_path)
    assert out.startswith("<defs><style>")
    assert "@font-face" in out
    assert "font-family:'Playfair Display'" in out
    assert "data:font/woff2;base64," in out
    # Source Serif Pro wasn't present → no rule for it
    assert "font-family:'Source Serif Pro'" not in out


def test_build_font_face_defs_handles_all_declared_families(tmp_path: Path) -> None:
    """When both heading + body families have files, both rules appear."""
    (tmp_path / "Playfair_Display.woff2").write_bytes(b"heading")
    (tmp_path / "Source_Serif_Pro.woff2").write_bytes(b"body")
    out = build_font_face_defs(EDITORIAL, font_dir=tmp_path)
    assert out.count("@font-face") == 2
    assert "font-family:'Playfair Display'" in out
    assert "font-family:'Source Serif Pro'" in out


def test_build_font_face_defs_all_templates_safe_with_empty_dir(tmp_path: Path) -> None:
    """All six templates must return valid (empty-string or well-formed) defs."""
    for name in ("editorial", "minimalist", "playful", "gallery_strip", "quote_driven", "spotlight"):
        template = get_template(name)
        out = build_font_face_defs(template, font_dir=tmp_path)
        # Empty dir → empty result; no crashes
        assert out == ""
