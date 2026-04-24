"""FlyerInput validation tests (Phase 22 FT-04).

Covers:
- FlyerInput minimal event-subtype validation (all event fields optional).
- FlyerInput info-subtype validation (description/call_to_action fields).
- subtype Literal enforcement.
- EventInput back-compat alias identity.
- Package-level re-export of FlyerInput and EventInput.
- LayoutZones relaxation: details/fee_badge optional for info flyers.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flyer_generator.models import EventInput, FlyerInput, LayoutZones


class TestFlyerInputDefaults:
    def test_minimal_event_flyer_validates(self) -> None:
        f = FlyerInput(
            title="T",
            org="Acme",
            style_concept="c",
            style_preset="photorealistic",
        )
        assert f.subtype == "event"
        assert f.date is None
        assert f.time is None
        assert f.location_name is None
        assert f.location_address is None
        assert f.fees is None

    def test_minimal_info_flyer_validates(self) -> None:
        f = FlyerInput(
            title="Notice",
            subtype="info",
            description="Road closure",
            org="City",
            style_concept="civic",
            style_preset="photorealistic",
        )
        assert f.subtype == "info"
        assert f.description == "Road closure"
        # Event-only fields remain None on info flyers.
        assert f.date is None
        assert f.fees is None

    def test_fully_populated_event_flyer(self) -> None:
        f = FlyerInput(
            title="Gala",
            subtype="event",
            date="2026-05-01",
            time="7pm",
            location_name="Hall",
            location_address="1 Main",
            fees="Free",
            org="Acme",
            style_concept="c",
            style_preset="photorealistic",
        )
        assert f.date == "2026-05-01"
        assert f.time == "7pm"
        assert f.fees == "Free"

    def test_bogus_subtype_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FlyerInput(
                title="T",
                subtype="bogus",  # type: ignore[arg-type]
                org="Acme",
                style_concept="c",
                style_preset="p",
            )

    def test_description_max_length(self) -> None:
        with pytest.raises(ValidationError):
            FlyerInput(
                title="T",
                subtype="info",
                description="a" * 601,
                org="Acme",
                style_concept="c",
                style_preset="p",
            )

    def test_call_to_action_accepted(self) -> None:
        f = FlyerInput(
            title="Service Launch",
            subtype="info",
            description="Now available",
            call_to_action="Visit our site",
            org="Acme",
            style_concept="c",
            style_preset="p",
        )
        assert f.call_to_action == "Visit our site"


class TestEventInputAlias:
    def test_alias_is_flyer_input(self) -> None:
        assert EventInput is FlyerInput

    def test_legacy_payload_still_validates(self) -> None:
        """Legacy callers passing the full event shape keep working."""
        data = {
            "title": "Legacy Event",
            "date": "2026-05-01",
            "time": "7:00 PM",
            "location_name": "The Hall",
            "location_address": "1 Main St",
            "fees": "Free",
            "org": "Acme",
            "style_concept": "summer",
            "style_preset": "photorealistic",
        }
        f = FlyerInput.model_validate(data)
        assert f.title == "Legacy Event"
        assert f.subtype == "event"


class TestPackageReExport:
    def test_flyer_input_importable_from_package(self) -> None:
        from flyer_generator import EventInput as EI
        from flyer_generator import FlyerInput as FI

        assert FI is EI
        assert FI is FlyerInput


class TestLayoutZonesRelaxation:
    def test_details_and_fee_badge_optional(self) -> None:
        z = LayoutZones(title="TOP_CENTER", org_credit="BOTTOM_CENTER")
        assert z.details is None
        assert z.fee_badge is None

    def test_info_flyer_zones(self) -> None:
        z = LayoutZones(title="TOP_CENTER", details=None, fee_badge=None)
        assert z.title == "TOP_CENTER"
        assert z.org_credit == "BOTTOM_CENTER"

    def test_event_flyer_zones(self) -> None:
        z = LayoutZones(
            title="TOP_CENTER",
            details="BOTTOM_CENTER",
            fee_badge="TOP_RIGHT",
            org_credit="BOTTOM_CENTER",
        )
        assert z.details == "BOTTOM_CENTER"
        assert z.fee_badge == "TOP_RIGHT"
