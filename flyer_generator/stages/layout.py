"""LayoutResolver -- maps zone labels to pixel coordinates."""

from flyer_generator.models import LayoutZones, ResolvedLayout
from flyer_generator.zones import ZONE_COORDS


class LayoutResolver:
    """Translate zone labels into pixel coordinates and text anchors.

    Pure logic, no I/O, no side effects.
    """

    def resolve(self, zones: LayoutZones) -> ResolvedLayout:
        """Map each zone name in *zones* to its pixel coordinate via ZONE_COORDS.

        Phase 22 (FT-08): ``zones.details`` and ``zones.fee_badge`` are
        Optional[ZoneName] -- they are ``None`` for info-subtype flyers
        whose vision prompt omits those zones. When ``None``, the
        resolver passes ``None`` through to ``ResolvedLayout`` (which
        also relaxed those fields in Plan 02). The composer's
        ``layout.X is not None`` gates skip those rendering blocks.

        Parameters
        ----------
        zones:
            Zone assignments from vision evaluation.

        Returns
        -------
        ResolvedLayout with ZoneCoord for title + org_credit (always)
        and ZoneCoord-or-None for details + fee_badge (Optional,
        info-subtype-aware).
        """
        return ResolvedLayout(
            title=ZONE_COORDS[zones.title],
            details=(
                ZONE_COORDS[zones.details] if zones.details is not None else None
            ),
            fee_badge=(
                ZONE_COORDS[zones.fee_badge] if zones.fee_badge is not None else None
            ),
            org_credit=ZONE_COORDS[zones.org_credit],
        )
