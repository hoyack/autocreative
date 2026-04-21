"""Instagram platform rules and validator.

Load-bearing: captions with URLs are not clickable (warn). 30-hashtag HARD cap enforced.
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
    check_no_urls_in_text,
)

RULES = PlatformRules(
    platform="instagram",
    body_max_chars=2200,
    body_recommended_max=None,
    body_visible_before_truncation=125,
    hashtag_hard_max=30,  # HARD cap, platform-enforced
    hashtag_recommended_max=8,
    image_aspects=(
        ImageAspect(width=1080, height=1080, aspect_ratio=1.0, role="feed_square"),
        ImageAspect(width=1080, height=1350, aspect_ratio=1080 / 1350, role="feed_portrait"),
        ImageAspect(width=1080, height=1920, aspect_ratio=1080 / 1920, role="story"),
    ),
    image_max_bytes=30 * 1024 * 1024,
    image_recommended_max_bytes=8 * 1024 * 1024,
    images_per_post_max=1,  # carousel/multi-image deferred
    clickable_links_in_body=False,  # load-bearing: IG strips URLs from caption
    strips_links_in_caption=True,
    readability_grade_max=12,
)


def validate(post: Post, rules: PlatformRules = RULES) -> ValidationReport:
    issues: list[ValidationIssue] = []
    body_issue = check_char_limit(
        post.copy.body, rules.body_max_chars, "copy.body", "INSTAGRAM_CAPTION_OVER"
    )
    if body_issue:
        issues.append(body_issue)
    # Primitive emits HASHTAG_COUNT_CAP; re-map to platform-specific rule_id.
    hashtag_issues = check_hashtag_count(
        post.copy.hashtags, rules.hashtag_hard_max, "copy.hashtags"
    )
    for issue in hashtag_issues:
        if issue.rule_id == "HASHTAG_COUNT_CAP":
            issues.append(
                issue.model_copy(update={"rule_id": "INSTAGRAM_HASHTAG_COUNT_OVER"})
            )
        else:
            issues.append(issue)
    # Unique to Instagram: URL-in-caption warn (per 19-RESEARCH.md Open Risks #1).
    issues.extend(
        check_no_urls_in_text(
            post.copy.body, rule_id="INSTAGRAM_LINK_IN_CAPTION", severity="warn"
        )
    )
    if post.image_bytes is not None:
        issues.extend(
            check_image_bytes(
                len(post.image_bytes),
                rules.image_max_bytes,
                rules.image_recommended_max_bytes,
                rule_id_error="INSTAGRAM_IMAGE_BYTES_OVER",
                rule_id_warn="INSTAGRAM_IMAGE_BYTES_LARGE",
            )
        )
        w, h = _pillow_dims(post.image_bytes)
        issues.extend(
            check_image_aspect(
                w, h, rules.image_aspects, rule_id="INSTAGRAM_IMAGE_ASPECT_MISMATCH"
            )
        )
    return ValidationReport(platform=rules.platform, issues=issues)
