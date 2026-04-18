"""Generative (LLM-driven) brochure pipeline stages — see docs/brochure-v2-plan.md."""

from flyer_generator.brochure.generative.fit import (
    estimate_body_capacity,
    needs_rewrite,
    optimize_fit,
)
from flyer_generator.brochure.generative.layout import choose_layout
from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    BrochurePrompt,
    LayoutChoice,
    SectionSpec,
    SectionText,
    VerificationVerdict,
)
from flyer_generator.brochure.generative.outline import generate_outline
from flyer_generator.brochure.generative.text import generate_section_texts

__all__ = [
    "BrochureOutline",
    "BrochurePrompt",
    "LayoutChoice",
    "SectionSpec",
    "SectionText",
    "VerificationVerdict",
    "choose_layout",
    "estimate_body_capacity",
    "generate_outline",
    "generate_section_texts",
    "needs_rewrite",
    "optimize_fit",
]
