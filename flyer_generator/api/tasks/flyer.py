"""arq task wrapping :class:`FlyerGenerator`.generate.

Writes one :class:`RenderRecord` (kind derived from FlyerInput.subtype —
``flyer_event_final`` or ``flyer_info_final``) + one :class:`FlyerRecord`
per generated flyer, then transitions :class:`JobRecord` to ``succeeded``
with ``result_ref`` pointing at the render row.

Phase 22 (FT-01 + FT-06): Late-binding template loader + subtype-aware
render kind. Mirrors the brochure worker's BLOCKER-2 module-scope import
pattern so direct-invocation tests can patch ``load_template`` via
``patch("flyer_generator.api.tasks.flyer.load_template")``.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from flyer_generator import FlyerGenerator
from flyer_generator.api.models import FlyerRecord, RenderRecord
from flyer_generator.api.tasks._state import mark_failed, mark_running, mark_succeeded
from flyer_generator.models import FlyerInput

# NOTE: Module-scope import so direct-invocation tests can patch via
# ``patch("flyer_generator.api.tasks.flyer.load_template")``. Mirrors the
# BLOCKER-2 pattern from brochure.py:22-33: import errors surface at
# worker-boot, not at first request.
from flyer_generator.flyer.schema_renderer.loader import load_template

logger = structlog.get_logger()


def _validate_template_slug(template_name: str) -> None:
    """T-22-10 mitigation: refuse template names that look like file paths.

    The loader's file-path branch activates when ``name_or_path.endswith(".json")``
    (loader.py:20). FlyerCreateRequest.template enforces ``max_length=64`` but
    payloads can still contain ``.json`` (e.g. ``"foo.json"`` is 8 chars) or
    path separators — escape hatches that would let user input read arbitrary
    JSON files. Reject those names here, BEFORE :func:`load_template`.

    Phase 22 threat register entry T-22-10. Phase 26 will harden further with
    adversarial coverage.
    """
    if (
        template_name.endswith(".json")
        or "/" in template_name
        or "\\" in template_name
    ):
        msg = (
            "template must be a bare slug, not a path "
            "(no '.json' suffix, no '/' or '\\\\' separators)"
        )
        raise ValueError(msg)


async def task_generate_flyer(ctx: dict, *, job_id: str, payload: dict) -> str | None:
    """Generate a flyer PNG.

    ``payload`` expects::

        {
            "event": <FlyerInput dict — may include subtype="event"|"info">,
            "template": <str, name of flyer template>,
            "preset": <str>,
            "brand_kit_slug": <str | None>,
            "accent": <str | None>,
            "max_bg_attempts": <int | None>,
        }

    Returns :class:`RenderRecord`.id (used as ``JobRecord.result_ref``).
    """
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]
    http_client = ctx["http_client"]

    log = logger.bind(job_id=job_id, kind="flyer")
    log.info("task_start")
    await mark_running(sessionmaker, job_id)

    try:
        flyer_input = FlyerInput.model_validate(payload["event"])
        template_name = payload["template"]

        # T-22-10: refuse path-like slugs BEFORE the loader's file-path branch.
        _validate_template_slug(template_name)

        # Load template BEFORE any Comfy work so FileNotFoundError /
        # ValidationError surfaces early (mirrors brochure worker behavior).
        template = load_template(template_name)

        log = log.bind(subtype=flyer_input.subtype, template=template_name)

        gen = FlyerGenerator(settings=settings, http_client=http_client)
        out = await gen.generate(flyer_input, template=template)

        # Persist PNG to disk under <artifact_root_flyer>/<job_id>.png.
        artifact_path = Path(settings.artifact_root_flyer) / f"{job_id}.png"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        out.save(artifact_path)

        # Render kind derived from subtype (Phase 22 FT-06).
        render_kind = (
            "flyer_event_final"
            if flyer_input.subtype == "event"
            else "flyer_info_final"
        )

        async with sessionmaker() as s:
            render = RenderRecord(
                kind=render_kind,
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
                title=flyer_input.title,
                template=template_name,  # Phase 22 FT-01
                preset=payload["preset"],
                brand_kit_slug=payload.get("brand_kit_slug"),
                event_payload=payload,
                render_id=render.id,
            )
            s.add(flyer)
            await s.commit()

            render_id = render.id

        await mark_succeeded(sessionmaker, job_id, result_ref=render_id)
        log.info("task_succeeded", render_id=render_id, render_kind=render_kind)
        return render_id

    except Exception as exc:
        log.exception("task_failed")
        await mark_failed(sessionmaker, job_id, exc)
        raise
