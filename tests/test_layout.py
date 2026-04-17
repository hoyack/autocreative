"""Tests for flyer_generator.stages.layout -- LayoutResolver zone-to-pixel mapping."""

import pytest

from flyer_generator.models import LayoutZones, ResolvedLayout
from flyer_generator.stages.layout import LayoutResolver
from flyer_generator.zones import ZONE_COORDS, ZoneCoord


class TestLayoutResolver:
    """Verify LayoutResolver.resolve() maps every ZoneName to the correct ZoneCoord."""

    def setup_method(self) -> None:
        self.resolver = LayoutResolver()

    def test_resolve_typical_layout(self) -> None:
        """A realistic layout returns correct pixel coordinates."""
        zones = LayoutZones(
            title="TOP_CENTER",
            details="BOTTOM_LEFT",
            fee_badge="BOTTOM_RIGHT",
            org_credit="BOTTOM_CENTER",
        )
        result = self.resolver.resolve(zones)

        assert isinstance(result, ResolvedLayout)
        assert result.title == ZoneCoord(x=540, y=320, anchor="middle")
        assert result.details == ZoneCoord(x=180, y=1600, anchor="start")
        assert result.fee_badge == ZoneCoord(x=900, y=1600, anchor="end")
        assert result.org_credit == ZoneCoord(x=540, y=1600, anchor="middle")

    def test_resolve_all_same_zone(self) -> None:
        """All zones set to MIDDLE_CENTER produce identical coords."""
        zones = LayoutZones(
            title="MIDDLE_CENTER",
            details="MIDDLE_CENTER",
            fee_badge="MIDDLE_CENTER",
            org_credit="MIDDLE_CENTER",
        )
        result = self.resolver.resolve(zones)

        expected = ZoneCoord(x=540, y=960, anchor="middle")
        assert result.title == expected
        assert result.details == expected
        assert result.fee_badge == expected
        assert result.org_credit == expected

    def test_resolve_default_org_credit(self) -> None:
        """org_credit defaults to BOTTOM_CENTER when not specified."""
        zones = LayoutZones(
            title="TOP_LEFT",
            details="MIDDLE_RIGHT",
            fee_badge="TOP_RIGHT",
        )
        result = self.resolver.resolve(zones)

        assert result.org_credit == ZoneCoord(x=540, y=1600, anchor="middle")

    @pytest.mark.parametrize(
        "zone_name",
        [
            "TOP_LEFT",
            "TOP_CENTER",
            "TOP_RIGHT",
            "MIDDLE_LEFT",
            "MIDDLE_CENTER",
            "MIDDLE_RIGHT",
            "BOTTOM_LEFT",
            "BOTTOM_CENTER",
            "BOTTOM_RIGHT",
        ],
    )
    def test_resolve_each_zone_name(self, zone_name: str) -> None:
        """Every valid ZoneName produces the matching ZoneCoord from ZONE_COORDS."""
        zones = LayoutZones(
            title=zone_name,  # type: ignore[arg-type]
            details=zone_name,  # type: ignore[arg-type]
            fee_badge=zone_name,  # type: ignore[arg-type]
            org_credit=zone_name,  # type: ignore[arg-type]
        )
        result = self.resolver.resolve(zones)

        expected = ZONE_COORDS[zone_name]
        assert result.title == expected
        assert result.details == expected
        assert result.fee_badge == expected
        assert result.org_credit == expected

    def test_all_zone_names_covered(self) -> None:
        """ZONE_COORDS contains exactly 9 entries -- one per ZoneName."""
        assert len(ZONE_COORDS) == 9
        expected_names = {
            "TOP_LEFT", "TOP_CENTER", "TOP_RIGHT",
            "MIDDLE_LEFT", "MIDDLE_CENTER", "MIDDLE_RIGHT",
            "BOTTOM_LEFT", "BOTTOM_CENTER", "BOTTOM_RIGHT",
        }
        assert set(ZONE_COORDS.keys()) == expected_names

    def test_resolve_returns_resolved_layout_type(self) -> None:
        """Return type is ResolvedLayout (Pydantic model)."""
        zones = LayoutZones(
            title="TOP_LEFT",
            details="BOTTOM_RIGHT",
            fee_badge="MIDDLE_CENTER",
        )
        result = self.resolver.resolve(zones)
        assert isinstance(result, ResolvedLayout)
