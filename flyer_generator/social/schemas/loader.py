"""Post template JSON loader.

Companion to ``schema_model.PostTemplate``. Templates ship alongside this
module under ``flyer_generator/social/schemas/*.json`` — the loader discovers
them via ``Path(__file__).parent`` (deviation from the brochure loader, which
reaches up a directory for its ``schemas/`` sibling).

The ``parse_template_name`` helper is the one choke-point the CLI and Plan 07
generator use to turn a ``<platform>__<intent>`` name into typed
``Platform`` / ``Intent`` values. It raises typed errors from
``flyer_generator.errors`` so callers can distinguish an unknown platform from
an unknown intent.
"""

from __future__ import annotations

import json
from pathlib import Path

from flyer_generator.errors import IntentUnsupportedError, PlatformUnsupportedError
from flyer_generator.social.models import Intent, Platform
from flyer_generator.social.schemas.schema_model import PostTemplate

_SCHEMAS_DIR = Path(__file__).parent
_KNOWN_PLATFORMS: set[str] = {"linkedin", "twitter", "instagram", "facebook"}
_KNOWN_INTENTS: set[str] = {"announcement", "value-prop", "testimonial"}


def load_post_template(name_or_path: str) -> PostTemplate:
    """Load a ``PostTemplate`` by template name (e.g. ``linkedin__value-prop``)
    or explicit filesystem path ending in ``.json``.

    Raises:
        FileNotFoundError: No matching template exists. The error message
            includes the sorted list of available template names.
        pydantic.ValidationError: JSON failed PostTemplate validation.
    """

    if name_or_path.endswith(".json"):
        path = Path(name_or_path)
    else:
        path = _SCHEMAS_DIR / f"{name_or_path}.json"
    if not path.exists():
        available = list_post_templates()
        raise FileNotFoundError(
            f"Post template not found: {path}. Available: {available}"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    return PostTemplate.model_validate(raw)


def list_post_templates() -> list[str]:
    """All built-in post templates, sorted alphabetically."""

    if not _SCHEMAS_DIR.exists():
        return []
    return sorted(p.stem for p in _SCHEMAS_DIR.glob("*.json"))


def parse_template_name(name: str) -> tuple[Platform, Intent]:
    """Split a ``<platform>__<intent>`` template name into typed parts.

    Raises:
        ValueError: ``name`` lacks the ``__`` separator.
        PlatformUnsupportedError: platform component is not a known Platform.
        IntentUnsupportedError: intent component is not a known Intent.
    """

    if "__" not in name:
        raise ValueError(
            f"template name {name!r} must be '<platform>__<intent>'"
        )
    platform_part, intent_part = name.split("__", 1)
    if platform_part not in _KNOWN_PLATFORMS:
        raise PlatformUnsupportedError(
            f"unknown platform {platform_part!r} in template name {name!r}"
        )
    if intent_part not in _KNOWN_INTENTS:
        raise IntentUnsupportedError(
            f"unknown intent {intent_part!r} in template name {name!r}"
        )
    # Narrow to Platform/Intent Literal types.
    return platform_part, intent_part  # type: ignore[return-value]
