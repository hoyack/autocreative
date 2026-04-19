"""Schema-driven brochure rendering subsystem.

Renders tri-fold brochures from a pair of JSON documents:
  1. A *template schema* (flyer_generator/brochure/schemas/*.json) — declares
     panel layouts with shape primitives, text regions with char budgets,
     logo/image placeholders, and gradients.
  2. A *content* document (BrochureContent) — carries title/org/sections/
     bullets/contact/cta data keyed by role.

Design-first: no LLM or image-generation calls required. Phase 1 produces
visually complete brochures purely from data → SVG.

Public API:
    from flyer_generator.brochure.schema_renderer import (
        load_template,
        list_templates,
        render_schema_brochure,
        BrochureContent,
        TemplateSchema,
    )
"""

from __future__ import annotations

from flyer_generator.brochure.schema_renderer.content_model import (
    BrochureContent,
    ContentSection,
)
from flyer_generator.brochure.schema_renderer.image_gate import (
    collect_image_slots,
    generate_template_images,
    resolve_concept_for_slot,
)
from flyer_generator.brochure.schema_renderer.loader import (
    list_templates,
    load_template,
)
from flyer_generator.brochure.schema_renderer.renderer import render_schema_brochure
from flyer_generator.brochure.schema_renderer.schema_model import TemplateSchema
from flyer_generator.brochure.schema_renderer.text_gen import (
    TextBudget,
    collect_text_budgets,
    generate_content_from_prompt,
)

__all__ = [
    "BrochureContent",
    "ContentSection",
    "TemplateSchema",
    "TextBudget",
    "collect_image_slots",
    "collect_text_budgets",
    "generate_content_from_prompt",
    "generate_template_images",
    "list_templates",
    "load_template",
    "render_schema_brochure",
    "resolve_concept_for_slot",
]
