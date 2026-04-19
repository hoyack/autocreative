"""Gallery tests: every template in schemas/ × every content in sample-content/.

When a new template or content file is added, these tests automatically cover
it. Fails if any template-content pair raises, emits empty SVG, or rasterizes
to an unexpectedly-tiny PNG.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flyer_generator.brochure.schema_renderer import (
    BrochureContent,
    load_template,
    render_schema_brochure,
)
from flyer_generator.brochure.schema_renderer.loader import list_templates
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
)
from flyer_generator.stages.rasterizer import Rasterizer


_CONTENT_DIR = Path(__file__).resolve().parents[3] / "docs" / "brochure" / "sample-content"


def _content_files() -> list[Path]:
    if not _CONTENT_DIR.exists():
        return []
    return sorted(_CONTENT_DIR.glob("*.json"))


def _load_content(path: Path) -> BrochureContent:
    return BrochureContent.model_validate(json.loads(path.read_text()))


TEMPLATES = list_templates()
CONTENT_PATHS = _content_files()


@pytest.mark.parametrize("template_name", TEMPLATES)
def test_template_loads(template_name: str):
    t = load_template(template_name)
    # Every panel must declare at least one element
    for pname, panel in t.panels.items():
        assert len(panel.elements) > 0, f"panel {pname} of {template_name} has no elements"


@pytest.mark.parametrize(
    "template_name,content_path",
    [
        (t, p) for t in TEMPLATES for p in CONTENT_PATHS
    ],
)
def test_template_x_content_renders(template_name: str, content_path: Path):
    t = load_template(template_name)
    c = _load_content(content_path)
    outside, inside = render_schema_brochure(t, c)
    assert outside.startswith("<svg") and outside.endswith("</svg>")
    assert inside.startswith("<svg") and inside.endswith("</svg>")
    assert f'width="{BLEED_CANVAS_WIDTH}"' in outside


@pytest.mark.parametrize("template_name", TEMPLATES)
def test_template_rasterizes(template_name: str):
    if not CONTENT_PATHS:
        pytest.skip("no sample content available")
    t = load_template(template_name)
    c = _load_content(CONTENT_PATHS[0])
    outside, inside = render_schema_brochure(t, c)
    r = Rasterizer(width=BLEED_CANVAS_WIDTH, height=BLEED_CANVAS_HEIGHT)
    png_out = r.rasterize(outside)
    png_in = r.rasterize(inside)
    # A blank PNG at this resolution is usually ~15 KB (just white); anything
    # meaningful should be ≥ 40 KB. Catch template regressions where rendering
    # degenerates to near-empty output.
    assert len(png_out) > 40_000, f"{template_name} front PNG is suspiciously tiny ({len(png_out)} bytes)"
    assert len(png_in) > 40_000, f"{template_name} back PNG is suspiciously tiny ({len(png_in)} bytes)"
