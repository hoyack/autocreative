"""Stage 4: Imagery orchestration.

Generates 1 hero (cover) + 0-3 spot images in parallel, driven by LayoutChoice + outline.image_hints.

- Hero: reuses phase-6 BrochureCoverPromptBuilder + BrochureCoverVisionEvaluator (regen loop on rejection)
- Spots: simpler prompt variant, no vision evaluation (decorative, per design doc §4)
- Skips hero entirely when cover_treatment == "shapes_only"
"""

from __future__ import annotations

import asyncio
import copy
import secrets

import httpx
import structlog
from pydantic import BaseModel, ConfigDict

from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    LayoutChoice,
)
from flyer_generator.brochure.models import BrochureInput
from flyer_generator.brochure.stages.prompt_builder import BrochureCoverPromptBuilder
from flyer_generator.brochure.stages.vision import BrochureCoverVisionEvaluator
from flyer_generator.config import Settings
from flyer_generator.errors import MaxAttemptsExceededError
from flyer_generator.models import VisionVerdict, WorkflowConfig
from flyer_generator.presets import (
    FLYER_DIRECTIVES,
    UNIVERSAL_NEGATIVE,
    PresetRegistry,
    build_default_registry,
)
from flyer_generator.stages.comfy_client import ComfyClient
from flyer_generator.stages.prompt_builder import ComfyWorkflow
from flyer_generator.workflow_loader import load_workflow

logger = structlog.get_logger()


class GeneratedImagery(BaseModel):
    """Stage 4 output: hero + spot images produced for the brochure."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    hero_png_bytes: bytes | None = None
    spot_images: dict[str, bytes] = {}  # keyed by section heading
    hero_vision_verdict: VisionVerdict | None = None
    hero_attempts_used: int = 0


def _build_spot_workflow(
    wf_config: WorkflowConfig,
    presets: PresetRegistry,
    style_preset: str,
    hint: str,
) -> ComfyWorkflow:
    """Minimal spot-image workflow: style preset + hint, no cover directives, no title-safe edges."""
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
    workflow[ip["seed"]]["inputs"]["seed"] = seed

    return ComfyWorkflow(
        workflow=workflow,
        positive_prompt=positive,
        negative_prompt=negative,
        seed=seed,
        latent_dimensions=wf_config.latent_dimensions,
    )


async def generate_imagery(
    brochure: BrochureInput,
    outline: BrochureOutline,
    layout_choice: LayoutChoice,
    settings: Settings,
    *,
    presets: PresetRegistry | None = None,
    http_client: httpx.AsyncClient | None = None,
    comfy_client: ComfyClient | None = None,
    cover_builder: BrochureCoverPromptBuilder | None = None,
    cover_vision: BrochureCoverVisionEvaluator | None = None,
    workflow_name: str = "turbo_landscape",
) -> GeneratedImagery:
    """Produce hero + spot images in parallel.

    Test hooks: `comfy_client`, `cover_builder`, `cover_vision` can all be injected; otherwise built from settings.
    """
    if presets is None:
        presets = build_default_registry()

    _owns_http = False
    if http_client is None and comfy_client is None:
        http_client = httpx.AsyncClient(follow_redirects=True)
        _owns_http = True

    wf_config = load_workflow(workflow_name)

    if cover_builder is None:
        cover_builder = BrochureCoverPromptBuilder(presets, workflow_config=wf_config)
    if cover_vision is None:
        cover_vision = BrochureCoverVisionEvaluator(settings)
    if comfy_client is None:
        comfy_client = ComfyClient(settings, http_client)  # type: ignore[arg-type]

    # -- Hero (skipped when shapes_only) --
    hero_png_bytes: bytes | None = None
    hero_vision_verdict: VisionVerdict | None = None
    hero_attempts_used = 0

    if layout_choice.cover_treatment != "shapes_only":
        refinement_hint = ""
        rejection_history: list[str] = []
        for attempt in range(1, settings.max_bg_attempts + 1):
            logger.info("brochure_hero_attempt", attempt=attempt)
            wf = cover_builder.build(brochure, attempt, refinement_hint)
            _, raw_bytes = await comfy_client.generate(wf, attempt)
            verdict = await cover_vision.evaluate(
                image_bytes=raw_bytes,
                concept=brochure.hero_concept,
                style_preset=brochure.style_preset,
            )
            if verdict.approved:
                hero_png_bytes = raw_bytes
                hero_vision_verdict = verdict
                hero_attempts_used = attempt
                break
            rejection_history.extend(verdict.rejection_reasons)
            refinement_hint = verdict.refinement_hint
        else:
            if _owns_http and http_client is not None:
                await http_client.aclose()
            raise MaxAttemptsExceededError(
                f"Vision rejected {settings.max_bg_attempts} hero attempts. "
                f"Rejection history: {rejection_history}",
                trace_id="brochure-v2-imagery",
            )

    # -- Spot images (parallel, no vision gate) --
    spot_sections = [s for s in outline.sections if s.image_hint]
    spot_sections = spot_sections[:3]  # cap at 3 per design

    async def _gen_spot(hint: str, heading: str) -> tuple[str, bytes]:
        wf = _build_spot_workflow(wf_config, presets, brochure.style_preset, hint)
        _, png_bytes = await comfy_client.generate(wf, attempt=1)  # type: ignore[union-attr]
        return heading, png_bytes

    spot_images: dict[str, bytes] = {}
    if spot_sections:
        results = await asyncio.gather(
            *(_gen_spot(s.image_hint, s.heading) for s in spot_sections)  # type: ignore[arg-type]
        )
        spot_images = dict(results)

    if _owns_http and http_client is not None:
        await http_client.aclose()

    return GeneratedImagery(
        hero_png_bytes=hero_png_bytes,
        spot_images=spot_images,
        hero_vision_verdict=hero_vision_verdict,
        hero_attempts_used=hero_attempts_used,
    )
