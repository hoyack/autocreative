"""arq task wrapping :func:`render_schema_brochure` (sync) +
:func:`generate_template_images` (async) + PDF assembly.

The sync calls (SVG build, rasterize, PDF assembly) are wrapped in
``asyncio.to_thread`` to avoid blocking the arq worker's event loop during
cairosvg rasterization and reportlab PDF drawing (RESEARCH.md Open Q2).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

from flyer_generator.api.models import BrochureRecord, RenderRecord
from flyer_generator.api.tasks._state import mark_failed, mark_running, mark_succeeded
from flyer_generator.brand_kit import load_brand_kit
from flyer_generator.brochure.schema_renderer.content_model import BrochureContent
from flyer_generator.brochure.schema_renderer.image_gate import generate_template_images

# NOTE: The following three imports must stay at module scope so direct-
# invocation tests can patch them via ``patch("flyer_generator.api.tasks.brochure.X")``.
# They were module-local in the original plan — promoting them is a BLOCKER-2
# stability improvement (import errors surface at worker-boot, not at first
# request). Verified module paths (do NOT change without grepping the repo):
# - flyer_generator.brochure.schema_renderer.loader.load_template
# - flyer_generator.brochure.stages.pdf.assemble_brochure_pdf
# - flyer_generator.stages.rasterizer.Rasterizer
from flyer_generator.brochure.schema_renderer.loader import load_template
from flyer_generator.brochure.schema_renderer.renderer import render_schema_brochure
from flyer_generator.brochure.stages.pdf import assemble_brochure_pdf
from flyer_generator.stages.rasterizer import Rasterizer

logger = structlog.get_logger()


async def task_generate_brochure(ctx: dict, *, job_id: str, payload: dict) -> str | None:
    """Generate a brochure (front + back PNGs + print PDF).

    Per 21-07-PLAN.md Task 1 (parallel-id pattern): returns ``BrochureRecord.id``
    (== ``job_id``) as the primary ``result_ref``. The 3 render ids are
    discoverable through ``BrochureRecord.render_{front,back,pdf}_id`` via the
    new ``GET /api/v1/brochures/{id}`` detail route. Mirrors how campaigns
    link to JobRecord (see flyer_generator/api/routes/jobs.py lines 57-69
    comment: "JobRecord.id is reused as CampaignRecord.id").
    """
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]
    http_client = ctx["http_client"]

    log = logger.bind(job_id=job_id, kind="brochure")
    log.info("task_start")
    await mark_running(sessionmaker, job_id)

    try:
        content = BrochureContent.model_validate(payload["content"])
        template_name = payload["template"]
        slug = payload.get("brand_kit_slug")

        # Load brand kit if requested (raises BrandKitNotFoundError on miss).
        kit = None
        if slug is not None:
            kit = load_brand_kit(slug, base_dir=Path(settings.brand_kits_dir))

        template = load_template(template_name)

        # 1) Generate hero + spot images if requested (ASYNC, existing).
        # NOTE: generate_template_images keyword is ``workflow_name``, NOT
        # ``workflow`` — see image_gate.py:197.
        images: dict = {}
        if payload.get("generate_images", True):
            images = await generate_template_images(
                template,
                content,
                settings=settings,
                http_client=http_client,
                workflow_name=payload.get("workflow_name", "turbo_landscape"),
                style_preset=payload.get("style_preset", "photorealistic"),
            )

        # 2) Render the two SVGs (SYNC — wrap in to_thread).
        # ``BrandLogo`` has no in-memory ``.bytes`` attribute — it's a
        # filesystem-backed asset (``BrandLogo.path`` relative to kit dir).
        # Pass ``None`` for now; downstream renderer handles missing logos.
        # When logo-byte hydration lands, replace with the correct load.
        logo_bytes: bytes | None = None
        outside_svg, inside_svg = await asyncio.to_thread(
            render_schema_brochure,
            template,
            content,
            images=images,
            logo_bytes=logo_bytes,
        )

        # 3) Rasterize to PNG (SYNC — wrap in to_thread).
        rast = Rasterizer()

        def _rasterize_both() -> tuple[bytes, bytes]:
            return rast.rasterize(outside_svg), rast.rasterize(inside_svg)

        front_png, back_png = await asyncio.to_thread(_rasterize_both)

        # 4) Assemble PDF (SYNC — wrap in to_thread).
        pdf_bytes = await asyncio.to_thread(assemble_brochure_pdf, front_png, back_png)

        # 5) Write 3 artifacts to disk under a per-job subdir.
        base = Path(settings.artifact_root_brochure) / job_id
        base.mkdir(parents=True, exist_ok=True)
        front_path = base / "front.png"
        back_path = base / "back.png"
        pdf_path = base / "print.pdf"
        front_path.write_bytes(front_png)
        back_path.write_bytes(back_png)
        pdf_path.write_bytes(pdf_bytes)

        # 6) Persist 3 RenderRecords + BrochureRecord.
        async with sessionmaker() as s:
            r_front = RenderRecord(kind="brochure_front", file_path=str(front_path.resolve()))
            r_back = RenderRecord(kind="brochure_back", file_path=str(back_path.resolve()))
            r_pdf = RenderRecord(kind="brochure_pdf", file_path=str(pdf_path.resolve()))
            s.add_all([r_front, r_back, r_pdf])
            await s.flush()

            # Per 21-PATTERNS.md Q4 recommendation #2: assign brochure.id = job_id
            # so JobRecord.id == BrochureRecord.id. Mirrors how campaigns work
            # (see flyer_generator/api/routes/jobs.py:57-69 comment).
            brochure = BrochureRecord(
                id=job_id,  # parallel-id pattern (Plan 21-07 Task 1)
                title=getattr(content, "title", template_name),
                template=template_name,
                brand_kit_slug=slug,
                content_payload=payload,
                render_front_id=r_front.id,
                render_back_id=r_back.id,
                render_pdf_id=r_pdf.id,
            )
            s.add(brochure)
            await s.commit()
            # result_ref = brochure.id so /jobs/{id} -> /brochures/{result_ref}
            # finds the row directly. The single front_render_id (the previous
            # result_ref) is still discoverable via BrochureRecord.render_front_id
            # when the FE calls GET /brochures/{id}.
            result_ref = brochure.id

        await mark_succeeded(sessionmaker, job_id, result_ref=result_ref)
        log.info("task_succeeded", brochure_id=result_ref)
        return result_ref

    except Exception as exc:
        log.exception("task_failed")
        await mark_failed(sessionmaker, job_id, exc)
        raise
