"""Font bundling helpers for brochure SVG composition.

Walks `flyer_generator/assets/fonts/` for `.woff2` files whose stems match the
family names declared on a `LayoutTemplate`. For each match, inlines a
base64 `@font-face` rule into an SVG `<defs><style>…</style></defs>` block.

Missing fonts are silently skipped — templates still render via the system
generic fallback declared at the end of each `*_font_family` string
(e.g. `'Playfair Display', 'Times New Roman', serif`).
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

from flyer_generator.brochure.templates import LayoutTemplate

# Package-relative fonts directory — resolved once at import time.
_FONTS_DIR = Path(__file__).parent.parent.parent / "assets" / "fonts"


def _primary_family_name(font_family_decl: str) -> str:
    """Extract the first comma-separated family from a CSS font-family string.

    ``"'Playfair Display', 'Times New Roman', serif"`` → ``"Playfair Display"``
    """
    first = font_family_decl.split(",", 1)[0].strip()
    return first.strip("'\"").strip()


def _family_to_filename(family: str) -> str:
    """Map a CSS family name to an expected font filename stem.

    ``"Playfair Display"`` → ``"Playfair_Display"``
    """
    return re.sub(r"\s+", "_", family.strip())


def load_font_as_data_uri(path: Path) -> str:
    """Return a data-URI (base64 woff2) for an on-disk font file."""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:font/woff2;base64,{b64}"


def _font_face_rule(family: str, data_uri: str) -> str:
    """Return a single @font-face CSS rule for the given family + data URI."""
    return (
        f"@font-face{{"
        f"font-family:'{family}';"
        f"src:url({data_uri}) format('woff2');"
        f"font-display:swap;"
        f"}}"
    )


def build_font_face_defs(
    template: LayoutTemplate,
    font_dir: Path | None = None,
) -> str:
    """Return an SVG ``<defs><style>…</style></defs>`` block with @font-face
    rules for the given template's declared families.

    Families referenced by the template but missing a matching ``.woff2``
    file in ``font_dir`` are silently skipped. Returns an empty string when
    no matches are found.
    """
    directory = font_dir or _FONTS_DIR
    if not directory.exists() or not directory.is_dir():
        return ""

    wanted: dict[str, str] = {}  # family -> primary name
    for decl in (template.heading_font_family, template.body_font_family):
        family = _primary_family_name(decl)
        if family:
            wanted[family] = family  # dedupe via dict

    rules: list[str] = []
    for family in wanted:
        candidate = directory / f"{_family_to_filename(family)}.woff2"
        if not candidate.is_file():
            continue
        rules.append(_font_face_rule(family, load_font_as_data_uri(candidate)))

    if not rules:
        return ""
    return f"<defs><style>{''.join(rules)}</style></defs>"
