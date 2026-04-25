"""Tests for the postcard renderer (PostcardContent + render_postcard).

Mirrors the brochure renderer test layout: content_key resolution, address-block
rendering, both portrait and landscape canvases, and SVG-injection guards.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content(
    headline: str = "Hello",
    body: str = "Body copy",
    *,
    image_hint: str | None = None,
    with_address: bool = False,
):
    """Build a PostcardContent for tests. Imports are inside so the module is
    importable from the test runner before the SUT exists (RED gate)."""
    from flyer_generator.postcard.schema_renderer import (
        PostcardAddressBlock,
        PostcardContent,
    )

    address = None
    if with_address:
        address = PostcardAddressBlock(
            recipient_name="Jane Doe",
            street="123 Main St",
            city_state_zip="Springfield, IL 62701",
        )
    return PostcardContent(
        headline=headline,
        body=body,
        image_hint=image_hint,
        address_block=address,
    )


# ---------------------------------------------------------------------------
# Test 1: barrel re-export
# ---------------------------------------------------------------------------


def test_barrel_reexports_content_and_renderer() -> None:
    """from flyer_generator.postcard.schema_renderer import PostcardContent, render_postcard."""
    from flyer_generator.postcard.schema_renderer import (  # noqa: F401
        PostcardAddressBlock,
        PostcardContent,
        PostcardTemplateSchema,
        list_templates,
        load_template,
        render_postcard,
    )


# ---------------------------------------------------------------------------
# Tests 2-7: PostcardContent + resolve_key
# ---------------------------------------------------------------------------


def test_postcard_content_validates_minimal_payload() -> None:
    from flyer_generator.postcard.schema_renderer import PostcardContent

    c = PostcardContent(headline="Hi", body="There")
    assert c.headline == "Hi"
    assert c.body == "There"
    assert c.image_hint is None
    assert c.address_block is None


def test_resolve_key_headline_returns_string() -> None:
    c = _content(headline="Greetings")
    assert c.resolve_key("headline") == "Greetings"


def test_resolve_key_body_returns_string() -> None:
    c = _content(body="Body text here")
    assert c.resolve_key("body") == "Body text here"


def test_resolve_key_address_block_returns_field_when_set() -> None:
    c = _content(with_address=True)
    assert c.resolve_key("address_block.recipient_name") == "Jane Doe"
    assert c.resolve_key("address_block.street") == "123 Main St"
    assert c.resolve_key("address_block.city_state_zip") == "Springfield, IL 62701"


def test_resolve_key_address_block_returns_empty_string_when_none() -> None:
    c = _content(with_address=False)
    assert c.resolve_key("address_block.recipient_name") == ""
    assert c.resolve_key("address_block.street") == ""
    assert c.resolve_key("address_block.city_state_zip") == ""


def test_resolve_key_unknown_returns_none() -> None:
    c = _content()
    assert c.resolve_key("nonexistent.key") is None
    assert c.resolve_key("totally_made_up") is None


# ---------------------------------------------------------------------------
# Tests 8-10: render_postcard return shape
# ---------------------------------------------------------------------------


def test_render_postcard_returns_two_strings() -> None:
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        render_postcard,
    )

    t = load_template("classic_portrait")
    fr, bk = render_postcard(t, _content(with_address=True))
    assert isinstance(fr, str)
    assert isinstance(bk, str)


def test_front_svg_has_template_canvas_dims_classic_portrait() -> None:
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        render_postcard,
    )

    t = load_template("classic_portrait")
    fr, _ = render_postcard(t, _content(with_address=True))
    assert fr.startswith("<svg xmlns=")
    assert 'width="1200"' in fr
    assert 'height="1800"' in fr
    assert 'viewBox="0 0 1200 1800"' in fr


def test_back_svg_has_template_canvas_dims_classic_portrait() -> None:
    """Postcards have a single canvas dim shared between front and back faces."""
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        render_postcard,
    )

    t = load_template("classic_portrait")
    _, bk = render_postcard(t, _content(with_address=True))
    assert 'width="1200"' in bk
    assert 'height="1800"' in bk


# ---------------------------------------------------------------------------
# Tests 11-13: XML escape + content rendering
# ---------------------------------------------------------------------------


def test_front_svg_xml_escapes_headline() -> None:
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        render_postcard,
    )

    t = load_template("classic_portrait")
    raw = "Hello & Goodbye <World>"
    fr, _ = render_postcard(t, _content(headline=raw))
    # The escaped version must be present
    assert "Hello &amp; Goodbye &lt;World&gt;" in fr
    # The raw, unescaped version must not appear
    assert "Hello & Goodbye <World>" not in fr


def test_back_svg_xml_escapes_body() -> None:
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        render_postcard,
    )

    t = load_template("classic_portrait")
    raw_body = "Cats & dogs <love>"
    _, bk = render_postcard(t, _content(body=raw_body))
    assert "Cats &amp; dogs &lt;love&gt;" in bk
    assert "Cats & dogs <love>" not in bk


def test_back_svg_contains_all_three_address_fields_when_supplied() -> None:
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        render_postcard,
    )

    t = load_template("classic_portrait")
    _, bk = render_postcard(t, _content(with_address=True))
    assert "Jane Doe" in bk
    assert "123 Main St" in bk
    assert "Springfield, IL 62701" in bk


# ---------------------------------------------------------------------------
# Tests 14-15: address-None path + landscape canvas
# ---------------------------------------------------------------------------


def test_back_svg_renders_without_address_block() -> None:
    """address_block=None must NOT raise; address TextElements emit empty text or are skipped."""
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        render_postcard,
    )

    t = load_template("classic_portrait")
    fr, bk = render_postcard(t, _content(with_address=False))
    # Both SVGs must be valid + non-empty
    assert fr.startswith("<svg ")
    assert bk.startswith("<svg ")
    # And the back SVG's outer wrapper must close cleanly
    assert bk.endswith("</svg>")
    # Address fields must not leak as the raw text "None" or similar literal
    assert ">None<" not in bk


def test_render_postcard_modern_landscape_dimensions() -> None:
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        render_postcard,
    )

    t = load_template("modern_landscape")
    fr, bk = render_postcard(t, _content(with_address=True))
    assert 'width="1800"' in fr
    assert 'height="1200"' in fr
    assert 'width="1800"' in bk
    assert 'height="1200"' in bk


# ---------------------------------------------------------------------------
# Test 16: SVG injection guard
# ---------------------------------------------------------------------------


def test_script_injection_in_body_is_xml_escaped() -> None:
    """Adversarial body content with HTML tags must be escaped, not rendered raw."""
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        render_postcard,
    )

    t = load_template("classic_portrait")
    payload = "<script>alert(1)</script>"
    _, bk = render_postcard(t, _content(body=payload))
    # Raw script tag must not appear in the SVG body output
    assert "<script>" not in bk
    assert "</script>" not in bk
    # Escaped form must be present somewhere
    assert "&lt;script&gt;" in bk


def test_script_injection_in_headline_is_xml_escaped() -> None:
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        render_postcard,
    )

    t = load_template("classic_portrait")
    payload = "<img src=x onerror=alert(1)>"
    fr, _ = render_postcard(t, _content(headline=payload))
    # The raw img tag in text content should not appear (would be inside <text>)
    # We check the escaped form appears somewhere in the output.
    assert "&lt;img" in fr


def test_script_injection_in_address_field_is_xml_escaped() -> None:
    from flyer_generator.postcard.schema_renderer import (
        PostcardAddressBlock,
        PostcardContent,
        load_template,
        render_postcard,
    )

    t = load_template("classic_portrait")
    content = PostcardContent(
        headline="Hi",
        body="Body",
        address_block=PostcardAddressBlock(
            recipient_name="<b>Bold</b> Person",
            street="123 Main",
            city_state_zip="Anywhere, USA",
        ),
    )
    _, bk = render_postcard(t, content)
    assert "<b>Bold</b>" not in bk
    assert "&lt;b&gt;Bold&lt;/b&gt;" in bk
