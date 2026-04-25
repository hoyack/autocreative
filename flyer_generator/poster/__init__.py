"""Poster rendering subsystem.

Posters are larger-canvas flyer variants with explicit print-size presets
(18×24, 24×36, 27×40 portrait). The pipeline reuses ``FlyerGenerator`` with
injected canvas dimensions; this package provides only the poster-specific
template registry.

Public API:
    from flyer_generator.poster.schema_renderer import (
        load_template,
        list_templates,
        PosterTemplateSchema,
    )
"""
