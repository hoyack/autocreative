"""Pydantic v2 data contracts for the Phase 19 social-posting subsystem.

Every model uses ``ConfigDict(extra="forbid")`` so malformed ``post.json`` or
``campaign.json`` files fail loudly at load time. ``PlatformRules`` and
``ImageAspect`` are also ``frozen=True`` -- they describe static per-platform
constants that must not be mutated after construction.

This module is import-side-effect free: no filesystem, network, or env access.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["linkedin", "twitter", "instagram", "facebook"]
Intent = Literal["announcement", "value-prop", "testimonial"]
ImageRole = Literal["link_preview", "feed_square", "feed_portrait", "story", "primary"]


class ImageAspect(BaseModel):
    """A single recommended image aspect for a platform."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    aspect_ratio: float = Field(gt=0.0)
    role: ImageRole


class PlatformRules(BaseModel):
    """Static per-platform validation rules (body length, images, hashtags).

    Frozen so generator code can treat rule instances as constants.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: Platform
    body_max_chars: int = Field(gt=0)
    body_recommended_max: int | None = None
    body_visible_before_truncation: int | None = None
    hashtag_hard_max: int | None = None
    hashtag_recommended_max: int = Field(ge=0)
    image_aspects: tuple[ImageAspect, ...] = Field(default_factory=tuple)
    image_max_bytes: int = Field(gt=0)
    image_recommended_max_bytes: int = Field(gt=0)
    images_per_post_max: int = Field(ge=0)
    clickable_links_in_body: bool
    strips_links_in_caption: bool
    readability_grade_max: int = 12


class ValidationIssue(BaseModel):
    """A single validator finding. Severity drives ``ValidationReport.passed``."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["info", "warn", "error"]
    rule_id: str
    message: str
    field: str | None = None
    actual: object | None = None
    expected: object | None = None


class ValidationReport(BaseModel):
    """Aggregated validator output for one post on one platform."""

    model_config = ConfigDict(extra="forbid")

    platform: Platform
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True iff no error-severity issues are present (warnings allowed)."""
        return not any(i.severity == "error" for i in self.issues)

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warn"]


class PostCopy(BaseModel):
    """Rendered copy fields for one post."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    body: str = ""
    cta: str | None = None
    hashtags: list[str] = Field(default_factory=list)


class PostBrief(BaseModel):
    """Input-side brief describing what to generate for one platform."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    intent: Intent
    platform: Platform
    cta: str | None = None
    source_url: str | None = None
    image_hint: str | None = None
    hashtags_seed: list[str] = Field(default_factory=list)


class PostSpec(BaseModel):
    """Wrapper that pairs a brief with an optional template-name override.

    Distinct from :class:`Post` which is the generated output artifact.
    """

    model_config = ConfigDict(extra="forbid")

    brief: PostBrief
    template_name: str | None = None  # default = "{platform}__{intent}"


class Post(BaseModel):
    """A generated post artifact. ``image_bytes`` travels in-memory only."""

    model_config = ConfigDict(extra="forbid")

    platform: Platform
    intent: Intent
    copy: PostCopy
    image_bytes: bytes | None = None
    validation_report: ValidationReport
    audit_summary: str = "unknown"


class Campaign(BaseModel):
    """A collection of posts across platforms for one topic.

    ``posts`` is a mapping of ``"{platform}__{intent}"`` -> arbitrary dict.
    Using ``dict[str, object]`` (rather than ``dict[str, Post]``) keeps
    ``campaign.json`` serializable without embedding raw PNG bytes -- Plan 07
    tightens this once binary-in-JSON resolution lands.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    campaign_id: str
    brand_kit_slug: str
    topic: str = ""
    platforms: list[Platform] = Field(default_factory=list)
    created_at: datetime
    posts: dict[str, object] = Field(default_factory=dict)
    # In-memory only: full Post objects keyed by "{platform}__{intent}",
    # preserving image_bytes for downstream persistence. Excluded from
    # campaign.json to avoid embedding base64 PNGs.
    posts_full: dict[str, "Post"] = Field(default_factory=dict, exclude=True, repr=False)
