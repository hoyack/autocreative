"""BrochureContent tests + BrochureInput adapter tests."""

from __future__ import annotations

import pytest

from flyer_generator.brochure.models import (
    BrochureBackPanel,
    BrochureInput,
    BrochureSection,
    ContactBlock,
)
from flyer_generator.brochure.schema_renderer.content_model import (
    BackPanelContent,
    BrochureContent,
    ContentSection,
)


def test_minimal_content_requires_title_and_sections():
    c = BrochureContent(
        title="Hi",
        org="Test Co",
        sections=[ContentSection(heading="H")],
    )
    assert c.title == "Hi"


def test_resolve_key_top_level():
    c = BrochureContent(
        title="T", org="O", sections=[ContentSection(heading="H")]
    )
    assert c.resolve_key("title") == "T"
    assert c.resolve_key("org") == "O"
    assert c.resolve_key("tagline") is None


def test_resolve_key_sections_indexed():
    c = BrochureContent(
        title="T",
        org="O",
        sections=[
            ContentSection(heading="A", bullets=["one", "two"]),
            ContentSection(heading="B", lead_paragraph="Lead text"),
        ],
    )
    assert c.resolve_key("sections[0].heading") == "A"
    assert c.resolve_key("sections[0].bullets") == ["one", "two"]
    assert c.resolve_key("sections[1].lead_paragraph") == "Lead text"


def test_resolve_key_missing_section_returns_none():
    c = BrochureContent(title="T", org="O", sections=[ContentSection(heading="H")])
    assert c.resolve_key("sections[5].heading") is None


def test_resolve_key_contact():
    c = BrochureContent(
        title="T",
        org="O",
        sections=[ContentSection(heading="H")],
        contact=ContactBlock(phone="555", email="a@b"),
    )
    assert c.resolve_key("contact.phone") == "555"
    assert c.resolve_key("contact.email") == "a@b"
    assert c.resolve_key("contact.address") is None


def test_resolve_key_back_panel():
    c = BrochureContent(
        title="T",
        org="O",
        sections=[ContentSection(heading="H")],
        back_panel=BackPanelContent(
            heading="Act", body="Body text", bullets=["a", "b"]
        ),
    )
    assert c.resolve_key("back_panel.heading") == "Act"
    assert c.resolve_key("back_panel.bullets") == ["a", "b"]


def test_resolve_key_extras():
    c = BrochureContent(
        title="T",
        org="O",
        sections=[ContentSection(heading="H")],
        extras={"promo": "SPRING25"},
    )
    assert c.resolve_key("extras.promo") == "SPRING25"


def test_resolve_key_section_shorthand():
    c = BrochureContent(
        title="T",
        org="O",
        sections=[ContentSection(heading="A"), ContentSection(heading="B")],
    )
    assert c.resolve_key("section.heading", section_index=0) == "A"
    assert c.resolve_key("section.heading", section_index=1) == "B"


class TestBrochureInputAdapter:
    def test_plain_body_becomes_lead_paragraph(self):
        b = BrochureInput(
            title="T",
            hero_concept="hc",
            style_preset="photorealistic",
            org="O",
            sections=[
                BrochureSection(heading="H", body="Just one paragraph."),
                BrochureSection(heading="H2", body="Another."),
            ],
        )
        c = BrochureContent.from_brochure_input(b)
        assert c.title == "T"
        assert c.sections[0].lead_paragraph == "Just one paragraph."
        assert c.sections[0].bullets == []

    def test_bullets_split_from_body(self):
        body = "Intro sentence.\n\n- First bullet\n- Second bullet\n- Third bullet"
        b = BrochureInput(
            title="T",
            hero_concept="hc",
            style_preset="photorealistic",
            org="O",
            sections=[
                BrochureSection(heading="H", body=body),
                BrochureSection(heading="H2", body="simple"),
            ],
        )
        c = BrochureContent.from_brochure_input(b)
        assert c.sections[0].lead_paragraph == "Intro sentence."
        assert c.sections[0].bullets == ["First bullet", "Second bullet", "Third bullet"]

    def test_back_panel_adapter_splits_structure(self):
        b = BrochureInput(
            title="T",
            hero_concept="hc",
            style_preset="photorealistic",
            org="O",
            sections=[
                BrochureSection(heading="H", body="a"),
                BrochureSection(heading="H2", body="b"),
            ],
            back_panel=BrochureBackPanel(
                kind="cta",
                content="Title here\n\n- Call now\n- Email today",
            ),
        )
        c = BrochureContent.from_brochure_input(b)
        assert c.back_panel is not None
        assert c.back_panel.heading == "Title here"
        assert c.back_panel.bullets == ["Call now", "Email today"]
