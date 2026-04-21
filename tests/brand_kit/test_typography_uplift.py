"""Numeric guardrail for Plan 18-08 typography uplift (B7 policy).

These assertions are the contract that Plan 18-08 delivered on. They
re-check every time the test suite runs so future edits don't silently
re-introduce the "fonts read too small" regression.

B1: direct-module imports only - no `from flyer_generator.brand_kit import ...`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flyer_generator.brochure.schema_renderer.loader import (
    list_templates,
    load_template,
)


MIN_BODY_SIZE = 34
MIN_BULLET_SIZE = 32
LINE_HEIGHT_RATIO_RANGE = (1.26, 1.34)
MIN_CHARS_PER_LINE = 20  # loose sanity floor


SCHEMAS_DIR = (
    Path(__file__).resolve().parents[2]
    / "flyer_generator"
    / "brochure"
    / "schemas"
)


@pytest.mark.parametrize("template_name", list_templates())
def test_body_size_meets_baseline(template_name: str) -> None:
    """B7: every template's body_size must be >= 34 after uplift."""
    t = load_template(template_name)
    assert t.typography.body_size >= MIN_BODY_SIZE, (
        f"{template_name}: body_size {t.typography.body_size} < {MIN_BODY_SIZE}"
    )


@pytest.mark.parametrize("template_name", list_templates())
def test_bullet_size_meets_baseline(template_name: str) -> None:
    """B7: every template's bullet_size must be >= 32 after uplift."""
    t = load_template(template_name)
    assert t.typography.bullet_size >= MIN_BULLET_SIZE, (
        f"{template_name}: bullet_size {t.typography.bullet_size} < {MIN_BULLET_SIZE}"
    )


@pytest.mark.parametrize("template_name", list_templates())
def test_body_line_height_is_proportional(template_name: str) -> None:
    t = load_template(template_name)
    ratio = t.typography.body_line_height / t.typography.body_size
    lo, hi = LINE_HEIGHT_RATIO_RANGE
    assert lo <= ratio <= hi, (
        f"{template_name}: body_line_height/body_size = {ratio:.2f} "
        f"outside [{lo}, {hi}]"
    )


@pytest.mark.parametrize("template_name", list_templates())
def test_bullet_line_height_is_proportional(template_name: str) -> None:
    t = load_template(template_name)
    ratio = t.typography.bullet_line_height / t.typography.bullet_size
    lo, hi = LINE_HEIGHT_RATIO_RANGE
    assert lo <= ratio <= hi, (
        f"{template_name}: bullet_line_height/bullet_size = {ratio:.2f} "
        f"outside [{lo}, {hi}]"
    )


@pytest.mark.parametrize("template_name", list_templates())
def test_body_max_chars_not_regressed(template_name: str) -> None:
    """Sanity floor: char budget should never drop below a clearly-usable line length."""
    t = load_template(template_name)
    assert t.typography.body_max_chars_per_line >= MIN_CHARS_PER_LINE, (
        f"{template_name}: body_max_chars_per_line {t.typography.body_max_chars_per_line} "
        f"< {MIN_CHARS_PER_LINE}"
    )


@pytest.mark.parametrize("template_name", list_templates())
def test_raw_json_body_size_meets_baseline(template_name: str) -> None:
    """B7 grep-verifiable: direct JSON read (not via model defaulting) shows body_size >= 34."""
    schema_path = SCHEMAS_DIR / f"{template_name}.json"
    raw = json.loads(schema_path.read_text(encoding="utf-8"))
    body_size = raw.get("typography", {}).get("body_size")
    assert body_size is not None, f"{template_name}: no body_size in raw JSON"
    assert body_size >= MIN_BODY_SIZE, (
        f"{template_name}: raw body_size {body_size} < {MIN_BODY_SIZE}"
    )


@pytest.mark.parametrize("template_name", list_templates())
def test_raw_json_bullet_size_meets_baseline(template_name: str) -> None:
    """B7 grep-verifiable: direct JSON read shows bullet_size >= 32."""
    schema_path = SCHEMAS_DIR / f"{template_name}.json"
    raw = json.loads(schema_path.read_text(encoding="utf-8"))
    bullet_size = raw.get("typography", {}).get("bullet_size")
    assert bullet_size is not None, f"{template_name}: no bullet_size in raw JSON"
    assert bullet_size >= MIN_BULLET_SIZE, (
        f"{template_name}: raw bullet_size {bullet_size} < {MIN_BULLET_SIZE}"
    )


def test_all_13_templates_uplifted() -> None:
    """Meta-assertion: 13 known templates all validate + meet thresholds."""
    names = list_templates()
    assert len(names) == 13, f"Expected 13 templates, got {len(names)}: {names}"
    for name in names:
        t = load_template(name)
        assert t.typography.body_size >= MIN_BODY_SIZE
        assert t.typography.bullet_size >= MIN_BULLET_SIZE
