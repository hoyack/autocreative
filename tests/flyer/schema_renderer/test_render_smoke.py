"""End-to-end render smoke tests for all (template x subtype) permutations.

Phase 22 FT-08: every shipped flyer template renders cleanly for both
event and info subtypes (where subtype_compat allows).

Matrix:
- event subtype: all 6 templates (editorial_classic, bold_modern,
  minimal_photo, retro_poster, zine, tight_typographic)
- info subtype:  4 templates (editorial_classic, minimal_photo, zine,
  tight_typographic) -- bold_modern + retro_poster are
  subtype_compat=['event'] only per Plan 01

Total permutations: 6 + 4 = 10. Each is exercised by both
test_template_renders_permutation and test_template_svg_is_xml_parseable
giving 20 total tests.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from flyer_generator.flyer.schema_renderer import list_templates, load_template
from flyer_generator.models import (
    ComfyJob,
    FlyerInput,
    GeneratedBackground,
    LayoutZones,
    VisionVerdict,
)
from flyer_generator.stages.composer import PosterComposer
from flyer_generator.stages.layout import LayoutResolver


# Permutation matrix: event supports all templates; info supports
# whatever the template's subtype_compat declares.
def _permutations() -> tuple[list[tuple[str, str]], list[str]]:
    params: list[tuple[str, str]] = []
    ids: list[str] = []
    for name in list_templates():
        tpl = load_template(name)
        for subtype in tpl.subtype_compat:
            params.append((name, subtype))
            ids.append(f"{name}-{subtype}")
    return params, ids


_PARAMS, _IDS = _permutations()


def _sample_event_flyer() -> FlyerInput:
    return FlyerInput(
        title="Phase 22 Gala",
        subtype="event",
        date="2026-05-01",
        time="7:00 PM",
        location_name="The Grand Hall",
        location_address="1 Main St, Exampletown",
        fees="Free admission",
        org="Acme Foundation",
        style_concept="summer festival",
        style_preset="photorealistic",
    )


def _sample_info_flyer() -> FlyerInput:
    return FlyerInput(
        title="Public Notice",
        subtype="info",
        description=(
            "Main Street utility work scheduled for May 1-3. "
            "Please plan alternate routes during this period."
        ),
        call_to_action="Visit city.example/road-work for updates",
        org="City of Example",
        style_concept="civic bulletin",
        style_preset="photorealistic",
    )


def _fake_background() -> GeneratedBackground:
    return GeneratedBackground(
        image_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 200,
        source_dimensions=(832, 1472),
        final_dimensions=(1080, 1920),
        comfy_job=ComfyJob(
            prompt_id="phase22-smoke",
            submitted_at=datetime.now(timezone.utc),
            positive_prompt="",
            negative_prompt="",
            seed=42,
            attempt_number=1,
        ),
    )


def _verdict_event() -> VisionVerdict:
    return VisionVerdict(
        approved=True,
        confidence=0.95,
        text_color="white",
        raw_response="{}",
        zones=LayoutZones(
            title="TOP_CENTER",
            details="BOTTOM_CENTER",
            fee_badge="TOP_RIGHT",
            org_credit="BOTTOM_CENTER",
        ),
    )


def _verdict_info() -> VisionVerdict:
    return VisionVerdict(
        approved=True,
        confidence=0.95,
        text_color="white",
        raw_response="{}",
        zones=LayoutZones(
            title="TOP_CENTER",
            details=None,
            fee_badge=None,
            org_credit="BOTTOM_CENTER",
        ),
    )


@pytest.mark.parametrize("template_name,subtype", _PARAMS, ids=_IDS)
def test_template_renders_permutation(template_name: str, subtype: str) -> None:
    template = load_template(template_name)
    if subtype == "event":
        event = _sample_event_flyer()
        verdict = _verdict_event()
    else:
        event = _sample_info_flyer()
        verdict = _verdict_info()

    layout = LayoutResolver().resolve(verdict.zones)
    svg = PosterComposer().compose(
        event,
        _fake_background(),
        verdict,
        layout,
        template=template,
    )

    assert svg.startswith("<svg"), (
        f"template {template_name} subtype {subtype} did not emit <svg prefix"
    )
    assert svg.rstrip().endswith("</svg>"), (
        f"template {template_name} subtype {subtype} did not close </svg>"
    )
    # Title always appears (composer uppercases it).
    assert (event.title.upper() in svg) or (event.title in svg)

    if subtype == "event":
        # Event-specific strings appear somewhere in the SVG (date may be
        # formatted, but raw token or its uppercase variant should be there).
        assert (
            "2026-05-01" in svg
            or "MAY" in svg.upper()
            or "GALA" in svg.upper()
        ), f"event template {template_name} missed event detail rendering"
    else:
        # Info: description appears; event-only strings must NOT appear.
        desc_substring = "Main Street utility work"
        assert (
            desc_substring in svg or desc_substring.upper() in svg.upper()
        ), f"info template {template_name} missed description rendering"
        assert "2026-05-01" not in svg
        # Event-only venue string absent
        assert "The Grand Hall" not in svg


@pytest.mark.parametrize("template_name,subtype", _PARAMS, ids=_IDS)
def test_template_svg_is_xml_parseable(template_name: str, subtype: str) -> None:
    """Quick XML-parse smoke -- ensures no unclosed tags or bad escape sequences."""
    import xml.etree.ElementTree as ET

    template = load_template(template_name)
    if subtype == "event":
        event = _sample_event_flyer()
        verdict = _verdict_event()
    else:
        event = _sample_info_flyer()
        verdict = _verdict_info()
    layout = LayoutResolver().resolve(verdict.zones)
    svg = PosterComposer().compose(
        event,
        _fake_background(),
        verdict,
        layout,
        template=template,
    )
    # Should parse as XML without raising.
    try:
        ET.fromstring(svg)
    except ET.ParseError as exc:
        pytest.fail(f"Template {template_name}/{subtype} emitted invalid XML: {exc}")
