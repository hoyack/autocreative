"""Per checker B1: direct-module imports only.

Exercises schema loading, naming convention, and platform-aspect coherence for
all 12 templates required by SOC-03 (3 intents x 4 platforms).

These tests are the source-of-truth for the Plan 05 template contract. If
either the template files or the ``PostTemplate`` Pydantic model drift, these
tests fail loud here rather than at render time in Plan 06.
"""

from __future__ import annotations

import pytest

from flyer_generator.social.schemas.loader import (
    list_post_templates,
    load_post_template,
    parse_template_name,
)

_EXPECTED_NAMES = [
    "facebook__announcement",
    "facebook__testimonial",
    "facebook__value-prop",
    "instagram__announcement",
    "instagram__testimonial",
    "instagram__value-prop",
    "linkedin__announcement",
    "linkedin__testimonial",
    "linkedin__value-prop",
    "twitter__announcement",
    "twitter__testimonial",
    "twitter__value-prop",
]

# Platform primary canvas -- (width, height). Templates may use these or a
# secondary aspect from their platform's rules.
_EXPECTED_CANVASES: dict[str, set[tuple[int, int]]] = {
    "linkedin": {(1200, 627), (1200, 1200)},
    "twitter": {(1200, 675)},
    "instagram": {(1080, 1080), (1080, 1350), (1080, 1920)},
    "facebook": {(1200, 630), (1080, 1080), (1080, 1350)},
}

# Hashtag budget must not exceed platform hard cap (in chars, approximating
# hashtag count x avg len)
_MAX_BODY_CHARS: dict[str, int] = {
    "linkedin": 3000,
    "twitter": 280,
    "instagram": 2200,
    "facebook": 63206,  # system cap; individual templates target <500 for engagement
}


def test_all_twelve_templates_listed() -> None:
    actual = list_post_templates()
    assert actual == _EXPECTED_NAMES, f"got {actual}"


@pytest.mark.parametrize("name", _EXPECTED_NAMES)
def test_template_loads_and_validates(name: str) -> None:
    t = load_post_template(name)
    assert t.schema_version == "1"
    assert t.name == name


@pytest.mark.parametrize("name", _EXPECTED_NAMES)
def test_template_platform_and_intent_match_filename(name: str) -> None:
    platform, intent = parse_template_name(name)
    t = load_post_template(name)
    assert t.platform == platform
    assert t.intent == intent


@pytest.mark.parametrize("name", _EXPECTED_NAMES)
def test_template_canvas_matches_platform_aspect(name: str) -> None:
    t = load_post_template(name)
    allowed = _EXPECTED_CANVASES[t.platform]
    actual = (t.canvas.width, t.canvas.height)
    assert actual in allowed, (
        f"{name}: canvas {actual} not in platform's allowed set {allowed}"
    )


@pytest.mark.parametrize("name", _EXPECTED_NAMES)
def test_template_body_budget_within_platform_cap(name: str) -> None:
    t = load_post_template(name)
    body_budget = t.text_budgets.get("copy.body", 0)
    cap = _MAX_BODY_CHARS[t.platform]
    assert body_budget <= cap, (
        f"{name}: copy.body budget {body_budget} exceeds platform cap {cap}"
    )


@pytest.mark.parametrize("name", _EXPECTED_NAMES)
def test_template_has_required_budget_keys(name: str) -> None:
    """Every template must declare budgets for title/body/cta/hashtags."""
    t = load_post_template(name)
    required_keys = {"copy.title", "copy.body", "copy.cta", "copy.hashtags"}
    missing = required_keys - t.text_budgets.keys()
    assert not missing, f"{name}: missing text_budgets keys {missing}"
    for key, val in t.text_budgets.items():
        assert val > 0, f"{name}: text_budgets[{key!r}] must be positive"


@pytest.mark.parametrize("name", _EXPECTED_NAMES)
def test_template_has_at_least_one_text_slot(name: str) -> None:
    t = load_post_template(name)
    assert len(t.text_slots) >= 1, f"{name}: expected >=1 text_slot"


@pytest.mark.parametrize("name", _EXPECTED_NAMES)
def test_image_slot_bbox_within_canvas_when_present(name: str) -> None:
    t = load_post_template(name)
    if t.image_slot is None:
        return
    x, y, w, h = t.image_slot.bbox
    assert x >= 0 and y >= 0, f"{name}: image_slot origin negative"
    assert x + w <= t.canvas.width, (
        f"{name}: image_slot extends past canvas width "
        f"({x}+{w} > {t.canvas.width})"
    )
    assert y + h <= t.canvas.height, (
        f"{name}: image_slot extends past canvas height "
        f"({y}+{h} > {t.canvas.height})"
    )


def test_at_least_one_text_only_template() -> None:
    """At least one Twitter template should have image_slot=None to exercise
    text-only branch (19-RESEARCH.md Open Risks #8)."""
    t = load_post_template("twitter__announcement")
    assert t.image_slot is None, (
        "twitter__announcement should be text-only (image_slot=null)"
    )


def test_palette_and_typography_nullable_for_brand_kit_injection() -> None:
    """Templates should leave palette/typography null so apply_brand_kit
    fills them (SOC-02/SOC-05 invariant per Plan 05 Task 2 Step 1)."""
    for name in _EXPECTED_NAMES:
        t = load_post_template(name)
        assert t.palette is None, (
            f"{name}: palette should be null (inherit from brand kit)"
        )
        assert t.typography is None, (
            f"{name}: typography should be null (inherit from brand kit)"
        )
