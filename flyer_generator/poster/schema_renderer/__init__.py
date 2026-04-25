"""Schema-driven poster template registry.

Loads JSON templates under ``flyer_generator/poster/schemas/`` and exposes
them as validated Pydantic v2 :class:`PosterTemplateSchema` instances.

Public API:
    from flyer_generator.poster.schema_renderer import (
        load_template,
        list_templates,
        PosterTemplateSchema,
    )
"""

from __future__ import annotations

from flyer_generator.poster.schema_renderer.loader import (
    list_templates,
    load_template,
)
from flyer_generator.poster.schema_renderer.schema_model import PosterTemplateSchema

__all__ = [
    "PosterTemplateSchema",
    "list_templates",
    "load_template",
]
