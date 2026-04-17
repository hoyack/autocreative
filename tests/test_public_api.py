"""Tests for the public API surface of flyer_generator."""

import asyncio

import flyer_generator


def test_all_exports_importable():
    """Every symbol in __all__ is importable and not None."""
    for name in flyer_generator.__all__:
        obj = getattr(flyer_generator, name)
        assert obj is not None, f"{name} is None"


def test_generate_flyer_is_async():
    """generate_flyer() must be an async coroutine function."""
    from flyer_generator import generate_flyer

    assert asyncio.iscoroutinefunction(generate_flyer)


def test_flyer_generator_importable():
    """FlyerGenerator class is importable and callable (constructable)."""
    from flyer_generator import FlyerGenerator

    assert callable(FlyerGenerator)


def test_custom_preset_registration():
    """Custom presets can be registered and retrieved via PresetRegistry."""
    from flyer_generator import PresetRegistry, StylePreset

    registry = PresetRegistry()
    custom = StylePreset(
        name="custom_neon",
        positive_fragments=["Neon lights: {concept}.", "Cyberpunk vibes."],
        negative_fragment="daylight, natural, soft",
        description="Custom neon style",
    )
    registry.register(custom)
    assert "custom_neon" in registry.list_names()
    retrieved = registry.get("custom_neon")
    assert retrieved.name == "custom_neon"
    assert "{concept}" in retrieved.positive_fragments[0]


def test_version_exists():
    """Package exposes __version__ string."""
    from flyer_generator import __version__

    assert __version__ == "0.1.0"
