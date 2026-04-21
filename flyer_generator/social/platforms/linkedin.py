"""LinkedIn platform rules and validator.

Values verified April 2026. Sources: socialrails.com, imresizer.com, linkedin.com/help.
"""

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
)

RULES = PlatformRules(
    platform="linkedin",
    body_max_chars=3000,
    body_recommended_max=2500,
    body_visible_before_truncation=210,
    hashtag_hard_max=30,
    hashtag_recommended_max=4,
    image_aspects=(
        ImageAspect(width=1200, height=627, aspect_ratio=1200 / 627, role="link_preview"),
        ImageAspect(width=1200, height=1200, aspect_ratio=1.0, role="feed_square"),
    ),
    image_max_bytes=5 * 1024 * 1024,
    image_recommended_max_bytes=1 * 1024 * 1024,
    images_per_post_max=1,
    clickable_links_in_body=True,
    strips_links_in_caption=False,
    readability_grade_max=12,
)


def validate(post: Post, rules: PlatformRules = RULES) -> ValidationReport:
    issues: list[ValidationIssue] = []
    body_issue = check_char_limit(
        post.copy.body, rules.body_max_chars, "copy.body", "LINKEDIN_BODY_OVER"
    )
    if body_issue:
        issues.append(body_issue)
    issues.extend(
        check_hashtag_count(post.copy.hashtags, rules.hashtag_hard_max, "copy.hashtags")
    )
    if post.image_bytes is not None:
        issues.extend(
            check_image_bytes(
                len(post.image_bytes),
                rules.image_max_bytes,
                rules.image_recommended_max_bytes,
                rule_id_error="LINKEDIN_IMAGE_BYTES_OVER",
                rule_id_warn="LINKEDIN_IMAGE_BYTES_LARGE",
            )
        )
        w, h = _pillow_dims(post.image_bytes)
        issues.extend(
            check_image_aspect(
                w, h, rules.image_aspects, rule_id="LINKEDIN_IMAGE_ASPECT_MISMATCH"
            )
        )
    return ValidationReport(platform=rules.platform, issues=issues)
