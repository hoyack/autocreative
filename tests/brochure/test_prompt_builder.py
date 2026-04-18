"""Tests for the brochure cover prompt builder."""

from __future__ import annotations

from flyer_generator.brochure.stages.prompt_builder import (
    BROCHURE_COVER_DIRECTIVES,
    BrochureCoverPromptBuilder,
)
from flyer_generator.presets import (
    FLYER_DIRECTIVES,
    UNIVERSAL_NEGATIVE,
    build_default_registry,
)
from flyer_generator.workflow_loader import load_workflow
from tests.brochure.fixtures.sample_brochures import FULL_BROCHURE, MINIMAL_BROCHURE


def _builder() -> BrochureCoverPromptBuilder:
    return BrochureCoverPromptBuilder(
        presets=build_default_registry(),
        workflow_config=load_workflow("turbo_landscape"),
    )


def test_build_returns_comfy_workflow_with_landscape_latent() -> None:
    wf = _builder().build(MINIMAL_BROCHURE, attempt=1)
    assert wf.latent_dimensions == (1472, 832)
    assert isinstance(wf.positive_prompt, str)
    assert isinstance(wf.negative_prompt, str)


def test_positive_prompt_substitutes_hero_concept() -> None:
    wf = _builder().build(MINIMAL_BROCHURE, attempt=1)
    assert MINIMAL_BROCHURE.hero_concept in wf.positive_prompt


def test_positive_prompt_contains_brochure_directives_not_flyer() -> None:
    wf = _builder().build(MINIMAL_BROCHURE, attempt=1)
    for directive in BROCHURE_COVER_DIRECTIVES:
        assert directive in wf.positive_prompt
    # Flyer-specific directives must NOT appear.
    for flyer_directive in FLYER_DIRECTIVES:
        assert flyer_directive not in wf.positive_prompt


def test_negative_prompt_includes_universal_negative() -> None:
    wf = _builder().build(FULL_BROCHURE, attempt=1)
    assert UNIVERSAL_NEGATIVE in wf.negative_prompt


def test_refinement_hint_appears_in_positive_prompt() -> None:
    wf = _builder().build(
        MINIMAL_BROCHURE,
        attempt=2,
        refinement_hint="more calm sky at top",
    )
    assert "more calm sky at top" in wf.positive_prompt
    assert "Additional direction" in wf.positive_prompt


def test_refinement_hint_omitted_when_empty() -> None:
    wf = _builder().build(MINIMAL_BROCHURE, attempt=1, refinement_hint="")
    assert "Additional direction" not in wf.positive_prompt


def test_workflow_nodes_contain_injected_values() -> None:
    wf = _builder().build(MINIMAL_BROCHURE, attempt=1)
    config = load_workflow("turbo_landscape")
    ip = config.injection_points
    # The deep-copied workflow inside wf.workflow should have the injected prompts/seed.
    assert wf.workflow[ip["positive_prompt"]]["inputs"]["text"] == wf.positive_prompt
    assert wf.workflow[ip["negative_prompt"]]["inputs"]["text"] == wf.negative_prompt
    assert wf.workflow[ip["seed"]]["inputs"]["seed"] == wf.seed


def test_builder_lazy_loads_default_landscape_workflow() -> None:
    # Constructed without an explicit workflow_config → should default to turbo_landscape.
    builder = BrochureCoverPromptBuilder(presets=build_default_registry())
    wf = builder.build(MINIMAL_BROCHURE, attempt=1)
    assert wf.latent_dimensions == (1472, 832)


def test_seed_varies_between_calls() -> None:
    builder = _builder()
    seeds = {builder.build(MINIMAL_BROCHURE, attempt=1).seed for _ in range(5)}
    assert len(seeds) >= 2  # vanishingly unlikely to all collide
