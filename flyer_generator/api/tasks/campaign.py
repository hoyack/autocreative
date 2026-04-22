"""arq task wrapping :func:`generate_campaign`.

Writes one :class:`CampaignRecord` + N :class:`PostRecord` rows (one per
platform) + M :class:`RenderRecord` rows (one per post that produced an
image).  ``JobRecord.result_ref`` is left NULL — the polling route fuses
per-post render URLs from ``CampaignRecord.posts`` at GET time.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from flyer_generator.api.models import CampaignRecord, PostRecord, RenderRecord
from flyer_generator.api.tasks._state import mark_failed, mark_running, mark_succeeded
from flyer_generator.brand_kit import load_brand_kit
from flyer_generator.social import generate_campaign

logger = structlog.get_logger()


async def task_generate_campaign(ctx: dict, *, job_id: str, payload: dict) -> None:
    """Generate a campaign (N platforms from shared hero).

    ``payload`` expects ``{"brand_kit_slug": str, "topic": str, "intent": str,
    "platforms": list[str], "style_preset": str | None}``.

    Returns ``None``.  The route layer fuses per-post render URLs from the
    ``CampaignRecord.posts`` relationship on ``GET /jobs/{id}``.
    """
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]

    log = logger.bind(job_id=job_id, kind="social_campaign")
    log.info("task_start")
    await mark_running(sessionmaker, job_id)

    try:
        slug = payload["brand_kit_slug"]
        kit = load_brand_kit(slug, base_dir=Path(settings.brand_kits_dir))

        campaign = await generate_campaign(
            kit,
            topic=payload["topic"],
            platforms=payload["platforms"],
            intent=payload["intent"],
            settings=settings,
            audit=True,
            style_preset=payload.get("style_preset") or "social_graphic",
        )

        async with sessionmaker() as s:
            camp_row = CampaignRecord(
                id=job_id,  # reuse job_id as campaign id for simplicity
                topic=payload["topic"],
                intent=payload["intent"],
                brand_kit_slug=slug,
                platforms=list(payload["platforms"]),
                summary_payload=campaign.model_dump(mode="json"),
            )
            s.add(camp_row)
            await s.flush()

            # BLOCKER-1: iterate ``campaign.posts_full.values()`` — real Post
            # objects with ``image_bytes``. ``campaign.posts`` is
            # ``dict[str, object]`` holding serializable dicts; iterating it
            # yields string KEYS, which makes ``post.image_bytes`` below
            # raise AttributeError (``'str' object has no attribute
            # 'image_bytes'``). See flyer_generator/social/models.py:140-160
            # + flyer_generator/social/campaign.py:272-297.
            for post in campaign.posts_full.values():
                render_id: str | None = None
                if post.image_bytes is not None:
                    image_path = getattr(post, "image_path", None)
                    if image_path is None:
                        image_path = (
                            Path(settings.social_campaigns_dir)
                            / slug
                            / job_id
                            / f"{post.platform}.png"
                        )
                        image_path.parent.mkdir(parents=True, exist_ok=True)
                        image_path.write_bytes(post.image_bytes)
                    r = RenderRecord(
                        kind="social_post_image",
                        file_path=str(Path(image_path).resolve()),
                    )
                    s.add(r)
                    await s.flush()
                    render_id = r.id

                s.add(
                    PostRecord(
                        platform=post.platform,
                        intent=post.intent,
                        topic=payload["topic"],
                        brand_kit_slug=slug,
                        campaign_id=camp_row.id,
                        post_payload=post.model_dump(mode="json"),
                        render_id=render_id,
                    )
                )
            await s.commit()

        # Campaign jobs use NULL result_ref — route fuses per-post render URLs
        # on GET /jobs/{id} from CampaignRecord.posts relationship.
        await mark_succeeded(sessionmaker, job_id, result_ref=None)
        log.info("task_succeeded", post_count=len(campaign.posts_full))
        return None

    except Exception as exc:
        log.exception("task_failed")
        await mark_failed(sessionmaker, job_id, exc)
        raise
