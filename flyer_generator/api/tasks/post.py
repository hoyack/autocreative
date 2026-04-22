"""arq task wrapping :func:`generate_post`.

Writes one :class:`PostRecord` + (if ``image_bytes`` present) one
:class:`RenderRecord` (kind ``"social_post_image"``).
"""

from __future__ import annotations

from pathlib import Path

import structlog

from flyer_generator.api.models import PostRecord, RenderRecord
from flyer_generator.api.tasks._state import mark_failed, mark_running, mark_succeeded
from flyer_generator.brand_kit import load_brand_kit
from flyer_generator.social import PostBrief, generate_post

logger = structlog.get_logger()


async def task_generate_post(ctx: dict, *, job_id: str, payload: dict) -> str | None:
    """Generate one social post.

    ``payload`` expects ``{"brand_kit_slug": str, "topic": str, "intent": str,
    "platform": str, "cta": str | None, "image_hint": str | None,
    "style_preset": str | None, "campaign_id": str | None}``.

    Returns the new :class:`RenderRecord`.id when an image was generated, or
    ``None`` if the post has no image (text-only flow).
    """
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]

    log = logger.bind(
        job_id=job_id, kind="social_post", platform=payload.get("platform")
    )
    log.info("task_start")
    await mark_running(sessionmaker, job_id)

    try:
        slug = payload["brand_kit_slug"]
        # load_brand_kit raises BrandKitNotFoundError on miss — propagates via
        # the outer ``except`` below so mark_failed writes the error_detail.
        kit = load_brand_kit(slug, base_dir=Path(settings.brand_kits_dir))

        brief = PostBrief(
            topic=payload["topic"],
            intent=payload["intent"],
            platform=payload["platform"],
            cta=payload.get("cta"),
            image_hint=payload.get("image_hint"),
        )
        post = await generate_post(
            brief,
            kit,
            settings=settings,
            audit=True,
            style_preset=payload.get("style_preset") or "social_graphic",
        )

        render_id: str | None = None
        async with sessionmaker() as s:
            if post.image_bytes is not None:
                # The post generator may or may not have a ``image_path``
                # attribute exposed — defensive getattr falls back to a
                # deterministic per-job path.
                image_path = getattr(post, "image_path", None)
                if image_path is None:
                    image_path = Path(settings.social_campaigns_dir) / slug / f"{job_id}.png"
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    image_path.write_bytes(post.image_bytes)

                render = RenderRecord(
                    kind="social_post_image",
                    file_path=str(Path(image_path).resolve()),
                )
                s.add(render)
                await s.flush()
                render_id = render.id

            row = PostRecord(
                platform=payload["platform"],
                intent=payload["intent"],
                topic=payload["topic"],
                brand_kit_slug=slug,
                campaign_id=payload.get("campaign_id"),
                post_payload=post.model_dump(mode="json"),
                render_id=render_id,
            )
            s.add(row)
            await s.commit()

        await mark_succeeded(sessionmaker, job_id, result_ref=render_id)
        log.info("task_succeeded", render_id=render_id)
        return render_id

    except Exception as exc:
        log.exception("task_failed")
        await mark_failed(sessionmaker, job_id, exc)
        raise
