"""Phase 20 API-layer settings. Extends the existing ``Settings`` so every
existing ``FLYER_*`` knob remains accessible via ``AppSettings()`` without
reimplementing a parallel config system."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import NoDecode, SettingsConfigDict

from flyer_generator.config import Settings


class AppSettings(Settings):
    """FastAPI + SQLAlchemy + arq settings.

    Inherits every existing ``FLYER_*`` field from :class:`Settings`
    (``anthropic_api_key``, ``comfycloud_api_key``, ``brand_kits_dir``,
    ``social_campaigns_dir``, ``output_dir``, retry knobs, model names, ...).

    Adds five Phase 20 fields:

    * ``database_url`` — SQLAlchemy async DSN (default: local SQLite).
    * ``redis_url`` — arq broker (default: ``redis://localhost:6379``).
    * ``cors_origins`` — FastAPI CORS allow-list. Accepts comma-separated env
      string (e.g. ``FLYER_CORS_ORIGINS="http://a,http://b"``).
    * ``artifact_root_flyer`` — where the flyer worker writes PNG output.
    * ``artifact_root_brochure`` — where the brochure worker writes PNG+PDF.

    The existing ``brand_kits_dir`` and ``social_campaigns_dir`` fields are
    reused as artifact roots for their respective subsystems — no new field.
    """

    model_config = SettingsConfigDict(
        env_prefix="FLYER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./flyer.db"
    redis_url: str = "redis://localhost:6379"
    # ``NoDecode`` tells pydantic-settings to NOT JSON-decode the raw env
    # value; the ``_split_cors_origins_csv`` validator below then handles
    # both bare CSV (``"http://a,http://b"``) and JSON (``'["http://a"]'``)
    # inputs uniformly.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    artifact_root_flyer: Path = Path("./output/flyers")
    artifact_root_brochure: Path = Path("./output/brochures")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins_csv(cls, v: object) -> object:
        """Accept a bare comma-separated env string for ``FLYER_CORS_ORIGINS``.

        The field is annotated with :class:`pydantic_settings.NoDecode`, which
        tells pydantic-settings NOT to JSON-decode the raw env value. This
        validator then handles both formats uniformly:

        * Bare CSV: ``"http://a,http://b"`` → ``["http://a", "http://b"]``
        * JSON array: ``'["http://a", "http://b"]'`` → ``["http://a", "http://b"]``

        The CSV idiom matches the one documented in the class docstring and
        in Phase 20 CONTEXT.md (FastAPI CORS allow-list).
        """
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return v
