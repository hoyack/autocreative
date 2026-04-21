"""Platform-aware post audit.

Wraps ``flyer_generator.brand_kit.audit.AuditReport`` (does NOT subclass -- per
19-PATTERNS.md line 364) and adds three new categories on top of
brand_kit's whitespace/contrast/density: platform_compliance, link_policy,
readability.

Design choice (B-04): ``audit_post`` does NOT call ``audit_render`` -- the
brochure audit entry point requires a ``BrochureContent`` + ``TemplateSchema``
shape that is alien to social posts. Instead, Plan 08 extracts two shared
primitives out of brand_kit/audit.py -- ``scan_text_contrast`` and
``scan_image_density`` -- and calls them directly with post-specific pairs and
regions. This yields a REAL ``ContrastReport`` + REAL density map in
``SocialAuditReport.brand_audit``, satisfying SOC-07 without adapter gymnastics.

B1: this module does NOT write to ``flyer_generator/social/__init__.py``.
Direct-module imports only.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, ConfigDict, Field

from flyer_generator.brand_kit.audit import AuditReport
from flyer_generator.brand_kit.models import BrandKit
from flyer_generator.social.models import Post, ValidationIssue, ValidationReport
from flyer_generator.social.platforms import PLATFORM_REGISTRY
from flyer_generator.social.readability import flesch_kincaid_grade
from flyer_generator.social.schemas.schema_model import PostTemplate

logger = structlog.get_logger(__name__)


class SocialAuditReport(BaseModel):
    """Aggregate report covering platform compliance + readability + brand (contrast/density).

    Fields:
        validation: ValidationReport from platforms.<name>.validate. Contains
            platform-specific issues (char-cap, hashtag-cap, image-aspect,
            link-in-caption, etc.). ``validation.passed`` = no error-severity
            entries.
        readability_grade: Flesch-Kincaid grade for ``post.copy.body``.
        readability_issue: warn-severity ValidationIssue when
            ``grade > rules.readability_grade_max``; None otherwise.
        hashtag_issues: subset of ``validation.issues`` whose ``field`` starts
            with ``copy.hashtags``. Reserved for callers who want to surface
            hashtag-only problems without filtering the full validation list.
        brand_audit: AuditReport wrapping the real ContrastReport + density map
            for image-bearing posts. None for text-only posts (no PNG to scan).
        issues: net-new audit-level ValidationIssues (currently the
            ``READABILITY_HIGH_GRADE`` warn, when present). Platform-emitted
            issues live in ``validation.issues`` and are not duplicated here.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    validation: ValidationReport
    readability_grade: float
    readability_issue: ValidationIssue | None = None
    hashtag_issues: list[ValidationIssue] = Field(default_factory=list)
    brand_audit: AuditReport | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """True iff validation passed, brand_audit (if present) is clean, and no
        error-severity audit-level issues exist."""
        if not self.validation.passed:
            return False
        if self.brand_audit is not None and not self.brand_audit.is_clean:
            return False
        if any(i.severity == "error" for i in self.issues):
            return False
        return True


def _readability_check(
    body: str, grade_max: int = 12
) -> tuple[float, ValidationIssue | None]:
    """Compute Flesch-Kincaid grade and emit a warn issue if over threshold."""
    grade = flesch_kincaid_grade(body)
    if grade > grade_max:
        issue = ValidationIssue(
            severity="warn",
            rule_id="READABILITY_HIGH_GRADE",
            message=f"body readability grade {grade:.1f} exceeds threshold {grade_max}",
            field="copy.body",
            actual=round(grade, 2),
            expected=grade_max,
        )
        return (grade, issue)
    return (grade, None)


def _bbox_overlaps(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    """AABB overlap test. True iff rectangles share any area."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (
        ax + aw <= bx
        or bx + bw <= ax
        or ay + ah <= by
        or by + bh <= ay
    )


def audit_post(
    post: Post,
    brand_kit: BrandKit,
    template: PostTemplate,
) -> SocialAuditReport:
    """Run platform + readability + (if image) contrast/density audit.

    Returns a ``SocialAuditReport``. Raises no exceptions for advisory issues --
    everything is surfaced via severity in the returned report.

    Args:
        post: The generated post (copy, image_bytes, platform, intent).
        brand_kit: The applied brand kit (palette drives fg/bg mapping).
        template: The PostTemplate used to render the post (text_slots +
            image_slot drive the contrast-pair + density-region lists).
    """
    log = logger.bind(
        platform=post.platform, intent=post.intent, template=template.name
    )
    log.info("audit_post_start")

    # Step 1 -- platform validation (char caps, hashtag caps, image aspects, etc.)
    _rules_unused, validate_fn = PLATFORM_REGISTRY[post.platform]  # type: ignore[index]
    rules = _rules_unused  # alias for readability below
    validation = validate_fn(post, rules)

    # Step 2 -- readability (always run, including text-only posts)
    grade, readability_issue = _readability_check(
        post.copy.body, grade_max=rules.readability_grade_max
    )

    # Step 3 -- hashtag subset: pull validation issues that target hashtags.
    hashtag_issues = [
        i
        for i in validation.issues
        if i.field is not None and i.field.startswith("copy.hashtags")
    ]

    # Step 4 -- image-pixel audit (skip for text-only). Call the shared
    # primitives directly (scan_text_contrast + scan_image_density) rather than
    # audit_render, which is brochure-shaped (BrochureContent + TemplateSchema
    # with panels). The primitives were extracted in Task 1 specifically so
    # post audit is not forced to construct fake brochure shapes just to get
    # contrast + density.
    brand_audit: AuditReport | None = None
    if post.image_bytes is not None and brand_kit.palette is not None:
        # Local imports keep module-load time low and isolate primitive
        # availability to the image-bearing branch.
        from flyer_generator.brand_kit.audit import (  # noqa: PLC0415
            scan_image_density,
            scan_text_contrast,
        )
        from flyer_generator.brand_kit.contrast import ContrastReport  # noqa: PLC0415

        palette = brand_kit.palette
        # 5-field BrandPalette: every role is required, so lookup is safe.
        color_role_to_hex = {
            "primary": palette.primary.hex,
            "secondary": palette.secondary.hex,
            "accent": palette.accent.hex,
            "neutral_dark": palette.neutral_dark.hex,
            "neutral_light": palette.neutral_light.hex,
        }

        # Derive (fg, bg) pairs from the rendered PostTemplate's text_slots.
        # Mirrors brochure audit's panel-background approximation (see
        # flyer_generator/brand_kit/audit.py::_panel_bg_hex): bg is the kit's
        # neutral_light (template background) unless the TextSlot's bbox
        # overlaps the image_slot, in which case bg is the kit's neutral_dark
        # (scrim/dark-overlay approximation).
        default_bg = color_role_to_hex["neutral_light"]
        overlay_bg = color_role_to_hex["neutral_dark"]
        image_bbox: tuple[float, float, float, float] | None = (
            tuple(template.image_slot.bbox)
            if template.image_slot is not None
            else None
        )

        pairs: list[tuple[str, str]] = []
        for slot in template.text_slots:
            fg_hex = color_role_to_hex.get(
                slot.color_role, color_role_to_hex["neutral_dark"]
            )
            slot_bbox = tuple(slot.bbox)
            bg_hex = (
                overlay_bg
                if image_bbox is not None
                and _bbox_overlaps(slot_bbox, image_bbox)
                else default_bg
            )
            pairs.append((fg_hex, bg_hex))

        # regions = [(x, y, w, h), ...] -- one per image_slot (density across
        # the rendered hero area). Text-slot regions are covered by contrast.
        regions: list[tuple[int, int, int, int]] = []
        if template.image_slot is not None:
            ix, iy, iw, ih = template.image_slot.bbox
            regions.append((int(ix), int(iy), int(iw), int(ih)))

        try:
            contrast_report: ContrastReport = scan_text_contrast(palette, pairs)
            density_map: dict[str, float] = (
                scan_image_density(post.image_bytes, regions) if regions else {}
            )
        except Exception as err:  # noqa: BLE001 -- advisory, structured log not crash
            log.warning(
                "audit_post_brand_audit_primitive_failed",
                error=str(err),
                error_type=type(err).__name__,
            )
            brand_audit = None
        else:
            # Wrap the real contrast + density into AuditReport. whitespace is
            # left empty for post v1 -- social posts do not decompose into
            # multi-panel layouts; per-slot whitespace is not informative the
            # way brochure panel-whitespace is. density uses the image_slot
            # region key.
            brand_audit = AuditReport(
                whitespace={},
                contrast=contrast_report,
                density=density_map,
                issues=[],
                cycle=0,
            )

    # Step 5 -- assemble net-new audit-level issues.
    # Link-policy (INSTAGRAM_LINK_IN_CAPTION) is ALREADY emitted by
    # platforms.instagram.validate; we do not duplicate it here -- it already
    # lives in validation.issues.
    audit_issues: list[ValidationIssue] = []
    if readability_issue is not None:
        audit_issues.append(readability_issue)

    report = SocialAuditReport(
        validation=validation,
        readability_grade=grade,
        readability_issue=readability_issue,
        hashtag_issues=hashtag_issues,
        brand_audit=brand_audit,
        issues=audit_issues,
    )
    log.info(
        "audit_post_end",
        validation_passed=validation.passed,
        readability_grade=round(grade, 2),
        is_clean=report.is_clean,
    )
    return report
