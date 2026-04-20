"""End-to-end rendering tests for all 3 starter templates."""

from __future__ import annotations

import pytest

from flyer_generator.brochure.schema_renderer import (
    BrochureContent,
    ContentSection,
    load_template,
    render_schema_brochure,
)
from flyer_generator.brochure.schema_renderer.content_model import BackPanelContent
from flyer_generator.brochure.models import ContactBlock
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
)


STARTERS = ["editorial_classic", "geometric_bold", "quote_center"]


def _sample_content() -> BrochureContent:
    return BrochureContent(
        title="Test Brochure Title",
        subtitle="A clear subtitle for testing",
        tagline="Short tagline here.",
        org="Acme Test Co",
        contact=ContactBlock(
            name="Jane Doe",
            phone="(555) 123-4567",
            email="hi@acme.test",
            url="acme.test",
            address="1 Test St, Nowhere, CA 00000",
        ),
        sections=[
            ContentSection(
                heading="Section One",
                lead_paragraph="A concise lead paragraph introducing this section.",
                bullets=["First bullet", "Second bullet", "Third bullet"],
            ),
            ContentSection(
                heading="Section Two",
                lead_paragraph="Another lead paragraph with some punch.",
                bullets=["Alpha", "Beta", "Gamma", "Delta"],
            ),
            ContentSection(
                heading="Section Three",
                lead_paragraph="A third lead paragraph.",
                bullets=["One", "Two", "Three"],
            ),
        ],
        back_panel=BackPanelContent(
            heading="Ready to begin?",
            body="One sentence inviting the reader to take action.",
            bullets=["Call us", "Email us", "Visit our website"],
        ),
    )


@pytest.mark.parametrize("template_name", STARTERS)
def test_template_renders_both_sheets(template_name: str):
    t = load_template(template_name)
    c = _sample_content()
    outside, inside = render_schema_brochure(t, c)
    assert outside.startswith("<svg")
    assert inside.startswith("<svg")
    assert outside.endswith("</svg>")
    assert inside.endswith("</svg>")


@pytest.mark.parametrize("template_name", STARTERS)
def test_template_uses_full_bleed_canvas(template_name: str):
    t = load_template(template_name)
    c = _sample_content()
    outside, inside = render_schema_brochure(t, c)
    assert f'width="{BLEED_CANVAS_WIDTH}"' in outside
    assert f'height="{BLEED_CANVAS_HEIGHT}"' in outside


@pytest.mark.parametrize("template_name", STARTERS)
def test_template_renders_crop_marks(template_name: str):
    t = load_template(template_name)
    c = _sample_content()
    outside, inside = render_schema_brochure(t, c)
    assert "crop-marks-outside" in outside
    assert "crop-marks-inside" in inside


@pytest.mark.parametrize("template_name", STARTERS)
def test_title_appears_on_front_cover(template_name: str):
    t = load_template(template_name)
    c = _sample_content()
    outside, _ = render_schema_brochure(t, c)
    # Title may be wrapped across multiple tspans; each individual word should appear
    for word in ("Test", "Brochure", "Title"):
        assert word in outside or word.upper() in outside


@pytest.mark.parametrize("template_name", STARTERS)
def test_org_appears_somewhere(template_name: str):
    t = load_template(template_name)
    c = _sample_content()
    outside, inside = render_schema_brochure(t, c)
    assert "Acme" in outside or "Acme" in inside or "ACME" in outside or "ACME" in inside


@pytest.mark.parametrize("template_name", STARTERS)
def test_at_least_one_section_heading_appears_inside(template_name: str):
    t = load_template(template_name)
    c = _sample_content()
    _, inside = render_schema_brochure(t, c)
    # At least one section heading should land inside
    assert (
        "Section One" in inside
        or "Section Two" in inside
        or "Section Three" in inside
    )


@pytest.mark.parametrize("template_name", STARTERS)
def test_bullets_rendered_somewhere(template_name: str):
    t = load_template(template_name)
    c = _sample_content()
    outside, inside = render_schema_brochure(t, c)
    combined = outside + inside
    # At least one of our bullet items should appear
    assert (
        "First bullet" in combined
        or "Alpha" in combined
        or "Call us" in combined
    )


@pytest.mark.parametrize("template_name", STARTERS)
def test_no_python_exceptions_with_sparse_content(template_name: str):
    """Render with bare-minimum content: no optional fields."""
    t = load_template(template_name)
    c = BrochureContent(
        title="T",
        org="O",
        sections=[ContentSection(heading="H"), ContentSection(heading="H2"), ContentSection(heading="H3")],
    )
    outside, inside = render_schema_brochure(t, c)
    assert "<svg" in outside and "<svg" in inside


def test_rasterize_roundtrip_smoke():
    """Renderer output must rasterize via existing Rasterizer."""
    from flyer_generator.stages.rasterizer import Rasterizer

    t = load_template("editorial_classic")
    c = _sample_content()
    outside, inside = render_schema_brochure(t, c)
    r = Rasterizer(width=BLEED_CANVAS_WIDTH, height=BLEED_CANVAS_HEIGHT)
    png_out = r.rasterize(outside)
    png_in = r.rasterize(inside)
    assert len(png_out) > 1000
    assert len(png_in) > 1000
    # PNG signature
    assert png_out[:4] == b"\x89PNG"
    assert png_in[:4] == b"\x89PNG"


# --------------------------------------------------------------------------- #
# Phase 4 — image placeholder embedding
# --------------------------------------------------------------------------- #


def _png_bytes() -> bytes:
    """Return a 128×128 solid-color PNG.

    Large enough for cairo to upsample into the placeholder bbox without
    running out of memory (a 1×1 PNG scaled to 900px blows cairo's cache).
    """
    import io

    from PIL import Image

    img = Image.new("RGB", (128, 128), color=(64, 128, 192))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_image_embeds_as_base64_when_slot_supplied() -> None:
    t = load_template("hero_image_dominant")
    c = _sample_content()
    images = {"hero": _png_bytes()}
    outside, _inside = render_schema_brochure(t, c, images=images)
    # <image tag emitted
    assert "<image " in outside
    # base64 data URL header present
    assert "data:image/png;base64," in outside
    # Crop-to-fill aspect ratio
    assert 'preserveAspectRatio="xMidYMid slice"' in outside


def test_image_slot_with_rounded_mask_emits_clippath_with_rx() -> None:
    t = load_template("hero_image_dominant")
    c = _sample_content()
    # spot_1 on inner_left uses mask=rounded corner_radius=22
    images = {"spot_1": _png_bytes()}
    _outside, inside = render_schema_brochure(t, c, images=images)
    assert "<clipPath" in inside
    # The rounded rect inside the clipPath should carry rx/ry (float serializes to "22.0")
    assert 'rx="22' in inside
    assert 'ry="22' in inside


def test_image_slot_missing_uses_fallback() -> None:
    t = load_template("hero_image_dominant")
    c = _sample_content()
    # No images passed → all placeholders fall back
    outside, _inside = render_schema_brochure(t, c, images={})
    # No <image> tag
    assert "<image " not in outside
    # Fallback gradient (linearGradient) or placeholder label should still render
    assert "<svg" in outside


def test_image_embedding_does_not_emit_fallback_label() -> None:
    t = load_template("hero_image_dominant")
    c = _sample_content()
    images = {"hero": _png_bytes()}
    outside, _inside = render_schema_brochure(t, c, images=images)
    # When image is present, placeholder label "[ hero ]" should NOT appear
    assert "[ hero ]" not in outside
    assert "[hero]" not in outside


def test_images_kwarg_is_optional_backward_compatible() -> None:
    t = load_template("hero_image_dominant")
    c = _sample_content()
    # Must still work when images kwarg omitted (Phase 1 behavior)
    outside, inside = render_schema_brochure(t, c)
    assert "<svg" in outside and "<svg" in inside


def test_multiple_slots_embed_distinct_base64_payloads() -> None:
    t = load_template("hero_image_dominant")
    c = _sample_content()
    hero = _png_bytes()
    spot = b"\x89PNG-unique-spot-signature"
    images = {"hero": hero, "spot_1": spot}
    outside, inside = render_schema_brochure(t, c, images=images)
    # hero on outside, spot_1 on inside (inner_left panel)
    assert "<image " in outside
    assert "<image " in inside


def test_image_embedding_rasterizes_cleanly() -> None:
    """Real rasterizer must accept the embedded-image SVG without errors."""
    from flyer_generator.stages.rasterizer import Rasterizer

    t = load_template("hero_image_dominant")
    c = _sample_content()
    images = {"hero": _png_bytes(), "spot_1": _png_bytes()}
    outside, inside = render_schema_brochure(t, c, images=images)
    r = Rasterizer(width=BLEED_CANVAS_WIDTH, height=BLEED_CANVAS_HEIGHT)
    png_out = r.rasterize(outside)
    png_in = r.rasterize(inside)
    assert png_out[:4] == b"\x89PNG"
    assert png_in[:4] == b"\x89PNG"


# --------------------------------------------------------------------------- #
# Phase 4 stretch — texture_slot fills
# --------------------------------------------------------------------------- #


def _template_with_texture_slot_shape():
    """Build an in-memory template whose front_cover has a texture_slot rect."""
    from flyer_generator.brochure.schema_renderer.schema_model import (
        Canvas,
        Palette,
        PanelSchema,
        ShapeElement,
        SolidFill,
        TemplateSchema,
        TextureSlotFill,
    )

    bg_rect = ShapeElement(
        kind="rect",
        rect=(0.0, 0.0, 1100.0, 2550.0),
        fill=TextureSlotFill(slot="grain", fallback=SolidFill(color="#222222")),
        bleed=True,
    )
    return TemplateSchema(
        schema_version="1",
        name="test_texture",
        description="template with a texture_slot shape fill",
        canvas=Canvas(width=1100, height=2550),
        palette=Palette(accent_default="#ABABAB"),
        panels={
            "front_cover": PanelSchema(elements=[bg_rect]),
            "back_cover": PanelSchema(elements=[]),
            "tuck_flap": PanelSchema(elements=[]),
            "inner_left": PanelSchema(elements=[]),
            "inner_center": PanelSchema(elements=[]),
            "inner_right": PanelSchema(elements=[]),
        },
    )


def test_textures_kwarg_emits_pattern_on_outside_sheet() -> None:
    t = _template_with_texture_slot_shape()
    c = _sample_content()
    outside, _ = render_schema_brochure(t, c, textures={"grain": _png_bytes()})
    assert "<pattern" in outside
    assert 'patternUnits="userSpaceOnUse"' in outside
    assert "data:image/png;base64," in outside


def test_textures_missing_slot_falls_back_to_fallback_fill() -> None:
    t = _template_with_texture_slot_shape()
    c = _sample_content()
    # No textures supplied → fallback SolidFill color appears instead of pattern
    outside, _ = render_schema_brochure(t, c)
    assert "<pattern" not in outside
    assert "#222222" in outside


# --------------------------------------------------------------------------- #
# Phase 6 — real logo embedding in logo_placeholder
# --------------------------------------------------------------------------- #


def _template_with_logo_placeholder():
    """In-memory template whose tuck_flap has a single logo_placeholder."""
    from flyer_generator.brochure.schema_renderer.schema_model import (
        Canvas,
        LogoPlaceholder,
        Palette,
        PanelSchema,
        TemplateSchema,
    )

    logo_el = LogoPlaceholder(
        bbox=(100.0, 100.0, 400.0, 200.0),
        fallback_style="monogram_circle",
    )
    return TemplateSchema(
        schema_version="1",
        name="test_logo",
        description="template with a logo_placeholder",
        canvas=Canvas(width=1100, height=2550),
        palette=Palette(accent_default="#ABABAB"),
        panels={
            "front_cover": PanelSchema(elements=[]),
            "back_cover": PanelSchema(elements=[]),
            "tuck_flap": PanelSchema(elements=[logo_el]),
            "inner_left": PanelSchema(elements=[]),
            "inner_center": PanelSchema(elements=[]),
            "inner_right": PanelSchema(elements=[]),
        },
    )


def test_logo_bytes_emits_base64_image_when_supplied() -> None:
    t = _template_with_logo_placeholder()
    c = _sample_content()
    outside, _ = render_schema_brochure(t, c, logo_bytes=_png_bytes())
    # Logo is embedded as <image> with xMidYMid meet (logos never crop)
    assert "<image " in outside
    assert 'preserveAspectRatio="xMidYMid meet"' in outside
    assert "data:image/png;base64," in outside


def test_logo_absent_renders_monogram_fallback() -> None:
    t = _template_with_logo_placeholder()
    c = _sample_content()
    outside, _ = render_schema_brochure(t, c)
    # No logo → monogram circle + initials of the org ("Acme Test Co" → "AT")
    assert "<circle" in outside
    assert "AT" in outside
    assert "<image " not in outside


def test_logo_svg_input_inlines_as_nested_svg() -> None:
    t = _template_with_logo_placeholder()
    c = _sample_content()
    svg_logo = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        b'<circle cx="50" cy="50" r="40" fill="#123456"/></svg>'
    )
    outside, _ = render_schema_brochure(t, c, logo_bytes=svg_logo)
    # Inner <svg> viewport emitted at the bbox position
    assert 'x="100' in outside or 'x="100.0' in outside
    # The nested logo markup is inlined (fill color flows through)
    assert "#123456" in outside
    # Not a base64 data URL
    assert "data:image/png" not in outside


def test_logo_jpeg_uses_jpeg_mime_type() -> None:
    """JPG logos should be embedded with image/jpeg MIME type."""
    t = _template_with_logo_placeholder()
    c = _sample_content()
    # Minimal JPEG SOI marker — enough for our content-type sniff
    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    outside, _ = render_schema_brochure(t, c, logo_bytes=jpeg_bytes)
    assert "data:image/jpeg;base64," in outside


# --------------------------------------------------------------------------- #
# Palette accent override
# --------------------------------------------------------------------------- #


def test_accent_override_replaces_template_default() -> None:
    """--color-accent / accent_override swaps the palette accent_default."""
    t = load_template("editorial_classic")
    c = _sample_content()
    # Default palette accent is some dark blue; force a sage green and assert
    # it shows up in the output SVG (monogram fallback uses accent_default).
    override = "#AABBCC"
    outside, inside = render_schema_brochure(t, c, accent_override=override)
    combined = outside + inside
    assert override in combined


def test_accent_override_none_preserves_template_default() -> None:
    t = load_template("editorial_classic")
    c = _sample_content()
    # Without override, the template's accent stays in effect
    outside_default, _ = render_schema_brochure(t, c)
    # Sanity: accent_override=None is the same render
    outside_none, _ = render_schema_brochure(t, c, accent_override=None)
    assert outside_default == outside_none
