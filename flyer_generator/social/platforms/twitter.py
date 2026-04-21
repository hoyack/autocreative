"""Twitter/X platform rules and validator (standard tier -- 280 char)."""

from __future__ import annotations

from flyer_generator.social.models import (
    ImageAspect,
    PlatformRules,
    Post,
    ValidationIssue,
    ValidationReport,
)
from flyer_generator.social.validation import (
    _pillow_dims,
    check_char_limit,
    check_hashtag_count,
    check_image_aspect,
    check_image_bytes,
    check_image_count,
)

RULES = PlatformRules(
    platform="twitter",
    body_max_chars=280,
    body_recommended_max=None,
    body_visible_before_truncation=None,
    hashtag_hard_max=None,  # no hard cap
    hashtag_recommended_max=2,
    image_aspects=(
        ImageAspect(width=1200, height=675, aspect_ratio=1200 / 675, role="primary"),
    ),
    image_max_bytes=5 * 1024 * 1024,
    image_recommended_max_bytes=2 * 1024 * 1024,
    images_per_post_max=4,
    clickable_links_in_body=True,
    strips_links_in_caption=False,
    readability_grade_max=12,
)


def validate(
    post: Post,
    rules: PlatformRules = RULES,
    image_count: int = 1,
) -> ValidationReport:
    """Validate a Twitter/X post.

    ``image_count`` models multi-image tweets: a single ``Post`` carries at
    most one ``image_bytes`` payload, but callers staging carousels bump this
    kwarg. When ``post.image_bytes is None`` the effective count is 0.
    """
    issues: list[ValidationIssue] = []
    body_issue = check_char_limit(
        post.copy.body, rules.body_max_chars, "copy.body", "TWITTER_TEXT_OVER"
    )
    if body_issue:
        issues.append(body_issue)
    issues.extend(
        check_hashtag_count(post.copy.hashtags, rules.hashtag_hard_max, "copy.hashtags")
    )
    effective_count = image_count if post.image_bytes is not None else 0
    issues.extend(
        check_image_count(
            effective_count, rules.images_per_post_max, rule_id="TWITTER_IMAGE_COUNT_OVER"
        )
    )
    if post.image_bytes is not None:
        issues.extend(
            check_image_bytes(
                len(post.image_bytes),
                rules.image_max_bytes,
                rules.image_recommended_max_bytes,
                rule_id_error="TWITTER_IMAGE_BYTES_OVER",
                rule_id_warn="TWITTER_IMAGE_BYTES_LARGE",
            )
        )
        w, h = _pillow_dims(post.image_bytes)
        issues.extend(
            check_image_aspect(
                w, h, rules.image_aspects, rule_id="TWITTER_IMAGE_ASPECT_MISMATCH"
            )
        )
    return ValidationReport(platform=rules.platform, issues=issues)
