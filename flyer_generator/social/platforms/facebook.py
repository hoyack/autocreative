"""Facebook platform rules and validator.

No hard char cap at the product level (63206 is system-level). Warn over 500
is an engagement heuristic.
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
    platform="facebook",
    body_max_chars=63206,  # system cap
    body_recommended_max=500,  # engagement recommended upper
    body_visible_before_truncation=None,
    hashtag_hard_max=None,
    hashtag_recommended_max=2,
    image_aspects=(
        ImageAspect(width=1200, height=630, aspect_ratio=1200 / 630, role="link_preview"),
        ImageAspect(width=1080, height=1080, aspect_ratio=1.0, role="feed_square"),
        ImageAspect(width=1080, height=1350, aspect_ratio=1080 / 1350, role="feed_portrait"),
    ),
    image_max_bytes=30 * 1024 * 1024,
    image_recommended_max_bytes=8 * 1024 * 1024,
    images_per_post_max=1,
    clickable_links_in_body=True,
    strips_links_in_caption=False,
    readability_grade_max=12,
)


def validate(post: Post, rules: PlatformRules = RULES) -> ValidationReport:
    issues: list[ValidationIssue] = []
    # Hard cap at system level (very permissive -- almost always passes).
    body_issue = check_char_limit(
        post.copy.body, rules.body_max_chars, "copy.body", "FACEBOOK_BODY_OVER"
    )
    if body_issue:
        issues.append(body_issue)
    # Warn over recommended engagement threshold.
    if (
        rules.body_recommended_max is not None
        and len(post.copy.body) > rules.body_recommended_max
    ):
        issues.append(
            ValidationIssue(
                severity="warn",
                rule_id="FACEBOOK_BODY_LONG",
                message=(
                    f"body is {len(post.copy.body)} chars, above recommended "
                    f"{rules.body_recommended_max} for engagement"
                ),
                field="copy.body",
                actual=len(post.copy.body),
                expected=rules.body_recommended_max,
            )
        )
    issues.extend(
        check_hashtag_count(post.copy.hashtags, rules.hashtag_hard_max, "copy.hashtags")
    )
    if post.image_bytes is not None:
        issues.extend(
            check_image_bytes(
                len(post.image_bytes),
                rules.image_max_bytes,
                rules.image_recommended_max_bytes,
                rule_id_error="FACEBOOK_IMAGE_BYTES_OVER",
                rule_id_warn="FACEBOOK_IMAGE_BYTES_LARGE",
            )
        )
        w, h = _pillow_dims(post.image_bytes)
        issues.extend(
            check_image_aspect(
                w, h, rules.image_aspects, rule_id="FACEBOOK_IMAGE_ASPECT_MISMATCH"
            )
        )
    return ValidationReport(platform=rules.platform, issues=issues)
