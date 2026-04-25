"""PosterComposer -- SVG composition engine.

Combines background image, text overlays, scrim gradients, fee badge,
accent elements, and org credit into a complete SVG document.

Ports the n8n "Compose Poster SVG" node logic 1:1 into Python.

Phase 22 (FT-03): `PosterComposer.compose()` accepts an optional
`template: FlyerTemplateSchema | None` keyword and reads typography /
scrim opacity / accent color from the template when supplied. When
`template is None`, the composer falls back to the Phase-21 hardcoded
values so existing CLI / direct-API callers remain byte-compatible.

The composer is also subtype-aware: when `event.subtype == "info"` it
skips the fee badge and details block, instead rendering
`event.description` and `event.call_to_action` in the title-adjacent
region.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from flyer_generator.errors import CompositionError
from flyer_generator.models import (
    FlyerInput,
    GeneratedBackground,
    ResolvedLayout,
    VisionVerdict,
)
from flyer_generator.zones import ZoneCoord  # noqa: F401  (kept for type-import users)

if TYPE_CHECKING:
    # Type-only import to avoid a runtime cycle: schema_renderer pulls in
    # brochure utilities and that chain need not load when composer is used
    # by callers who never pass a template.
    from flyer_generator.flyer.schema_renderer.schema_model import FlyerTemplateSchema


# Design coordinate system. Zone coords / scrims / accent stripe were
# authored against an 1080×1920 canvas; ``PosterComposer.canvas_width`` is
# parameterized but defaults to 1080 so existing call sites keep byte-
# identical output. Phase 24-02 moved the runtime canvas/margin from
# module-level constants into instance attributes (self._canvas_width and
# self._margin_px) so the poster pipeline can render at larger canvases.
_DESIGN_CANVAS_WIDTH = 1080
_DESIGN_CANVAS_HEIGHT = 1920
_DESIGN_MARGIN_PX = 60  # 60px margin on each side = text fits in 960px

# Hardcoded back-compat defaults (used when template is None) — match the
# Phase-21 behavior exactly so existing callers see byte-identical output.
_DEFAULT_HEADING_FAMILY = "'Arial Black', 'Helvetica Neue', Arial, sans-serif"
_DEFAULT_BODY_FAMILY = "Arial, sans-serif"
_DEFAULT_SCRIM_OPACITY_TOP = 0.75
_DEFAULT_SCRIM_OPACITY_BOTTOM = 0.85


def _title_params(
    title: str,
    anchor: str = "middle",
    anchor_x: int = 540,
    *,
    canvas_width: int = _DESIGN_CANVAS_WIDTH,
    margin_px: int = _DESIGN_MARGIN_PX,
) -> tuple[int, int]:
    """Return (font_size, max_chars_per_line) for the UPPERCASED title.

    D-06: measure AFTER .upper().
    Enforces margin safety: computes the actual available width from the
    anchor position to the nearest edge, then limits max_chars to fit.

    ``canvas_width`` and ``margin_px`` are kwargs so the composer can pass
    instance-level values (Phase 24-02). Their defaults preserve the
    pre-refactor behavior for any direct callers (the test suite imports
    this function directly).
    """
    length = len(title)
    if length <= 14:
        font_size, max_chars = 82, 14
    elif length <= 20:
        font_size, max_chars = 72, 20
    elif length <= 30:
        font_size, max_chars = 62, 18
    else:
        font_size, max_chars = 52, 22

    # Compute available width based on anchor position.
    # "start" text extends rightward from anchor_x to right margin.
    # "end" text extends leftward from anchor_x to left margin.
    # "middle" text extends both ways from anchor_x.
    if anchor == "start":
        available_width = (canvas_width - margin_px) - max(anchor_x, margin_px)
    elif anchor == "end":
        available_width = min(anchor_x, canvas_width - margin_px) - margin_px
    else:  # middle
        half_to_edge = min(anchor_x - margin_px, (canvas_width - margin_px) - anchor_x)
        available_width = half_to_edge * 2

    # Approx 0.75 * font_size per uppercase char (Arial Black is very wide,
    # plus letter-spacing: 2 adds ~2px per char)
    char_width_est = font_size * 0.75
    max_safe_chars = int(available_width / char_width_est)

    if max_chars > max_safe_chars:
        max_chars = max(max_safe_chars, 8)  # floor at 8 to avoid degenerate wrapping

    return font_size, max_chars


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Word-wrap *text* with widow-line merge.

    Ports the n8n wrapText function exactly:
    - Split words, accumulate lines by char count.
    - Widow-merge: if last line < 40% of previous line length, merge back.
    - If words <= 2, return [text] as a single line.

    Do NOT use textwrap.wrap (different breaking behavior, no widow merge).
    """
    words = text.split()
    if len(words) <= 2:
        return [text]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    # Widow merge: if last line < 40% of previous line length, merge back.
    if len(lines) >= 2:
        if len(lines[-1]) < 0.4 * len(lines[-2]):
            merged = f"{lines[-2]} {lines[-1]}"
            lines[-2] = merged
            lines.pop()

    return lines


def _get_scrim_zones(title_zone: str, details_zone: str | None) -> set[str]:
    """Return set of row names needing scrims (e.g., {"TOP", "BOTTOM"}).

    D-09: extract row via split('_')[0] from both zone names. When
    `details_zone` is None (info subtype), only the title-zone row is
    considered — info flyers have a single content cluster.
    """
    rows: set[str] = set()
    rows.add(title_zone.split("_")[0])
    if details_zone is not None:
        rows.add(details_zone.split("_")[0])
    return rows


def _select_layout_variant(title_row: str, details_row: str, title_col: str) -> str:
    """Select a visual layout variant based on zone placement pattern.

    Returns one of: "centered", "editorial", "sidebar", "minimal".
    Different zone combos naturally produce different visual treatments.
    """
    if title_row == "TOP" and details_row == "BOTTOM" and title_col == "CENTER":
        return "centered"  # classic poster: title top-center, details bottom
    if title_col == "LEFT":
        return "sidebar"  # left-aligned title gets vertical accent bar
    if title_row == details_row:
        return "minimal"  # same row = tight layout, keep decorations small
    return "editorial"  # everything else gets the full-width editorial line


def _gradient_defs(fade_color: str, scrim_top: float, scrim_bottom: float) -> str:
    """Build SVG <defs> block with topFade, bottomFade, middleFade gradients.

    `scrim_top` / `scrim_bottom` are 0..1 opacity values. The middle radial
    fade keeps its hardcoded 0.6 because templates do not declare a
    middle-scrim opacity (only top/bottom).
    """
    return (
        "<defs>"
        f'<linearGradient id="topFade" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="rgba({fade_color},{scrim_top})"/>'
        f'<stop offset="100%" stop-color="rgba({fade_color},0)"/>'
        "</linearGradient>"
        f'<linearGradient id="bottomFade" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="rgba({fade_color},0)"/>'
        f'<stop offset="100%" stop-color="rgba({fade_color},{scrim_bottom})"/>'
        "</linearGradient>"
        f'<radialGradient id="middleFade" cx="0.5" cy="0.5" r="0.6">'
        f'<stop offset="0%" stop-color="rgba({fade_color},0.6)"/>'
        f'<stop offset="100%" stop-color="rgba({fade_color},0)"/>'
        "</radialGradient>"
        "</defs>"
    )


class PosterComposer:
    """SVG composition engine.

    Combines background image, text overlays, scrim gradients, fee badge,
    accent elements, and org credit into a complete SVG poster.

    Phase 22: composer is template-driven (typography / scrim / accent
    read from `FlyerTemplateSchema` when supplied) and subtype-aware
    (info flyers render description + call_to_action instead of date /
    time / venue / fees).

    Phase 24-02: composer accepts a ``canvas_width`` constructor kwarg
    (default 1080 — flyer canvas; preserves Phase 21–23 byte-identical
    output for the no-arg call site). When called with a larger canvas
    (e.g. 5400 for an 18×24" poster at 300 DPI), the margin scales
    proportionally as ``canvas_width × 60 / 1080`` and the SVG outer
    width / height / viewBox + scaled positions follow suit. Layout
    zones still come from the 1080×1920 design grid (zones.py); the
    rasterizer takes the final pixel dimensions, so absolute pixel
    coordinates inside the SVG remain consistent with that grid for
    canvas_width=1080. For other canvas widths a scale factor is
    applied to all SVG positions / sizes derived from the design grid.
    """

    def __init__(self, canvas_width: int = 1080) -> None:
        """Construct a PosterComposer for ``canvas_width``-pixel-wide output.

        Args:
            canvas_width: Output SVG width in pixels. Defaults to 1080
                (the flyer canvas) for back-compat. ``self._margin_px`` is
                derived as ``round(canvas_width × 60 / 1080)`` so the
                relative margin stays constant across sizes.
        """
        self._canvas_width = canvas_width
        # Margin scales proportionally to keep the visual ratio constant.
        self._margin_px = round(canvas_width * _DESIGN_MARGIN_PX / _DESIGN_CANVAS_WIDTH)
        # Canvas height derives from the design 1080:1920 ratio. The
        # rasterizer is the source of truth for the final raster
        # dimensions (cairosvg's output_width / output_height override
        # the SVG width / height attributes).
        self._canvas_height = round(
            canvas_width * _DESIGN_CANVAS_HEIGHT / _DESIGN_CANVAS_WIDTH
        )
        # Scale factor applied to design-grid coords (zones, scrim
        # positions, accent stripe, org credit) when emitting SVG.
        self._scale = canvas_width / _DESIGN_CANVAS_WIDTH

    # ------------------------------------------------------------------
    # Template helpers — back-compat fallbacks when template is None
    # ------------------------------------------------------------------

    @staticmethod
    def _template_heading_family(template: "FlyerTemplateSchema | None") -> str:
        if template is None:
            return _DEFAULT_HEADING_FAMILY
        return template.typography.heading_family

    @staticmethod
    def _template_body_family(template: "FlyerTemplateSchema | None") -> str:
        if template is None:
            return _DEFAULT_BODY_FAMILY
        return template.typography.body_family

    @staticmethod
    def _template_scrim_opacity(
        template: "FlyerTemplateSchema | None", position: str
    ) -> float:
        """`position` is 'top' or 'bottom'. Returns a 0..1 opacity value."""
        if template is None:
            return (
                _DEFAULT_SCRIM_OPACITY_TOP
                if position == "top"
                else _DEFAULT_SCRIM_OPACITY_BOTTOM
            )
        if position == "top":
            return float(template.palette.scrim_opacity_top)
        return float(template.palette.scrim_opacity_bottom)

    @staticmethod
    def _template_accent(
        template: "FlyerTemplateSchema | None", event_accent: str
    ) -> str:
        """Template accent wins over `event.color_accent` when supplied."""
        if template is None:
            return event_accent
        return template.palette.accent_default

    @staticmethod
    def _template_cover_title_size(
        template: "FlyerTemplateSchema | None", default_size: int
    ) -> int:
        """When `template` is supplied, its `cover_title_size` overrides the
        length-bucket default returned by `_title_params`. When None, the
        bucket default is returned unchanged.
        """
        if template is None:
            return default_size
        return int(template.typography.cover_title_size)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose(
        self,
        event: FlyerInput,
        background: GeneratedBackground,
        verdict: VisionVerdict,
        layout: ResolvedLayout,
        *,
        template: "FlyerTemplateSchema | None" = None,
    ) -> str:
        """Build a complete SVG poster string.

        Parameters
        ----------
        event:
            Structured flyer input (event or info subtype).
        background:
            Generated background image with raw bytes.
        verdict:
            Vision evaluation result with text_color and zone assignments.
        layout:
            Pixel-resolved zone coordinates for title, details, fee_badge,
            org_credit.
        template:
            Optional flyer template providing typography / scrim / accent
            overrides. When None, the composer uses Phase-21 hardcoded
            defaults (back-compat).

        Returns
        -------
        Complete SVG string ready for rasterization.

        Raises
        ------
        CompositionError
            On any unexpected failure during SVG assembly.
        """
        try:
            return self._build_svg(event, background, verdict, layout, template=template)
        except CompositionError:
            raise
        except Exception as exc:
            msg = f"SVG composition failed: {exc}"
            raise CompositionError(msg) from exc

    # ------------------------------------------------------------------
    # Internal builder
    # ------------------------------------------------------------------

    def _build_svg(
        self,
        event: FlyerInput,
        background: GeneratedBackground,
        verdict: VisionVerdict,
        layout: ResolvedLayout,
        *,
        template: "FlyerTemplateSchema | None" = None,
    ) -> str:
        is_info = event.subtype == "info"

        # ----- a. XML-escape all user strings (COMP-08 guard) -----
        # Title: uppercase FIRST, then escape (escaping after upper would
        # corrupt entities like &amp; -> &AMP;).
        title_upper = escape(event.title.upper())
        # Optional event fields (None on info flyers per Plan 02).
        date_esc = escape(event.date) if event.date else ""
        time_esc = escape(event.time) if event.time else ""
        venue_esc = escape(event.location_name) if event.location_name else ""
        address_esc = escape(event.location_address) if event.location_address else ""
        fees_esc = escape(event.fees) if event.fees else ""
        org_esc = escape(event.org)
        url_esc = escape(event.url) if event.url is not None else None
        # Info-only fields (None on event flyers).
        description_esc = escape(event.description) if event.description else ""
        cta_esc = escape(event.call_to_action) if event.call_to_action else ""

        # ----- b. Derive colors -----
        if verdict.text_color == "white":
            text_color = "#ffffff"
            stroke_color = "rgba(0,0,0,0.5)"
            subtle_color = "rgba(255,255,255,0.85)"
            fade_color = "0,0,0"
        else:
            text_color = "#1a1a1a"
            stroke_color = "rgba(255,255,255,0.4)"
            subtle_color = "rgba(26,26,26,0.75)"
            fade_color = "255,255,255"

        # Template-driven accent wins over event.color_accent.
        accent_color = self._template_accent(template, event.color_accent)

        # Template-driven typography
        title_font = self._template_heading_family(template)
        body_font = self._template_body_family(template)

        # ----- c. Base64-encode background -----
        b64_bg = base64.b64encode(background.image_bytes).decode("ascii")

        # ----- d. Build title block -----
        t_anchor = layout.title.anchor
        bucket_font_size, max_chars = _title_params(
            title_upper,
            t_anchor,
            layout.title.x,
            canvas_width=_DESIGN_CANVAS_WIDTH,
            margin_px=_DESIGN_MARGIN_PX,
        )
        # Template's cover_title_size overrides the bucket default when supplied.
        font_size = self._template_cover_title_size(template, bucket_font_size)
        lines = _wrap_text(title_upper, max_chars)
        line_height = font_size * 1.25
        total_height = len(lines) * line_height
        start_y = layout.title.y - (total_height / 2) + font_size * 0.8

        # Clamp title x to respect safe margins (in design-grid coords; the
        # SVG output is scaled at the end so the design coords stay 1080-wide).
        tx = layout.title.x
        if t_anchor == "start":
            tx = max(tx, _DESIGN_MARGIN_PX)
        elif t_anchor == "end":
            tx = min(tx, _DESIGN_CANVAS_WIDTH - _DESIGN_MARGIN_PX)

        title_elements: list[str] = []
        for i, line in enumerate(lines):
            ly = start_y + i * line_height
            title_elements.append(
                f'<text x="{tx}" y="{ly:.1f}" text-anchor="{t_anchor}" '
                f'font-family="{title_font}" font-size="{font_size}" '
                f'font-weight="900" letter-spacing="2" '
                f'fill="{text_color}" '
                f'paint-order="stroke" stroke="{stroke_color}" stroke-width="3">'
                f"{line}</text>"
            )

        # ----- e. Build accent decoration -----
        # Select layout variant based on zone placement pattern.
        # For info flyers (no details zone), default to "centered" if the
        # title is centered, otherwise "minimal" — info flyers don't have
        # the title<->details axis the heuristic was designed around.
        title_row = verdict.zones.title.split("_")[0]
        title_col = verdict.zones.title.split("_")[1]
        if verdict.zones.details is not None:
            details_row = verdict.zones.details.split("_")[0]
            layout_variant = _select_layout_variant(title_row, details_row, title_col)
        else:
            # Info flyer — pick a sensible default that doesn't depend on details.
            if title_col == "LEFT":
                layout_variant = "sidebar"
            elif title_row == "TOP" and title_col == "CENTER":
                layout_variant = "centered"
            else:
                layout_variant = "minimal"

        accent_line_y = start_y + (len(lines) - 1) * line_height + 20

        if layout_variant == "centered":
            # Classic centered line under title
            accent_line_x = (
                tx - 100 if t_anchor == "middle" else (tx if t_anchor == "start" else tx - 200)
            )
            accent_line = (
                f'<rect x="{accent_line_x}" y="{accent_line_y:.1f}" '
                f'width="200" height="4" rx="2" '
                f'fill="{accent_color}" opacity="0.9"/>'
            )
        elif layout_variant == "editorial":
            # Thin full-width line with accent dot (design-grid coords).
            accent_line = (
                f'<line x1="{_DESIGN_MARGIN_PX}" y1="{accent_line_y:.1f}" '
                f'x2="{_DESIGN_CANVAS_WIDTH - _DESIGN_MARGIN_PX}" y2="{accent_line_y:.1f}" '
                f'stroke="{accent_color}" stroke-width="1.5" opacity="0.6"/>'
                f'<circle cx="{tx}" cy="{accent_line_y:.1f}" r="4" '
                f'fill="{accent_color}" opacity="0.9"/>'
            )
        elif layout_variant == "sidebar":
            # Vertical accent bar to the left of title (design-grid coords).
            bar_x = (
                tx - 20
                if t_anchor == "start"
                else (tx - max(len(lines[0]) * font_size * 0.65 / 2, 100) - 20)
            )
            accent_line = (
                f'<rect x="{max(bar_x, _DESIGN_MARGIN_PX - 20):.0f}" '
                f'y="{start_y - font_size * 0.3:.1f}" '
                f'width="4" height="{total_height + 10:.1f}" rx="2" '
                f'fill="{accent_color}" opacity="0.9"/>'
            )
        else:  # "minimal"
            # Small dash under title, understated
            dash_w = 80
            accent_line_x = (
                tx - dash_w / 2
                if t_anchor == "middle"
                else (tx if t_anchor == "start" else tx - dash_w)
            )
            accent_line = (
                f'<rect x="{accent_line_x:.0f}" y="{accent_line_y:.1f}" '
                f'width="{dash_w}" height="3" rx="1.5" '
                f'fill="{accent_color}" opacity="0.7"/>'
            )

        # ----- f. Build details block (event subtype only) -----
        # Subtype gate: info flyers never render the details block, even if
        # layout.details happens to be populated. Defensive: also check
        # `layout.details is None` (post-Plan-02 LayoutZones relaxation).
        details_elements: list[str] = []
        if not is_info and layout.details is not None:
            details_elements = self._build_details_elements(
                layout=layout,
                layout_variant=layout_variant,
                date_esc=date_esc,
                time_esc=time_esc,
                venue_esc=venue_esc,
                address_esc=address_esc,
                url_esc=url_esc,
                text_color=text_color,
                subtle_color=subtle_color,
                accent_color=accent_color,
                body_font=body_font,
            )

        # ----- f.1 Build description block (info subtype only) -----
        description_elements: list[str] = []
        if is_info:
            description_elements = self._build_info_description_elements(
                event=event,
                layout=layout,
                template=template,
                text_color=text_color,
                subtle_color=subtle_color,
                body_font=body_font,
                title_bottom_y=start_y + (len(lines) - 1) * line_height + font_size,
                description_esc=description_esc,
                cta_esc=cta_esc,
            )

        # ----- g. Build fee badge (event subtype only) -----
        # Subtype gate: info flyers never render fee badges. Defensive:
        # also gate on `layout.fee_badge is None` and on empty fees_esc.
        fee_elements: list[str] = []
        if not is_info and layout.fee_badge is not None and fees_esc:
            badge_width = max(min(len(fees_esc) * 22 + 60, 400), 140)
            badge_height = 56
            badge_rx = 28
            fee_font_size = 22 if len(fees_esc) > 15 else 30

            fx = layout.fee_badge.x
            fy = layout.fee_badge.y
            f_anchor = layout.fee_badge.anchor

            # Collision avoidance: if badge and title share same zone row,
            # push badge below the title block + accent line
            title_bottom = start_y + (len(lines) - 1) * line_height + font_size
            if abs(fy - layout.title.y) < 50:
                fy = title_bottom + 40

            if f_anchor == "middle":
                badge_x = fx - badge_width / 2
            elif f_anchor == "start":
                badge_x = fx
            else:  # end
                badge_x = fx - badge_width

            badge_y = fy - 28
            badge_center_x = badge_x + badge_width / 2

            fee_elements.append(
                f'<rect x="{badge_x:.0f}" y="{badge_y}" '
                f'width="{badge_width}" height="{badge_height}" '
                f'rx="{badge_rx}" '
                f'fill="{accent_color}"/>'
            )
            fee_elements.append(
                f'<text x="{badge_center_x:.0f}" y="{fy + 8}" text-anchor="middle" '
                f'font-family="{body_font}" font-size="{fee_font_size}" '
                f'font-weight="bold" fill="#1a1a1a">{fees_esc}</text>'
            )

        # ----- h. Build org credit -----
        org_credit = (
            f'<text x="540" y="1840" text-anchor="middle" '
            f'font-family="{body_font}" font-size="20" '
            f'fill="{text_color}" opacity="0.55">'
            f"Presented by {org_esc}</text>"
        )

        # ----- i. Build scrims -----
        assert verdict.zones is not None
        scrim_rows = _get_scrim_zones(verdict.zones.title, verdict.zones.details)
        scrim_elements: list[str] = []
        if "TOP" in scrim_rows:
            scrim_elements.append(
                '<rect x="0" y="0" width="1080" height="700" '
                'fill="url(#topFade)"/>'
            )
        if "BOTTOM" in scrim_rows:
            scrim_elements.append(
                '<rect x="0" y="1220" width="1080" height="700" '
                'fill="url(#bottomFade)"/>'
            )
        if "MIDDLE" in scrim_rows:
            scrim_elements.append(
                '<rect x="0" y="600" width="1080" height="720" '
                'fill="url(#middleFade)"/>'
            )

        # ----- j. Build accent stripe -----
        accent_stripe = (
            f'<rect x="0" y="1908" width="1080" height="12" '
            f'fill="{accent_color}" opacity="0.8"/>'
        )

        # ----- k. Assemble final SVG -----
        defs = _gradient_defs(
            fade_color,
            scrim_top=self._template_scrim_opacity(template, "top"),
            scrim_bottom=self._template_scrim_opacity(template, "bottom"),
        )

        bg_image = (
            f'<image href="data:image/png;base64,{b64_bg}" '
            f'width="1080" height="1920" '
            f'preserveAspectRatio="xMidYMid slice"/>'
        )

        # Subtype dispatch for the content block list:
        # - event: title + accent_line + details + fee_elements
        # - info:  title + accent_line + description (no details, no fee)
        if is_info:
            content_blocks = title_elements + [accent_line] + description_elements
        else:
            content_blocks = (
                title_elements + [accent_line] + details_elements + fee_elements
            )

        # SVG outer width / height scale with self._canvas_width while the
        # viewBox stays in design-grid coords (0 0 1080 1920) so all interior
        # coordinates (zones, scrims, accent stripe, bg image, org credit)
        # keep producing byte-identical output at canvas_width=1080. For
        # larger canvases the cairosvg rasterizer's output_width /
        # output_height (set by Rasterizer.__init__) is the source of truth
        # for the final raster dimensions.
        parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{self._canvas_width}" height="{self._canvas_height}" '
            f'viewBox="0 0 {_DESIGN_CANVAS_WIDTH} {_DESIGN_CANVAS_HEIGHT}">',
            defs,
            bg_image,
            *scrim_elements,
            *content_blocks,
            org_credit,
            accent_stripe,
            "</svg>",
        ]

        return "".join(parts)

    # ------------------------------------------------------------------
    # Per-block helpers
    # ------------------------------------------------------------------

    def _build_details_elements(
        self,
        *,
        layout: ResolvedLayout,
        layout_variant: str,
        date_esc: str,
        time_esc: str,
        venue_esc: str,
        address_esc: str,
        url_esc: str | None,
        text_color: str,
        subtle_color: str,
        accent_color: str,
        body_font: str,
    ) -> list[str]:
        """Build the date/time/venue/address details block (event flyers).

        Body fields use the template's `body_family` (or hardcoded default).
        The date stays in the heading family by tradition (it's the
        prominent inverse of the title); only the secondary lines consume
        `body_font`.
        """
        assert layout.details is not None  # caller guards
        dx = layout.details.x
        dy = layout.details.y
        d_anchor = layout.details.anchor

        # Separator style varies with layout variant
        if d_anchor == "middle":
            sep_x = dx - 70
        elif d_anchor == "end":
            sep_x = dx - 140
        else:
            sep_x = dx

        # Clamp details x to safe margins (design-grid coords).
        if d_anchor == "start":
            dx = max(dx, _DESIGN_MARGIN_PX)
            sep_x = dx
        elif d_anchor == "end":
            dx = min(dx, _DESIGN_CANVAS_WIDTH - _DESIGN_MARGIN_PX)
            sep_x = dx - 140

        if layout_variant == "editorial":
            separator = (
                f'<line x1="{sep_x}" y1="{dy + 42}" '
                f'x2="{sep_x + 140}" y2="{dy + 42}" '
                f'stroke="{accent_color}" stroke-width="1.5" opacity="0.5"/>'
            )
        elif layout_variant == "sidebar":
            separator = (
                f'<rect x="{dx - 4 if d_anchor == "start" else sep_x}" y="{dy + 35}" '
                f'width="3" height="100" rx="1.5" '
                f'fill="{accent_color}" opacity="0.4"/>'
            )
        else:
            separator = (
                f'<rect x="{sep_x}" y="{dy + 42}" '
                f'width="140" height="2" rx="1" '
                f'fill="{text_color}" opacity="0.3"/>'
            )

        elements: list[str] = [
            # date — kept in the heading-feel family for visual emphasis
            f'<text x="{dx}" y="{dy - 40}" text-anchor="{d_anchor}" '
            f"font-family=\"'Arial Black', Arial, sans-serif\" font-size=\"40\" "
            f'font-weight="bold" letter-spacing="1" '
            f'fill="{text_color}">{date_esc}</text>',
            # time — body family
            f'<text x="{dx}" y="{dy + 15}" text-anchor="{d_anchor}" '
            f'font-family="{body_font}" font-size="34" '
            f'fill="{subtle_color}">{time_esc}</text>',
            # separator
            separator,
            # venue — body family
            f'<text x="{dx}" y="{dy + 90}" text-anchor="{d_anchor}" '
            f'font-family="{body_font}" font-size="30" '
            f'font-weight="bold" opacity="0.95" '
            f'fill="{text_color}">{venue_esc}</text>',
            # address — body family
            f'<text x="{dx}" y="{dy + 130}" text-anchor="{d_anchor}" '
            f'font-family="{body_font}" font-size="24" '
            f'fill="{subtle_color}">{address_esc}</text>',
        ]

        if url_esc is not None:
            elements.append(
                f'<text x="{dx}" y="{dy + 210}" text-anchor="{d_anchor}" '
                f'font-family="{body_font}" font-size="22" '
                f'fill="{subtle_color}">{url_esc}</text>'
            )

        return elements

    def _build_info_description_elements(
        self,
        *,
        event: FlyerInput,
        layout: ResolvedLayout,
        template: "FlyerTemplateSchema | None",
        text_color: str,
        subtle_color: str,
        body_font: str,
        title_bottom_y: float,
        description_esc: str,
        cta_esc: str,
    ) -> list[str]:
        """Build SVG elements for an info flyer's description + CTA.

        Rendered in the title zone region, anchored below the title's
        bottom edge. Uses `template.typography.body_family` (already in
        `body_font`) and `template.typography.body_size` /
        `body_line_height` when a template is supplied; falls back to
        sensible defaults otherwise. Description text is XML-escaped by
        the caller (passed in as `description_esc`).
        """
        if not description_esc and not cta_esc:
            return []

        # Template-driven body sizing (with back-compat fallbacks).
        if template is not None:
            body_size = int(template.typography.body_size)
            line_height = int(template.typography.body_line_height)
            max_chars_per_line = int(template.typography.body_max_chars_per_line)
        else:
            body_size = 34
            line_height = 44
            max_chars_per_line = 32

        # Anchor description below the title, with breathing room.
        anchor = layout.title.anchor
        anchor_x = layout.title.x
        # Clamp x to safe margins to mirror title clamping (design-grid coords).
        if anchor == "start":
            anchor_x = max(anchor_x, _DESIGN_MARGIN_PX)
        elif anchor == "end":
            anchor_x = min(anchor_x, _DESIGN_CANVAS_WIDTH - _DESIGN_MARGIN_PX)

        # Start ~80px below the title's bottom edge (room for accent line).
        y0 = title_bottom_y + 80

        elements: list[str] = []

        if description_esc:
            # Wrap on the escaped string so we don't break entity sequences.
            # XML entities (&amp;, &lt;, ...) include no whitespace, so
            # word-boundary wrapping at spaces stays safe.
            wrapped = _wrap_text(description_esc, max_chars_per_line)
            for i, line in enumerate(wrapped):
                ly = y0 + i * line_height
                elements.append(
                    f'<text x="{anchor_x}" y="{ly:.1f}" text-anchor="{anchor}" '
                    f'font-family="{body_font}" font-size="{body_size}" '
                    f'fill="{text_color}" opacity="0.95">{line}</text>'
                )
            cta_y0 = y0 + len(wrapped) * line_height + line_height  # blank line spacer
        else:
            cta_y0 = y0

        if cta_esc:
            cta_size = body_size + 4  # mild emphasis
            wrapped_cta = _wrap_text(cta_esc, max_chars_per_line)
            for i, line in enumerate(wrapped_cta):
                ly = cta_y0 + i * line_height
                elements.append(
                    f'<text x="{anchor_x}" y="{ly:.1f}" text-anchor="{anchor}" '
                    f'font-family="{body_font}" font-size="{cta_size}" '
                    f'font-weight="bold" '
                    f'fill="{text_color}">{line}</text>'
                )

        return elements
