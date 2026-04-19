"""BrochureGenerator — end-to-end pipeline orchestrator for the brochure.

Wires: prompt_builder → comfy_client → vision (hero evaluation) → composer (two SVGs) → rasterizer (two PNGs) → pdf (2-page PDF). Hero regen loop mirrors FlyerGenerator: on vision rejection, feed refinement_hint back and retry up to settings.max_bg_attempts.
"""

from __future__ import annotations

import hashlib
import uuid

import httpx

from flyer_generator.brochure.generative.models import LayoutChoice
from flyer_generator.brochure.models import BrochureInput, BrochureOutput
from flyer_generator.brochure.stages.composer import compose_brochure_svgs
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
    compute_panel_layout,
)
from flyer_generator.brochure.stages.pdf import assemble_brochure_pdf
from flyer_generator.brochure.stages.prompt_builder import BrochureCoverPromptBuilder
from flyer_generator.brochure.stages.vision import BrochureCoverVisionEvaluator
from flyer_generator.brochure.templates import get_template
from flyer_generator.config import Settings
from flyer_generator.errors import MaxAttemptsExceededError
from flyer_generator.logging_config import get_logger
from flyer_generator.presets import PresetRegistry, build_default_registry
from flyer_generator.stages.comfy_client import ComfyClient
from flyer_generator.stages.rasterizer import Rasterizer
from flyer_generator.workflow_loader import load_workflow


class BrochureGenerator:
    """End-to-end brochure pipeline. See module docstring for stage order."""

    def __init__(
        self,
        settings: Settings,
        presets: PresetRegistry | None = None,
        http_client: httpx.AsyncClient | None = None,
        workflow_name: str = "turbo_landscape",
    ) -> None:
        self.settings = settings

        if presets is None:
            presets = build_default_registry()

        self._owns_http = False
        if http_client is None:
            http_client = httpx.AsyncClient(follow_redirects=True)
            self._owns_http = True

        wf_config = load_workflow(workflow_name)
        self._prompt_builder = BrochureCoverPromptBuilder(presets, workflow_config=wf_config)
        self._comfy_client = ComfyClient(settings, http_client)
        self._vision = BrochureCoverVisionEvaluator(settings)
        self._rasterizer = Rasterizer(width=BLEED_CANVAS_WIDTH, height=BLEED_CANVAS_HEIGHT)

    async def generate(
        self,
        brochure: BrochureInput,
        *,
        layout_choice: LayoutChoice | None = None,
    ) -> BrochureOutput:
        """Run the full brochure generation pipeline.

        When `layout_choice` is provided, composer uses its template + shape
        parameters; otherwise the composer falls back to its default
        (editorial, medium density). Use this to force a specific
        LayoutTemplate for JSON-driven style testing.

        Raises:
            MaxAttemptsExceededError: If vision rejects all hero generation attempts.
        """
        trace_id = uuid.uuid4().hex
        logger = get_logger().bind(trace_id=trace_id, brochure_title=brochure.title)

        refinement_hint = ""
        rejection_history: list[str] = []
        final_verdict = None
        hero_bytes: bytes | None = None
        attempts_used = 0

        for attempt in range(1, self.settings.max_bg_attempts + 1):
            logger.info("brochure_attempt_start", attempt=attempt, hint=refinement_hint)

            workflow = self._prompt_builder.build(brochure, attempt, refinement_hint)
            prompt_hash = hashlib.sha256(
                workflow.positive_prompt.encode()
            ).hexdigest()[:12]
            logger.info("brochure_prompt_composed", prompt_hash=prompt_hash, attempt=attempt)

            comfy_job, raw_bytes = await self._comfy_client.generate(workflow, attempt)

            verdict = await self._vision.evaluate(
                image_bytes=raw_bytes,
                concept=brochure.hero_concept,
                style_preset=brochure.style_preset,
            )

            if verdict.approved:
                logger.info(
                    "brochure_hero_approved",
                    confidence=verdict.confidence,
                )
                hero_bytes = raw_bytes
                final_verdict = verdict
                attempts_used = attempt
                break

            logger.warning(
                "brochure_hero_rejected",
                attempt=attempt,
                reasons=verdict.rejection_reasons,
                hint=verdict.refinement_hint,
            )
            rejection_history.extend(verdict.rejection_reasons)
            refinement_hint = verdict.refinement_hint

        if hero_bytes is None or final_verdict is None:
            raise MaxAttemptsExceededError(
                f"Vision rejected {self.settings.max_bg_attempts} brochure hero attempts. "
                f"Rejection history: {rejection_history}",
                trace_id=trace_id,
            )

        # Compose SVGs → rasterize → assemble PDF
        layout = compute_panel_layout()
        template = get_template(layout_choice.template) if layout_choice else None
        outside_svg, inside_svg = compose_brochure_svgs(
            brochure,
            layout,
            hero_bytes,
            layout_choice=layout_choice,
            template=template,
        )
        front_png = self._rasterizer.rasterize(outside_svg)
        back_png = self._rasterizer.rasterize(inside_svg)
        pdf_bytes = assemble_brochure_pdf(front_png, back_png)

        logger.info(
            "brochure_generated",
            front_kb=len(front_png) // 1024,
            back_kb=len(back_png) // 1024,
            pdf_kb=len(pdf_bytes) // 1024,
            attempts_used=attempts_used,
        )

        return BrochureOutput(
            front_png_bytes=front_png,
            back_png_bytes=back_png,
            pdf_bytes=pdf_bytes,
            dimensions=(BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT),
            attempts_used=attempts_used,
            hero_vision_verdict=final_verdict,
            trace_id=trace_id,
        )


async def generate_brochure(
    brochure: BrochureInput,
    settings: Settings | None = None,
    presets: PresetRegistry | None = None,
) -> BrochureOutput:
    """One-shot async convenience: construct a BrochureGenerator and run it."""
    if settings is None:
        settings = Settings()
    gen = BrochureGenerator(settings=settings, presets=presets)
    return await gen.generate(brochure)
