"""LayoutResolver -- maps zone labels to pixel coordinates."""

from flyer_generator.models import LayoutZones, ResolvedLayout
from flyer_generator.zones import ZONE_COORDS


class LayoutResolver:
    """Translate zone labels into pixel coordinates and text anchors.

    Pure logic, no I/O, no side effects.
    """

    def resolve(self, zones: LayoutZones) -> ResolvedLayout:
        """Map each zone name in *zones* to its pixel coordinate via ZONE_COORDS.

        Parameters
        ----------
        zones:
            Zone assignments from vision evaluation.

        Returns
        -------
        ResolvedLayout with ZoneCoord for title, details, fee_badge, org_credit.
        """
        return ResolvedLayout(
            title=ZONE_COORDS[zones.title],
            details=ZONE_COORDS[zones.details],
            fee_badge=ZONE_COORDS[zones.fee_badge],
            org_credit=ZONE_COORDS[zones.org_credit],
        )
