"""Per checker B1: direct-module imports only (no from flyer_generator.social import ...)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from flyer_generator.social.models import (
    Campaign,
    ImageAspect,
    PlatformRules,
    Post,
    PostBrief,
    PostCopy,
    PostSpec,
    ValidationIssue,
    ValidationReport,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_FILE = REPO_ROOT / ".social-template.json"


def _minimal_brief() -> PostBrief:
    return PostBrief(topic="test", intent="value-prop", platform="linkedin")


def test_post_brief_minimal_fields() -> None:
    b = _minimal_brief()
    assert b.topic == "test"
    assert b.intent == "value-prop"
    assert b.platform == "linkedin"
    assert b.cta is None
    assert b.hashtags_seed == []


def test_post_brief_all_optional_fields() -> None:
    b = PostBrief(
        topic="t",
        intent="announcement",
        platform="twitter",
        cta="Learn more",
        source_url="https://example.com",
        image_hint="abstract",
        hashtags_seed=["ai", "ml"],
    )
    assert b.cta == "Learn more"
    assert b.hashtags_seed == ["ai", "ml"]


def test_platform_rules_frozen() -> None:
    rules = PlatformRules(
        platform="linkedin",
        body_max_chars=3000,
        hashtag_recommended_max=4,
        image_aspects=(ImageAspect(width=1200, height=627, aspect_ratio=1.91, role="link_preview"),),
        image_max_bytes=5_242_880,
        image_recommended_max_bytes=1_048_576,
        images_per_post_max=1,
        clickable_links_in_body=True,
        strips_links_in_caption=False,
    )
    with pytest.raises(ValidationError):
        rules.body_max_chars = 9999  # type: ignore[misc]


def test_validation_report_passed_property() -> None:
    r_clean = ValidationReport(platform="linkedin")
    assert r_clean.passed is True
    r_warn = ValidationReport(
        platform="linkedin",
        issues=[ValidationIssue(severity="warn", rule_id="X", message="m")],
    )
    assert r_warn.passed is True
    r_err = ValidationReport(
        platform="linkedin",
        issues=[ValidationIssue(severity="error", rule_id="X", message="m")],
    )
    assert r_err.passed is False


def test_post_constructs_and_roundtrips() -> None:
    post = Post(
        platform="linkedin",
        intent="value-prop",
        copy=PostCopy(title="T", body="B", cta="C", hashtags=["#x"]),
        image_bytes=None,
        validation_report=ValidationReport(platform="linkedin"),
        audit_summary="clean",
    )
    round_tripped = Post.model_validate_json(post.model_dump_json())
    assert round_tripped == post


def test_extra_forbid_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        PostBrief(topic="t", intent="value-prop", platform="linkedin", nonsense=True)  # type: ignore[call-arg]


def test_social_template_json_roundtrips_through_campaign() -> None:
    """The tracked .social-template.json at repo root must validate as Campaign."""
    assert TEMPLATE_FILE.exists(), f"{TEMPLATE_FILE} must exist and be tracked"
    data = json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))
    c = Campaign.model_validate(data)
    assert c.campaign_id == data["campaign_id"]
    # Round-trip: dump and re-parse
    c2 = Campaign.model_validate_json(c.model_dump_json())
    assert c2.brand_kit_slug == c.brand_kit_slug
