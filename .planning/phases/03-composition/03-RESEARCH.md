# Phase 3: Composition - Research

**Researched:** 2026-04-16
**Domain:** SVG composition + rasterization (Python, cairosvg, Pillow)
**Confidence:** HIGH

## Summary

Phase 3 implements the visual composition pipeline: LayoutResolver (zone labels to pixel coords), PosterComposer (SVG builder), and Rasterizer (SVG to PNG via cairosvg). All three components are well-constrained by the spec, the n8n reference implementation, and the CONTEXT.md decisions. The n8n "Compose Poster SVG" node contains the complete SVG template with exact font sizes, scrim gradients, badge geometry, and accent positioning -- this is the authoritative reference to port.

The primary risk is cairosvg's handling of embedded base64 images and text rendering (font availability). Cairo system libraries are available on the target machine. The composition pipeline is entirely local (no network calls), making it fast and highly testable with snapshot tests.

**Primary recommendation:** Port the n8n "Compose Poster SVG" node logic 1:1 into Python f-strings, add XML escaping for all user strings, and use cairosvg.svg2png() with explicit output_width=1080, output_height=1920 for rasterization.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** LayoutResolver is a pure function `resolve(zones: LayoutZones) -> ResolvedLayout` per spec S6.6
- **D-02:** Uses ZONE_COORDS from zones.py -- already defined in Phase 1 with exact pixel values
- **D-03:** ResolvedLayout has title, details, fee_badge, org_credit fields each containing a ZoneCoord
- **D-04:** PosterComposer.compose() takes event, background, verdict, layout and returns SVG string
- **D-05:** Background embedded as base64 data:image/png;base64 URL on `<image>` element -- SVG will be ~2MB but is transient
- **D-06:** Title sizing: font size + wrap-width derived from len(title). Thresholds: <=14 chars -> 82px/14cpl, <=20 -> 72px/20cpl, <=30 -> 62px/18cpl, else -> 52px/22cpl
- **D-07:** Widow-line merge: if last wrapped line is < 40% the previous, merge back
- **D-08:** Text color from verdict.text_color: "white" -> #ffffff, "dark" -> #1a1a1a. Stroke is opposite with ~50% opacity
- **D-09:** Scrim gradients only darken zones actually used by title/details -- TOP gets topFade, BOTTOM gets bottomFade, MIDDLE gets radial middleFade
- **D-10:** Fee badge: pill shape (rx=28), width clamped [140, 400], font shrinks if text > 15 chars (22px vs 30px)
- **D-11:** Org credit pinned at y=1840, center-anchored, always "Presented by {org}"
- **D-12:** Accent line: 200x4px under title, positioned per title anchor. Accent stripe: 12px at y=1908, full width
- **D-13:** All user-supplied strings XML-escaped via xml.sax.saxutils.escape()
- **D-14:** SVG built via f-strings -- no Jinja2
- **D-15:** Rasterizer.rasterize(svg: str) -> bytes using cairosvg.svg2png()
- **D-16:** Output dimensions forced to 1080x1920 via output_width/output_height params
- **D-17:** Sanity check: verify resulting PNG is 1080x1920 via Pillow, raise RasterizationError on mismatch
- **D-18:** Pin cairosvg >= 2.7.1 to avoid base64 image drop bug

### Claude's Discretion
- Whether to use a helper function for SVG text element generation or inline f-strings
- Exact scrim opacity values (spec says top 0.75, bottom 0.85, middle radial 0.6 -- can tune)
- Test approach for SVG output (snapshot tests, structural assertions, or both)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COMP-01 | LayoutResolver maps zone labels to pixel coordinates and text anchors | zones.py ZONE_COORDS already defined; resolve() is a dict lookup, pure function |
| COMP-02 | PosterComposer generates SVG with base64-embedded background image | n8n Compose Poster SVG node provides complete template; base64 module in stdlib |
| COMP-03 | Title auto-sized by length with word-wrap and widow-line merge | n8n node has exact thresholds and wrap logic to port |
| COMP-04 | Text color (white/dark) and stroke applied from vision verdict | Color mapping defined in CONTEXT D-08 |
| COMP-05 | Zone-specific scrim gradients applied only to zones used by title/details | n8n node has scrim logic; row extracted from zone name via split('_')[0] |
| COMP-06 | Fee badge rendered as pill shape with dynamic width clamped [140, 400] | n8n node has exact badge geometry |
| COMP-07 | Accent line under title and accent stripe at bottom from event color_accent | n8n node has positioning logic |
| COMP-08 | All user-supplied strings XML-escaped before SVG insertion | xml.sax.saxutils.escape() covers <, >, & for text content |
| COMP-09 | Rasterizer converts SVG to 1080x1920 PNG via cairosvg with dimension sanity check | cairosvg.svg2png() with output_width + output_height confirmed; Pillow for verification |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.11+ required
- Pillow for image processing, cairosvg for SVG-to-PNG rasterization
- Pydantic v2 for all data contracts
- structlog for logging
- No Node.js deps (no sharp, no Puppeteer)
- System deps: Cairo + libffi required for cairosvg

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Zone-to-pixel mapping | Application logic | -- | Pure function, no I/O, dict lookup from zones.py data |
| SVG composition | Application logic | -- | String building with f-strings, no external services |
| XML escaping | Application logic | -- | stdlib xml.sax.saxutils, applied before SVG insertion |
| Base64 encoding | Application logic | -- | stdlib base64 module on in-memory PNG bytes |
| SVG rasterization | System library (Cairo) | -- | cairosvg wraps C Cairo library for rendering |
| Dimension verification | Application logic | -- | Pillow opens PNG bytes, checks .size tuple |

## Standard Stack

### Core (already in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| cairosvg | >=2.9.0 | SVG to PNG rasterization | Already pinned in pyproject.toml; handles embedded base64 images [VERIFIED: pyproject.toml] |
| Pillow | >=12.2.0 | PNG dimension verification | Already pinned; used to verify output is 1080x1920 [VERIFIED: pyproject.toml] |

### Supporting (stdlib -- no install needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| xml.sax.saxutils | stdlib | XML escaping user strings | Every user-supplied string before SVG insertion [VERIFIED: python3 stdlib] |
| base64 | stdlib | Encode PNG bytes to base64 for SVG embedding | Background image embedding in `<image>` element [VERIFIED: python3 stdlib] |
| textwrap | stdlib | NOT used -- custom word wrap needed | Custom wrap logic needed for widow-line merge [VERIFIED: stdlib lacks widow merge] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| f-strings for SVG | Jinja2 templates | Overkill for this complexity (CONTEXT D-14 locks f-strings) |
| cairosvg | resvg-py | v2 fallback; cairosvg is primary (locked decision) |
| xml.sax.saxutils.escape | html.escape | html.escape adds quote=True by default; saxutils.escape is more explicit for XML context |

## Architecture Patterns

### System Architecture Diagram

```
VisionVerdict.zones (LayoutZones)
        |
        v
[LayoutResolver] --resolve()--> ResolvedLayout (ZoneCoord per element)
        |
        v
EventInput + GeneratedBackground + VisionVerdict + ResolvedLayout
        |
        v
[PosterComposer] --compose()--> SVG string (~2MB with embedded base64 image)
  |-- base64-encode background PNG
  |-- build SVG defs (gradient scrims)
  |-- build title block (auto-sized, wrapped, widow-merged)
  |-- build details block (date/time/venue/address/url)
  |-- build fee badge (pill shape)
  |-- build org credit (pinned y=1840)
  |-- build accent elements (line + stripe)
  |-- XML-escape all user strings
        |
        v
[Rasterizer] --rasterize()--> PNG bytes (1080x1920)
  |-- cairosvg.svg2png(bytestring=..., output_width=1080, output_height=1920)
  |-- Pillow dimension sanity check
```

### Recommended Project Structure

```
flyer_generator/
  stages/
    layout.py         # LayoutResolver.resolve() -- NEW
    composer.py        # PosterComposer.compose() -- NEW
    rasterizer.py      # Rasterizer.rasterize() -- NEW
tests/
  test_layout.py      # NEW -- zone resolution tests
  test_composer.py     # NEW -- SVG composition tests
  test_rasterizer.py   # NEW -- rasterization tests
  fixtures/
    sample_1080x1920.png  # NEW -- tiny valid PNG for composer tests
```

### Pattern 1: Pure Function Layout Resolution

**What:** LayoutResolver.resolve() is a stateless function that maps LayoutZones to ResolvedLayout via ZONE_COORDS lookup.
**When to use:** Every time the pipeline needs pixel coordinates from vision zone labels.
**Example:**
```python
# Source: spec S6.6 + zones.py (Phase 1)
from flyer_generator.models import LayoutZones, ResolvedLayout
from flyer_generator.zones import ZONE_COORDS

def resolve(zones: LayoutZones) -> ResolvedLayout:
    return ResolvedLayout(
        title=ZONE_COORDS[zones.title],
        details=ZONE_COORDS[zones.details],
        fee_badge=ZONE_COORDS[zones.fee_badge],
        org_credit=ZONE_COORDS[zones.org_credit],
    )
```

### Pattern 2: SVG Composition via F-Strings with Helper Functions

**What:** Build SVG as a single string using f-strings, with helper functions for repeated patterns (text elements, gradient defs).
**When to use:** PosterComposer.compose() constructs the full SVG document.
**Example:**
```python
# Source: n8n Compose Poster SVG node (docs/n8n.json)
from xml.sax.saxutils import escape

def _svg_text(x: int, y: int, anchor: str, font_family: str,
              font_size: int, fill: str, text: str, **attrs: str) -> str:
    extra = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'font-family="{font_family}" font-size="{font_size}" '
            f'fill="{fill}" {extra}>{escape(text)}</text>')
```

### Pattern 3: Word Wrap with Widow-Line Merge

**What:** Custom word wrapper that splits text by character count and merges widow lines (last line < 40% of previous).
**When to use:** Title text wrapping in the composer.
**Example:**
```python
# Source: n8n Compose Poster SVG node wrapText function
def wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if len(words) <= 2:
        return [text]
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    # Widow-line merge
    if len(lines) > 1:
        last = lines[-1]
        prev = lines[-2]
        if len(last) < len(prev) * 0.4:
            lines.pop()
            lines[-1] = f"{prev} {last}"
    return lines
```

### Pattern 4: Scrim Zone Detection

**What:** Extract row name from zone label to determine which scrim gradients to apply.
**When to use:** Only add scrims for zones actually used by title and details.
**Example:**
```python
# Source: n8n Compose Poster SVG node scrim logic
def _get_scrim_zones(title_zone: str, details_zone: str) -> set[str]:
    """Return set of row names ('TOP', 'MIDDLE', 'BOTTOM') needing scrims."""
    return {title_zone.split("_")[0], details_zone.split("_")[0]}
```

### Anti-Patterns to Avoid
- **Blanket darkening:** Do NOT apply scrims to the entire image. Only darken zones with text. The whole point of vision-driven layout is preserving the artwork where text isn't placed.
- **Pixel-pushing without the spec:** Do NOT invent positioning values. Use the exact coordinates from ZONE_COORDS and the exact dy offsets from the n8n template (dy-40, dy+15, dy+42, dy+90, dy+130, dy+210 for details block).
- **Using textwrap.wrap for title:** stdlib textwrap has different breaking behavior and no widow-line merge. Port the n8n wrapText function directly.
- **Forgetting to escape user strings:** Every user field (title, date, time, venue, address, fees, org, url) must go through escape() before SVG insertion. Unescaped `&` or `<` in venue names will break SVG parsing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| XML escaping | Custom regex replacements | xml.sax.saxutils.escape() | Handles &, <, > correctly; easy to miss edge cases with regex |
| SVG to PNG | Headless browser / subprocess | cairosvg.svg2png() | Single function call, no external process, no Node.js |
| PNG dimension check | Manual byte parsing | Pillow Image.open(BytesIO(data)).size | Handles all PNG variants correctly |
| Base64 encoding | Manual byte conversion | base64.b64encode() | stdlib, correct padding, no bugs |

**Key insight:** The SVG building IS the hand-rolled part of this phase -- everything else should use stdlib or established libraries. The SVG template is complex but it's a direct port from the working n8n implementation, not a design exercise.

## Common Pitfalls

### Pitfall 1: cairosvg output_width/output_height Must Both Be Specified
**What goes wrong:** Specifying only output_width or only output_height results in the SVG's intrinsic dimensions being used instead.
**Why it happens:** cairosvg only overrides dimensions when both are provided together.
**How to avoid:** Always pass both `output_width=1080` and `output_height=1920` to svg2png(). [VERIFIED: GitHub issue #164 + maintainer confirmation]
**Warning signs:** Output PNG is not 1080x1920 -- the Pillow sanity check (COMP-09) catches this.

### Pitfall 2: xml.sax.saxutils.escape() Does Not Escape Quotes
**What goes wrong:** If user strings contain `"` or `'` and are placed in SVG attribute values, the SVG breaks.
**Why it happens:** escape() only handles &, <, > by default. Quotes require the optional `entities` parameter.
**How to avoid:** User strings in this SVG design are placed as text content (between tags), not in attributes. escape() is sufficient for text content. If any string ever goes into an attribute, use `quoteattr()` instead. [VERIFIED: python3 interactive test]
**Warning signs:** SVG parse errors on strings with quotes in them.

### Pitfall 3: Title .upper() Affects Character Count
**What goes wrong:** The n8n version uppercases the title (`toUpperCase()`). If you measure length before uppercasing, the font size thresholds work on the wrong string.
**Why it happens:** Uppercase doesn't change length in ASCII, but the character count should be measured on the final display string.
**How to avoid:** Uppercase the title first, then measure length for font size selection. [VERIFIED: n8n Compose Poster SVG node does `title.toUpperCase()` first]

### Pitfall 4: Scrim fadeColor Must Match text_color Intent
**What goes wrong:** Dark text on a light scrim (or vice versa) makes text unreadable.
**Why it happens:** Scrim darkens for white text (rgb(0,0,0)) or lightens for dark text (rgb(255,255,255)). Getting this backwards defeats the purpose.
**How to avoid:** When text_color is "white", scrim fade is black (0,0,0). When text_color is "dark", scrim fade is white (255,255,255). [VERIFIED: n8n Compose Poster SVG node fadeColor logic]

### Pitfall 5: Large SVG String Performance
**What goes wrong:** The SVG with embedded base64 background is ~2MB. String concatenation in a loop can be slow.
**Why it happens:** Base64 of a 1080x1920 PNG is ~1.5-2MB.
**How to avoid:** Build the SVG in one pass with a single f-string interpolation, not iterative concatenation. The SVG is transient -- it's only kept in memory long enough for cairosvg to rasterize. [ASSUMED]

### Pitfall 6: cairosvg Font Availability
**What goes wrong:** cairosvg renders text using system fonts. If Arial Black / Arial / Helvetica are not installed, text renders in a fallback font with different metrics.
**Why it happens:** Cairo uses fontconfig to find fonts. Server environments often lack common fonts.
**How to avoid:** The font family chain ('Arial Black', 'Helvetica Neue', Arial, sans-serif) provides fallbacks. In minimal environments, sans-serif always resolves to something. Accept that font metrics may differ slightly across systems -- the layout is designed with generous spacing. [ASSUMED]

## Code Examples

### Complete LayoutResolver

```python
# Source: spec S6.6, zones.py, models.py
from flyer_generator.models import LayoutZones, ResolvedLayout
from flyer_generator.zones import ZONE_COORDS


class LayoutResolver:
    """Maps vision zone labels to pixel coordinates."""

    def resolve(self, zones: LayoutZones) -> ResolvedLayout:
        return ResolvedLayout(
            title=ZONE_COORDS[zones.title],
            details=ZONE_COORDS[zones.details],
            fee_badge=ZONE_COORDS[zones.fee_badge],
            org_credit=ZONE_COORDS[zones.org_credit],
        )
```

### Rasterizer with Sanity Check

```python
# Source: spec S6.8, CONTEXT D-15 through D-18
import io
import cairosvg
from PIL import Image
from flyer_generator.errors import RasterizationError


class Rasterizer:
    """Converts SVG string to PNG bytes at 1080x1920."""

    def rasterize(self, svg: str) -> bytes:
        try:
            png_bytes = cairosvg.svg2png(
                bytestring=svg.encode("utf-8"),
                output_width=1080,
                output_height=1920,
            )
        except Exception as exc:
            raise RasterizationError(f"cairosvg failed: {exc}") from exc

        # Sanity check dimensions
        img = Image.open(io.BytesIO(png_bytes))
        if img.size != (1080, 1920):
            raise RasterizationError(
                f"Expected 1080x1920, got {img.size[0]}x{img.size[1]}"
            )
        return png_bytes
```

### Title Sizing Thresholds (from n8n)

```python
# Source: n8n Compose Poster SVG node, CONTEXT D-06
def _title_params(title: str) -> tuple[int, int]:
    """Return (font_size, max_chars_per_line) based on title length."""
    length = len(title)
    if length <= 14:
        return 82, 14
    if length <= 20:
        return 72, 20
    if length <= 30:
        return 62, 18
    return 52, 22
```

### SVG Gradient Definitions (from n8n)

```python
# Source: n8n Compose Poster SVG node gradient defs
def _gradient_defs(fade_color: str) -> str:
    """Build SVG <defs> with scrim gradient definitions.

    fade_color: '0,0,0' for white text, '255,255,255' for dark text
    """
    return f"""<defs>
    <linearGradient id="topFade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="rgb({fade_color})" stop-opacity="0.75"/>
      <stop offset="100%" stop-color="rgb({fade_color})" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="bottomFade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="rgb({fade_color})" stop-opacity="0"/>
      <stop offset="100%" stop-color="rgb({fade_color})" stop-opacity="0.85"/>
    </linearGradient>
    <radialGradient id="middleFade" cx="0.5" cy="0.5" r="0.6">
      <stop offset="0%" stop-color="rgb({fade_color})" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="rgb({fade_color})" stop-opacity="0"/>
    </radialGradient>
  </defs>"""
```

### Details Block Layout (from n8n)

```python
# Source: n8n Compose Poster SVG node details block
# dy offsets relative to layout.details.y:
#   date:      dy - 40
#   time:      dy + 15
#   separator: dy + 42  (rect, width=140, height=2)
#   venue:     dy + 90
#   address:   dy + 130
#   url:       dy + 210 (if present)
```

### Fee Badge Geometry (from n8n)

```python
# Source: n8n Compose Poster SVG node fee badge
# Badge width: max(min(len(fees) * 22 + 60, 400), 140)
# Badge height: 56, rx=28 (full pill)
# Badge y offset: fy - 28 (centered on zone y)
# Font size: 22 if len(fees) > 15 else 30
# Text fill: always #1a1a1a (dark on accent color)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| cairosvg < 2.7 base64 bug | cairosvg >= 2.7.1 fixes embedded base64 images | 2023 | Must pin >= 2.7.1; project pins >= 2.9.0 which is safe |
| Puppeteer/Chrome for SVG rasterization | cairosvg pure Python | Stable for years | No Node.js dependency, faster, simpler |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SVG string concatenation performance is adequate at ~2MB | Pitfall 5 | LOW -- could use list join instead; trivial fix |
| A2 | System fonts (Arial/sans-serif) are available on target | Pitfall 6 | MEDIUM -- text may render differently; visual-only impact, not functional |

## Open Questions

1. **Font metrics across environments**
   - What we know: Cairo uses fontconfig; Arial Black may not be installed everywhere
   - What's unclear: Whether text positioning is visually acceptable with fallback fonts
   - Recommendation: Accept sans-serif fallback for v1; add font check to test suite if needed

2. **SVG text wrapping fidelity**
   - What we know: SVG `<text>` elements don't auto-wrap; we pre-wrap by character count
   - What's unclear: Whether character-count wrapping matches visual width at all font sizes
   - Recommendation: The n8n version uses the same approach and works; accept character-based wrapping for v1

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| libcairo2 | cairosvg rasterization | Yes | 1.16.0 | -- |
| Python 3.11+ | Runtime | Yes | (system) | -- |
| cairosvg (pip) | COMP-09 | No (not yet installed) | -- | `uv add cairosvg` (in pyproject.toml already) |
| Pillow (pip) | Dimension check | No (not yet installed) | -- | `uv add pillow` (in pyproject.toml already) |

**Missing dependencies with no fallback:** None -- all system deps present.

**Missing dependencies with fallback:** cairosvg and Pillow are declared in pyproject.toml but not yet installed in the current environment. Running `uv sync` will resolve this.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | -- |
| V3 Session Management | No | -- |
| V4 Access Control | No | -- |
| V5 Input Validation | Yes | xml.sax.saxutils.escape() on all user strings before SVG insertion |
| V6 Cryptography | No | -- |

### Known Threat Patterns for SVG Composition

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XML injection via user strings | Tampering | xml.sax.saxutils.escape() on title, venue, org, fees, url, date, time, address |
| SVG script injection | Tampering | No `<script>` elements in template; user strings never placed in executable context |
| Billion laughs (XML entity expansion) | DoS | cairosvg parses the SVG we build; no external entity references in our template |

## Sources

### Primary (HIGH confidence)
- docs/n8n.json "Compose Poster SVG" node -- complete SVG template with exact values [VERIFIED: file read]
- docs/spec.md S6.6, S6.7, S6.8 -- stage specifications [VERIFIED: file read]
- flyer_generator/zones.py -- ZONE_COORDS with all 9 zone pixel positions [VERIFIED: file read]
- flyer_generator/models.py -- ResolvedLayout, VisionVerdict, EventInput models [VERIFIED: file read]
- flyer_generator/errors.py -- CompositionError, RasterizationError [VERIFIED: file read]
- [CairoSVG documentation](https://cairosvg.org/documentation/) -- svg2png API parameters [VERIFIED: Context7 + WebSearch]
- [CairoSVG issue #164](https://github.com/Kozea/CairoSVG/issues/164) -- output_width + output_height must both be specified [VERIFIED: GitHub issue]

### Secondary (MEDIUM confidence)
- Python xml.sax.saxutils.escape() behavior -- tested interactively [VERIFIED: python3 REPL]
- Cairo system library availability -- checked via dpkg and ldconfig [VERIFIED: system probe]

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in pyproject.toml, versions verified
- Architecture: HIGH -- n8n reference implementation provides complete template to port
- Pitfalls: HIGH -- cairosvg gotchas verified against GitHub issues; XML escaping tested

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (stable domain, no fast-moving dependencies)
