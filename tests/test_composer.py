"""Tests for flyer_generator.stages.composer -- PosterComposer SVG composition."""

from __future__ import annotations

import base64

import pytest

from flyer_generator.models import (
    EventInput,
    GeneratedBackground,
    LayoutZones,
    ResolvedLayout,
    VisionVerdict,
)
from flyer_generator.stages.composer import PosterComposer, _title_params, _wrap_text
from flyer_generator.zones import ZONE_COORDS, ZoneCoord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_event(**overrides: object) -> EventInput:
    defaults = dict(
        title="Summer Fest",
        date="June 15, 2026",
        time="8:00 PM",
        location_name="Central Park",
        location_address="123 Main St",
        fees="$25",
        org="Events Co",
        style_concept="summer",
        style_preset="photorealistic",
        color_accent="#F59E0B",
    )
    defaults.update(overrides)
    return EventInput(**defaults)  # type: ignore[arg-type]


def _make_background(image_bytes: bytes = b"PNG_FAKE") -> GeneratedBackground:
    from datetime import datetime, timezone
    from flyer_generator.models import ComfyJob

    job = ComfyJob(
        prompt_id="test-123",
        submitted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        positive_prompt="test",
        negative_prompt="test",
        seed=42,
        attempt_number=1,
    )
    return GeneratedBackground(
        image_bytes=image_bytes,
        source_dimensions=(832, 1472),
        final_dimensions=(1080, 1920),
        comfy_job=job,
    )


def _make_verdict(
    text_color: str = "white",
    title_zone: str = "TOP_CENTER",
    details_zone: str = "BOTTOM_LEFT",
    fee_badge_zone: str = "BOTTOM_RIGHT",
) -> VisionVerdict:
    return VisionVerdict(
        approved=True,
        confidence=0.9,
        zones=LayoutZones(
            title=title_zone,  # type: ignore[arg-type]
            details=details_zone,  # type: ignore[arg-type]
            fee_badge=fee_badge_zone,  # type: ignore[arg-type]
        ),
        text_color=text_color,  # type: ignore[arg-type]
        raw_response="test",
    )


def _make_layout(
    title_zone: str = "TOP_CENTER",
    details_zone: str = "BOTTOM_LEFT",
    fee_badge_zone: str = "BOTTOM_RIGHT",
) -> ResolvedLayout:
    return ResolvedLayout(
        title=ZONE_COORDS[title_zone],
        details=ZONE_COORDS[details_zone],
        fee_badge=ZONE_COORDS[fee_badge_zone],
        org_credit=ZONE_COORDS["BOTTOM_CENTER"],
    )


def _compose_default(**event_overrides: object) -> str:
    """Shortcut: compose with default fixtures, optional event overrides."""
    composer = PosterComposer()
    return composer.compose(
        event=_make_event(**event_overrides),
        background=_make_background(),
        verdict=_make_verdict(),
        layout=_make_layout(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComposeReturnsSVG:
    def test_compose_returns_valid_svg(self) -> None:
        svg = _compose_default()
        assert "<svg" in svg
        assert "</svg>" in svg
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg
        assert 'viewBox="0 0 1080 1920"' in svg


class TestComposeEmbedsBase64:
    def test_compose_embeds_background_base64(self) -> None:
        svg = _compose_default()
        expected_b64 = base64.b64encode(b"PNG_FAKE").decode("ascii")
        assert f"data:image/png;base64,{expected_b64}" in svg


class TestTitleUppercased:
    def test_title_uppercased(self) -> None:
        svg = _compose_default(title="Summer Fest")
        assert "SUMMER FEST" in svg


class TestTitleSizing:
    def test_title_sizing_short(self) -> None:
        svg = _compose_default(title="Hi")
        assert 'font-size="82"' in svg

    def test_title_sizing_medium(self) -> None:
        svg = _compose_default(title="Summer Festival")
        # "SUMMER FESTIVAL" = 15 chars -> fontSize=72
        assert 'font-size="72"' in svg

    def test_title_sizing_long(self) -> None:
        svg = _compose_default(title="The Greatest Show On Earth Tonight")
        # 33 chars after upper -> fontSize=52
        assert 'font-size="52"' in svg


class TestWrapText:
    def test_wrap_text_widow_merge(self) -> None:
        result = _wrap_text("ONE TWO THREE FOUR X", 10)
        # Without widow merge: ["ONE TWO", "THREE FOUR", "X"]
        # With widow merge: "X" is < 40% of "THREE FOUR" (10 chars), so merge
        # Result: ["ONE TWO", "THREE FOUR X"]
        assert len(result) == 2
        assert result[-1] == "THREE FOUR X"

    def test_wrap_text_short_passthrough(self) -> None:
        result = _wrap_text("HI THERE", 20)
        assert result == ["HI THERE"]


class TestTextColor:
    def test_text_color_white(self) -> None:
        composer = PosterComposer()
        svg = composer.compose(
            event=_make_event(),
            background=_make_background(),
            verdict=_make_verdict(text_color="white"),
            layout=_make_layout(),
        )
        assert 'fill="#ffffff"' in svg
        assert 'stroke="rgba(0,0,0,0.5)"' in svg

    def test_text_color_dark(self) -> None:
        composer = PosterComposer()
        svg = composer.compose(
            event=_make_event(),
            background=_make_background(),
            verdict=_make_verdict(text_color="dark"),
            layout=_make_layout(),
        )
        assert 'fill="#1a1a1a"' in svg
        assert 'stroke="rgba(255,255,255,0.4)"' in svg


class TestScrims:
    def test_scrim_top_only(self) -> None:
        composer = PosterComposer()
        svg = composer.compose(
            event=_make_event(),
            background=_make_background(),
            verdict=_make_verdict(
                title_zone="TOP_CENTER", details_zone="TOP_LEFT"
            ),
            layout=_make_layout(
                title_zone="TOP_CENTER", details_zone="TOP_LEFT"
            ),
        )
        assert 'fill="url(#topFade)"' in svg
        assert 'fill="url(#bottomFade)"' not in svg
        assert 'fill="url(#middleFade)"' not in svg

    def test_scrim_top_and_bottom(self) -> None:
        composer = PosterComposer()
        svg = composer.compose(
            event=_make_event(),
            background=_make_background(),
            verdict=_make_verdict(
                title_zone="TOP_CENTER", details_zone="BOTTOM_LEFT"
            ),
            layout=_make_layout(
                title_zone="TOP_CENTER", details_zone="BOTTOM_LEFT"
            ),
        )
        assert 'fill="url(#topFade)"' in svg
        assert 'fill="url(#bottomFade)"' in svg
        assert 'fill="url(#middleFade)"' not in svg


class TestFeeBadge:
    def test_fee_badge_present(self) -> None:
        svg = _compose_default(fees="$25")
        assert 'rx="28"' in svg
        assert "$25" in svg

    def test_fee_badge_absent_when_empty(self) -> None:
        svg = _compose_default(fees="")
        assert 'rx="28"' not in svg

    def test_fee_badge_width_clamped(self) -> None:
        # Short fees: width should be >= 140
        short_svg = _compose_default(fees="X")
        assert 'width="140"' in short_svg

        # Long fees: width should be <= 400
        long_svg = _compose_default(fees="A" * 30)
        assert 'width="400"' in long_svg


class TestAccentElements:
    def test_accent_line_present(self) -> None:
        svg = _compose_default()
        assert 'width="200"' in svg
        assert 'height="4"' in svg

    def test_accent_stripe_present(self) -> None:
        svg = _compose_default()
        assert 'y="1908"' in svg
        assert 'height="12"' in svg


class TestOrgCredit:
    def test_org_credit(self) -> None:
        svg = _compose_default(org="Events Co")
        assert "Presented by Events Co" in svg
        assert 'y="1840"' in svg


class TestXMLEscaping:
    def test_xml_escaping(self) -> None:
        svg = _compose_default(title="Rock & Roll <Live>")
        # Should contain escaped versions, NOT raw & or <
        # Title wraps across lines so check parts individually
        assert "&amp;" in svg
        assert "&lt;LIVE&gt;" in svg
        assert "ROCK &amp; ROLL" in svg
        assert "Rock & Roll <Live>" not in svg


class TestURL:
    def test_url_included_when_present(self) -> None:
        svg = _compose_default(url="https://example.com")
        assert "https://example.com" in svg

    def test_url_absent_when_none(self) -> None:
        svg = _compose_default(url=None)
        assert "example.com" not in svg
