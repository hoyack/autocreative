"""Poster template schema loader — reads JSON, validates via Pydantic."""

from __future__ import annotations

import json
from pathlib import Path

from flyer_generator.poster.schema_renderer.schema_model import PosterTemplateSchema

_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


def load_template(name_or_path: str) -> PosterTemplateSchema:
    """Load a poster template schema by name (looks under schemas/) or file path.

    Raises:
        FileNotFoundError: No matching file found.
        pydantic.ValidationError: JSON doesn't match PosterTemplateSchema.
    """
    if name_or_path.endswith(".json"):
        path = Path(name_or_path)
    else:
        path = _SCHEMAS_DIR / f"{name_or_path}.json"

    if not path.exists():
        available = list_templates()
        raise FileNotFoundError(
            f"Schema template not found: {path}. Available: {available}"
        )

    raw = json.loads(path.read_text(encoding="utf-8"))
    return PosterTemplateSchema.model_validate(raw)


def list_templates() -> list[str]:
    """All built-in schema templates (alphabetical)."""
    if not _SCHEMAS_DIR.exists():
        return []
    return sorted(p.stem for p in _SCHEMAS_DIR.glob("*.json"))
