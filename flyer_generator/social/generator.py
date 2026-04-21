"""Single-post generator orchestrator.

Composition:
  PostBrief → load template → generate voice-aware copy → (hero image, optional) → render PNG → validate → Post
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from flyer_generator.brand_kit.models import BrandKit
from flyer_generator.config import Settings
from flyer_generator.social.models import Post, PostBrief
from flyer_generator.social.platforms import (
    PLATFORM_REGISTRY,
    load_platform_rules,
)
from flyer_generator.social.renderer import render_post
from flyer_generator.social.schemas.loader import load_post_template
from flyer_generator.social.schemas.schema_model import PostTemplate
from flyer_generator.social.voice import generate_social_copy
from flyer_generator.social.workflow_map import select_workflow_for_aspect

logger = structlog.get_logger(__name__)


async def _generate_hero_image(
    template: PostTemplate,
    brief: PostBrief,
    brand_kit: BrandKit,
    settings: Settings,
    comfy_client: Any | None,
) -> bytes:
    """Generate a single hero image matching template.image_slot.aspect via ComfyCloud.

    Delegates to the shared `generate_single_image` helper in
    `flyer_generator.brochure.schema_renderer.image_gate` (added in Task 0 of
    this plan). That helper handles workflow loading, ComfyClient init with
    correct (settings, http_client) args, submit/poll/download, and error
    propagation.

    Tests may inject a mock `comfy_client` exposing `generate_image(
    workflow_name, prompt, brand_kit)` to short-circuit real ComfyCloud calls.
    No other fallback: if no comfy_client is injected AND ComfyCloud cannot
    be reached, the underlying ComfyClient raises ComfySubmitError /
    ComfyJobTimeoutError which surface to the caller as SocialError (wrapped).
    """
    import httpx  # noqa: PLC0415

    from flyer_generator.brochure.schema_renderer.image_gate import (  # noqa: PLC0415
        generate_single_image,
    )
    from flyer_generator.errors import ComfySubmitError  # noqa: PLC0415

    if template.image_slot is None:
        raise RuntimeError("_generate_hero_image called with no image_slot")
    workflow_name = select_workflow_for_aspect(template.image_slot.aspect)
    prompt = brief.image_hint or brief.topic

    # Test-injection path: prefer the mock if provided
    if comfy_client is not None and hasattr(comfy_client, "generate_image"):
        return await comfy_client.generate_image(
            workflow_name=workflow_name,
            prompt=prompt,
            brand_kit=brand_kit,
        )

    # Production path: use the shared helper with a fresh httpx client.
    # ComfyCloud jobs take 30-90s; default httpx timeout is too short.
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=180.0
        ) as http:
            return await generate_single_image(
                workflow_name=workflow_name,
                prompt=prompt,
                settings=settings,
                http_client=http,
            )
    except ComfySubmitError as err:
        # Wrap as SocialError so callers catch a single family. Preserve the
        # underlying ComfyCloud error via `from err` for debugging.
        from flyer_generator.errors import SocialError  # noqa: PLC0415

        raise SocialError(
            f"hero image generation failed: {err}",
            workflow=workflow_name,
            template=template.name,
        ) from err


async def generate_post(
    brief: PostBrief,
    brand_kit: BrandKit,
    *,
    template: PostTemplate | None = None,
    settings: Settings | None = None,
    text_client: Any | None = None,
    comfy_client: Any | None = None,
    audit: bool = False,
) -> Post:
    """Run the full single-post pipeline and return a Post artifact."""
    if settings is None:
        settings = Settings()

    trace_id = uuid.uuid4().hex
    log = logger.bind(
        trace_id=trace_id,
        platform=brief.platform,
        intent=brief.intent,
        topic=brief.topic[:40],
    )
    log.info("generate_post_start")

    # Step 1: load template (default: f"{platform}__{intent}")
    if template is None:
        template_name = f"{brief.platform}__{brief.intent}"
        template = load_post_template(template_name)
    log.info("generate_post_template_loaded", template=template.name)

    # Step 2: resolve platform rules
    platform_rules = load_platform_rules(brief.platform)

    # Step 3: generate voice-aware copy
    copy = await generate_social_copy(
        brief,
        platform_rules,
        template,
        brand_voice=brand_kit.voice if brand_kit else None,
        settings=settings,
        text_client=text_client,
    )
    log.info("generate_post_copy_ready", body_len=len(copy.body), hashtag_count=len(copy.hashtags))

    # Step 4: generate hero (skip for text-only)
    hero_bytes: bytes | None = None
    if template.image_slot is not None:
        log.info("generate_post_hero_start", aspect=template.image_slot.aspect)
        hero_bytes = await _generate_hero_image(
            template, brief, brand_kit, settings, comfy_client
        )
        log.info("generate_post_hero_ready", bytes_len=len(hero_bytes))
    else:
        log.info("generate_post_text_only")

    # Step 5: render PNG
    png_bytes = render_post(template, copy, brand_kit, hero_image_bytes=hero_bytes)
    log.info("generate_post_render_ready", png_bytes_len=len(png_bytes))

    # Step 6: build Post (no image_bytes for text-only per rule; for image posts, attach rendered PNG)
    post_image = png_bytes if template.image_slot is not None else None

    # Step 7: validate — compose a preliminary Post then run platform validator
    from flyer_generator.social.models import (  # noqa: PLC0415
        ValidationReport,
    )
    preliminary = Post(
        platform=brief.platform,
        intent=brief.intent,
        copy=copy,
        image_bytes=post_image,
        validation_report=ValidationReport(platform=brief.platform),
        audit_summary="pending",
    )
    _rules, validate_fn = PLATFORM_REGISTRY[brief.platform]  # type: ignore[index]
    report = validate_fn(preliminary, _rules)
    log.info(
        "generate_post_validate_ready",
        passed=report.passed,
        n_issues=len(report.issues),
    )

    # Step 8: audit (Plan 08 extension point; for Plan 07 we leave a string summary)
    audit_summary = "unknown"
    if audit:
        try:
            from flyer_generator.social.audit import audit_post  # noqa: PLC0415
            audit_report = audit_post(preliminary, brand_kit, template)
            audit_summary = "clean" if audit_report.is_clean else f"{len(audit_report.issues)} issue(s)"
        except ImportError:
            audit_summary = "audit-module-missing"
        except Exception as err:  # noqa: BLE001 -- audit is advisory, not a gate in Plan 07
            log.warning("generate_post_audit_failed", error=str(err))
            audit_summary = f"audit-error:{type(err).__name__}"

    final = preliminary.model_copy(
        update={"validation_report": report, "audit_summary": audit_summary}
    )
    log.info("generate_post_end", audit_summary=audit_summary, passed=report.passed)
    return final
