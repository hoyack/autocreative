"""Generative (LLM-driven) brochure pipeline stages — see docs/brochure-v2-plan.md."""

from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    BrochurePrompt,
    SectionSpec,
    SectionText,
)
from flyer_generator.brochure.generative.outline import generate_outline
from flyer_generator.brochure.generative.text import generate_section_texts

__all__ = [
    "BrochureOutline",
    "BrochurePrompt",
    "SectionSpec",
    "SectionText",
    "generate_outline",
    "generate_section_texts",
]
