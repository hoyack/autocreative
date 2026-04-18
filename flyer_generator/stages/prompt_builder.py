"""StylePromptBuilder — composes ComfyCloud workflow JSON from presets."""

from __future__ import annotations

import copy
import secrets
from typing import TYPE_CHECKING

from pydantic import BaseModel

from flyer_generator.models import EventInput, WorkflowConfig
from flyer_generator.presets import (
    FLYER_DIRECTIVES,
    UNIVERSAL_NEGATIVE,
    PresetRegistry,
)

if TYPE_CHECKING:
    pass


class ComfyWorkflow(BaseModel):
    """Immutable snapshot of a fully-composed ComfyCloud workflow."""

    workflow: dict  # Deep-copied node graph with injected values
    positive_prompt: str
    negative_prompt: str
    seed: int
    latent_dimensions: tuple[int, int] = (832, 1472)


class StylePromptBuilder:
    """Builds ComfyWorkflow objects from EventInput + PresetRegistry."""

    def __init__(
        self,
        presets: PresetRegistry,
        workflow_config: WorkflowConfig | None = None,
    ) -> None:
        self._presets = presets
        self._workflow_config = workflow_config

    def build(
        self,
        event: EventInput,
        attempt: int,
        refinement_hint: str = "",
    ) -> ComfyWorkflow:
        """Compose a ComfyWorkflow from the event's style preset.

        Uses the workflow_config's injection_points to place prompts and seed
        into the correct ComfyUI node IDs. Falls back to loading turbo_portrait
        if no workflow_config was provided.
        """
        wf = self._get_workflow_config()

        preset = self._presets.get(event.style_preset)

        # Positive prompt: preset fragments (concept substituted) + directives + optional hint
        parts: list[str] = [
            frag.replace("{concept}", event.style_concept)
            for frag in preset.positive_fragments
        ]
        parts.extend(FLYER_DIRECTIVES)
        if refinement_hint:
            parts.append(f"Additional direction: {refinement_hint}")
        positive_prompt = " ".join(parts)

        # Negative prompt: universal + preset-specific
        negative_prompt = f"{UNIVERSAL_NEGATIVE}, {preset.negative_fragment}"

        # Random seed
        seed = secrets.randbelow(2**31)

        # Deep-copy node graph and inject via injection_points
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
        """Return the workflow config, lazy-loading default if needed."""
        if self._workflow_config is None:
            from flyer_generator.workflow_loader import load_workflow

            self._workflow_config = load_workflow("turbo_portrait")
        return self._workflow_config
