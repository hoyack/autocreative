"""Post template schemas and loader (Phase 19 Plan 05).

The package re-exports the canonical loader entry points so that callers can
write::

    from flyer_generator.social.schemas import load_post_template

Template schema classes live in :mod:`schema_model`; the filesystem loader and
name-parsing helpers live in :mod:`loader`. Deep imports remain valid.
"""

from flyer_generator.social.schemas.loader import (
    list_post_templates,
    load_post_template,
    parse_template_name,
)

__all__ = ["list_post_templates", "load_post_template", "parse_template_name"]
