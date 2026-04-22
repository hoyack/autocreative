"""Campaign orchestrator: one source hero, N platform crops, N per-platform copies.

Per 19-RESEARCH.md §Campaign Image Crop Strategy: hero-sharing is the single biggest
cost lever (4x vs per-platform regeneration). We generate ONE source hero, upscale
it to a 2048x2048 union dimension via Pillow LANCZOS, then center-crop per-platform
to each target size in PLATFORM_CROP_SIZES. Per-platform copy, however, is generated
INDEPENDENTLY so banned-word retries, hashtag caps, and char budgets are honored for
each platform rather than being derived from a single shared string.

W-01 fix (mirrors Plan 07): hero generation routes through the shared
`generate_single_image` helper in `flyer_generator.brochure.schema_renderer.image_gate`.
Do NOT reintroduce the single-arg ComfyClient init (missing http_client) or a
submit call that takes `workflow=` + `prompt=` kwargs (the real signature is a
positional `ComfyWorkflowLike`). Those patterns are exactly the bug W-01 tracks.

W-05 fix: campaign_id + trace_id use `str(ULID())` (stable `python-ulid>=3.1.0`
API). The `.hex` attribute is NOT on the `ulid.ULID` class.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Sequence

import structlog
from ulid import ULID

from flyer_generator.brand_kit.models import BrandKit
from flyer_generator.config import Settings
from flyer_generator.errors import CampaignError
from flyer_generator.social.crop import (
    PLATFORM_CROP_SIZES,
    crop_hero_for_platform,
    upscale_source_hero,
)
from flyer_generator.social.generator import generate_post
from flyer_generator.social.models import (
    Campaign,
    Intent,
    Platform,
    Post,
    PostBrief,
)
from flyer_generator.social.schemas.loader import load_post_template
from flyer_generator.social.workflow_map import select_workflow_for_campaign

logger = structlog.get_logger(__name__)


def _primary_role_for_platform(
    platform: Platform, include_story: bool = False
) -> str:
    """Pick the primary PLATFORM_CROP_SIZES role key for a given platform.

    LinkedIn/Facebook default to ``link_preview`` (1.91:1) since that is the
    dominant consumed render. Twitter uses ``primary`` (16:9). Instagram is
    ``feed_square`` unless ``include_story=True``, in which case the full
    9:16 story slot is emitted.
    """
    if platform == "linkedin":
        return "link_preview"
    if platform == "twitter":
        return "primary"
    if platform == "instagram":
        return "story" if include_story else "feed_square"
    if platform == "facebook":
        return "link_preview"
    raise CampaignError(f"unknown platform {platform!r}")


async def _generate_shared_hero(
    workflow_name: str,
    prompt: str,
    brand_kit: BrandKit,
    settings: Settings,
    comfy_client: Any | None,
    *,
    style_preset: str = "social_graphic",
) -> bytes:
    """Generate ONE source hero and upscale to 2048x2048.

    W-01 fix (mirrors Plan 07 B-05): uses the shared ``generate_single_image``
    helper in ``flyer_generator.brochure.schema_renderer.image_gate`` rather
    than constructing a ComfyClient directly. Never calls the broken single-
    arg ComfyClient init (missing http_client) or a submit with workflow= +
    prompt= keyword args (wrong kwargs -- real signature takes a positional
    ComfyWorkflowLike).
    """
    import httpx  # noqa: PLC0415

    from flyer_generator.brochure.schema_renderer.image_gate import (  # noqa: PLC0415
        generate_single_image,
    )
    from flyer_generator.errors import ComfySubmitError  # noqa: PLC0415

    if comfy_client is not None and hasattr(comfy_client, "generate_image"):
        native = await comfy_client.generate_image(
            workflow_name=workflow_name,
            prompt=prompt,
            brand_kit=brand_kit,
        )
    else:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=180.0
            ) as http:
                native = await generate_single_image(
                    workflow_name=workflow_name,
                    prompt=prompt,
                    settings=settings,
                    http_client=http,
                    style_preset=style_preset,
                )
        except ComfySubmitError as err:
            raise CampaignError(
                f"shared hero generation failed: {err}",
                workflow=workflow_name,
            ) from err

    # Upscale to 2048x2048 union dimension per 19-RESEARCH.md §Source hero dimension
    return upscale_source_hero(native, target=(2048, 2048))


async def generate_campaign(
    brand_kit: BrandKit,
    topic: str,
    platforms: Sequence[Platform],
    intent: Intent = "value-prop",
    *,
    include_story: bool = False,
    cta: str | None = None,
    image_hint: str | None = None,
    settings: Settings | None = None,
    text_client: Any | None = None,
    comfy_client: Any | None = None,
    audit: bool = False,
    style_preset: str = "social_graphic",
) -> Campaign:
    """Generate a multi-platform campaign from a single topic with a shared source hero.

    Args:
        brand_kit: Applied brand kit (drives palette + typography + voice).
        topic: Campaign topic string -- fed to LLM copy generation for every
            platform.
        platforms: Non-empty sequence of target :class:`Platform` literals.
        intent: Shared :class:`Intent` applied to every platform. Mixed-intent
            campaigns are out of scope for v1.
        include_story: When ``True`` and Instagram is in ``platforms``, force
            portrait workflow + 9:16 story crop for Instagram.
        cta: Optional CTA override applied to every platform brief.
        image_hint: Optional image-prompt override. Defaults to ``topic``.
        settings: Optional :class:`Settings` (defaults to ``Settings()``).
        text_client: Optional injected LLM text client (tests use mocks).
        comfy_client: Optional injected ComfyCloud client exposing
            ``generate_image(workflow_name, prompt, brand_kit)`` (tests use
            mocks).
        audit: When ``True``, each per-platform :func:`generate_post` call runs
            :func:`audit_post` and records the summary on the generated Post.

    Returns:
        A :class:`Campaign` whose ``posts`` dict is keyed by
        ``f"{platform}__{intent}"`` and whose values are serialized ``Post``
        dicts (image bytes excluded from JSON).

    Raises:
        CampaignError: ``platforms`` is empty, or hero generation fails.
    """
    if settings is None:
        settings = Settings()
    if not platforms:
        raise CampaignError("at least one platform is required")
    trace_id = str(ULID())
    campaign_id = str(ULID())
    # Derive slug from brand_kit.name: lowercase + replace spaces with hyphen.
    brand_slug = (brand_kit.name or "unknown").lower().replace(" ", "-")

    log = logger.bind(
        trace_id=trace_id,
        campaign_id=campaign_id,
        brand=brand_slug,
        n_platforms=len(platforms),
        topic=topic[:40],
    )
    log.info("generate_campaign_start")

    # Step 1 -- select single workflow + generate shared hero
    workflow_name = select_workflow_for_campaign(
        platforms, include_story=include_story
    )
    log.info("generate_campaign_workflow_selected", workflow=workflow_name)
    try:
        shared_hero = await _generate_shared_hero(
            workflow_name, image_hint or topic, brand_kit, settings, comfy_client,
            style_preset=style_preset,
        )
        log.info("generate_campaign_hero_ready", bytes_len=len(shared_hero))
    except CampaignError:
        # Already wrapped + logged at the source; re-raise without double-wrapping.
        log.error("generate_campaign_hero_failed")
        raise
    except Exception as err:  # noqa: BLE001
        log.error("generate_campaign_hero_failed", error=str(err))
        raise CampaignError(f"hero generation failed: {err}") from err

    # Step 2 -- fan out: per-platform copy + crop + render
    async def _one_platform(platform: Platform) -> tuple[Platform, Post]:
        plog = log.bind(platform=platform)
        brief = PostBrief(
            topic=topic,
            intent=intent,
            platform=platform,
            cta=cta,
            image_hint=image_hint,
        )
        template = load_post_template(f"{platform}__{intent}")
        # Crop shared hero to this platform's target (skip for text-only posts).
        if template.image_slot is not None:
            role = _primary_role_for_platform(platform, include_story=include_story)
            target_dims = PLATFORM_CROP_SIZES[(platform, role)]
            cropped = crop_hero_for_platform(
                shared_hero, target_dims[0], target_dims[1]
            )
        else:
            cropped = None

        # Inject the cropped hero into a fake comfy_client that returns it
        # directly: generate_post will then skip ComfyCloud entirely for this
        # platform and use the shared hero as-is.
        class _PreloadedHero:
            async def generate_image(
                self, *, workflow_name: str, prompt: str, brand_kit: BrandKit
            ) -> bytes:
                return cropped or b""

        effective_comfy = _PreloadedHero() if cropped is not None else None
        post = await generate_post(
            brief,
            brand_kit,
            template=template,
            settings=settings,
            text_client=text_client,
            comfy_client=effective_comfy,
            audit=audit,
            style_preset=style_preset,
        )
        plog.info(
            "generate_campaign_post_ready",
            platform=platform,
            passed=post.validation_report.passed,
        )
        return (platform, post)

    results = await asyncio.gather(
        *(_one_platform(p) for p in platforms),
        return_exceptions=True,
    )
    posts_by_key: dict[str, object] = {}
    for item in results:
        if isinstance(item, Exception):
            log.warning("generate_campaign_platform_failed", error=str(item))
            continue
        platform, post = item
        key = f"{platform}__{intent}"
        posts_by_key[key] = post.model_dump(mode="json", exclude={"image_bytes"})
        # store that the post had image bytes so a downstream CLI can persist them
        if post.image_bytes is not None:
            # type: ignore[index] -- we just set this to a dict above
            posts_by_key[key]["__has_image"] = True  # type: ignore[index]

    campaign = Campaign(
        campaign_id=campaign_id,
        brand_kit_slug=brand_slug,
        topic=topic,
        platforms=list(platforms),
        created_at=datetime.now(tz=timezone.utc),
        posts=posts_by_key,
    )
    log.info("generate_campaign_end", n_posts=len(posts_by_key))
    return campaign
