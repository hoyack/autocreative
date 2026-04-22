"""arq task wrapping :class:`FlyerGenerator`.generate.

Writes one :class:`RenderRecord` (kind ``"flyer_final"``) + one
:class:`FlyerRecord` per generated flyer, then transitions the
:class:`JobRecord` to ``succeeded`` with ``result_ref`` pointing at the
render row.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from flyer_generator import EventInput, FlyerGenerator
from flyer_generator.api.models import FlyerRecord, RenderRecord
from flyer_generator.api.tasks._state import mark_failed, mark_running, mark_succeeded

logger = structlog.get_logger()


async def task_generate_flyer(ctx: dict, *, job_id: str, payload: dict) -> str | None:
    """Generate a flyer PNG.

    ``payload`` expects ``{"event": <EventInput dict>, "preset": str,
    "brand_kit_slug": str | None, ...}``.
    Returns :class:`RenderRecord`.id (used as ``JobRecord.result_ref``).
    """
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]
    http_client = ctx["http_client"]

    log = logger.bind(job_id=job_id, kind="flyer")
    log.info("task_start")
    await mark_running(sessionmaker, job_id)

    try:
        event = EventInput.model_validate(payload["event"])
        gen = FlyerGenerator(settings=settings, http_client=http_client)
        out = await gen.generate(event)

        # Persist PNG to disk under ``<artifact_root_flyer>/<job_id>.png``.
        artifact_path = Path(settings.artifact_root_flyer) / f"{job_id}.png"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        out.save(artifact_path)

        async with sessionmaker() as s:
            render = RenderRecord(
                kind="flyer_final",
                file_path=str(artifact_path.resolve()),
                comfy_job_id=getattr(out, "comfy_job_id", None),
                vision_verdict=(
                    out.final_vision_verdict.model_dump(mode="json")
                    if getattr(out, "final_vision_verdict", None) is not None
                    else None
                ),
            )
            s.add(render)
            await s.flush()  # assign render.id

            flyer = FlyerRecord(
                title=event.title,
                preset=payload["preset"],
                brand_kit_slug=payload.get("brand_kit_slug"),
                event_payload=payload,
                render_id=render.id,
            )
            s.add(flyer)
            await s.commit()

            render_id = render.id

        await mark_succeeded(sessionmaker, job_id, result_ref=render_id)
        log.info("task_succeeded", render_id=render_id)
        return render_id

    except Exception as exc:
        log.exception("task_failed")
        await mark_failed(sessionmaker, job_id, exc)
        raise
