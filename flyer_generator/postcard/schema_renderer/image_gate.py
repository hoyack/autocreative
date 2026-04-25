"""Phase 24.1 (PLF-01) — postcard hero image generation.

The perception loop (2026-04-25, Finding F1) showed that
``POST /api/v1/postcards`` succeeded in ~3 seconds without ever invoking
ComfyCloud, so the rendered front PNG always carried the literal
``[ hero ]`` placeholder string. This module wires the missing Comfy
call.

Compared to the brochure pipeline:

- Brochure has a multi-slot template (hero + spot_1..N) with a vision
  gate on the hero. Postcards have a single ``hero`` image slot and
  haven't had a vision gate before. Per ``24.1-CONTEXT.md`` decision
  ("the bug is `no Comfy call is made`"), wiring a basic single-shot
  Comfy call without vision retries is the locked acceptance bar.
- Failures are logged and swallowed: the renderer's gradient fallback
  covers a missing image, so a flaky ComfyCloud should never block the
  postcard from rendering.

Public API
----------
``generate_postcard_hero(template, content, *, settings, http_client,
workflow_name, style_preset)`` returns ``{"hero": png_bytes}`` on success
or ``{}`` on failure / when ``content.image_hint`` is None.
"""

from __future__ import annotations

import httpx
import structlog

from flyer_generator.config import Settings
from flyer_generator.postcard.schema_renderer.content_model import (
    PostcardContent,
)
from flyer_generator.postcard.schema_renderer.schema_model import (
    PostcardTemplateSchema,
)

logger = structlog.get_logger()


async def generate_postcard_hero(
    template: PostcardTemplateSchema,
    content: PostcardContent,
    *,
    settings: Settings,
    http_client: httpx.AsyncClient,
    workflow_name: str = "turbo_landscape",
    style_preset: str = "photorealistic",
) -> dict[str, bytes]:
    """Generate a single hero image for a postcard via ComfyCloud.

    Mirrors the brochure pipeline's spot-image path (no vision gate, no
    multi-attempt retry beyond ``ComfyClient``'s built-in 5xx backoff).
    Returns ``{"hero": raw_png_bytes}`` on success or ``{}`` when
    ``content.image_hint`` is None or generation fails — the renderer's
    gradient fallback covers an empty result so a flaky ComfyCloud never
    blocks the postcard from rendering.

    The call routes through
    :func:`flyer_generator.brochure.schema_renderer.image_gate.generate_single_image`
    — the canonical single-image helper that already handles workflow
    loading, ``ComfyClient`` construction with the correct
    ``(settings, http_client)`` args, and submit/poll/download. That is
    the same seam ``social/generator.py`` and ``social/campaign.py`` use,
    keeping postcard generation consistent with the rest of the stack.

    Patching ``flyer_generator.stages.comfy_client.ComfyClient.generate``
    in tests (the lowest seam) intercepts the outbound Comfy call
    regardless of which helper invokes it.
    """
    # ``template`` is unused today — postcards declare a single hero slot
    # whose dimensions are baked into the workflow choice. Keep the kwarg
    # so a future template that varies the hero workflow can override it
    # without breaking the call site.
    del template

    if content.image_hint is None:
        return {}

    # Local import: the brochure helper is the canonical Comfy-single-shot
    # entry point and importing at module top would create a circular
    # import (postcard -> brochure -> postcard schema_renderer __init__).
    from flyer_generator.brochure.schema_renderer.image_gate import (  # noqa: PLC0415
        generate_single_image,
    )

    log = logger.bind(
        workflow=workflow_name,
        style_preset=style_preset,
        prompt_len=len(content.image_hint),
    )

    try:
        raw_bytes = await generate_single_image(
            workflow_name=workflow_name,
            prompt=content.image_hint,
            settings=settings,
            http_client=http_client,
            style_preset=style_preset,
        )
    except Exception as err:  # noqa: BLE001 — best-effort hero generation
        # Postcards must always render; a ComfyCloud blip just means we
        # fall back to the placeholder gradient. This matches the
        # brochure spot-image policy in
        # ``brochure/schema_renderer/image_gate.py::_gen_spot``.
        log.warning(
            "postcard_hero_generate_failed",
            error_type=type(err).__name__,
            error=str(err) or repr(err),
        )
        return {}

    log.info("postcard_hero_generated", image_bytes=len(raw_bytes))
    return {"hero": raw_bytes}
