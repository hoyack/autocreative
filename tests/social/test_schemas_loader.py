"""RED tests for Task 1: schema_model + loader primitives.

Per checker B1: direct-module imports only.

These tests exercise the loader/schema-model API *before* any JSON templates
exist. They assert:
  * PostTemplate, ImageSlot, TextSlot classes exist with documented fields.
  * load_post_template raises FileNotFoundError with "Available:" listing.
  * list_post_templates returns a sorted list (empty when no JSON present).
  * parse_template_name splits ``<platform>__<intent>`` and enforces the
    Platform / Intent membership via the typed errors in flyer_generator.errors.
"""

from __future__ import annotations

import pytest

from flyer_generator.errors import (
    IntentUnsupportedError,
    PlatformUnsupportedError,
)
from flyer_generator.social.schemas.loader import (
    list_post_templates,
    load_post_template,
    parse_template_name,
)
from flyer_generator.social.schemas.schema_model import (
    ImageSlot,
    PostTemplate,
    TextSlot,
)


# -------------------------------------------------------------- parse_template_name


def test_parse_template_name_happy() -> None:
    assert parse_template_name("linkedin__value-prop") == ("linkedin", "value-prop")
    assert parse_template_name("twitter__announcement") == ("twitter", "announcement")
    assert parse_template_name("instagram__testimonial") == (
        "instagram",
        "testimonial",
    )
    assert parse_template_name("facebook__announcement") == (
        "facebook",
        "announcement",
    )


def test_parse_template_name_missing_separator_raises_valueerror() -> None:
    with pytest.raises(ValueError):
        parse_template_name("linkedin-value-prop")


def test_parse_template_name_unknown_platform_raises_typed_error() -> None:
    with pytest.raises(PlatformUnsupportedError):
        parse_template_name("myspace__value-prop")


def test_parse_template_name_unknown_intent_raises_typed_error() -> None:
    with pytest.raises(IntentUnsupportedError):
        parse_template_name("linkedin__unknown")


# --------------------------------------------------------------- load_post_template


def test_load_post_template_missing_file_lists_available() -> None:
    with pytest.raises(FileNotFoundError) as exc:
        load_post_template("does__not-exist")
    assert "Available:" in str(exc.value)


# -------------------------------------------------------------- list_post_templates


def test_list_post_templates_returns_sorted_list() -> None:
    names = list_post_templates()
    assert names == sorted(names)


# --------------------------------------------------------- schema_model class shape


def test_post_template_allows_null_palette_and_typography() -> None:
    # Brand-kit injection happens at render time, so ship with None.
    t = PostTemplate(
        schema_version="1",
        name="linkedin__value-prop",
        platform="linkedin",
        intent="value-prop",
        description="tiny fixture",
        canvas={"width": 1200, "height": 627},
    )
    assert t.palette is None
    assert t.typography is None
    assert t.image_slot is None
    assert t.shapes == []
    assert t.text_slots == []
    assert t.logo_slot is None


def test_image_slot_aspect_literal_enforced() -> None:
    slot = ImageSlot(bbox=(0, 0, 1200, 627), aspect="1.91:1")
    assert slot.slot_name == "hero"
    with pytest.raises(Exception):
        ImageSlot(bbox=(0, 0, 1200, 627), aspect="nonsense")  # type: ignore[arg-type]


def test_text_slot_role_literal_enforced() -> None:
    slot = TextSlot(
        bbox=(0, 0, 100, 50),
        role="title",
        content_key="copy.title",
        max_chars=80,
        color_role="neutral_light",
        font_role="heading",
        font_size=64,
    )
    assert slot.font_weight == "normal"
    with pytest.raises(Exception):
        TextSlot(
            bbox=(0, 0, 100, 50),
            role="not_a_role",  # type: ignore[arg-type]
            content_key="copy.title",
            max_chars=80,
            color_role="neutral_light",
            font_role="heading",
            font_size=64,
        )


def test_post_template_forbids_extra_fields() -> None:
    with pytest.raises(Exception):
        PostTemplate(
            schema_version="1",
            name="linkedin__value-prop",
            platform="linkedin",
            intent="value-prop",
            description="",
            canvas={"width": 1200, "height": 627},
            unexpected_key="no",  # type: ignore[call-arg]
        )
