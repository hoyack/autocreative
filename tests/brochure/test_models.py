"""Tests for flyer_generator.brochure.models — validation + BrochureOutput.save()."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from flyer_generator.brochure.models import (
    BrochureBackPanel,
    BrochureInput,
    BrochureOutput,
    BrochureSection,
    ContactBlock,
    validate_hex_color,
)
from tests.brochure.fixtures.sample_brochures import FULL_BROCHURE, MINIMAL_BROCHURE


# ---------- validate_hex_color ----------


@pytest.mark.parametrize("value", ["#F59E0B", "#000000", "#ffffff", "#aAbBcC"])
def test_validate_hex_color_accepts_valid(value: str) -> None:
    assert validate_hex_color(value) == value


@pytest.mark.parametrize("value", ["red", "#ABC", "#GGGGGG", "F59E0B", "#F59E0", ""])
def test_validate_hex_color_rejects_invalid(value: str) -> None:
    with pytest.raises(ValueError, match="color_accent"):
        validate_hex_color(value)


# ---------- BrochureInput ----------


def test_brochure_input_minimal_roundtrips() -> None:
    dumped = MINIMAL_BROCHURE.model_dump()
    rebuilt = BrochureInput(**dumped)
    assert rebuilt == MINIMAL_BROCHURE


def test_brochure_input_full_roundtrips() -> None:
    dumped = FULL_BROCHURE.model_dump()
    rebuilt = BrochureInput(**dumped)
    assert rebuilt == FULL_BROCHURE


def test_brochure_input_rejects_invalid_accent() -> None:
    with pytest.raises(ValidationError, match="color_accent"):
        BrochureInput(
            title="x",
            hero_concept="x",
            style_preset="photorealistic",
            color_accent="not-a-color",
            org="x",
            sections=[
                BrochureSection(heading="a", body="b"),
                BrochureSection(heading="c", body="d"),
            ],
        )


def test_brochure_input_rejects_too_few_sections() -> None:
    with pytest.raises(ValidationError, match="at least 2 items|min_length"):
        BrochureInput(
            title="x",
            hero_concept="x",
            style_preset="photorealistic",
            org="x",
            sections=[BrochureSection(heading="only one", body="body")],
        )


def test_brochure_input_rejects_too_many_sections() -> None:
    sections = [BrochureSection(heading=f"h{i}", body=f"b{i}") for i in range(6)]
    with pytest.raises(ValidationError, match="at most 5 items|max_length"):
        BrochureInput(
            title="x",
            hero_concept="x",
            style_preset="photorealistic",
            org="x",
            sections=sections,
        )


@pytest.mark.parametrize("count", [2, 3, 4, 5])
def test_brochure_input_accepts_section_counts_in_bounds(count: int) -> None:
    sections = [BrochureSection(heading=f"h{i}", body=f"b{i}") for i in range(count)]
    bi = BrochureInput(
        title="x",
        hero_concept="x",
        style_preset="photorealistic",
        org="x",
        sections=sections,
    )
    assert len(bi.sections) == count


def test_brochure_input_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden|extra fields"):
        BrochureInput(
            title="x",
            hero_concept="x",
            style_preset="photorealistic",
            org="x",
            sections=[
                BrochureSection(heading="a", body="b"),
                BrochureSection(heading="c", body="d"),
            ],
            unexpected_field="boom",
        )


# ---------- BrochureBackPanel ----------


@pytest.mark.parametrize("kind", ["cta", "bio", "map_stub", "contact"])
def test_brochure_back_panel_accepts_all_literal_kinds(kind: str) -> None:
    panel = BrochureBackPanel(kind=kind, content="x")
    assert panel.kind == kind


def test_brochure_back_panel_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError, match="literal_error|Input should be"):
        BrochureBackPanel(kind="not-a-kind", content="x")


# ---------- ContactBlock ----------


def test_contact_block_all_fields_default_none() -> None:
    cb = ContactBlock()
    assert cb.name is None
    assert cb.phone is None
    assert cb.email is None
    assert cb.url is None
    assert cb.address is None


# ---------- BrochureOutput.save() ----------


def test_brochure_output_save_writes_three_files(tmp_path: Path) -> None:
    out = BrochureOutput(
        front_png_bytes=b"\x89PNG-front",
        back_png_bytes=b"\x89PNG-back",
        pdf_bytes=b"%PDF-1.4\nfake",
        attempts_used=1,
        trace_id="trace-abc",
    )

    target = tmp_path / "brochures"
    out.save(target)

    assert (target / "brochure_front.png").read_bytes() == b"\x89PNG-front"
    assert (target / "brochure_back.png").read_bytes() == b"\x89PNG-back"
    assert (target / "brochure_print.pdf").read_bytes() == b"%PDF-1.4\nfake"


def test_brochure_output_defaults_are_importable() -> None:
    out = BrochureOutput()
    assert out.dimensions == (3300, 2550)
    assert out.front_png_bytes == b""
