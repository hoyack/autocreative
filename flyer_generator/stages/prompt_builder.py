"""StylePromptBuilder — composes ComfyCloud workflow JSON from presets."""

from __future__ import annotations

import copy
import secrets

from pydantic import BaseModel

from flyer_generator.models import EventInput
from flyer_generator.presets import (
    COMFY_WORKFLOW_TEMPLATE,
    FLYER_DIRECTIVES,
    UNIVERSAL_NEGATIVE,
    PresetRegistry,
)


class ComfyWorkflow(BaseModel):
    """Immutable snapshot of a fully-composed ComfyCloud workflow."""

    workflow: dict  # Deep-copied COMFY_WORKFLOW_TEMPLATE with injected values
    positive_prompt: str
    negative_prompt: str
    seed: int


class StylePromptBuilder:
    """Builds ComfyWorkflow objects from EventInput + PresetRegistry."""

    def __init__(self, presets: PresetRegistry) -> None:
        self._presets = presets

    def build(
        self,
        event: EventInput,
        attempt: int,
        refinement_hint: str = "",
    ) -> ComfyWorkflow:
        """Compose a ComfyWorkflow from the event's style preset.

        Args:
            event: Structured event data containing style_concept and style_preset.
            attempt: Current generation attempt number (informational).
            refinement_hint: Optional hint from vision rejection to refine the prompt.

        Returns:
            A ComfyWorkflow with composed prompts, seed, and deep-copied workflow dict.

        Raises:
            UnknownPresetError: If event.style_preset is not in the registry.
        """
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

        # Deep-copy template and inject values
        workflow = copy.deepcopy(COMFY_WORKFLOW_TEMPLATE)
        workflow["positive_prompt"] = positive_prompt
        workflow["negative_prompt"] = negative_prompt
        workflow["seed"] = seed

        return ComfyWorkflow(
            workflow=workflow,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed=seed,
        )
