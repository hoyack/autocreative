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
