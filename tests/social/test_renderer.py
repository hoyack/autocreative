"""Tests for flyer_generator.social.renderer.render_post.

Per checker B1: direct-module imports only.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from PIL import Image

from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandPalette,
    BrandTypography,
    ColorUsage,
)
from flyer_generator.errors import SocialError
from flyer_generator.social.models import PostCopy
from flyer_generator.social.renderer import render_post
from flyer_generator.social.schemas.loader import list_post_templates, load_post_template


def _make_kit() -> BrandKit:
    return BrandKit(
        name="Test Brand",
        fetched_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
        palette=BrandPalette(
            primary=ColorUsage(hex="#1E3A5F"),
            secondary=ColorUsage(hex="#C4A269"),
            accent=ColorUsage(hex="#E8F1F2"),
            neutral_dark=ColorUsage(hex="#1A1A1A"),
            neutral_light=ColorUsage(hex="#FAFAF7"),
        ),
        typography=BrandTypography(
            heading_family="'Test Heading', sans-serif",
            body_family="'Test Body', sans-serif",
        ),
    )


def _make_copy() -> PostCopy:
    return PostCopy(
        title="Typed Validation Wins",
        body="LinkedIn body text under 1400 characters.",
        cta="Read More",
        hashtags=["#python", "#pydantic"],
    )


def _make_tiny_png(w: int = 100, h: int = 100) -> bytes:
    img = Image.new("RGB", (w, h), (64, 128, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_render_post_linkedin_value_prop_produces_correct_dims() -> None:
    template = load_post_template("linkedin__value-prop")
    copy = _make_copy()
    kit = _make_kit()
    hero = _make_tiny_png()
    png = render_post(template, copy, kit, hero_image_bytes=hero)
    img = Image.open(io.BytesIO(png))
    assert img.size == (template.canvas.width, template.canvas.height)


def test_render_post_text_only_twitter_no_hero() -> None:
    template = load_post_template("twitter__announcement")
    assert template.image_slot is None  # text-only
    copy = _make_copy()
    kit = _make_kit()
    png = render_post(template, copy, kit, hero_image_bytes=None)
    img = Image.open(io.BytesIO(png))
    assert img.size == (template.canvas.width, template.canvas.height)


def test_render_post_requires_brand_kit_when_template_palette_null() -> None:
    template = load_post_template("linkedin__value-prop")
    assert template.palette is None  # templates ship palette=null
    with pytest.raises(SocialError):
        render_post(template, _make_copy(), brand_kit=None)


def test_render_post_all_twelve_templates_produce_pngs() -> None:
    """Smoke test: every one of the 12 templates renders without raising."""
    kit = _make_kit()
    copy = _make_copy()
    hero = _make_tiny_png()
    names = list_post_templates()
    assert len(names) >= 12
    for name in names:
        template = load_post_template(name)
        png = render_post(template, copy, kit, hero_image_bytes=hero)
        img = Image.open(io.BytesIO(png))
        assert img.size == (template.canvas.width, template.canvas.height), name


def test_render_post_non_rect_shape_logs_skip_warning(capsys) -> None:
    """Non-rect ShapeElement kinds (circle/polygon/etc.) are skipped with a warning in v1.

    Plan 06 v1 supports only `kind: "rect"` shapes (documented limitation;
    templates in Plan 05 use rect only). A template carrying a non-rect shape
    must render successfully with the shape omitted and a structured warning
    logged -- NOT crash.

    Note: structlog in this project ships with its default ConsoleRenderer
    stdout sink; it is NOT wired into the stdlib ``logging`` module, so
    ``caplog`` sees nothing. The warning lands on stdout as a structured
    key=value line. Assert against stdout via ``capsys``.
    """
    from flyer_generator.brochure.schema_renderer.schema_model import (
        ShapeElement,
        SolidFill,
    )

    template = load_post_template("linkedin__value-prop")
    # Inject a non-rect shape into the template (circle)
    bad_shape = ShapeElement(
        type="shape",
        kind="circle",
        rect=(100.0, 100.0, 80.0, 80.0),
        fill=SolidFill(type="solid", color="#FF0000", opacity=1.0),
        z=50,
    )
    mutated = template.model_copy(update={"shapes": [*template.shapes, bad_shape]})

    kit = _make_kit()
    copy = _make_copy()
    hero = _make_tiny_png()

    png = render_post(mutated, copy, kit, hero_image_bytes=hero)

    # Render still produces correctly-sized output
    img = Image.open(io.BytesIO(png))
    assert img.size == (template.canvas.width, template.canvas.height)

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert (
        "social_renderer_shape_kind_unsupported_in_v1" in combined
        or "circle" in combined
    ), f"expected non-rect warning in stdout/stderr; got: {combined!r}"


def test_render_post_xml_escapes_user_content() -> None:
    """User copy with < > & is XML-escaped so it cannot break the SVG parser.

    T-19-06-01 mitigation.
    """
    template = load_post_template("linkedin__value-prop")
    kit = _make_kit()
    copy = PostCopy(
        title="A & B <script>alert('x')</script>",
        body="Body & body",
        cta="Go",
        hashtags=["#x"],
    )
    hero = _make_tiny_png()
    png = render_post(template, copy, kit, hero_image_bytes=hero)
    # Must produce a valid PNG (i.e. CairoSVG did not choke on unescaped markup).
    img = Image.open(io.BytesIO(png))
    assert img.size == (template.canvas.width, template.canvas.height)


def test_render_post_canvas_cap_enforced() -> None:
    """T-19-06-02: canvas exceeding 50 MP raises SocialError before rasterization."""
    from flyer_generator.brochure.schema_renderer.schema_model import Canvas

    template = load_post_template("linkedin__value-prop")
    huge = template.model_copy(update={"canvas": Canvas(width=10_000, height=10_000)})
    kit = _make_kit()
    copy = _make_copy()
    with pytest.raises(SocialError):
        render_post(huge, copy, kit, hero_image_bytes=_make_tiny_png())
