"""Phase 19 social media posting system -- public API.

Artifact producers: :func:`generate_post` (single), :func:`generate_campaign`
(multi-platform shared hero).
Platform rules: linkedin / twitter / instagram / facebook.
Intents: announcement / value-prop / testimonial.

Publishing to platform APIs is OUT OF SCOPE for Phase 19 (SOC-11). This
package produces artifacts (``post.json`` + ``image.png`` + optional
``audit.json``) and nothing else. No publishing-SDK client libraries are
imported anywhere under ``flyer_generator/social/``; the banned-import
guard test in ``tests/social/test_package_exports.py`` enforces that
invariant at CI time.
"""

from __future__ import annotations

# Audit
from flyer_generator.social.audit import SocialAuditReport, audit_post

# Campaign orchestrator
from flyer_generator.social.campaign import generate_campaign

# Single-post orchestrator
from flyer_generator.social.generator import generate_post

# Data models
from flyer_generator.social.models import (
    Campaign,
    ImageAspect,
    Intent,
    Platform,
    PlatformRules,
    Post,
    PostBrief,
    PostCopy,
    PostSpec,
    ValidationIssue,
    ValidationReport,
)

# Platform registry
from flyer_generator.social.platforms import (
    PLATFORM_REGISTRY,
    load_platform_rules,
    validate_post,
)

# Readability
from flyer_generator.social.readability import flesch_kincaid_grade

# Schema / templates
from flyer_generator.social.schemas.loader import (
    list_post_templates,
    load_post_template,
    parse_template_name,
)
from flyer_generator.social.schemas.schema_model import (
    ImageSlot,
    PostTemplate,
    TextSlot,
)

# Storage
from flyer_generator.social.storage import (
    list_campaigns,
    load_campaign,
    load_post,
    resolve_campaign_dir,
    save_campaign,
    save_post,
)

# Voice
from flyer_generator.social.voice import (
    format_voice_directive,
    generate_social_copy,
)

__all__ = sorted(
    [
        "Campaign",
        "ImageAspect",
        "ImageSlot",
        "Intent",
        "PLATFORM_REGISTRY",
        "Platform",
        "PlatformRules",
        "Post",
        "PostBrief",
        "PostCopy",
        "PostSpec",
        "PostTemplate",
        "SocialAuditReport",
        "TextSlot",
        "ValidationIssue",
        "ValidationReport",
        "audit_post",
        "flesch_kincaid_grade",
        "format_voice_directive",
        "generate_campaign",
        "generate_post",
        "generate_social_copy",
        "list_campaigns",
        "list_post_templates",
        "load_campaign",
        "load_platform_rules",
        "load_post",
        "load_post_template",
        "parse_template_name",
        "resolve_campaign_dir",
        "save_campaign",
        "save_post",
        "validate_post",
    ]
)
