"""arq task wrapping :func:`render_postcard` + PDF assembly.

Phase 23 (PC-01 + PC-02 + PC-04 + PC-06):

- Parallel-id pattern (``PostcardRecord.id == job_id``) mirrors the brochure
  worker (Plan 21-07). The route handler computes a server-side ULID, persists
  ``JobRecord(id=ulid, ...)``, then this worker writes
  ``PostcardRecord(id=job_id, ...)`` so the FE can navigate
  ``/jobs/{id}`` -> ``/postcards/{id}`` without an extra lookup.
- T-23-01 path-traversal guard (``_validate_template_slug``) mirrors Phase 22
  T-22-10 (flyer worker). The postcard loader's file-path branch fires when
  ``name_or_path.endswith(".json")``, so we refuse path-like slugs BEFORE
  ``load_template`` runs.
- BLOCKER-2 module-scope imports (``load_template`` / ``render_postcard`` /
  ``Rasterizer`` / ``assemble_postcard_pdf``) mirror the brochure worker so
  direct-invocation tests can patch them via
  ``patch("flyer_generator.api.tasks.postcard.X")``.
- Writes 3 ``RenderRecord`` rows (``postcard_front``, ``postcard_back``,
  ``postcard_pdf``) + 1 ``PostcardRecord`` under
  ``<artifact_root_brochure>/postcards/<job_id>/``. We re-use
  ``artifact_root_brochure`` rather than introducing a new env var
  (CONTEXT.md "Claude's discretion"); the directory is namespaced by
  ``/postcards/`` so it never collides with brochure outputs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import structlog

from flyer_generator.api.models import (
    PostcardRecord,
    RenderRecord,
)
from flyer_generator.api.tasks._state import (
    mark_failed,
    mark_running,
    mark_succeeded,
)

# NOTE: BLOCKER-2 module-scope imports — patchable via
# ``patch("flyer_generator.api.tasks.postcard.X")``. Mirrors the brochure
# worker's pattern (flyer_generator/api/tasks/brochure.py:22-33). Import
# errors surface at worker-boot, not at first request.
from flyer_generator.postcard.schema_renderer.content_model import (
    PostcardAddressBlock,
    PostcardContent,
)
from flyer_generator.postcard.schema_renderer.image_gate import (
    generate_postcard_hero,
)
from flyer_generator.postcard.schema_renderer.loader import load_template
from flyer_generator.postcard.schema_renderer.renderer import render_postcard
from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf
from flyer_generator.stages.rasterizer import Rasterizer

logger = structlog.get_logger()


def _validate_template_slug(template_name: str) -> None:
    """T-23-01 mitigation: refuse template names that look like file paths.

    Mirrors Phase 22 T-22-10 (flyer worker). The postcard loader's file-path
    branch activates when ``name_or_path.endswith(".json")``
    (postcard/schema_renderer/loader.py:22-25). PostcardCreateRequest.template
    enforces ``max_length=64`` but payloads can still contain ``.json``
    (e.g. ``"foo.json"`` is 8 chars) or path separators — escape hatches that
    would let user input read arbitrary JSON files. Reject those names BEFORE
    :func:`load_template`.
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


def _content_from_payload(payload: dict) -> PostcardContent:
    """Translate the API request body into a :class:`PostcardContent`.

    Decouples the schema_renderer package from ``api.schemas.postcards`` —
    the renderer never imports api/. The mapping is 1:1 on the four
    rendering-relevant fields (``headline`` / ``body`` / ``image_hint`` /
    ``address_block``); ``brand_kit_slug`` and ``template`` are handled
    elsewhere in the worker.
    """
    ab_payload = payload.get("address_block")
    ab = (
        PostcardAddressBlock.model_validate(ab_payload)
        if ab_payload is not None
        else None
    )
    return PostcardContent(
        headline=payload["headline"],
        body=payload["body"],
        image_hint=payload.get("image_hint"),
        address_block=ab,
    )


async def task_generate_postcard(
    ctx: dict, *, job_id: str, payload: dict
) -> str | None:
    """Generate a postcard (front PNG + back PNG + print PDF).

    Per PC-02 parallel-id: ``PostcardRecord.id`` is set to ``job_id`` (NOT
    auto-generated) so ``JobRecord.id == PostcardRecord.id`` and the FE can
    navigate ``/jobs/{id}`` -> ``/postcards/{id}`` without a lookup.

    ``payload`` mirrors :class:`PostcardCreateRequest`::

        {
            "headline": str,
            "body": str,
            "image_hint": str | None,
            "brand_kit_slug": str | None,
            "template": str,
            "address_block": {
                "recipient_name": str,
                "street": str,
                "city_state_zip": str,
            } | None,
        }

    Returns the ``PostcardRecord.id`` (== ``job_id``) which is also stamped
    into ``JobRecord.result_ref``.
    """
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]
    # ctx["http_client"] is the worker-startup-shared httpx client when
    # arq runs in production; tests pass None and the helper below builds
    # a one-shot client per task invocation.
    ctx_http_client = ctx.get("http_client")

    log = logger.bind(job_id=job_id, kind="postcard")
    log.info("task_start")
    await mark_running(sessionmaker, job_id)

    try:
        template_name = payload["template"]

        # T-23-01: refuse path-like slugs BEFORE load_template's file-path branch.
        _validate_template_slug(template_name)

        # Surface FileNotFoundError / ValidationError BEFORE rendering work.
        template = load_template(template_name)

        content = _content_from_payload(payload)

        log = log.bind(template=template_name)

        # 1) Phase 24.1 (PLF-01): generate Comfy hero image when image_hint
        # is supplied. Mirrors the brochure worker's
        # ``generate_template_images`` step but kept lightweight (single
        # slot, no vision gate). Failures fall back to the placeholder
        # gradient — postcards must always render.
        images: dict[str, bytes] = {}
        if (
            payload.get("generate_images", True)
            and content.image_hint is not None
        ):
            if ctx_http_client is not None:
                images = await generate_postcard_hero(
                    template,
                    content,
                    settings=settings,
                    http_client=ctx_http_client,
                    workflow_name=payload.get("workflow", "turbo_landscape"),
                    style_preset=payload.get(
                        "style_preset", "photorealistic"
                    ),
                )
            else:
                # ComfyCloud jobs take 30-90s; default httpx 5s timeout
                # would ReadTimeout on every attempt. Mirrors
                # ``social/generator.py``'s 180s budget.
                async with httpx.AsyncClient(
                    follow_redirects=True, timeout=180.0
                ) as http:
                    images = await generate_postcard_hero(
                        template,
                        content,
                        settings=settings,
                        http_client=http,
                        workflow_name=payload.get(
                            "workflow", "turbo_landscape"
                        ),
                        style_preset=payload.get(
                            "style_preset", "photorealistic"
                        ),
                    )

        # 2) Render the two SVGs (SYNC — wrap in to_thread). Pass the
        # generated images dict as a kwarg so the front-panel hero
        # placeholder is hydrated when Comfy succeeded; empty dict falls
        # back to the placeholder's gradient fill. ``images`` is supplied
        # via keyword so pre-existing test stubs that mock
        # ``render_postcard`` with a ``(template, content)`` signature
        # remain compatible (Phase 24.1 PLF-01 back-compat).
        front_svg, back_svg = await asyncio.to_thread(
            lambda: render_postcard(template, content, images=images)
        )

        # 3) Rasterize each panel at the template canvas dims (SYNC — to_thread).
        rast = Rasterizer(
            width=template.canvas.width, height=template.canvas.height
        )

        def _rasterize_both() -> tuple[bytes, bytes]:
            return rast.rasterize(front_svg), rast.rasterize(back_svg)

        front_png, back_png = await asyncio.to_thread(_rasterize_both)

        # 4) Assemble PDF (SYNC — to_thread).
        pdf_bytes = await asyncio.to_thread(
            assemble_postcard_pdf,
            front_png,
            back_png,
            template.canvas.width,
            template.canvas.height,
        )

        # 5) Write 3 artifacts under <artifact_root_brochure>/postcards/<job_id>/.
        # Reusing artifact_root_brochure rather than adding a new env var
        # (CONTEXT.md Claude's discretion). The directory is namespaced by
        # /postcards/ so it does not collide with brochure outputs.
        base = Path(settings.artifact_root_brochure) / "postcards" / job_id
        base.mkdir(parents=True, exist_ok=True)
        front_path = base / "front.png"
        back_path = base / "back.png"
        pdf_path = base / "print.pdf"
        front_path.write_bytes(front_png)
        back_path.write_bytes(back_png)
        pdf_path.write_bytes(pdf_bytes)

        # 6) Persist 3 RenderRecords + 1 PostcardRecord.
        async with sessionmaker() as s:
            r_front = RenderRecord(
                kind="postcard_front", file_path=str(front_path.resolve())
            )
            r_back = RenderRecord(
                kind="postcard_back", file_path=str(back_path.resolve())
            )
            r_pdf = RenderRecord(
                kind="postcard_pdf", file_path=str(pdf_path.resolve())
            )
            s.add_all([r_front, r_back, r_pdf])
            await s.flush()  # assign render ids

            # PC-02 parallel-id: postcard.id := job_id (no new_ulid default).
            postcard = PostcardRecord(
                id=job_id,
                template=template_name,
                brand_kit_slug=payload.get("brand_kit_slug"),
                content_payload=payload,
                render_front_id=r_front.id,
                render_back_id=r_back.id,
                render_pdf_id=r_pdf.id,
            )
            s.add(postcard)
            await s.commit()
            result_ref = postcard.id

        await mark_succeeded(sessionmaker, job_id, result_ref=result_ref)
        log.info("task_succeeded", postcard_id=result_ref)
        return result_ref

    except Exception as exc:
        log.exception("task_failed")
        await mark_failed(sessionmaker, job_id, exc)
        raise
