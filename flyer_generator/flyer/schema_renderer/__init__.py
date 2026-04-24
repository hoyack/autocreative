"""Schema-driven flyer rendering subsystem.

Renders 1080x1920 event/info flyers from a JSON template + FlyerInput content.

Public API:
    from flyer_generator.flyer.schema_renderer import (
        load_template,
        list_templates,
        FlyerTemplateSchema,
    )
"""

from __future__ import annotations

from flyer_generator.flyer.schema_renderer.loader import (
    list_templates,
    load_template,
)
from flyer_generator.flyer.schema_renderer.schema_model import FlyerTemplateSchema

__all__ = [
    "FlyerTemplateSchema",
    "list_templates",
    "load_template",
]
