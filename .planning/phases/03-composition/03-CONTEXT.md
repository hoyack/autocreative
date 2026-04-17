# Phase 3: Composition - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the visual composition pipeline: LayoutResolver translates zone labels to pixel coordinates, PosterComposer builds SVG with text overlays + scrims + badges + accents, and Rasterizer converts SVG to PNG via cairosvg. Input is a background image + VisionVerdict from Phase 2. Output is a complete 1080x1920 PNG flyer. No pipeline orchestration (Phase 4), no regeneration loop (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Layout Resolution (stages/layout.py)
- **D-01:** LayoutResolver is a pure function `resolve(zones: LayoutZones) -> ResolvedLayout` per spec §6.6
- **D-02:** Uses ZONE_COORDS from zones.py — already defined in Phase 1 with exact pixel values
- **D-03:** ResolvedLayout has title, details, fee_badge, org_credit fields each containing a ZoneCoord

### SVG Composition (stages/composer.py)
- **D-04:** PosterComposer.compose() takes event, background, verdict, layout and returns SVG string
- **D-05:** Background embedded as base64 data:image/png;base64 URL on <image> element — SVG will be ~2MB but is transient
- **D-06:** Title sizing: font size + wrap-width derived from len(title). Thresholds from n8n: ≤14 chars → 82px/14cpl, ≤20 → 72px/20cpl, ≤30 → 62px/18cpl, else → 52px/22cpl
- **D-07:** Widow-line merge: if last wrapped line is < 40% the previous, merge back
- **D-08:** Text color from verdict.text_color: "white" → #ffffff, "dark" → #1a1a1a. Stroke is opposite with ~50% opacity
- **D-09:** Scrim gradients only darken zones actually used by title/details — TOP gets topFade, BOTTOM gets bottomFade, MIDDLE gets radial middleFade
- **D-10:** Fee badge: pill shape (rx=28), width clamped [140, 400], font shrinks if text > 15 chars (22px vs 30px)
- **D-11:** Org credit pinned at y=1840, center-anchored, always "Presented by {org}"
- **D-12:** Accent line: 200×4px under title, positioned per title anchor. Accent stripe: 12px at y=1908, full width
- **D-13:** All user-supplied strings (title, venue, org, url, fees) XML-escaped via xml.sax.saxutils.escape()
- **D-14:** SVG built via f-strings — no Jinja2 needed for this complexity level

### Rasterization (stages/rasterizer.py)
- **D-15:** Rasterizer.rasterize(svg: str) -> bytes using cairosvg.svg2png()
- **D-16:** Output dimensions forced to 1080×1920 via output_width/output_height params
- **D-17:** Sanity check: verify resulting PNG is 1080×1920 via Pillow, raise RasterizationError on mismatch
- **D-18:** Pin cairosvg >= 2.7.1 to avoid base64 image drop bug (from research pitfalls)

### Claude's Discretion
- Whether to use a helper function for SVG text element generation or inline f-strings
- Exact scrim opacity values (spec says top 0.75, bottom 0.85, middle radial 0.6 — can tune)
- Test approach for SVG output (snapshot tests, structural assertions, or both)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Specification
- `docs/spec.md` §6.6 — LayoutResolver spec (zone → pixel mapping, ZoneCoord, ResolvedLayout)
- `docs/spec.md` §6.7 — PosterComposer spec (title sizing, scrims, badges, accent line, text color, SVG build)
- `docs/spec.md` §6.8 — Rasterizer spec (cairosvg, dimension check)

### Reference Implementation
- `docs/n8n.json` — Compose Poster SVG node (complete SVG composition logic with exact font sizes, scrim gradients, badge geometry, accent positioning), Rasterize SVG to PNG node

### Foundation (Phase 1 output)
- `flyer_generator/zones.py` — ZONE_COORDS, ZoneCoord, ZoneName
- `flyer_generator/models.py` — VisionVerdict, LayoutZones, ResolvedLayout, EventInput, GeneratedBackground, FlyerOutput

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `flyer_generator/zones.py` — ZONE_COORDS dict with all 9 zone pixel positions, ZoneCoord frozen dataclass
- `flyer_generator/models.py` — ResolvedLayout model already defined, VisionVerdict with text_color and zones
- `flyer_generator/errors.py` — CompositionError, RasterizationError ready to use

### Established Patterns
- Stage classes with typed inputs/outputs
- Injected dependencies via __init__
- Pydantic models for all cross-stage data

### Integration Points
- stages/layout.py imports from zones.py and models.py
- stages/composer.py imports from models.py (EventInput, VisionVerdict, GeneratedBackground, ResolvedLayout)
- stages/rasterizer.py uses cairosvg and Pillow for verification

</code_context>

<specifics>
## Specific Ideas

- The n8n Compose Poster SVG node contains the complete SVG template — carry over the structure verbatim (gradient defs, scrim logic, text positioning, badge geometry)
- Title line height is fontSize × 1.25
- Title block centered vertically on layout.title.y
- Font family chain: 'Arial Black', 'Helvetica Neue', Arial, sans-serif for title; Arial, Helvetica, sans-serif for other text
- Details block layout: date at dy-40, time at dy+15, separator line at dy+42, venue at dy+90, address at dy+130, url at dy+210

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-composition*
*Context gathered: 2026-04-16 via auto mode*
