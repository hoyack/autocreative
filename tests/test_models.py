"""Tests for flyer_generator.models — all 7 Pydantic data contracts."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from flyer_generator.models import (
    ComfyJob,
    EventInput,
    FlyerOutput,
    GeneratedBackground,
    LayoutZones,
    ResolvedLayout,
    VisionVerdict,
)
from flyer_generator.zones import ZoneCoord


def _make_event(**overrides):
    defaults = {
        "title": "Test Event",
        "date": "Saturday, May 2, 2026",
        "time": "9:00 AM - 12:00 PM",
        "location_name": "Test Venue",
        "location_address": "123 Test St, City, ST 12345",
        "fees": "FREE",
        "org": "Test Org",
        "style_concept": "test concept",
        "style_preset": "photorealistic",
    }
    defaults.update(overrides)
    return EventInput(**defaults)


class TestEventInput:
    def test_event_input_valid(self):
        e = _make_event(color_accent="#FF5500")
        assert e.title == "Test Event"
        assert e.color_accent == "#FF5500"

    def test_event_input_default_color(self):
        e = _make_event()
        assert e.color_accent == "#F59E0B"

    def test_event_input_invalid_hex_color(self):
        with pytest.raises(ValidationError):
            _make_event(color_accent="notahex")

    def test_event_input_3digit_hex_rejected(self):
        with pytest.raises(ValidationError):
            _make_event(color_accent="#FFF")

    def test_event_input_title_max_length(self):
        with pytest.raises(ValidationError):
            _make_event(title="x" * 121)

    def test_event_input_optional_url(self):
        e1 = _make_event(url=None)
        assert e1.url is None
        e2 = _make_event(url="https://example.com")
        assert e2.url == "https://example.com"


class TestComfyJob:
    def test_comfy_job_fields(self):
        now = datetime.now(tz=timezone.utc)
        job = ComfyJob(
            prompt_id="abc-123",
            submitted_at=now,
            positive_prompt="a test prompt",
            negative_prompt="bad stuff",
            seed=42,
            attempt_number=1,
        )
        assert job.prompt_id == "abc-123"
        assert job.seed == 42
        assert job.attempt_number == 1


class TestGeneratedBackground:
    def test_generated_background_fields(self):
        now = datetime.now(tz=timezone.utc)
        job = ComfyJob(
            prompt_id="bg-1",
            submitted_at=now,
            positive_prompt="pos",
            negative_prompt="neg",
            seed=99,
            attempt_number=1,
        )
        bg = GeneratedBackground(
            image_bytes=b"\x89PNG",
            source_dimensions=(832, 1472),
            final_dimensions=(1080, 1920),
            comfy_job=job,
        )
        assert bg.source_dimensions == (832, 1472)
        assert bg.final_dimensions == (1080, 1920)


class TestLayoutZones:
    def test_layout_zones_valid(self):
        z = LayoutZones(title="TOP_LEFT", details="BOTTOM_CENTER", fee_badge="TOP_RIGHT")
        assert z.title == "TOP_LEFT"

    def test_layout_zones_invalid_zone(self):
        with pytest.raises(ValidationError):
            LayoutZones(title="INVALID_ZONE", details="BOTTOM_CENTER", fee_badge="TOP_RIGHT")

    def test_layout_zones_default_org_credit(self):
        z = LayoutZones(title="TOP_LEFT", details="BOTTOM_CENTER", fee_badge="TOP_RIGHT")
        assert z.org_credit == "BOTTOM_CENTER"


class TestVisionVerdict:
    def _make_zones(self):
        return LayoutZones(title="TOP_LEFT", details="BOTTOM_CENTER", fee_badge="TOP_RIGHT")

    def test_vision_verdict_approved_requires_zones(self):
        with pytest.raises(ValidationError):
            VisionVerdict(approved=True, confidence=0.9, raw_response="test", zones=None)

    def test_vision_verdict_rejected_no_zones_ok(self):
        v = VisionVerdict(
            approved=False,
            confidence=0.3,
            raw_response="rejected",
            rejection_reasons=["too busy"],
        )
        assert v.zones is None

    def test_vision_verdict_approved_with_zones(self):
        v = VisionVerdict(
            approved=True,
            confidence=0.9,
            zones=self._make_zones(),
            raw_response="looks good",
        )
        assert v.approved is True
        assert v.zones is not None

    def test_vision_verdict_confidence_bounds(self):
        with pytest.raises(ValidationError):
            VisionVerdict(approved=False, confidence=-0.1, raw_response="test")
        with pytest.raises(ValidationError):
            VisionVerdict(approved=False, confidence=1.1, raw_response="test")


class TestResolvedLayout:
    def test_resolved_layout_fields(self):
        rl = ResolvedLayout(
            title=ZoneCoord(x=180, y=320, anchor="start"),
            details=ZoneCoord(x=540, y=1600, anchor="middle"),
            fee_badge=ZoneCoord(x=900, y=320, anchor="end"),
            org_credit=ZoneCoord(x=540, y=1600, anchor="middle"),
        )
        assert rl.title.x == 180
        assert rl.org_credit.anchor == "middle"


class TestFlyerOutput:
    def test_flyer_output_save(self, tmp_path: Path):
        zones = LayoutZones(title="TOP_LEFT", details="BOTTOM_CENTER", fee_badge="TOP_RIGHT")
        verdict = VisionVerdict(
            approved=True,
            confidence=0.95,
            zones=zones,
            raw_response="good",
        )
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        output = FlyerOutput(
            png_bytes=png_data,
            dimensions=(1080, 1920),
            file_size_kb=1,
            event_title="Test",
            attempts_used=1,
            final_vision_verdict=verdict,
            zones_used=zones,
            trace_id="trace-123",
        )
        save_path = tmp_path / "subdir" / "flyer.png"
        output.save(save_path)
        assert save_path.exists()
        assert save_path.read_bytes() == png_data
