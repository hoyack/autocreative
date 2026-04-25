"""arq task wrapping :class:`FlyerGenerator`.generate at injected canvas dims.

Phase 24 (PO-01 + PO-02 + PO-04):

- Parallel-id pattern (``PosterRecord.id == job_id``) mirrors the postcard
  worker (Plan 23-04). The route handler computes a server-side ULID,
  persists ``JobRecord(id=ulid, ...)``, then this worker writes
  ``PosterRecord(id=job_id, ...)`` so the FE can navigate
  ``/jobs/{id}`` -> the existing JobStatusCard without a lookup.
- T-24-08 path-traversal guard (``_validate_template_slug``) refuses
  ``.json`` / ``/`` / ``\\`` BEFORE :func:`load_template` — same pattern as
  Phase 22 T-22-10 + Phase 23 T-23-01.
- BLOCKER-2 module-scope imports (``load_template`` + ``FlyerGenerator``) so
  direct-invocation tests can patch via
  ``patch("flyer_generator.api.tasks.poster.X")``.
- ``_size_to_canvas_dimensions`` maps the locked 3 size literals to print
  dims at 300 DPI: ``"18x24"`` -> ``(5400, 7200)``,
  ``"24x36"`` -> ``(7200, 10800)``, ``"27x40"`` -> ``(8100, 12000)``.
  Defense-in-depth past the schema-layer Pydantic Literal (T-24-14).
- Writes 1 ``RenderRecord(kind="poster_final")`` + 1 ``PosterRecord`` under
  ``<artifact_root_flyer>/posters/<job_id>.png``. We re-use
  ``artifact_root_flyer`` rather than introducing a new env var
  (CONTEXT.md "Claude's discretion"); the directory is namespaced by
  ``/posters/`` so the file never collides with flyer outputs at
  ``<artifact_root_flyer>/<job_id>.png``.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from flyer_generator import FlyerGenerator
from flyer_generator.api.models import PosterRecord, RenderRecord
from flyer_generator.api.tasks._state import (
    mark_failed,
    mark_running,
    mark_succeeded,
)
from flyer_generator.models import FlyerInput

# NOTE: BLOCKER-2 module-scope import — patchable via
# ``patch("flyer_generator.api.tasks.poster.load_template")``. Mirrors the
# postcard worker pattern (flyer_generator/api/tasks/postcard.py:43-54).
# Import errors surface at worker-boot, not at first request.
from flyer_generator.poster.schema_renderer.loader import load_template

logger = structlog.get_logger()


# Locked 3-value size mapping per CONTEXT D-XX (300 DPI portrait). Module-
# level so tests can ``from flyer_generator.api.tasks.poster import _SIZE_TO_CANVAS``
# and assert structure if needed.
_SIZE_TO_CANVAS: dict[str, tuple[int, int]] = {
    "18x24": (5400, 7200),
    "24x36": (7200, 10800),
    "27x40": (8100, 12000),
}


def _size_to_canvas_dimensions(size: str) -> tuple[int, int]:
    """Map the request ``size`` literal to ``(width, height)`` at 300 DPI.

    T-24-14 mitigation: defense-in-depth past the schema-layer Pydantic
    ``Literal["18x24","24x36","27x40"]``. Anything else raises ValueError
    so the JobRecord transitions to FAILED with ``error_detail.type ==
    "ValueError"`` instead of corrupting the canvas math downstream.
    """
    try:
        return _SIZE_TO_CANVAS[size]
    except KeyError as exc:
        raise ValueError(
            f"unknown poster size {size!r}; expected one of "
            f"{sorted(_SIZE_TO_CANVAS.keys())}"
        ) from exc


def _validate_template_slug(template_name: str) -> None:
    """T-24-08 mitigation: refuse template names that look like file paths.

    Mirrors Phase 22 T-22-10 (flyer worker) + Phase 23 T-23-01 (postcard
    worker). The poster loader's file-path branch activates when
    ``name_or_path.endswith(".json")``. ``PosterCreateRequest.template``
    enforces ``max_length=64`` but payloads can still contain ``.json`` or
    path separators — escape hatches that would let user input read arbitrary
    JSON files. Reject those names BEFORE :func:`load_template`.
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


def _build_flyer_input(payload: dict) -> FlyerInput:
    """Translate the API request body into a :class:`FlyerInput` for FlyerGenerator.

    Posters reuse the flyer pipeline end-to-end (PO-02), so we map poster
    fields onto FlyerInput. The ``subtype="info"`` choice is locked
    (CONTEXT.md): posters are informational/announcement-shaped, not date-
    anchored, and the Phase 22 vision prompt branch for ``info`` names
    TITLE + DESCRIPTION + ORG_CREDIT zones (no DETAILS or FEE_BADGE) which
    is appropriate for a poster.

    Field mapping:
      - ``headline``       -> ``FlyerInput.title``
      - ``subheading``     -> ``FlyerInput.description``  (info-subtype zone)
      - ``cta_text``       -> ``FlyerInput.call_to_action``
      - ``image_hint``     -> ``FlyerInput.style_concept`` (Comfy prompt seed)
      - ``style_preset``   -> ``FlyerInput.style_preset``
      - ``brand_kit_slug`` -> ``FlyerInput.org``  (placeholder; future plan
        may surface a brand_kit-derived org name)
    """
    return FlyerInput(
        title=payload["headline"],
        subtype="info",
        description=payload.get("subheading") or payload["headline"],
        call_to_action=payload.get("cta_text"),
        org=payload.get("brand_kit_slug") or "",
        style_concept=payload.get("image_hint") or payload["headline"],
        style_preset=payload["style_preset"],
    )


async def task_generate_poster(
    ctx: dict, *, job_id: str, payload: dict
) -> str | None:
    """Generate a poster (single PNG at injected canvas dims).

    Per PO-XX parallel-id: ``PosterRecord.id`` is set to ``job_id`` (NOT
    auto-generated) so ``JobRecord.id == PosterRecord.id``. Even though no
    GET ``/posters/{id}`` route exists, the parallel-id contract keeps the
    DB shape consistent with the other primitives.

    ``payload`` mirrors :class:`PosterCreateRequest`::

        {
            "headline": str,
            "subheading": str | None,
            "cta_text": str | None,
            "image_hint": str | None,
            "brand_kit_slug": str | None,
            "style_preset": str,
            "template": str,
            "size": "18x24" | "24x36" | "27x40",
        }

    Returns the ``RenderRecord.id`` (also stamped into
    ``JobRecord.result_ref`` so the FE can fetch the PNG via the existing
    ``GET /api/v1/renders/{render_id}/image`` route).
    """
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]
    http_client = ctx["http_client"]

    log = logger.bind(job_id=job_id, kind="poster")
    log.info("task_start")
    await mark_running(sessionmaker, job_id)

    try:
        template_name = payload["template"]
        size = payload["size"]

        # T-24-08: refuse path-like slugs BEFORE load_template's file-path branch.
        _validate_template_slug(template_name)

        # T-24-14: validate size + resolve canvas dims BEFORE Comfy work.
        canvas_dimensions = _size_to_canvas_dimensions(size)

        # Load template BEFORE Comfy so FileNotFoundError / ValidationError
        # surfaces early (mirrors postcard + flyer worker).
        template = load_template(template_name)

        flyer_input = _build_flyer_input(payload)

        log = log.bind(template=template_name, size=size, canvas=canvas_dimensions)

        gen = FlyerGenerator(
            settings=settings,
            http_client=http_client,
            canvas_dimensions=canvas_dimensions,
        )
        out = await gen.generate(flyer_input, template=template)

        # Persist PNG to disk under <artifact_root_flyer>/posters/<job_id>.png.
        # Reusing artifact_root_flyer (CONTEXT.md "Claude's discretion");
        # namespaced under /posters/ so output never collides with flyer
        # outputs at <artifact_root_flyer>/<job_id>.png.
        artifact_dir = Path(settings.artifact_root_flyer) / "posters"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{job_id}.png"
        out.save(artifact_path)

        async with sessionmaker() as s:
            render = RenderRecord(
                kind="poster_final",
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

            # PO-XX parallel-id: poster.id := job_id (no new_ulid default).
            poster = PosterRecord(
                id=job_id,
                template=template_name,
                size=size,
                brand_kit_slug=payload.get("brand_kit_slug"),
                content_payload=payload,
                render_id=render.id,
            )
            s.add(poster)
            await s.commit()

            render_id = render.id

        await mark_succeeded(sessionmaker, job_id, result_ref=render_id)
        log.info("task_succeeded", render_id=render_id, render_kind="poster_final")
        return render_id

    except Exception as exc:
        log.exception("task_failed")
        await mark_failed(sessionmaker, job_id, exc)
        raise
