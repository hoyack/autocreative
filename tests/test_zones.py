"""Tests for flyer_generator.zones — zone grid definitions."""

import pytest

from flyer_generator.zones import ZONE_COORDS, ZoneCoord


class TestZoneCoords:
    def test_zone_coords_count(self):
        assert len(ZONE_COORDS) == 9

    def test_zone_coords_top_row_y(self):
        for name in ["TOP_LEFT", "TOP_CENTER", "TOP_RIGHT"]:
            assert ZONE_COORDS[name].y == 320

    def test_zone_coords_middle_row_y(self):
        for name in ["MIDDLE_LEFT", "MIDDLE_CENTER", "MIDDLE_RIGHT"]:
            assert ZONE_COORDS[name].y == 960

    def test_zone_coords_bottom_row_y(self):
        for name in ["BOTTOM_LEFT", "BOTTOM_CENTER", "BOTTOM_RIGHT"]:
            assert ZONE_COORDS[name].y == 1600

    def test_zone_coords_left_column_x(self):
        for name in ["TOP_LEFT", "MIDDLE_LEFT", "BOTTOM_LEFT"]:
            assert ZONE_COORDS[name].x == 180

    def test_zone_coords_center_column_x(self):
        for name in ["TOP_CENTER", "MIDDLE_CENTER", "BOTTOM_CENTER"]:
            assert ZONE_COORDS[name].x == 540

    def test_zone_coords_right_column_x(self):
        for name in ["TOP_RIGHT", "MIDDLE_RIGHT", "BOTTOM_RIGHT"]:
            assert ZONE_COORDS[name].x == 900

    def test_zone_coord_anchors(self):
        for name, coord in ZONE_COORDS.items():
            if "LEFT" in name:
                assert coord.anchor == "start"
            elif "CENTER" in name:
                assert coord.anchor == "middle"
            elif "RIGHT" in name:
                assert coord.anchor == "end"

    def test_zone_coord_frozen(self):
        coord = ZONE_COORDS["TOP_LEFT"]
        with pytest.raises(AttributeError):
            coord.x = 999  # type: ignore[misc]
