"""PosterComposer -- SVG composition engine.

Combines background image, text overlays, scrim gradients, fee badge,
accent elements, and org credit into a complete SVG document.

Ports the n8n "Compose Poster SVG" node logic 1:1 into Python.
"""

from __future__ import annotations

import base64
from xml.sax.saxutils import escape

from flyer_generator.errors import CompositionError
from flyer_generator.models import (
    EventInput,
    GeneratedBackground,
    ResolvedLayout,
    VisionVerdict,
)
from flyer_generator.zones import ZoneCoord


# Safe margins: text must stay within this horizontal band (px from each edge)
_CANVAS_WIDTH = 1080
_MARGIN_PX = 60  # 60px margin on each side = text fits in 960px


def _title_params(title: str, anchor: str = "middle", anchor_x: int = 540) -> tuple[int, int]:
    """Return (font_size, max_chars_per_line) for the UPPERCASED title.

    D-06: measure AFTER .upper().
    Enforces margin safety: computes the actual available width from the
    anchor position to the nearest edge, then limits max_chars to fit.
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
        available_width = (_CANVAS_WIDTH - _MARGIN_PX) - max(anchor_x, _MARGIN_PX)
    elif anchor == "end":
        available_width = min(anchor_x, _CANVAS_WIDTH - _MARGIN_PX) - _MARGIN_PX
    else:  # middle
        half_to_edge = min(anchor_x - _MARGIN_PX, (_CANVAS_WIDTH - _MARGIN_PX) - anchor_x)
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


def _get_scrim_zones(title_zone: str, details_zone: str) -> set[str]:
    """Return set of row names needing scrims (e.g., {"TOP", "BOTTOM"}).

    D-09: extract row via split('_')[0] from both zone names.
    """
    rows: set[str] = set()
    rows.add(title_zone.split("_")[0])
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


def _gradient_defs(fade_color: str) -> str:
    """Build SVG <defs> block with topFade, bottomFade, middleFade gradients."""
    return (
        "<defs>"
        f'<linearGradient id="topFade" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="rgba({fade_color},0.75)"/>'
        f'<stop offset="100%" stop-color="rgba({fade_color},0)"/>'
        "</linearGradient>"
        f'<linearGradient id="bottomFade" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="rgba({fade_color},0)"/>'
        f'<stop offset="100%" stop-color="rgba({fade_color},0.85)"/>'
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
    accent elements, and org credit into a complete 1080x1920 SVG.
    """

    def compose(
        self,
        event: EventInput,
        background: GeneratedBackground,
        verdict: VisionVerdict,
        layout: ResolvedLayout,
    ) -> str:
        """Build a complete SVG poster string.

        Parameters
        ----------
        event:
            Structured event data (title, date, time, venue, fees, etc.).
        background:
            Generated background image with raw bytes.
        verdict:
            Vision evaluation result with text_color and zone assignments.
        layout:
            Pixel-resolved zone coordinates for title, details, fee_badge, org_credit.

        Returns
        -------
        Complete SVG string ready for rasterization.

        Raises
        ------
        CompositionError
            On any unexpected failure during SVG assembly.
        """
        try:
            return self._build_svg(event, background, verdict, layout)
        except CompositionError:
            raise
        except Exception as exc:
            msg = f"SVG composition failed: {exc}"
            raise CompositionError(msg) from exc

    def _build_svg(
        self,
        event: EventInput,
        background: GeneratedBackground,
        verdict: VisionVerdict,
        layout: ResolvedLayout,
    ) -> str:
        # ----- a. XML-escape all user strings -----
        # Title: uppercase FIRST, then escape (escaping after upper would
        # corrupt entities like &amp; -> &AMP;).
        title_upper = escape(event.title.upper())
        date_esc = escape(event.date)
        time_esc = escape(event.time)
        venue_esc = escape(event.location_name)
        address_esc = escape(event.location_address)
        fees_esc = escape(event.fees)
        org_esc = escape(event.org)
        url_esc = escape(event.url) if event.url is not None else None

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

        accent_color = event.color_accent

        # ----- c. Base64-encode background -----
        b64_bg = base64.b64encode(background.image_bytes).decode("ascii")

        # ----- d. Build title block -----
        t_anchor = layout.title.anchor
        font_size, max_chars = _title_params(title_upper, t_anchor, layout.title.x)
        lines = _wrap_text(title_upper, max_chars)
        line_height = font_size * 1.25
        total_height = len(lines) * line_height
        start_y = layout.title.y - (total_height / 2) + font_size * 0.8

        # Clamp title x to respect safe margins
        tx = layout.title.x
        if t_anchor == "start":
            tx = max(tx, _MARGIN_PX)
        elif t_anchor == "end":
            tx = min(tx, _CANVAS_WIDTH - _MARGIN_PX)

        title_font = "'Arial Black', 'Helvetica Neue', Arial, sans-serif"
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
        # Select layout variant based on zone placement pattern
        title_row = verdict.zones.title.split("_")[0]
        details_row = verdict.zones.details.split("_")[0]
        title_col = verdict.zones.title.split("_")[1]
        layout_variant = _select_layout_variant(title_row, details_row, title_col)

        accent_line_y = start_y + (len(lines) - 1) * line_height + 20

        if layout_variant == "centered":
            # Classic centered line under title
            accent_line_x = tx - 100 if t_anchor == "middle" else (tx if t_anchor == "start" else tx - 200)
            accent_line = (
                f'<rect x="{accent_line_x}" y="{accent_line_y:.1f}" '
                f'width="200" height="4" rx="2" '
                f'fill="{accent_color}" opacity="0.9"/>'
            )
        elif layout_variant == "editorial":
            # Thin full-width line with accent dot
            accent_line = (
                f'<line x1="{_MARGIN_PX}" y1="{accent_line_y:.1f}" '
                f'x2="{_CANVAS_WIDTH - _MARGIN_PX}" y2="{accent_line_y:.1f}" '
                f'stroke="{accent_color}" stroke-width="1.5" opacity="0.6"/>'
                f'<circle cx="{tx}" cy="{accent_line_y:.1f}" r="4" '
                f'fill="{accent_color}" opacity="0.9"/>'
            )
        elif layout_variant == "sidebar":
            # Vertical accent bar to the left of title
            bar_x = tx - 20 if t_anchor == "start" else (tx - max(len(lines[0]) * font_size * 0.65 / 2, 100) - 20)
            accent_line = (
                f'<rect x="{max(bar_x, _MARGIN_PX - 20):.0f}" '
                f'y="{start_y - font_size * 0.3:.1f}" '
                f'width="4" height="{total_height + 10:.1f}" rx="2" '
                f'fill="{accent_color}" opacity="0.9"/>'
            )
        else:  # "minimal"
            # Small dash under title, understated
            dash_w = 80
            accent_line_x = tx - dash_w / 2 if t_anchor == "middle" else (tx if t_anchor == "start" else tx - dash_w)
            accent_line = (
                f'<rect x="{accent_line_x:.0f}" y="{accent_line_y:.1f}" '
                f'width="{dash_w}" height="3" rx="1.5" '
                f'fill="{accent_color}" opacity="0.7"/>'
            )

        # ----- f. Build details block -----
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

        # Clamp details x to safe margins
        if d_anchor == "start":
            dx = max(dx, _MARGIN_PX)
            sep_x = dx
        elif d_anchor == "end":
            dx = min(dx, _CANVAS_WIDTH - _MARGIN_PX)
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

        details_elements: list[str] = [
            # date
            f'<text x="{dx}" y="{dy - 40}" text-anchor="{d_anchor}" '
            f"font-family=\"'Arial Black', Arial, sans-serif\" font-size=\"40\" "
            f'font-weight="bold" letter-spacing="1" '
            f'fill="{text_color}">{date_esc}</text>',
            # time
            f'<text x="{dx}" y="{dy + 15}" text-anchor="{d_anchor}" '
            f'font-family="Arial, sans-serif" font-size="34" '
            f'fill="{subtle_color}">{time_esc}</text>',
            # separator
            separator,
            # venue
            f'<text x="{dx}" y="{dy + 90}" text-anchor="{d_anchor}" '
            f'font-family="Arial, sans-serif" font-size="30" '
            f'font-weight="bold" opacity="0.95" '
            f'fill="{text_color}">{venue_esc}</text>',
            # address
            f'<text x="{dx}" y="{dy + 130}" text-anchor="{d_anchor}" '
            f'font-family="Arial, sans-serif" font-size="24" '
            f'fill="{subtle_color}">{address_esc}</text>',
        ]

        # url (only if present)
        if url_esc is not None:
            details_elements.append(
                f'<text x="{dx}" y="{dy + 210}" text-anchor="{d_anchor}" '
                f'font-family="Arial, sans-serif" font-size="22" '
                f'fill="{subtle_color}">{url_esc}</text>'
            )

        # ----- g. Build fee badge -----
        fee_elements: list[str] = []
        if fees_esc:
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
                f'font-family="Arial, sans-serif" font-size="{fee_font_size}" '
                f'font-weight="bold" fill="#1a1a1a">{fees_esc}</text>'
            )

        # ----- h. Build org credit -----
        org_credit = (
            f'<text x="540" y="1840" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="20" '
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
        defs = _gradient_defs(fade_color)

        bg_image = (
            f'<image href="data:image/png;base64,{b64_bg}" '
            f'width="1080" height="1920" '
            f'preserveAspectRatio="xMidYMid slice"/>'
        )

        parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            'width="1080" height="1920" viewBox="0 0 1080 1920">',
            defs,
            bg_image,
            *scrim_elements,
            *title_elements,
            accent_line,
            *details_elements,
            *fee_elements,
            org_credit,
            accent_stripe,
            "</svg>",
        ]

        return "".join(parts)
