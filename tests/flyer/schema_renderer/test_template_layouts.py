"""Layout-collision regression tests for the 6 flyer templates.

Phase 24.1 PLF-03: bold_modern's `cover_title` element is currently 600 pixels
tall (bbox h=600, starting at y=120). With a 140-pt font and multi-line wrap,
text rendered into that bbox visually intersects the details band that begins
at y=1300. The perception loop screenshot
`/tmp/perception/flyer-attempt2-render.png` shows the literal collision:
"MEETUP" letters punching through "The Fillmore", "2026-05-20" sitting inside
"T E C H".

This module guards three properties:

1. For every flyer template, the `cover_title` bbox does not overlap any
   `body`-role element bound to an `event.*` content key (purely deterministic
   bbox arithmetic — no rendering, no AI in the path).
2. For `bold_modern` specifically, the headline bbox vertical budget is
   capped (h <= 480) so that wrapped text cannot extend down into the details
   band even with a worst-case 4-line headline at line_height=147.
3. The other 5 schemas are byte-identical to their pre-fix baseline (sha256
   tripwire), proving the fix is surgically scoped to bold_modern.json.

# PLF-03 snapshot audit (2026-04-25):
#   grep -rn 'bold_modern' tests/ → references in:
#     - tests/api/test_worker_tasks.py:489 — uses template name in payload
#       (no rendered-output snapshot)
#     - tests/api/test_schemas.py:494,499 — pydantic round-trip on the
#       template name string only
#     - tests/flyer/schema_renderer/test_render_smoke.py:7,10 — comments only
#       (mentions bold_modern in the matrix description); the test itself
#       does NOT pin rendered SVG bytes for bold_modern
#     - tests/flyer/schema_renderer/test_loader.py:15,102 — STARTERS list +
#       subtype_compat assertion; does not pin layout coordinates
#   No __snapshots__/ directories under tests/. No pytest-snapshot fixtures.
#   No SVG/PNG hashes referencing bold_modern's geometry.
# Conclusion: NO existing snapshot tests depend on bold_modern's bbox values.
# Strategy: Task 2 adjusts bold_modern.json bboxes only. No snapshot updates
# are required as part of the GREEN commit.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from flyer_generator.flyer.schema_renderer.loader import load_template
from flyer_generator.flyer.schema_renderer.schema_model import TextElement

ALL_TEMPLATES = [
    "editorial_classic",
    "bold_modern",
    "minimal_photo",
    "retro_poster",
    "tight_typographic",
    "zine",
]

# sha256 of the 5 non-bold_modern schemas as of 2026-04-25 baseline (BEFORE
# PLF-03 fix). The fix touches only bold_modern.json; these hashes act as a
# tripwire if any of the other 5 schemas drift accidentally.
UNCHANGED_TEMPLATE_HASHES: dict[str, str] = {
    "editorial_classic": "18b837e6ed365d742b9306687ef4c0e5f7753e21afb85883470e26fc788e76fe",
    "minimal_photo": "720bfd670ca1ef3c50f14790d8424d66c917c683c99fce45335a18665401bc91",
    "retro_poster": "b7ee23f7442d76224925a27fb2454ff957c7611fc7e7dff146dbe503674a1a07",
    "tight_typographic": "e03f52aa1b42c8db579716831a04b973b75c9839773fe1cf183b806a321e55df",
    "zine": "918aa74b7437b4013a77347b95620785fd5a14e00a94898619fca48cdd5142ce",
}

_SCHEMAS_DIR = (
    Path(__file__).resolve().parents[3] / "flyer_generator" / "flyer" / "schemas"
)


def _rects_overlap(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> bool:
    """Axis-aligned rectangle intersection. Edge-touching is NOT overlap."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (
        ax + aw <= bx  # a is entirely left of b
        or bx + bw <= ax  # b is entirely left of a
        or ay + ah <= by  # a is entirely above b
        or by + bh <= ay  # b is entirely above a
    )


def _text_elements(template_name: str) -> list[TextElement]:
    """All TextElement entries across every panel of the template."""
    template = load_template(template_name)
    out: list[TextElement] = []
    for panel in template.panels.values():
        for el in panel.elements:
            if isinstance(el, TextElement):
                out.append(el)
    return out


def _cover_title(template_name: str) -> TextElement:
    elems = [el for el in _text_elements(template_name) if el.role == "cover_title"]
    assert len(elems) == 1, (
        f"template {template_name} should declare exactly one cover_title; got {len(elems)}"
    )
    return elems[0]


def _event_body_elements(template_name: str) -> list[TextElement]:
    """Body-role text elements bound to an event.* content_key (date/time/etc)."""
    return [
        el
        for el in _text_elements(template_name)
        if el.role == "body"
        and el.content_key is not None
        and el.content_key.startswith("event.")
    ]


@pytest.mark.parametrize("template_name", ALL_TEMPLATES)
def test_no_headline_details_overlap(template_name: str) -> None:
    """cover_title bbox must not overlap any event.* details bbox.

    Deterministic check: load the template JSON, find each (cover_title,
    details) pair, assert their (x, y, w, h) rects do not intersect. No
    rendering, no AI — pure JSON inspection.
    """
    title = _cover_title(template_name)
    details = _event_body_elements(template_name)
    assert details, (
        f"template {template_name} declares no event.* body elements — "
        "the bug-class this test guards is irrelevant; remove the parametrize "
        "case or document why."
    )

    title_rect = title.bbox
    for detail in details:
        assert not _rects_overlap(title_rect, detail.bbox), (
            f"[{template_name}] cover_title bbox {title_rect} overlaps "
            f"detail '{detail.content_key}' bbox {detail.bbox}"
        )


def test_bold_modern_headline_band_clears_details_band() -> None:
    """bold_modern: strict vertical separation + headline height cap.

    Three assertions tracking the full PLF-03 fix:
      (a) headline bbox bottom < details band top (vertical-band separation)
      (b) cover_title.bbox.h <= 480 — caps the headline's RENDER budget so
          even a worst-case 4-line wrap at 140-pt font + ~147 line-height
          (~588px raw, but fit_to_bbox truncates to 4 lines × 147 = 588px)
          cannot extend below y=600. THIS is the load-bearing assertion that
          fails on the current (buggy) schema where h=600.
      (c) gap between headline bottom and details top >= 240 px — generous
          breathing room defeating any wrapping miscalibration.
    """
    title = _cover_title("bold_modern")
    details = _event_body_elements("bold_modern")
    assert details, "bold_modern must declare event.* details"

    _, title_y, _, title_h = title.bbox
    headline_bottom = title_y + title_h
    details_top = min(d.bbox[1] for d in details)

    # (a) strict y-separation
    assert headline_bottom < details_top, (
        f"bold_modern headline_bottom={headline_bottom} must sit ABOVE "
        f"details_top={details_top}"
    )

    # (b) headline height cap — load-bearing PLF-03 assertion
    assert title_h <= 480, (
        f"bold_modern cover_title.bbox.h={title_h} exceeds 480px cap; a "
        "taller bbox allows wrapped text to render into the details band "
        "(see /tmp/perception/flyer-attempt2-render.png)"
    )

    # (c) generous gap — defends against sub-bbox text overflow
    assert details_top - headline_bottom >= 240, (
        f"bold_modern vertical gap between headline ({headline_bottom}) and "
        f"details ({details_top}) is {details_top - headline_bottom}px; need >=240"
    )


@pytest.mark.parametrize("template_name", sorted(UNCHANGED_TEMPLATE_HASHES.keys()))
def test_other_5_templates_unchanged_byte_identical(template_name: str) -> None:
    """Tripwire: the 5 non-bold_modern schemas must be byte-identical to baseline.

    If this fails, someone has edited a schema other than bold_modern as part
    of (or after) PLF-03. PLF-03's contract is "fix bold_modern, leave the
    other 5 alone" — drift must be reviewed deliberately.
    """
    expected = UNCHANGED_TEMPLATE_HASHES[template_name]
    path = _SCHEMAS_DIR / f"{template_name}.json"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == expected, (
        f"[{template_name}] schema sha256 changed from baseline:\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}\n"
        "PLF-03 must not modify any template other than bold_modern."
    )
