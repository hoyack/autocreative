"""FlyerGenerator -- pipeline orchestrator wiring all 7 stages."""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING

import httpx
import structlog

from flyer_generator.config import Settings
from flyer_generator.errors import MaxAttemptsExceededError
from flyer_generator.logging_config import get_logger
from flyer_generator.models import EventInput, FlyerInput, FlyerOutput
from flyer_generator.presets import PresetRegistry, build_default_registry
from flyer_generator.stages.composer import PosterComposer
from flyer_generator.stages.comfy_client import ComfyClient
from flyer_generator.stages.layout import LayoutResolver
from flyer_generator.stages.preprocessor import ImagePreprocessor
from flyer_generator.stages.prompt_builder import StylePromptBuilder
from flyer_generator.stages.rasterizer import Rasterizer
from flyer_generator.stages.vision import VisionEvaluator
from flyer_generator.workflow_loader import load_workflow

if TYPE_CHECKING:
    from flyer_generator.flyer.schema_renderer.schema_model import (
        FlyerTemplateSchema,
    )


class FlyerGenerator:
    """Pipeline orchestrator that wires all 7 stages into the generate-evaluate-retry loop.

    Stages: prompt_builder -> comfy_client -> preprocessor -> vision -> layout -> composer -> rasterizer

    On vision rejection, feeds refinement_hint back to prompt_builder and retries
    up to ``settings.max_bg_attempts`` times. Raises MaxAttemptsExceededError on exhaustion.

    Phase 24-02 (PO-02): ``__init__`` accepts an optional
    ``canvas_dimensions: tuple[int, int]`` keyword. When ``None`` (default),
    the pipeline falls back to ``(1080, 1920)`` — preserving Phase 22 byte-
    identical flyer behavior for the existing flyer worker which calls
    ``FlyerGenerator(settings=..., http_client=...)`` with no kwarg. When
    supplied (e.g. ``(5400, 7200)`` for 18×24" posters at 300 DPI), the
    entire stage chain — preprocessor upscale target, composer canvas
    math, rasterizer output, and ``FlyerOutput.dimensions`` — operates at
    the injected size.
    """

    def __init__(
        self,
        settings: Settings,
        presets: PresetRegistry | None = None,
        http_client: httpx.AsyncClient | None = None,
        *,
        canvas_dimensions: tuple[int, int] | None = None,
    ) -> None:
        self.settings = settings
        # Default to the flyer canvas (1080, 1920) when callers omit the
        # kwarg. The poster worker (Plan 24-04) injects a per-size tuple
        # so the entire stage chain renders at the right print canvas.
        self._canvas_dimensions: tuple[int, int] = canvas_dimensions or (1080, 1920)

        if presets is None:
            presets = build_default_registry()

        self._owns_http = False
        if http_client is None:
            http_client = httpx.AsyncClient(follow_redirects=True)
            self._owns_http = True

        wf_config = load_workflow(settings.workflow)
        self._prompt_builder = StylePromptBuilder(presets, workflow_config=wf_config)
        self._comfy_client = ComfyClient(settings, http_client)
        # Stage chain receives the injected canvas dimensions so upscale,
        # composition, and rasterization all operate at the same size.
        self._preprocessor = ImagePreprocessor(final_dimensions=self._canvas_dimensions)
        self._vision = VisionEvaluator(settings)
        self._layout = LayoutResolver()
        self._composer = PosterComposer(canvas_width=self._canvas_dimensions[0])
        self._rasterizer = Rasterizer(
            width=self._canvas_dimensions[0],
            height=self._canvas_dimensions[1],
        )

    async def generate(
        self,
        event: FlyerInput,
        *,
        template: "FlyerTemplateSchema | None" = None,
    ) -> FlyerOutput:
        """Run the full flyer generation pipeline.

        Args:
            event: FlyerInput (event or info subtype) — title + org +
                style_concept + style_preset are required; event-specific
                fields (date/time/location/fees) and info-specific fields
                (description/call_to_action) are optional and gated on
                ``event.subtype``.
            template: Optional FlyerTemplateSchema. When supplied, the
                composer reads typography / scrim opacity / accent color
                from the template instead of the Phase-21 hardcoded
                defaults. When ``None``, preserves pre-Phase-22 byte-
                identical output (back-compat for CLI / direct callers).

        Returns:
            FlyerOutput with rasterized PNG bytes and metadata.

        Raises:
            MaxAttemptsExceededError: If vision rejects all attempts.
        """
        trace_id = uuid.uuid4().hex
        logger: structlog.stdlib.BoundLogger = get_logger().bind(
            trace_id=trace_id, event_title=event.title
        )

        refinement_hint = ""
        rejection_history: list[str] = []

        for attempt in range(1, self.settings.max_bg_attempts + 1):
            logger.info("attempt_start", attempt=attempt, hint=refinement_hint)

            # Stage 1: Build ComfyCloud workflow from preset + event
            workflow = self._prompt_builder.build(event, attempt, refinement_hint)

            # D-17: log prompt hash at info level, never full prompt at info
            prompt_hash = hashlib.sha256(
                workflow.positive_prompt.encode()
            ).hexdigest()[:12]
            logger.info("prompt_composed", prompt_hash=prompt_hash, attempt=attempt)
            logger.debug("prompt_full", positive_prompt=workflow.positive_prompt)

            # Stage 2: Submit to ComfyCloud, poll, download
            comfy_job, raw_bytes = await self._comfy_client.generate(workflow, attempt)

            # Stage 3: Upscale raw bytes to final resolution
            background = self._preprocessor.upscale(raw_bytes, comfy_job)

            # Stage 4: Vision evaluation
            verdict = await self._vision.evaluate(background, event)

            if verdict.approved:
                logger.info(
                    "vision_approved",
                    confidence=verdict.confidence,
                    zones=verdict.zones.model_dump() if verdict.zones else None,
                )

                # Stage 5: Resolve zone labels to pixel coordinates
                layout = self._layout.resolve(verdict.zones)

                # Stage 6: Compose SVG
                svg = self._composer.compose(
                    event, background, verdict, layout, template=template
                )

                # Stage 7: Rasterize SVG to PNG
                png_bytes = self._rasterizer.rasterize(svg)

                logger.info(
                    "flyer_generated",
                    size_kb=len(png_bytes) // 1024,
                    attempts_used=attempt,
                )

                return FlyerOutput(
                    png_bytes=png_bytes,
                    dimensions=self._canvas_dimensions,
                    file_size_kb=len(png_bytes) // 1024,
                    event_title=event.title,
                    attempts_used=attempt,
                    final_vision_verdict=verdict,
                    zones_used=verdict.zones,
                    trace_id=trace_id,
                )

            # Rejected -- log and prepare next attempt
            logger.warning(
                "vision_rejected",
                attempt=attempt,
                reasons=verdict.rejection_reasons,
                hint=verdict.refinement_hint,
            )
            rejection_history.extend(verdict.rejection_reasons)
            refinement_hint = verdict.refinement_hint

        raise MaxAttemptsExceededError(
            f"Vision rejected {self.settings.max_bg_attempts} backgrounds. "
            f"Rejection history: {rejection_history}",
            trace_id=trace_id,
        )
