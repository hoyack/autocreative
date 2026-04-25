"""Schema-driven postcard rendering subsystem.

Renders 2-sided postcards (front + back panels) from a JSON template +
PostcardCreateRequest content.

Public API:
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        list_templates,
        PostcardTemplateSchema,
    )
"""

from __future__ import annotations

from flyer_generator.postcard.schema_renderer.loader import (
    list_templates,
    load_template,
)
from flyer_generator.postcard.schema_renderer.schema_model import (
    PostcardTemplateSchema,
)

__all__ = [
    "PostcardTemplateSchema",
    "list_templates",
    "load_template",
]
