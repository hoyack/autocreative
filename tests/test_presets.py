"""Tests for flyer_generator.presets — preset registry and built-in presets."""

import pytest

from flyer_generator.errors import UnknownPresetError
from flyer_generator.presets import (
    COMFY_WORKFLOW_TEMPLATE,
    FLYER_DIRECTIVES,
    UNIVERSAL_NEGATIVE,
    PresetRegistry,
    StylePreset,
    build_default_registry,
)


class TestPresetRegistry:
    def test_default_registry_has_six_presets(self):
        reg = build_default_registry()
        assert len(reg.list_names()) == 6

    def test_default_registry_preset_names(self):
        reg = build_default_registry()
        assert reg.list_names() == [
            "anime",
            "photorealistic",
            "retro_poster",
            "scifi",
            "watercolor",
            "western_cartoon",
        ]

    def test_preset_get_returns_correct(self):
        reg = build_default_registry()
        p = reg.get("photorealistic")
        assert p.name == "photorealistic"

    def test_preset_unknown_raises(self):
        reg = build_default_registry()
        with pytest.raises(UnknownPresetError):
            reg.get("nonexistent")

    def test_preset_concept_placeholder(self):
        reg = build_default_registry()
        for name in reg.list_names():
            preset = reg.get(name)
            has_concept = any("{concept}" in frag for frag in preset.positive_fragments)
            assert has_concept, f"Preset {name} missing {{concept}} placeholder"

    def test_preset_register_custom(self):
        reg = build_default_registry()
        custom = StylePreset(
            name="custom_neon",
            positive_fragments=["Neon glow: {concept}."],
            negative_fragment="dull, muted",
            description="Custom neon style",
        )
        reg.register(custom)
        assert "custom_neon" in reg.list_names()
        assert reg.get("custom_neon").name == "custom_neon"


class TestConstants:
    def test_flyer_directives_not_empty(self):
        assert isinstance(FLYER_DIRECTIVES, list)
        assert len(FLYER_DIRECTIVES) > 0

    def test_universal_negative_not_empty(self):
        assert isinstance(UNIVERSAL_NEGATIVE, str)
        assert len(UNIVERSAL_NEGATIVE) > 0

    def test_comfy_workflow_template_latent_dims(self):
        dims = COMFY_WORKFLOW_TEMPLATE["latent_dimensions"]
        assert dims["width"] == 832
        assert dims["height"] == 1472
