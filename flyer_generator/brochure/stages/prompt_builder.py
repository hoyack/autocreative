"""Brochure cover prompt builder.

Reuses the flyer PresetRegistry, StylePreset fragments, and UNIVERSAL_NEGATIVE,
but swaps FLYER_DIRECTIVES (portrait 9:16, text-free) for BROCHURE_COVER_DIRECTIVES
(landscape 16:9-ish, text-safe edges, centred subject in middle third for clean
title overlay).
"""

from __future__ import annotations

import copy
import secrets

from flyer_generator.brochure.models import BrochureInput
from flyer_generator.models import WorkflowConfig
from flyer_generator.presets import UNIVERSAL_NEGATIVE, PresetRegistry
from flyer_generator.stages.prompt_builder import ComfyWorkflow

BROCHURE_COVER_DIRECTIVES: list[str] = [
    "Landscape composition, 16:9 aspect ratio.",
    "Main subject centred in the middle third of the frame.",
    "Clean, low-detail areas along the left and right edges for title and subtitle overlay.",
    "Soft gradient or calm sky toward the top third to anchor a large overlaid headline.",
    "No text, no writing, no letters, no signs, no graphic design elements.",
    "Visually balanced — no single corner dominating attention.",
]


class BrochureCoverPromptBuilder:
    """Builds a ComfyCloud workflow for the brochure cover hero image."""

    def __init__(
        self,
        presets: PresetRegistry,
        workflow_config: WorkflowConfig | None = None,
    ) -> None:
        self._presets = presets
        self._workflow_config = workflow_config

    def build(
        self,
        brochure: BrochureInput,
        attempt: int,
        refinement_hint: str = "",
    ) -> ComfyWorkflow:
        """Compose a ComfyWorkflow targeting the cover panel hero image.

        Mirrors the flyer StylePromptBuilder's injection pattern: preset fragments
        with {concept} substitution, then BROCHURE_COVER_DIRECTIVES, then optional
        refinement hint from a previous vision rejection.
        """
        wf = self._get_workflow_config()
        preset = self._presets.get(brochure.style_preset)

        parts: list[str] = [
            frag.replace("{concept}", brochure.hero_concept)
            for frag in preset.positive_fragments
        ]
        parts.extend(BROCHURE_COVER_DIRECTIVES)
        if refinement_hint:
            parts.append(f"Additional direction: {refinement_hint}")
        positive_prompt = " ".join(parts)

        negative_prompt = f"{UNIVERSAL_NEGATIVE}, {preset.negative_fragment}"

        seed = secrets.randbelow(2**31)

        workflow = copy.deepcopy(wf.workflow)
        ip = wf.injection_points
        workflow[ip["positive_prompt"]]["inputs"]["text"] = positive_prompt
        workflow[ip["negative_prompt"]]["inputs"]["text"] = negative_prompt
        workflow[ip["seed"]]["inputs"]["seed"] = seed

        return ComfyWorkflow(
            workflow=workflow,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            latent_dimensions=wf.latent_dimensions,
        )

    def _get_workflow_config(self) -> WorkflowConfig:
        """Return the workflow config, lazy-loading the landscape default."""
        if self._workflow_config is None:
            from flyer_generator.workflow_loader import load_workflow

            self._workflow_config = load_workflow("turbo_landscape")
        return self._workflow_config
