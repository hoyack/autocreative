"""Phase 24-03 Task 1: PosterCreateRequest + PosterSize schema tests.

Covers PO-01 (request schema). Mirrors the postcard schema test pattern with
the size Literal enum + flyer-like fields per CONTEXT decisions.

Locked size values: "18x24", "24x36", "27x40" (exactly 3 — see threat T-24-07).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flyer_generator.api.schemas import PosterCreateRequest, PosterSize


# ---------------------------------------------------------------------------
# PosterCreateRequest — minimal + full payloads
# ---------------------------------------------------------------------------


def test_minimal_valid_payload() -> None:
    """Only required fields supplied: headline, style_preset, template, size."""
    req = PosterCreateRequest(
        headline="Grand Opening",
        style_preset="photorealistic",
        template="editorial_grand",
        size="18x24",
    )
    assert req.headline == "Grand Opening"
    assert req.style_preset == "photorealistic"
    assert req.template == "editorial_grand"
    assert req.size == "18x24"
    # Optional fields default to None
    assert req.subheading is None
    assert req.cta_text is None
    assert req.image_hint is None
    assert req.brand_kit_slug is None


def test_full_payload_with_all_optionals() -> None:
    """Every field populated."""
    req = PosterCreateRequest(
        headline="Headline",
        subheading="A compelling subheading",
        cta_text="Buy tickets",
        image_hint="cinematic vista at dusk",
        brand_kit_slug="acme-co",
        style_preset="anime",
        template="bold_announcement",
        size="24x36",
    )
    assert req.headline == "Headline"
    assert req.subheading == "A compelling subheading"
    assert req.cta_text == "Buy tickets"
    assert req.image_hint == "cinematic vista at dusk"
    assert req.brand_kit_slug == "acme-co"
    assert req.style_preset == "anime"
    assert req.template == "bold_announcement"
    assert req.size == "24x36"


# ---------------------------------------------------------------------------
# size — exactly 3 Literal values accepted, all others rejected (T-24-07)
# ---------------------------------------------------------------------------


def test_size_accepted_18x24() -> None:
    req = PosterCreateRequest(
        headline="x",
        style_preset="p",
        template="t",
        size="18x24",
    )
    assert req.size == "18x24"


def test_size_accepted_24x36() -> None:
    req = PosterCreateRequest(
        headline="x",
        style_preset="p",
        template="t",
        size="24x36",
    )
    assert req.size == "24x36"


def test_size_accepted_27x40() -> None:
    req = PosterCreateRequest(
        headline="x",
        style_preset="p",
        template="t",
        size="27x40",
    )
    assert req.size == "27x40"


def test_size_rejected_36x48() -> None:
    """36x48 is NOT in the locked enum (deferred to a future ANSI/ISO expansion)."""
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            style_preset="p",
            template="t",
            size="36x48",  # type: ignore[arg-type]
        )


def test_size_rejected_invalid_format_18_x_24() -> None:
    """Whitespace variants must be rejected — the enum is byte-exact."""
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            style_preset="p",
            template="t",
            size="18 x 24",  # type: ignore[arg-type]
        )


def test_size_rejected_empty_string() -> None:
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            style_preset="p",
            template="t",
            size="",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# extra="forbid" — unknown keys rejected (T-24-06)
# ---------------------------------------------------------------------------


def test_extra_forbid_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            style_preset="p",
            template="t",
            size="18x24",
            unknown_field="boom",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# headline — min_length=1, max_length=120
# ---------------------------------------------------------------------------


def test_headline_min_length_1() -> None:
    """Empty headline rejected."""
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="",
            style_preset="p",
            template="t",
            size="18x24",
        )


def test_headline_max_length_120_boundary() -> None:
    """120-char headline OK; 121-char rejected."""
    req = PosterCreateRequest(
        headline="x" * 120,
        style_preset="p",
        template="t",
        size="18x24",
    )
    assert len(req.headline) == 120
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x" * 121,
            style_preset="p",
            template="t",
            size="18x24",
        )


# ---------------------------------------------------------------------------
# subheading — optional, max_length=200
# ---------------------------------------------------------------------------


def test_subheading_max_length_200() -> None:
    """200-char subheading OK; 201-char rejected."""
    req = PosterCreateRequest(
        headline="x",
        subheading="x" * 200,
        style_preset="p",
        template="t",
        size="18x24",
    )
    assert req.subheading is not None
    assert len(req.subheading) == 200
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            subheading="x" * 201,
            style_preset="p",
            template="t",
            size="18x24",
        )


# ---------------------------------------------------------------------------
# cta_text — optional, max_length=120
# ---------------------------------------------------------------------------


def test_cta_text_max_length_120() -> None:
    req = PosterCreateRequest(
        headline="x",
        cta_text="x" * 120,
        style_preset="p",
        template="t",
        size="18x24",
    )
    assert req.cta_text is not None
    assert len(req.cta_text) == 120
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            cta_text="x" * 121,
            style_preset="p",
            template="t",
            size="18x24",
        )


# ---------------------------------------------------------------------------
# image_hint — optional, max_length=500
# ---------------------------------------------------------------------------


def test_image_hint_max_length_500() -> None:
    req = PosterCreateRequest(
        headline="x",
        image_hint="x" * 500,
        style_preset="p",
        template="t",
        size="18x24",
    )
    assert req.image_hint is not None
    assert len(req.image_hint) == 500
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            image_hint="x" * 501,
            style_preset="p",
            template="t",
            size="18x24",
        )


# ---------------------------------------------------------------------------
# style_preset / template — required + max_length=64
# ---------------------------------------------------------------------------


def test_style_preset_required_and_max_length_64() -> None:
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            style_preset="",
            template="t",
            size="18x24",
        )
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            style_preset="x" * 65,
            template="t",
            size="18x24",
        )


def test_template_required_and_max_length_64() -> None:
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            style_preset="p",
            template="",
            size="18x24",
        )
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            style_preset="p",
            template="x" * 65,
            size="18x24",
        )


# ---------------------------------------------------------------------------
# brand_kit_slug — regex ^[a-z0-9][a-z0-9-]*$ (T-24-09)
# ---------------------------------------------------------------------------


def test_brand_kit_slug_regex_rejects_uppercase() -> None:
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            brand_kit_slug="Foo",
            style_preset="p",
            template="t",
            size="18x24",
        )


def test_brand_kit_slug_regex_rejects_special_chars() -> None:
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            brand_kit_slug="not_valid!",
            style_preset="p",
            template="t",
            size="18x24",
        )


def test_brand_kit_slug_regex_accepts_dashes() -> None:
    req = PosterCreateRequest(
        headline="x",
        brand_kit_slug="acme-co",
        style_preset="p",
        template="t",
        size="18x24",
    )
    assert req.brand_kit_slug == "acme-co"


def test_brand_kit_slug_regex_accepts_lowercase_alnum() -> None:
    req = PosterCreateRequest(
        headline="x",
        brand_kit_slug="shrubnet",
        style_preset="p",
        template="t",
        size="18x24",
    )
    assert req.brand_kit_slug == "shrubnet"


def test_brand_kit_slug_max_length_64() -> None:
    req = PosterCreateRequest(
        headline="x",
        brand_kit_slug="a" * 64,
        style_preset="p",
        template="t",
        size="18x24",
    )
    assert req.brand_kit_slug is not None
    assert len(req.brand_kit_slug) == 64
    with pytest.raises(ValidationError):
        PosterCreateRequest(
            headline="x",
            brand_kit_slug="a" * 65,
            style_preset="p",
            template="t",
            size="18x24",
        )


# ---------------------------------------------------------------------------
# Barrel re-export
# ---------------------------------------------------------------------------


def test_barrel_export_round_trip() -> None:
    """`from flyer_generator.api.schemas import PosterCreateRequest, PosterSize` succeeds."""
    from flyer_generator.api.schemas import (  # noqa: F401
        PosterCreateRequest as _PCR,
        PosterSize as _PS,
    )
    assert _PCR is PosterCreateRequest
    # PosterSize is a typing.Literal alias — identity check via name
    assert _PS is PosterSize
