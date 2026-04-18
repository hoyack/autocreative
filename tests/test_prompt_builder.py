"""Tests for StylePromptBuilder prompt composition logic."""

from __future__ import annotations

import pytest

from flyer_generator.errors import UnknownPresetError
from flyer_generator.models import EventInput
from flyer_generator.presets import (
    FLYER_DIRECTIVES,
    UNIVERSAL_NEGATIVE,
    build_default_registry,
)
from flyer_generator.stages.prompt_builder import ComfyWorkflow, StylePromptBuilder
from flyer_generator.workflow_loader import load_workflow
from tests.fixtures.sample_events import SAMPLE_EVENT


@pytest.fixture()
def wf_config():
    return load_workflow("turbo_portrait")


@pytest.fixture()
def builder(wf_config) -> StylePromptBuilder:
    return StylePromptBuilder(presets=build_default_registry(), workflow_config=wf_config)


class TestBuildReturnsComfyWorkflow:
    def test_return_type(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert isinstance(result, ComfyWorkflow)

    def test_has_positive_and_negative(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert result.positive_prompt
        assert result.negative_prompt

    def test_has_latent_dimensions(self, builder: StylePromptBuilder) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert result.latent_dimensions == (832, 1472)


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
    def test_is_deep_copy(self, builder: StylePromptBuilder, wf_config) -> None:
        """Modifying the returned workflow must not affect the loaded config."""
        result = builder.build(SAMPLE_EVENT, attempt=1)
        seed_node = wf_config.injection_points["seed"]
        original_steps = wf_config.workflow[seed_node]["inputs"]["steps"]
        result.workflow[seed_node]["inputs"]["steps"] = 999
        # Original config unchanged
        assert wf_config.workflow[seed_node]["inputs"]["steps"] == original_steps

    def test_has_injected_values(self, builder: StylePromptBuilder, wf_config) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        ip = wf_config.injection_points
        assert result.workflow[ip["positive_prompt"]]["inputs"]["text"] == result.positive_prompt
        assert result.workflow[ip["negative_prompt"]]["inputs"]["text"] == result.negative_prompt
        assert result.workflow[ip["seed"]]["inputs"]["seed"] == result.seed

    def test_preserves_template_keys(self, builder: StylePromptBuilder, wf_config) -> None:
        result = builder.build(SAMPLE_EVENT, attempt=1)
        for node_id in wf_config.injection_points.values():
            assert node_id in result.workflow


class TestStandardSquareWorkflow:
    """Verify the second workflow (different node IDs, dimensions) works."""

    def test_standard_square_builds(self) -> None:
        wf = load_workflow("standard_square")
        builder = StylePromptBuilder(build_default_registry(), workflow_config=wf)
        result = builder.build(SAMPLE_EVENT, attempt=1)
        assert result.latent_dimensions == (1024, 1024)
        ip = wf.injection_points
        assert result.workflow[ip["positive_prompt"]]["inputs"]["text"] == result.positive_prompt
        assert result.workflow[ip["seed"]]["inputs"]["seed"] == result.seed


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
