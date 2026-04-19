"""Phase 4: image generation for schema-renderer `image_placeholder` slots.

Walks a TemplateSchema, collects every unique slot name, and generates one
image per slot via ComfyCloud. Hero slot is routed through
BrochureCoverPromptBuilder + BrochureCoverVisionEvaluator so text-in-image
artifacts are rejected and retried. Spot slots use a minimal spot prompt and
run in parallel with no vision gate.

Failed slots are simply omitted from the returned dict — the renderer falls
back to the placeholder's `fallback_fill` so a template that fails to produce
an image still produces a valid brochure.
"""

from __future__ import annotations

import asyncio
import copy
import secrets

import httpx
import structlog

from flyer_generator.brochure.models import BrochureInput, BrochureSection
from flyer_generator.brochure.schema_renderer.content_model import BrochureContent
from flyer_generator.brochure.schema_renderer.schema_model import (
    ImagePlaceholder,
    TemplateSchema,
)
from flyer_generator.brochure.stages.prompt_builder import (
    BrochureCoverPromptBuilder,
)
from flyer_generator.brochure.stages.vision import BrochureCoverVisionEvaluator
from flyer_generator.config import Settings
from flyer_generator.models import WorkflowConfig
from flyer_generator.presets import (
    UNIVERSAL_NEGATIVE,
    PresetRegistry,
    build_default_registry,
)
from flyer_generator.stages.comfy_client import ComfyClient
from flyer_generator.stages.prompt_builder import ComfyWorkflow
from flyer_generator.workflow_loader import load_workflow

logger = structlog.get_logger()


def collect_image_slots(template: TemplateSchema) -> list[str]:
    """Return unique `image_placeholder.slot` values across all panels.

    Order follows first-occurrence in panel iteration (front_cover, back_cover,
    tuck_flap, inner_left, inner_center, inner_right) so debugging logs read
    naturally.
    """
    seen: list[str] = []
    for panel in template.panels.values():
        for el in panel.elements:
            if isinstance(el, ImagePlaceholder) and el.slot not in seen:
                seen.append(el.slot)
    return seen


def resolve_concept_for_slot(slot: str, content: BrochureContent) -> str | None:
    """Pick the content concept that best matches a slot name.

    Mapping:
      - "hero" → content.hero_concept
      - "spot_N" → sections[N-1].image_concept → .icon_hint → heading-derived
      - anything else → None (caller should skip)
    """
    if slot == "hero":
        return content.hero_concept

    if slot.startswith("spot_"):
        try:
            idx = int(slot.split("_", 1)[1]) - 1
        except (ValueError, IndexError):
            return None
        if idx < 0 or idx >= len(content.sections):
            return None
        section = content.sections[idx]
        if section.image_concept:
            return section.image_concept
        if section.icon_hint:
            return section.icon_hint
        return f"A visual metaphor for: {section.heading}"

    return None


def _content_as_brochure_input(
    content: BrochureContent,
    style_preset: str,
) -> BrochureInput:
    """Adapt BrochureContent to a minimal BrochureInput for the cover builder.

    BrochureCoverPromptBuilder reads only .style_preset and .hero_concept, but
    BrochureInput has hard min_length=2 / max_length=5 on sections; pad or
    truncate accordingly.
    """
    sections: list[BrochureSection] = []
    for s in content.sections[:5]:
        body = s.lead_paragraph or (s.bullets[0] if s.bullets else s.heading)
        sections.append(
            BrochureSection(heading=s.heading, body=body, icon_hint=s.icon_hint)
        )
    while len(sections) < 2:
        sections.append(BrochureSection(heading="_", body="_"))

    return BrochureInput(
        title=content.title,
        subtitle=content.subtitle,
        hero_concept=content.hero_concept or content.title,
        style_preset=style_preset,
        color_accent=content.color_accent,
        org=content.org,
        contact=content.contact,
        sections=sections,
    )


def _build_spot_workflow(
    wf_config: WorkflowConfig,
    presets: PresetRegistry,
    style_preset: str,
    hint: str,
) -> ComfyWorkflow:
    """Minimal spot-image workflow, no cover directives or vision gate.

    Kept local (instead of importing from generative.imagery) so the schema
    renderer has no dependency on the legacy prompt-driven pipeline.
    """
    preset = presets.get(style_preset)
    positive = " ".join(
        frag.replace("{concept}", hint) for frag in preset.positive_fragments
    )
    negative = f"{UNIVERSAL_NEGATIVE}, {preset.negative_fragment}"
    seed = secrets.randbelow(2**31)

    workflow = copy.deepcopy(wf_config.workflow)
    ip = wf_config.injection_points
    workflow[ip["positive_prompt"]]["inputs"]["text"] = positive
    if "negative_prompt" in ip:
        workflow[ip["negative_prompt"]]["inputs"]["text"] = negative
    seed_inputs = workflow[ip["seed"]]["inputs"]
    seed_inputs["noise_seed" if "noise_seed" in seed_inputs else "seed"] = seed

    return ComfyWorkflow(
        workflow=workflow,
        positive_prompt=positive,
        negative_prompt=negative,
        seed=seed,
        latent_dimensions=wf_config.latent_dimensions,
    )


async def generate_template_images(
    template: TemplateSchema,
    content: BrochureContent,
    *,
    style_preset: str = "photorealistic",
    workflow_name: str = "ernie_landscape",
    settings: Settings | None = None,
    presets: PresetRegistry | None = None,
    http_client: httpx.AsyncClient | None = None,
    comfy_client: ComfyClient | None = None,
    cover_builder: BrochureCoverPromptBuilder | None = None,
    cover_vision: BrochureCoverVisionEvaluator | None = None,
) -> dict[str, bytes]:
    """Produce {slot: png_bytes} for every unique image_placeholder slot in template.

    Hero slot runs a vision-gated retry loop up to settings.max_bg_attempts.
    Spot slots run in parallel, no vision gate. If any slot exhausts retries
    or raises, it is omitted from the result; the renderer then falls back to
    the placeholder's `fallback_fill`.

    Test hooks: comfy_client, cover_builder, cover_vision are all injectable;
    if omitted, a real ComfyClient is constructed from settings.
    """
    if settings is None:
        settings = Settings()
    if presets is None:
        presets = build_default_registry()

    slots = collect_image_slots(template)
    if not slots:
        return {}

    _owns_http = False
    if http_client is None and comfy_client is None:
        http_client = httpx.AsyncClient(follow_redirects=True)
        _owns_http = True

    wf_config = load_workflow(workflow_name)

    if comfy_client is None:
        comfy_client = ComfyClient(settings, http_client)  # type: ignore[arg-type]
    if cover_builder is None:
        cover_builder = BrochureCoverPromptBuilder(presets, workflow_config=wf_config)
    if cover_vision is None:
        cover_vision = BrochureCoverVisionEvaluator(settings)

    brochure_in = _content_as_brochure_input(content, style_preset)

    images: dict[str, bytes] = {}

    try:
        # --- Hero (vision-gated, sequential) ---
        if "hero" in slots and content.hero_concept:
            refinement_hint = ""
            rejection_history: list[str] = []
            for attempt in range(1, settings.max_bg_attempts + 1):
                logger.info(
                    "schema_hero_attempt",
                    attempt=attempt,
                    max_attempts=settings.max_bg_attempts,
                    workflow=workflow_name,
                )
                try:
                    wf = cover_builder.build(brochure_in, attempt, refinement_hint)
                    _, raw = await comfy_client.generate(wf, attempt)
                except Exception as err:
                    logger.warning(
                        "schema_hero_generate_error",
                        attempt=attempt,
                        error=str(err),
                    )
                    break
                verdict = await cover_vision.evaluate(
                    image_bytes=raw,
                    concept=brochure_in.hero_concept,
                    style_preset=brochure_in.style_preset,
                )
                if verdict.approved:
                    images["hero"] = raw
                    logger.info("schema_hero_approved", attempts_used=attempt)
                    break
                rejection_history.extend(verdict.rejection_reasons)
                refinement_hint = verdict.refinement_hint
            else:
                logger.warning(
                    "schema_hero_exhausted",
                    max_attempts=settings.max_bg_attempts,
                    rejection_history=rejection_history,
                )

        # --- Spots (parallel, no vision gate) ---
        spot_slots = [s for s in slots if s != "hero"]
        spot_jobs: list[tuple[str, str]] = []
        for s in spot_slots:
            concept = resolve_concept_for_slot(s, content)
            if concept:
                spot_jobs.append((s, concept))
            else:
                logger.info("schema_spot_skipped_no_concept", slot=s)

        async def _gen_spot(slot: str, hint: str) -> tuple[str, bytes] | None:
            try:
                wf = _build_spot_workflow(wf_config, presets, style_preset, hint)
                _, raw = await comfy_client.generate(wf, attempt=1)  # type: ignore[union-attr]
                return (slot, raw)
            except Exception as err:
                logger.warning("schema_spot_failed", slot=slot, error=str(err))
                return None

        if spot_jobs:
            results = await asyncio.gather(
                *(_gen_spot(s, c) for s, c in spot_jobs)
            )
            for r in results:
                if r is not None:
                    images[r[0]] = r[1]
    finally:
        if _owns_http and http_client is not None:
            await http_client.aclose()

    return images
