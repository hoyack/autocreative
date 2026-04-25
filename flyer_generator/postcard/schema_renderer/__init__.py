"""Schema-driven postcard rendering subsystem.

Renders 2-sided postcards (front + back panels) from a JSON template +
PostcardContent payload.

Public API:
    from flyer_generator.postcard.schema_renderer import (
        load_template,
        list_templates,
        PostcardTemplateSchema,
        PostcardContent,
        PostcardAddressBlock,
        render_postcard,
    )
"""

from __future__ import annotations

from flyer_generator.postcard.schema_renderer.content_model import (
    PostcardAddressBlock,
    PostcardContent,
)
from flyer_generator.postcard.schema_renderer.loader import (
    list_templates,
    load_template,
)
from flyer_generator.postcard.schema_renderer.renderer import render_postcard
from flyer_generator.postcard.schema_renderer.schema_model import (
    PostcardTemplateSchema,
)

__all__ = [
    "PostcardAddressBlock",
    "PostcardContent",
    "PostcardTemplateSchema",
    "list_templates",
    "load_template",
    "render_postcard",
]
