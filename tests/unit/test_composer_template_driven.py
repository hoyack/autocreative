"""PosterComposer template-driven rendering tests (Phase 22 FT-03).

Covers Plan 22-03:
- `template` keyword-only parameter on PosterComposer.compose
- back-compat: omitted/None template renders identical to Phase-21 hardcoded behavior
- template-driven typography (heading_family, body_family, cover_title_size)
- template-driven scrim opacity (palette.scrim_opacity_top/bottom)
- template-driven accent (palette.accent_default wins over event.color_accent)
- subtype-aware rendering: info flyers skip fee badge + details, render description + CTA
- COMP-08 XML escape coverage for description + call_to_action
"""

from __future__ import annotations

from datetime import datetime, timezone

from flyer_generator.flyer.schema_renderer.loader import load_template
from flyer_generator.models import (
    ComfyJob,
    FlyerInput,
    GeneratedBackground,
    LayoutZones,
    ResolvedLayout,
    VisionVerdict,
)
from flyer_generator.stages.composer import PosterComposer
from flyer_generator.zones import ZONE_COORDS


def _event_flyer(**over) -> FlyerInput:
    defaults = dict(
        title="Test Gala",
        subtype="event",
        date="2026-05-01",
        time="7:00 PM",
        location_name="The Hall",
        location_address="1 Main St",
        fees="Free",
        org="Acme",
        style_concept="summer",
        style_preset="photorealistic",
        color_accent="#F59E0B",
    )
    defaults.update(over)
    return FlyerInput(**defaults)


def _info_flyer(**over) -> FlyerInput:
    defaults = dict(
        title="Road Closure Notice",
        subtype="info",
        description="Main Street will be closed on May 1 for utility work.",
        call_to_action="Please use Oak Avenue as an alternate route.",
        org="City of Example",
        style_concept="civic bulletin",
        style_preset="photorealistic",
        color_accent="#1E3A5F",
    )
    defaults.update(over)
    return FlyerInput(**defaults)


def _bg() -> GeneratedBackground:
    return GeneratedBackground(
        image_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
        source_dimensions=(832, 1472),
        final_dimensions=(1080, 1920),
        comfy_job=ComfyJob(
            prompt_id="x",
            submitted_at=datetime.now(timezone.utc),
            positive_prompt="",
            negative_prompt="",
            seed=0,
            attempt_number=1,
        ),
    )


def _verdict_event() -> VisionVerdict:
    return VisionVerdict(
        approved=True,
        confidence=0.9,
        text_color="white",
        raw_response="{}",
        zones=LayoutZones(
            title="TOP_CENTER",
            details="BOTTOM_LEFT",
            fee_badge="BOTTOM_RIGHT",
            org_credit="BOTTOM_CENTER",
        ),
    )


def _verdict_info() -> VisionVerdict:
    return VisionVerdict(
        approved=True,
        confidence=0.9,
        text_color="white",
        raw_response="{}",
        zones=LayoutZones(
            title="TOP_CENTER",
            details=None,
            fee_badge=None,
            org_credit="BOTTOM_CENTER",
        ),
    )


def _layout_event() -> ResolvedLayout:
    return ResolvedLayout(
        title=ZONE_COORDS["TOP_CENTER"],
        details=ZONE_COORDS["BOTTOM_LEFT"],
        fee_badge=ZONE_COORDS["BOTTOM_RIGHT"],
        org_credit=ZONE_COORDS["BOTTOM_CENTER"],
    )


def _layout_info() -> ResolvedLayout:
    return ResolvedLayout(
        title=ZONE_COORDS["TOP_CENTER"],
        details=None,
        fee_badge=None,
        org_credit=ZONE_COORDS["BOTTOM_CENTER"],
    )


# ---------------------------------------------------------------------------
# TestBackwardCompat — template kwarg + None == omitted
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_compose_without_template_still_works(self) -> None:
        svg = PosterComposer().compose(
            _event_flyer(), _bg(), _verdict_event(), _layout_event()
        )
        assert svg.startswith("<svg")
        assert svg.rstrip().endswith("</svg>")

    def test_explicit_none_template_equals_omitted(self) -> None:
        a = PosterComposer().compose(
            _event_flyer(), _bg(), _verdict_event(), _layout_event()
        )
        b = PosterComposer().compose(
            _event_flyer(),
            _bg(),
            _verdict_event(),
            _layout_event(),
            template=None,
        )
        assert a == b


# ---------------------------------------------------------------------------
# TestTemplateDriven — typography / scrim / accent reads template
# ---------------------------------------------------------------------------


class TestTemplateDriven:
    def test_heading_family_from_template(self) -> None:
        tpl = load_template("editorial_classic")
        svg = PosterComposer().compose(
            _event_flyer(),
            _bg(),
            _verdict_event(),
            _layout_event(),
            template=tpl,
        )
        assert tpl.typography.heading_family in svg

    def test_body_family_from_template(self) -> None:
        tpl = load_template("editorial_classic")
        svg = PosterComposer().compose(
            _event_flyer(),
            _bg(),
            _verdict_event(),
            _layout_event(),
            template=tpl,
        )
        assert tpl.typography.body_family in svg

    def test_accent_from_template_not_event(self) -> None:
        # editorial_classic accent = "#1E3A5F"; event accent = "#F59E0B"
        tpl = load_template("editorial_classic")
        event = _event_flyer(color_accent="#F59E0B")
        svg = PosterComposer().compose(
            event,
            _bg(),
            _verdict_event(),
            _layout_event(),
            template=tpl,
        )
        # Template wins
        assert "#1E3A5F" in svg

    def test_scrim_opacity_from_template(self) -> None:
        # editorial_classic has scrim_opacity_top 0.60
        tpl = load_template("editorial_classic")
        svg = PosterComposer().compose(
            _event_flyer(),
            _bg(),
            _verdict_event(),
            _layout_event(),
            template=tpl,
        )
        # Look for the opacity value (0.6 or 0.60) in the <stop> stop-color rgba(...)
        assert ("0.6" in svg) or ("0.60" in svg)

    def test_cover_title_size_from_template(self) -> None:
        # editorial_classic.cover_title_size = 88
        tpl = load_template("editorial_classic")
        svg = PosterComposer().compose(
            _event_flyer(title="Hi"),  # short title — no auto-shrink
            _bg(),
            _verdict_event(),
            _layout_event(),
            template=tpl,
        )
        # Template's 88 should appear, not the hardcoded 82
        assert 'font-size="88"' in svg


# ---------------------------------------------------------------------------
# TestSubtypeRendering — info flyers skip details/fee, render description+CTA
# ---------------------------------------------------------------------------


class TestSubtypeRendering:
    def test_info_flyer_omits_fee_badge(self) -> None:
        tpl = load_template("editorial_classic")
        svg = PosterComposer().compose(
            _info_flyer(),
            _bg(),
            _verdict_info(),
            _layout_info(),
            template=tpl,
        )
        # Fee badge identifier (rx="28") must NOT be present for info flyers
        assert 'rx="28"' not in svg

    def test_info_flyer_omits_details_block(self) -> None:
        tpl = load_template("editorial_classic")
        svg = PosterComposer().compose(
            _info_flyer(),
            _bg(),
            _verdict_info(),
            _layout_info(),
            template=tpl,
        )
        # Date/time/venue/fees content must NOT appear in info-flyer SVG
        assert "7:00 PM" not in svg
        assert "1 Main St" not in svg

    def test_info_flyer_renders_description(self) -> None:
        tpl = load_template("editorial_classic")
        svg = PosterComposer().compose(
            _info_flyer(),
            _bg(),
            _verdict_info(),
            _layout_info(),
            template=tpl,
        )
        # Description text appears (XML-escaped form is plain since no special chars)
        assert "Main Street will be closed" in svg

    def test_info_flyer_renders_call_to_action(self) -> None:
        tpl = load_template("editorial_classic")
        svg = PosterComposer().compose(
            _info_flyer(),
            _bg(),
            _verdict_info(),
            _layout_info(),
            template=tpl,
        )
        assert "Oak Avenue" in svg

    def test_info_flyer_renders_description_xml_escaped(self) -> None:
        tpl = load_template("editorial_classic")
        evil_desc = "Closure <script>alert(1)</script> notice"
        f = _info_flyer(description=evil_desc)
        svg = PosterComposer().compose(
            f, _bg(), _verdict_info(), _layout_info(), template=tpl
        )
        # The raw <script> must not appear; escaped form must
        assert "<script>" not in svg
        assert "&lt;script&gt;" in svg

    def test_info_flyer_with_no_template_still_works(self) -> None:
        # Back-compat: info subtype without a template should still render
        # (skips fee + details; renders description + CTA).
        svg = PosterComposer().compose(
            _info_flyer(),
            _bg(),
            _verdict_info(),
            _layout_info(),
        )
        assert svg.startswith("<svg")
        assert "Main Street will be closed" in svg
        assert 'rx="28"' not in svg  # no fee badge

    def test_info_flyer_with_no_description_renders_no_description_block(self) -> None:
        # If event.description is None or empty for an info flyer, no description elements emitted
        tpl = load_template("editorial_classic")
        f = _info_flyer(description=None, call_to_action=None)
        svg = PosterComposer().compose(
            f, _bg(), _verdict_info(), _layout_info(), template=tpl
        )
        # The flyer still has a title, but no description content
        assert svg.startswith("<svg")
        assert "Main Street" not in svg
        assert "Oak Avenue" not in svg


# ---------------------------------------------------------------------------
# TestXMLEscaping — COMP-08 regression guard
# ---------------------------------------------------------------------------


class TestXMLEscaping:
    """COMP-08 regression guard — every user-supplied string XML-escaped."""

    def test_title_with_special_chars_escaped(self) -> None:
        tpl = load_template("editorial_classic")
        f = _event_flyer(title='Gala & "Special" <Event>')
        svg = PosterComposer().compose(
            f, _bg(), _verdict_event(), _layout_event(), template=tpl
        )
        # raw '<Event>' must not appear
        assert "<Event>" not in svg
        # ampersand or angle bracket must be escaped
        assert "&amp;" in svg or "&lt;Event&gt;" in svg

    def test_call_to_action_with_special_chars_escaped(self) -> None:
        tpl = load_template("editorial_classic")
        f = _info_flyer(call_to_action='Visit & enjoy <today>!')
        svg = PosterComposer().compose(
            f, _bg(), _verdict_info(), _layout_info(), template=tpl
        )
        assert "<today>" not in svg
        assert "&amp;" in svg
