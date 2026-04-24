"""Flyer Generator - AI-powered event flyer generation."""

__version__ = "0.1.0"

from flyer_generator.config import Settings
from flyer_generator.errors import (
    ComfyJobTimeoutError,
    FlyerGeneratorError,
    MaxAttemptsExceededError,
    VisionResponseParseError,
)
from flyer_generator.models import EventInput, FlyerInput, FlyerOutput
from flyer_generator.pipeline import FlyerGenerator
from flyer_generator.presets import PresetRegistry, StylePreset


async def generate_flyer(
    event: FlyerInput,
    settings: Settings | None = None,
    presets: PresetRegistry | None = None,
) -> FlyerOutput:
    """Construct a FlyerGenerator with defaults and run once.

    Convenience function for one-shot usage. Users who need custom
    HTTP clients or repeated generation should instantiate
    FlyerGenerator directly.
    """
    if settings is None:
        settings = Settings()
    generator = FlyerGenerator(settings, presets=presets)
    return await generator.generate(event)


__all__ = [
    "generate_flyer",
    "FlyerGenerator",
    "FlyerInput",
    "EventInput",  # deprecated alias for FlyerInput
    "FlyerOutput",
    "Settings",
    "PresetRegistry",
    "StylePreset",
    "FlyerGeneratorError",
    "MaxAttemptsExceededError",
    "VisionResponseParseError",
    "ComfyJobTimeoutError",
]
