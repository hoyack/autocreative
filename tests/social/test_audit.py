"""Per checker B1: direct-module imports only."""

from __future__ import annotations

import io
from datetime import datetime, timezone

from PIL import Image

from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandPalette,
    BrandTypography,
    ColorUsage,
)
from flyer_generator.social.audit import (
    SocialAuditReport,
    _readability_check,
    audit_post,
)
from flyer_generator.social.models import Post, PostCopy, ValidationReport
from flyer_generator.social.schemas.loader import load_post_template


def _make_kit() -> BrandKit:
    return BrandKit(
        name="Test",
        fetched_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
        palette=BrandPalette(
            primary=ColorUsage(hex="#1E3A5F"),
            secondary=ColorUsage(hex="#C4A269"),
            accent=ColorUsage(hex="#E8F1F2"),
            neutral_dark=ColorUsage(hex="#1A1A1A"),
            neutral_light=ColorUsage(hex="#FAFAF7"),
        ),
        typography=BrandTypography(
            heading_family="sans", body_family="sans"
        ),
    )


def _make_png(w: int, h: int) -> bytes:
    img = Image.new("RGB", (w, h), (64, 128, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_readability_check_low_grade_no_issue() -> None:
    grade, issue = _readability_check("The cat sat.", grade_max=12)
    assert grade < 12
    assert issue is None


def test_readability_check_high_grade_emits_warn() -> None:
    text = (
        "The phenomenological interpretation of institutional epistemologies "
        "necessitates a reconceptualization of hermeneutic methodologies. "
        "Consequently, multidimensional analysis frameworks accommodate interdisciplinary "
        "perspectives on sociocultural transformation processes."
    )
    grade, issue = _readability_check(text, grade_max=12)
    assert grade > 12
    assert issue is not None
    assert issue.severity == "warn"
    assert issue.rule_id == "READABILITY_HIGH_GRADE"


def test_audit_post_linkedin_clean() -> None:
    kit = _make_kit()
    template = load_post_template("linkedin__value-prop")
    png = _make_png(1200, 627)
    post = Post(
        platform="linkedin",
        intent="value-prop",
        copy=PostCopy(
            title="Short title",
            body="Short sentence. Easy to read. Quick to skim.",
            cta="Read",
            hashtags=["#test", "#python"],
        ),
        image_bytes=png,
        validation_report=ValidationReport(platform="linkedin"),
        audit_summary="unknown",
    )
    report = audit_post(post, kit, template)
    assert isinstance(report, SocialAuditReport)
    assert report.validation.platform == "linkedin"
    assert report.validation.passed is True
    assert report.readability_grade < 12
    assert report.readability_issue is None


def test_audit_post_instagram_link_in_caption_warn() -> None:
    kit = _make_kit()
    template = load_post_template("instagram__value-prop")
    png = _make_png(1080, 1350)
    post = Post(
        platform="instagram",
        intent="value-prop",
        copy=PostCopy(
            title="t",
            body="Visit our site at https://example.com for more info.",
            cta="Link in bio",
            hashtags=["#test"],
        ),
        image_bytes=png,
        validation_report=ValidationReport(platform="instagram"),
        audit_summary="unknown",
    )
    report = audit_post(post, kit, template)
    # INSTAGRAM_LINK_IN_CAPTION is emitted by the platform validator as a warn
    # issue. The audit composes the validation report, so we check the
    # validation issues list.
    link_issues = [
        i
        for i in report.validation.issues
        if i.rule_id == "INSTAGRAM_LINK_IN_CAPTION"
    ]
    assert len(link_issues) >= 1
    assert link_issues[0].severity == "warn"
    # passed should still be True -- warn doesn't flip passed
    assert report.validation.passed is True


def test_audit_post_text_only_twitter_no_brand_audit() -> None:
    kit = _make_kit()
    template = load_post_template("twitter__announcement")
    post = Post(
        platform="twitter",
        intent="announcement",
        copy=PostCopy(title="t", body="Short tweet.", cta="See", hashtags=["#a"]),
        image_bytes=None,
        validation_report=ValidationReport(platform="twitter"),
        audit_summary="unknown",
    )
    report = audit_post(post, kit, template)
    assert report.brand_audit is None  # no image = no brand-audit
    assert report.validation.passed is True


def test_audit_post_hard_error_blocks_is_clean() -> None:
    kit = _make_kit()
    template = load_post_template("linkedin__value-prop")
    png = _make_png(1200, 627)
    post = Post(
        platform="linkedin",
        intent="value-prop",
        copy=PostCopy(
            title="T",
            body="x" * 3500,  # OVER 3000 cap -- hard error
            cta="R",
            hashtags=[],
        ),
        image_bytes=png,
        validation_report=ValidationReport(platform="linkedin"),
        audit_summary="unknown",
    )
    report = audit_post(post, kit, template)
    assert report.validation.passed is False
    assert report.is_clean is False


def test_audit_post_image_bearing_produces_real_brand_audit() -> None:
    """B-04 regression guard: image-bearing posts MUST have a real brand_audit
    (ContrastReport + density map), not None-on-exception."""
    from flyer_generator.brand_kit.audit import AuditReport
    kit = _make_kit()
    template = load_post_template("linkedin__value-prop")
    png = _make_png(1200, 627)
    post = Post(
        platform="linkedin",
        intent="value-prop",
        copy=PostCopy(title="T", body="Short body.", cta="R", hashtags=["#a"]),
        image_bytes=png,
        validation_report=ValidationReport(platform="linkedin"),
        audit_summary="unknown",
    )
    report = audit_post(post, kit, template)
    assert report.brand_audit is not None, (
        "image-bearing post must produce real brand_audit (B-04 regression)"
    )
    assert isinstance(report.brand_audit, AuditReport)
    # Real contrast pairs computed, not empty ContrastReport
    assert len(report.brand_audit.contrast.pairs) >= 1
    # Real density map computed over image-slot regions
    assert "region_0" in report.brand_audit.density or any(
        k.startswith("region_") for k in report.brand_audit.density
    )
