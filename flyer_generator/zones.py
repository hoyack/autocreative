"""Zone grid definition and pixel coordinate mapping."""

from dataclasses import dataclass
from typing import Literal

# D-07: ZoneName is a Literal type with 9 values
ZoneName = Literal[
    "TOP_LEFT",
    "TOP_CENTER",
    "TOP_RIGHT",
    "MIDDLE_LEFT",
    "MIDDLE_CENTER",
    "MIDDLE_RIGHT",
    "BOTTOM_LEFT",
    "BOTTOM_CENTER",
    "BOTTOM_RIGHT",
]


# D-19: ZoneCoord is a frozen dataclass
@dataclass(frozen=True)
class ZoneCoord:
    """Pixel coordinate and text anchor for a zone position."""

    x: int
    y: int
    anchor: Literal["start", "middle", "end"]


# D-18, D-20: Zone pixel values from spec Section 6.6 and n8n workflow
ZONE_COORDS: dict[str, ZoneCoord] = {
    "TOP_LEFT":      ZoneCoord(x=180,  y=320,  anchor="start"),
    "TOP_CENTER":    ZoneCoord(x=540,  y=320,  anchor="middle"),
    "TOP_RIGHT":     ZoneCoord(x=900,  y=320,  anchor="end"),
    "MIDDLE_LEFT":   ZoneCoord(x=180,  y=960,  anchor="start"),
    "MIDDLE_CENTER": ZoneCoord(x=540,  y=960,  anchor="middle"),
    "MIDDLE_RIGHT":  ZoneCoord(x=900,  y=960,  anchor="end"),
    "BOTTOM_LEFT":   ZoneCoord(x=180,  y=1600, anchor="start"),
    "BOTTOM_CENTER": ZoneCoord(x=540,  y=1600, anchor="middle"),
    "BOTTOM_RIGHT":  ZoneCoord(x=900,  y=1600, anchor="end"),
}
