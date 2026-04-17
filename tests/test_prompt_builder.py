"""Tests for StylePromptBuilder prompt composition logic."""

from __future__ import annotations

import pytest

from flyer_generator.errors import UnknownPresetError
from flyer_generator.models import EventInput
from flyer_generator.presets import (
    COMFY_WORKFLOW_TEMPLATE,
    FLYER_DIRECTIVES,
    UNIVERSAL_NEGATIVE,
    build_default_registry,
)
from flyer_generator.stages.prompt_builder import ComfyWorkflow, StylePromptBuilder
from tests.fixtures.sample_events import SAMPLE_EVENT


@pytest.fixture()
def builder() -> StylePromptBuilder:
    return StylePromptBuilder(presets=build_default_registry())


class TestBuildReturnsComfyWorkflow:
    def test_return_type(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert isinstance(result, ComfyWorkflow)

    def test_has_positive_and_negative(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert result.positive_prompt
        assert result.negative_prompt


class TestPositivePrompt:
    def test_substitutes_concept(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert SAMPLE_EVENT.style_concept in result.positive_prompt
        assert "{concept}" not in result.positive_prompt

    def test_includes_all_directives(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        for directive in FLYER_DIRECTIVES:
            assert directive in result.positive_prompt

    def test_includes_refinement_hint(self, builder: StylePromptBuilder) -> None:
        hint = "more vibrant colors, less shadowy"
        result = builder.build(SAMPLE_EVENT, attempt=2, refinement_hint=hint)
        assert f"Additional direction: {hint}" in result.positive_prompt

    def test_excludes_hint_when_empty(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1, refinement_hint="")
        assert "Additional direction" not in result.positive_prompt

    def test_contains_preset_fragments(self, builder: StylePromptBuilder) -> None:
        """Verify preset-specific text appears (with concept substituted)."""
        result = builder.build(SAMPLE_EVENT, attempt=1)
        # photorealistic preset starts with "A cinematic photograph: {concept}."
        expected = f"A cinematic photograph: {SAMPLE_EVENT.style_concept}."
        assert expected in result.positive_prompt


class TestNegativePrompt:
    def test_contains_universal_negative(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert UNIVERSAL_NEGATIVE in result.negative_prompt

    def test_contains_preset_negative_fragment(self, builder: StylePromptBuilder) -> None:
        preset = build_default_registry().get("photorealistic")
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert preset.negative_fragment in result.negative_prompt

    def test_composition_format(self, builder: StylePromptBuilder) -> None:
        preset = build_default_registry().get("photorealistic")
        result = builder.build(SAMPLE_EVENT, attempt=1)
        expected = f"{UNIVERSAL_NEGATIVE}, {preset.negative_fragment}"
        assert result.negative_prompt == expected


class TestSeed:
    def test_seed_in_valid_range(self, builder: StylePromptBuilder) -> None:
        for _ in range(20):
            result = builder.build(SAMPLE_EVENT, attempt=1)
            assert 0 <= result.seed < 2**31


class TestWorkflowDict:
    def test_is_deep_copy(self, builder: StylePromptBuilder) -> None:
        """Modifying the returned workflow must not affect the global template."""
        result = builder.build(SAMPLE_EVENT, attempt=1)
        result.workflow["sampler_config"]["steps"] = 999
        assert COMFY_WORKFLOW_TEMPLATE["sampler_config"]["steps"] == 8

    def test_has_injected_values(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert result.workflow["positive_prompt"] == result.positive_prompt
        assert result.workflow["negative_prompt"] == result.negative_prompt
        assert result.workflow["seed"] == result.seed

    def test_preserves_template_keys(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert "model_files" in result.workflow
        assert "sampler_config" in result.workflow
        assert "latent_dimensions" in result.workflow


class TestUnknownPreset:
    def test_raises_unknown_preset_error(self, builder: StylePromptBuilder) -> None:
        bad_event = EventInput(
            title="Test",
            date="2026-01-01",
            time="10:00 AM",
            location_name="Somewhere",
            location_address="123 Main St",
            fees="FREE",
            org="Test Org",
            style_concept="test concept",
            style_preset="nonexistent_preset",
        )
        with pytest.raises(UnknownPresetError):
            builder.build(bad_event, attempt=1)
