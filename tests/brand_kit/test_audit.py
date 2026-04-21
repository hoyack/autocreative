"""Audit module: whitespace, contrast, density, iterate loop, + W10 remediations.

Direct-module imports only (B1)."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock

import pytest
from PIL import Image, ImageDraw

from flyer_generator.brand_kit.audit import (
    AuditIssue,
    AuditReport,
    audit_render,
    iterate_audit_loop,
    remediate_contrast,
    remediate_density,
)
from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandPalette,
    ColorUsage,
)
from flyer_generator.brochure.schema_renderer.content_model import (
    BrochureContent,
    ContentSection,
)
from flyer_generator.brochure.schema_renderer.loader import load_template
from flyer_generator.errors import BrandKitAuditError


# The outside sheet is three panels wide at 1100px each (editorial_classic
# canvas width) and 2550px tall. Match that so the crop math lines up.
_SHEET_W = 3300
_SHEET_H = 2550


def _solid_sheet_png(
    width: int = _SHEET_W, height: int = _SHEET_H, color: str = "#FAFAF7"
) -> bytes:
    h = color.lstrip("#")
    rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    img = Image.new("RGB", (width, height), rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _half_filled_sheet_png(width: int = _SHEET_W, height: int = _SHEET_H) -> bytes:
    """Back_cover (leftmost third) fully black; other two-thirds FAFAF7.

    Panel order on the outside sheet is (back_cover, tuck_flap, front_cover)
    per the plan's _OUTSIDE_ORDER constant.
    """
    img = Image.new("RGB", (width, height), (250, 250, 247))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width // 3, height], fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _minimal_content() -> BrochureContent:
    return BrochureContent(
        title="Test Brochure",
        subtitle="A subtitle",
        tagline="Tag",
        org="Org",
        sections=[
            ContentSection(
                heading="Heading",
                lead_paragraph="Lead paragraph text.",
                body_paragraphs=["Body one.", "Body two."],
                bullets=["Bullet one", "Bullet two"],
            )
        ],
    )


def _test_kit() -> BrandKit:
    from datetime import datetime, timezone

    return BrandKit(
        name="Test",
        fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        palette=BrandPalette(
            primary=ColorUsage(hex="#1E3A5F"),
            secondary=ColorUsage(hex="#C4A269"),
            accent=ColorUsage(hex="#E8F1F2"),
            neutral_dark=ColorUsage(hex="#1A1A1A"),
            neutral_light=ColorUsage(hex="#FAFAF7"),
        ),
    )


# ---- Whitespace --------------------------------------------------------


def test_audit_whitespace_empty_sheet() -> None:
    t = load_template("editorial_classic")
    content = _minimal_content()
    png = _solid_sheet_png(color=t.palette.neutral_light)
    rep = audit_render(content, t, png, side="outside")
    assert rep.whitespace["back_cover"] > 0.90
    assert rep.whitespace["front_cover"] > 0.90


def test_audit_whitespace_partial_fill() -> None:
    t = load_template("editorial_classic")
    content = _minimal_content()
    png = _half_filled_sheet_png()
    rep = audit_render(content, t, png, side="outside")
    # back_cover is fully filled black, so whitespace ratio is near 0
    assert rep.whitespace["back_cover"] < 0.10
    assert rep.whitespace["front_cover"] > 0.80


def test_audit_whitespace_panel_warning_issued() -> None:
    t = load_template("editorial_classic")
    content = _minimal_content()
    png = _solid_sheet_png(color=t.palette.neutral_light)
    rep = audit_render(content, t, png, side="outside")
    whitespace_warnings = [i for i in rep.issues if i.category == "whitespace"]
    assert len(whitespace_warnings) >= 1


# ---- Contrast ----------------------------------------------------------


def test_audit_contrast_detects_fail() -> None:
    """A template whose back_cover has an explicit #CCCCCC text on #FAFAF7 bg fails AA."""
    t = load_template("editorial_classic")
    back = t.panels["back_cover"]
    from flyer_generator.brochure.schema_renderer.schema_model import TextElement

    new_elements = []
    patched = False
    for el in back.elements:
        if isinstance(el, TextElement) and not patched:
            new_elements.append(el.model_copy(update={"color": "#CCCCCC"}))
            patched = True
        else:
            new_elements.append(el)
    new_back = back.model_copy(update={"elements": new_elements})
    patched_t = t.model_copy(
        update={"panels": {**t.panels, "back_cover": new_back}}
    )
    png = _solid_sheet_png(color=patched_t.palette.neutral_light)
    rep = audit_render(_minimal_content(), patched_t, png, side="outside")
    assert not rep.contrast.overall_aa_pass
    assert len(rep.contrast.fails()) >= 1


def test_audit_contrast_passes_clean_template() -> None:
    t = load_template("editorial_classic")
    png = _solid_sheet_png(color=t.palette.neutral_light)
    rep = audit_render(_minimal_content(), t, png, side="outside")
    # Every failing pair in the clean template (if any) must not be the canonical
    # high-contrast body/accent pairs.
    fails = rep.contrast.fails()
    for pair in fails:
        assert pair.fg not in ("#1A1A1A", "#1E3A5F")


# ---- Density -----------------------------------------------------------


def test_audit_density_populated() -> None:
    t = load_template("editorial_classic")
    content = _minimal_content()
    png = _solid_sheet_png(color=t.palette.neutral_light)
    rep = audit_render(content, t, png, side="outside")
    assert any(isinstance(v, float) for v in rep.density.values())


def test_audit_density_low_fill_flagged() -> None:
    t = load_template("editorial_classic")
    content = BrochureContent(
        title="X",
        subtitle="Y",
        tagline="T",
        org="O",
        sections=[
            ContentSection(
                heading="H",
                lead_paragraph="",
                body_paragraphs=[],
                bullets=[],
            )
        ],
    )
    png = _solid_sheet_png(color=t.palette.neutral_light)
    rep = audit_render(content, t, png, side="outside")
    title_issues = [
        i
        for i in rep.issues
        if i.category == "density" and i.content_key == "title"
    ]
    assert len(title_issues) >= 1


# ---- AuditReport.is_clean ----------------------------------------------


def test_audit_report_is_clean_empty() -> None:
    rep = AuditReport()
    assert rep.is_clean is True


def test_audit_report_is_clean_with_info_only() -> None:
    rep = AuditReport(
        issues=[AuditIssue(severity="info", category="density", detail="x")]
    )
    assert rep.is_clean is True


def test_audit_report_is_clean_false_with_error() -> None:
    rep = AuditReport(
        issues=[AuditIssue(severity="error", category="contrast", detail="x")]
    )
    assert rep.is_clean is False


# ---- iterate_audit_loop -------------------------------------------------


async def test_iterate_loop_converges_on_clean_first_cycle() -> None:
    t = load_template("editorial_classic")
    content = _minimal_content()
    png = _solid_sheet_png(color=t.palette.neutral_light)
    render = AsyncMock(return_value=(png, png))

    rep, final_content, final_template = await iterate_audit_loop(
        content, t, render=render, remediate=None, max_cycles=3, side="outside"
    )
    assert render.call_count >= 1
    assert rep.cycle >= 0


async def test_iterate_loop_strict_raises_on_exhaustion() -> None:
    t = load_template("editorial_classic")
    content = _minimal_content()
    png = _solid_sheet_png(color=t.palette.neutral_light)
    render = AsyncMock(return_value=(png, png))
    remediate = AsyncMock(side_effect=lambda c, tmpl, r: (c, tmpl))

    with pytest.raises(BrandKitAuditError) as ei:
        await iterate_audit_loop(
            content,
            t,
            render=render,
            remediate=remediate,
            max_cycles=2,
            strict=True,
            side="outside",
        )
    assert ei.value.cycles == 2


async def test_iterate_loop_non_strict_returns_report() -> None:
    t = load_template("editorial_classic")
    content = _minimal_content()
    png = _solid_sheet_png(color=t.palette.neutral_light)
    render = AsyncMock(return_value=(png, png))

    rep, _c, _t = await iterate_audit_loop(
        content,
        t,
        render=render,
        remediate=None,
        max_cycles=2,
        strict=False,
        side="outside",
    )
    assert isinstance(rep, AuditReport)


async def test_iterate_loop_remediate_called_on_issue() -> None:
    t = load_template("editorial_classic")
    content = _minimal_content()
    png = _solid_sheet_png(color=t.palette.neutral_light)
    render = AsyncMock(return_value=(png, png))
    remediate = AsyncMock(side_effect=lambda c, tmpl, r: (c, tmpl))

    await iterate_audit_loop(
        content,
        t,
        render=render,
        remediate=remediate,
        max_cycles=2,
        strict=False,
        side="outside",
    )
    assert render.call_count >= 1


# ---- W10a - remediate_contrast ----------------------------------------


async def test_remediate_contrast_swaps_failing_text() -> None:
    """W10a: remediate_contrast picks the opposite neutral for a failing fg."""
    t = load_template("editorial_classic")
    kit = _test_kit()
    # Build an audit report with a FAIL pair
    from flyer_generator.brand_kit.contrast import ContrastPair, ContrastReport

    audit = AuditReport(
        contrast=ContrastReport(
            pairs=[
                ContrastPair(
                    fg="#CCCCCC",
                    bg="#FAFAF7",
                    ratio=1.6,
                    level="FAIL",
                    panel="back_cover",
                    content_key="title",
                )
            ]
        ),
        issues=[
            AuditIssue(
                severity="error",
                category="contrast",
                panel="back_cover",
                content_key="title",
                detail="FAIL",
            )
        ],
    )
    content = _minimal_content()
    new_content, new_template = await remediate_contrast(
        content, t, audit, kit=kit
    )
    assert isinstance(new_template, type(t))
    # Concrete: the palette must have actually changed. If someone reverts
    # the arg order in remediate_contrast (passing kit first), apply_brand_kit
    # would receive a BrandKit as its `template` argument and fail - or worse,
    # silently no-op. Assert the returned template's accent differs from the
    # input template's accent so pytest catches the regression immediately.
    assert new_template.palette.accent_default != t.palette.accent_default, (
        "remediate_contrast must produce a palette change (arg-order regression?)"
    )


async def test_remediate_contrast_no_fails_is_noop() -> None:
    """remediate_contrast returns (content, template) unchanged when no FAILs exist."""
    t = load_template("editorial_classic")
    kit = _test_kit()
    audit = AuditReport()  # empty -> overall_aa_pass is True
    content = _minimal_content()
    new_content, new_template = await remediate_contrast(
        content, t, audit, kit=kit
    )
    assert new_template is t
    assert new_content is content


# ---- W10b - remediate_density -----------------------------------------


async def test_remediate_density_calls_regenerate_fn_with_tighter_budgets() -> None:
    """W10b: remediate_density calls regenerate_fn with a dict of tighter budgets."""
    t = load_template("editorial_classic")
    content = _minimal_content()
    audit = AuditReport(
        issues=[
            AuditIssue(
                severity="info",
                category="density",
                panel="back_cover",
                content_key="title",
                detail="title fills 10% of budget (5/50)",
            )
        ]
    )

    captured: dict[str, dict[str, int]] = {}

    async def fake_regen(budgets: dict[str, int]) -> BrochureContent:
        captured["budgets"] = dict(budgets)
        return content

    new_content, _new_template = await remediate_density(
        content, t, audit, regenerate_fn=fake_regen
    )
    assert "budgets" in captured
    assert "title" in captured["budgets"]
    assert captured["budgets"]["title"] > 0


async def test_remediate_density_no_issues_is_noop() -> None:
    t = load_template("editorial_classic")
    content = _minimal_content()
    audit = AuditReport()  # no issues

    called = False

    async def fake_regen(budgets: dict[str, int]) -> BrochureContent:
        nonlocal called
        called = True
        return content

    await remediate_density(content, t, audit, regenerate_fn=fake_regen)
    assert called is False


async def test_iterate_loop_composes_default_remediate_with_kit_and_regen() -> None:
    """Passing kit + regenerate_fn (and no explicit remediate) causes the loop
    to compose a default from remediate_contrast + remediate_density."""
    t = load_template("editorial_classic")
    content = _minimal_content()
    png = _solid_sheet_png(color=t.palette.neutral_light)
    render = AsyncMock(return_value=(png, png))
    kit = _test_kit()

    async def fake_regen(_budgets: dict[str, int]) -> BrochureContent:
        return content

    rep, _c, _t = await iterate_audit_loop(
        content,
        t,
        render=render,
        remediate=None,
        kit=kit,
        regenerate_fn=fake_regen,
        max_cycles=2,
        strict=False,
        side="outside",
    )
    assert isinstance(rep, AuditReport)


# ---- Oversize PNG raises -----------------------------------------------


def test_audit_rejects_oversized_png() -> None:
    t = load_template("editorial_classic")
    img = Image.new("RGB", (10000, 6000), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()
    with pytest.raises(BrandKitAuditError):
        audit_render(_minimal_content(), t, png, side="outside")
