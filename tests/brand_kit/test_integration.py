"""End-to-end: kit template -> apply -> render -> rasterize -> audit AA-clean.

B5: `from flyer_generator.stages.rasterizer import Rasterizer` is the
correct import path (the earlier draft used a non-existent module).
W12: both tests below carry the pytest 'slow' marker decoration so they
are deselected by `-m "not slow"` in fast CI runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flyer_generator.brand_kit.applier import apply_brand_kit
from flyer_generator.brand_kit.audit import audit_render
from flyer_generator.brand_kit.models import BrandKit
from flyer_generator.brochure.schema_renderer.content_model import BrochureContent
from flyer_generator.brochure.schema_renderer.loader import load_template
from flyer_generator.brochure.schema_renderer.renderer import render_schema_brochure

REPO_ROOT = Path(__file__).resolve().parents[2]


def _sample_content() -> BrochureContent:
    sample_path = REPO_ROOT / "docs" / "brochure" / "sample-content" / "law_firm.json"
    return BrochureContent.model_validate_json(sample_path.read_text(encoding="utf-8"))


@pytest.mark.slow
def test_end_to_end_brand_kit_applies_and_passes_aa() -> None:
    """Seeded brand-kit-template.json + editorial_classic + law_firm content ->
    renderer produces valid SVG -> audit_render reports AA-clean contrast.
    Decorated as slow because it runs the full render+raster pipeline."""
    # 1) Load the seeded kit from repo-tracked reference
    template_file = REPO_ROOT / ".brand-kit-template.json"
    kit = BrandKit.model_validate(json.loads(template_file.read_text(encoding="utf-8")))

    # 2) Load the template
    t = load_template("editorial_classic")

    # 3) Apply the kit
    applied_template, _logo_bytes = apply_brand_kit(t, kit)

    # 4) Load content
    content = _sample_content()

    # 5) Render (no LLM, no images -- pure SVG)
    outside_svg, inside_svg = render_schema_brochure(applied_template, content)
    assert outside_svg.startswith("<?xml") or outside_svg.lstrip().startswith("<svg")
    assert inside_svg.lstrip().startswith("<?xml") or inside_svg.lstrip().startswith("<svg")

    # 6) Rasterize -- B5: correct import path from `flyer_generator.stages.rasterizer`
    from flyer_generator.stages.rasterizer import Rasterizer

    # Bleed canvas dims come from brochure.stages.layout (same source as the
    # schema_renderer CLI uses). If somehow unavailable, fall back to the known
    # values (3376 x 2626 for trifold bleed canvas).
    try:
        from flyer_generator.brochure.stages.layout import (  # type: ignore[attr-defined]
            BLEED_CANVAS_HEIGHT,
            BLEED_CANVAS_WIDTH,
        )
    except ImportError:
        BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT = 3376, 2626

    rasterizer = Rasterizer(width=BLEED_CANVAS_WIDTH, height=BLEED_CANVAS_HEIGHT)
    outside_png = rasterizer.rasterize(outside_svg)
    assert len(outside_png) > 1000  # sanity: non-empty PNG

    # 7) Audit
    report = audit_render(content, applied_template, outside_png, side="outside")

    # The kit's neutral_dark=#1A1A1A on neutral_light=#FAFAF7 is AA-clean.
    # The kit's primary=#1E3A5F on neutral_light is also AA-clean.
    assert report.contrast.overall_aa_pass, (
        f"Contrast failures: {[p.model_dump() for p in report.contrast.fails()]}"
    )


@pytest.mark.slow
def test_end_to_end_no_mutation_of_input_template() -> None:
    """apply_brand_kit must not mutate the caller's template."""
    template_file = REPO_ROOT / ".brand-kit-template.json"
    kit = BrandKit.model_validate(json.loads(template_file.read_text(encoding="utf-8")))

    t = load_template("editorial_classic")
    before = t.model_dump_json()
    applied, _ = apply_brand_kit(t, kit)
    after = t.model_dump_json()
    assert before == after
    assert applied.model_dump_json() != before
