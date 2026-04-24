# Phase 22: Flyer Templates & Subtype Split — Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** 19 (9 new, 10 modified)
**Analogs found:** 19 / 19 — every Phase-22 file has a direct brochure-side or Phase-21 analog
**Analog scope:** `flyer_generator/brochure/`, `flyer_generator/api/`, `flyer_generator/stages/`, `tests/brochure/`, `tests/api/`, `frontend/src/pages/{brochures,flyers}/`, `alembic/versions/`

The guiding principle (locked in 22-CONTEXT `<decisions>` + plan cross-cutting section): **mirror the brochure JSON-schema pattern verbatim** wherever applicable. Almost every new file is a copy-and-adapt of a brochure-side peer. Places that diverge (single-canvas flyer panel list, optional event fields, subtype branching in vision, kind migration) are called out explicitly in the per-file excerpts.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `flyer_generator/flyer/schemas/*.json` (6 files) | template-data (JSON) | static-asset | `flyer_generator/brochure/schemas/editorial_classic.json` | **role-match** (single-panel vs. 6-panel; drop bleed canvas) |
| `flyer_generator/flyer/schema_renderer/__init__.py` | package barrel | import/export | `flyer_generator/brochure/schema_renderer/__init__.py` | exact |
| `flyer_generator/flyer/schema_renderer/schema_model.py` | Pydantic template schema | validation | `flyer_generator/brochure/schema_renderer/schema_model.py` | **role-match** (different panel set, different TextRole literals, same primitives: Fill/Stroke/Shape/Text/ImagePlaceholder) |
| `flyer_generator/flyer/schema_renderer/loader.py` | loader utility | file-I/O + validation | `flyer_generator/brochure/schema_renderer/loader.py` | **exact** (copy verbatim; only import path changes) |
| `flyer_generator/flyer/schema_renderer/content_resolver.py` | resolve_key resolver | data-transform | `flyer_generator/brochure/schema_renderer/content_model.py::BrochureContent.resolve_key` | **role-match** (event/info keys replace sections/back_panel keys) |
| `flyer_generator/models.py::EventInput` → `FlyerInput` | request model | validation | current `EventInput` (self) + brochure `BrochureInput` pattern for optional fields | **exact** (same-file evolution) |
| `flyer_generator/api/schemas/flyers.py::FlyerCreateRequest` | HTTP request schema | validation | `flyer_generator/api/schemas/brochures.py::BrochureCreateRequest` (has `template: str`) | **exact** |
| `flyer_generator/api/tasks/flyer.py::task_generate_flyer` | arq worker task | async request-response | `flyer_generator/api/tasks/brochure.py::task_generate_brochure` (late-bind template) | **exact** |
| `flyer_generator/pipeline.py::FlyerGenerator.generate` | pipeline orchestrator | async pipeline | current `FlyerGenerator.generate` (self; add template arg) | **exact** (same-file evolution) |
| `flyer_generator/stages/composer.py::PosterComposer.compose` | SVG composer | data-transform | current `PosterComposer.compose` (self; parameterize hardcoded typography + scrim + accent) | **role-match** (hardcoded → template-driven) |
| `flyer_generator/stages/vision.py::VisionEvaluator` | vision LLM wrapper | async request-response | current `VisionEvaluator.__init__` + `VISION_SYSTEM_PROMPT` (self; branch on subtype) | **exact** (same-file evolution) |
| `flyer_generator/api/models/flyer.py::FlyerRecord` | SQLAlchemy model | DB-CRUD | `flyer_generator/api/models/brochure.py::BrochureRecord` (has `template` column) | **exact** |
| `flyer_generator/api/models/render.py::RenderKind` | enum/string list | DB constant | `flyer_generator/api/models/render.py::RenderRecord.kind` (comment enumerates kinds) | **exact** (same-file evolution) |
| `alembic/versions/NNNN_flyer_template_and_subtype_split.py` | migration | DDL + data-rewrite | `alembic/versions/0001_initial_schema.py` (single migration in repo — copy structure) | **role-match** (add column + UPDATE WHERE kind='flyer_final') |
| `frontend/src/pages/flyers/new.tsx` | React form | request-response | `frontend/src/pages/brochures/new.tsx` (has `template` field + `<Input>`) + current `flyers/new.tsx` (self) | **exact** (graft brochure template pattern onto flyer form + add subtype conditional) |
| `frontend/src/pages/renders/gallery.tsx::KINDS` | FE filter list | static constant | `frontend/src/pages/renders/gallery.tsx::KINDS` (self; extend) | **exact** (same-file evolution) |
| `frontend/src/pages/jobs/list.tsx::KINDS` | FE filter list | static constant | `frontend/src/pages/jobs/list.tsx::KINDS` (self; no change — FLYER stays) | **exact** (no-op likely; row-level routing stays) |
| `frontend/src/api/openapi.snapshot.json` + `schema.gen.ts` | FE generated types | codegen | existing snapshot (self; regenerate) | **exact** (mechanical regen) |
| `tests/flyer/schema_renderer/test_loader.py` | loader test | file-I/O | `tests/brochure/schema_renderer/test_loader.py` | **exact** |
| `tests/flyer/schema_renderer/test_schema_model.py` | Pydantic validation test | validation | `tests/brochure/schema_renderer/test_schema_model.py` | **exact** |
| `tests/flyer/schema_renderer/test_render_smoke.py` | rendering smoke test | data-transform | `tests/brochure/schema_renderer/test_renderer.py` | **role-match** (flyer uses PosterComposer, not render_schema_brochure; assertions on SVG well-formedness + content keys) |

---

## Pattern Assignments

### `flyer_generator/flyer/schemas/*.json` — 6 template files (template-data / static-asset)

**Analog:** `flyer_generator/brochure/schemas/editorial_classic.json`

**Top-level shape to mirror** (lines 1-25):

```json
{
  "schema_version": "1",
  "name": "editorial_classic",
  "description": "Serif typography, thin accent rules, one hero image placeholder, dense but disciplined content blocks. Good for law firms, financial advisors, consultancies.",
  "tone_keywords": ["professional", "authoritative", "corporate", "editorial"],
  "canvas": { "width": 1100, "height": 2550 },
  "palette": {
    "accent_default": "#1E3A5F",
    "neutral_dark": "#1A1A1A",
    "neutral_light": "#FAFAF7",
    "muted": "#E8E6E1"
  },
  "typography": {
    "heading_family": "'Playfair Display', 'Times New Roman', serif",
    "body_family": "'Source Serif Pro', Georgia, serif",
    "cover_title_size": 120,
    "cover_subtitle_size": 42,
    "heading_size": 60,
    "body_size": 34,
    "body_line_height": 44,
    "body_max_chars_per_line": 32,
    "bullet_size": 34,
    "bullet_line_height": 44
  },
  "panels": { ... }
}
```

**Element shape to mirror** (lines 30-38 — text + shape + image_placeholder all coexist in one panel):

```json
{ "type": "shape", "kind": "rect", "rect": [0, 0, 1100, 8], "fill": { "type": "solid", "color": "#1E3A5F" }, "bleed": "top", "z": 0 },
{ "type": "image_placeholder", "bbox": [0, 120, 1100, 1420], "slot": "hero", "corner_radius": 0, "show_placeholder_label": true, "z": 3 },
{ "type": "text", "bbox": [80, 1580, 940, 60], "role": "static", "static_text": "ESTATE PLANNING", "font_size": 26, "letter_spacing": 6, "weight": "semibold", "color": "#1E3A5F", "uppercase": true, "z": 10 },
{ "type": "text", "bbox": [80, 1650, 940, 540], "role": "cover_title", "content_key": "title", "color": "#1A1A1A", "valign": "top", "z": 10 },
{ "type": "text", "bbox": [80, 2200, 940, 90], "role": "cover_subtitle", "content_key": "subtitle", "color": "#4A4A4A", "font_size": 36, "italic": true, "z": 10 }
```

**Flyer-specific adaptations** (Claude's Discretion per 22-CONTEXT lines 83-88):
- `canvas`: `{ "width": 1080, "height": 1920 }` (not 1100×2550; no bleed for on-screen PNGs)
- `panels`: single-entry map `{ "hero": { ... } }` — NOT the 6-panel brochure set. Schema validator (below) must not require the brochure 6-panel set.
- `content_key` strings: `"event.title"`, `"event.date"`, `"event.time"`, `"event.location_name"`, `"event.location_address"`, `"event.fees"`, `"event.description"`, `"event.call_to_action"`, `"org"`, `"tagline"`, `"url"` (flat namespace mirroring FlyerInput fields; no sections array).
- Omit `cta_heading`, `cta_body`, brochure-only text roles. Keep `cover_title`, `cover_subtitle`, `body`, `tagline`, `org_name`, `contact_*`, `static`.
- Six shipped templates (CONTEXT line 41): `editorial_classic`, `bold_modern`, `minimal_photo`, `retro_poster`, `zine`, `tight_typographic`. Each declares typography scale + scrim opacity + accent placement + shape mix (CONTEXT line 42) — NOT just color overrides.
- Event vs info zones: event templates reference `event.date`/`event.time`/`event.location_*`/`event.fees`; info templates reference `event.description`/`event.call_to_action`. Content resolver (below) returns `None` for missing keys — templates MAY include event-only keys safely if the renderer skips None-resolving text elements (mirror brochure behavior at `BrochureContent.resolve_key` line 279 returning `None`).

---

### `flyer_generator/flyer/schema_renderer/__init__.py` (package barrel)

**Analog:** `flyer_generator/brochure/schema_renderer/__init__.py`

**Pattern to mirror** (lines 22-48, trimmed — drop brochure-only exports):

```python
"""Schema-driven flyer rendering subsystem.

Renders 1080×1920 event/info flyers from a JSON template + FlyerInput content.

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
```

**Do NOT re-export** brochure-only helpers (BackPanelContent, BrochureBrief, collect_image_slots, generate_template_images, text_gen, image_gate). Flyer uses the existing Comfy pipeline for hero art, not the brochure image_gate.

---

### `flyer_generator/flyer/schema_renderer/schema_model.py` (Pydantic template schema)

**Analog:** `flyer_generator/brochure/schema_renderer/schema_model.py`

**Imports + primitives to copy verbatim** (lines 11-17 + the Fill/Stroke/GradientStop/ShapeElement primitives at lines 66-203):

```python
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.models import validate_hex_color
```

Re-use (import, don't duplicate) `validate_hex_color` from `flyer_generator/brochure/models.py:34` — shared utility, not brochure-specific. If desired, move `validate_hex_color` to a shared location, but that is OUT of scope for this phase (keep cross-package import).

**Pattern to mirror for the top-level schema** (brochure lines 355-387 → flyer-adapted):

```python
class FlyerTemplateSchema(BaseModel):
    """The top-level flyer template schema. Loaded from JSON under schemas/."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str
    tone_keywords: list[str] = Field(default_factory=list)
    subtype_compat: list[Literal["event", "info"]] = Field(
        default_factory=lambda: ["event", "info"],
        description="Which flyer subtypes this template supports.",
    )
    canvas: Canvas
    palette: Palette
    typography: Typography = Field(default_factory=Typography)
    panels: dict[_PanelName, PanelSchema]

    @field_validator("panels")
    @classmethod
    def _validate_panels_complete(
        cls, v: dict[str, PanelSchema]
    ) -> dict[str, PanelSchema]:
        required = {"hero"}  # flyer = single-canvas (DIVERGENCE)
        missing = required - set(v.keys())
        if missing:
            msg = f"template missing panels: {sorted(missing)}"
            raise ValueError(msg)
        return v
```

**Key divergences from brochure schema_model**:

1. `_PanelName = Literal["hero"]` (flyer is single-canvas). Brochure line 19-26 declares 6 panel names.
2. `Canvas` default `(1080, 1920)` (flyer aspect). Brochure supports any canvas.
3. `_TextRole` literal may omit brochure-only roles (`cta_heading`, `cta_body`, `quote`). Retain flyer-relevant roles (`cover_title`, `cover_subtitle`, `body`, `tagline`, `org_name`, `contact_*`, `static`).
4. Add `subtype_compat` list as shown above so the loader can refuse an info flyer through an event-only template (and vice-versa). Default lists both to preserve back-compat.

**Primitives to COPY verbatim (no changes needed)** from brochure `schema_model.py`:
- `GradientStop` (lines 66-79), `SolidFill` (81-91), `LinearGradientFill` (94-102), `RadialGradientFill` (105-111), `TextureSlotFill` (114-121), `Fill = Annotated[...]` (124-127)
- `Stroke` (130-141), `ShapeElement` (144-167), `TextElement` (170-202), `BulletsElement` (205-230)
- `LogoPlaceholder` (233-251), `ImagePlaceholder` (254-267), `DividerElement` (270-287)
- `PanelElement = Annotated[Union[...], Field(discriminator="type")]` (290-300), `PanelSchema` (303-308), `Palette` (318-337), `Typography` (340-351)

These are strictly structural and carry no brochure-specific semantics — the flyer will use the same XY coordinates, the same fills, the same text element wiring. Save code by directly importing them from the brochure module OR copying into the flyer module (prefer copy: the dependency line from `flyer.schema_renderer` → `brochure.schema_renderer` is an anti-pattern we should avoid; a small duplication is the lesser evil).

---

### `flyer_generator/flyer/schema_renderer/loader.py` (loader utility)

**Analog:** `flyer_generator/brochure/schema_renderer/loader.py`

**Pattern to mirror — COPY VERBATIM; change only the two imports** (entire file, 40 lines):

```python
"""Template schema loader — reads JSON, validates via Pydantic."""

from __future__ import annotations

import json
from pathlib import Path

from flyer_generator.flyer.schema_renderer.schema_model import FlyerTemplateSchema

_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


def load_template(name_or_path: str) -> FlyerTemplateSchema:
    """Load a flyer template schema by name (looks under schemas/) or file path.

    Raises:
        FileNotFoundError: No matching file found.
        pydantic.ValidationError: JSON doesn't match FlyerTemplateSchema.
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
    return FlyerTemplateSchema.model_validate(raw)


def list_templates() -> list[str]:
    """All built-in schema templates (alphabetical)."""
    if not _SCHEMAS_DIR.exists():
        return []
    return sorted(p.stem for p in _SCHEMAS_DIR.glob("*.json"))
```

**Only changes vs. brochure loader**:
- Import `FlyerTemplateSchema` instead of `TemplateSchema`.
- `_SCHEMAS_DIR` resolves via `Path(__file__).parent.parent / "schemas"` — works identically because the package layout mirrors brochure (schemas/ is a sibling of schema_renderer/ inside the `flyer/` package).
- Return type annotation: `-> FlyerTemplateSchema`.

---

### `flyer_generator/flyer/schema_renderer/content_resolver.py` (resolve_key resolver)

**Analog:** `flyer_generator/brochure/schema_renderer/content_model.py::BrochureContent.resolve_key` (lines 224-279)

**Pattern to mirror** (brochure lines 224-279; flyer-adapted to the flat `FlyerInput` namespace):

```python
"""Content-key resolver for flyer templates.

Templates reference fields via strings like "event.title", "event.description",
"org", "contact.phone". This module resolves those strings against a
FlyerInput instance. Returns None for keys that don't apply to the current
subtype (e.g. "event.date" on an info flyer) — templates MUST handle None
by skipping the element (mirrors BrochureContent.resolve_key behavior for
missing sections / extras).
"""

from __future__ import annotations

from typing import Any

from flyer_generator.models import FlyerInput


def resolve_key(flyer: FlyerInput, key: str) -> Any:
    """Resolve a `content_key` expression against a FlyerInput.

    Supported forms:
      - 'event.title', 'event.date', 'event.time', 'event.location_name',
        'event.location_address', 'event.fees', 'event.description',
        'event.call_to_action'
      - 'org', 'tagline', 'url', 'style_concept'
      - 'color_accent'

    Returns None when the key doesn't apply (e.g. 'event.date' on info subtype).
    """
    if key.startswith("event."):
        field = key.split(".", 1)[1]
        # All event fields are optional on FlyerInput; getattr returns None cleanly
        return getattr(flyer, field, None)

    if key in ("org", "title", "tagline", "url", "style_concept", "color_accent"):
        return getattr(flyer, key, None)

    return None
```

**Key divergences from `BrochureContent.resolve_key`**:
- No `sections[i].heading` or `back_panel.body` or `extras.foo` — flat namespace.
- No `contact.*` (flyer has no `ContactBlock` — brand kit's contact info is applied at composer-time, not via content_key).
- No `section.X` shorthand — single-panel means no indexed sections.
- The brochure version uses `BrochureContent` as `self`; this version takes `flyer: FlyerInput` explicitly (no class needed — flyer content is already the input model itself).

**Decision hint for planner:** if the complexity is too low to merit a whole module, inline `resolve_key` onto `FlyerInput.resolve_key(self, key)` as a method (mirrors `BrochureContent.resolve_key` exactly). CONTEXT line 5 of the file list allows "or extend an existing module."

---

### `flyer_generator/models.py::EventInput` → `FlyerInput` (request model)

**Analog:** self (current `EventInput` in `flyer_generator/models.py` lines 27-48) + the pattern "optional fields with sensible defaults" from `flyer_generator/brochure/schema_renderer/content_model.py::BrochureContent` (lines 114-137)

**Current state** (models.py lines 27-48):

```python
class EventInput(BaseModel):
    """Structured event data — the pipeline's primary input."""

    title: str = Field(max_length=120)
    date: str = Field(max_length=120)
    time: str = Field(max_length=120)
    location_name: str = Field(max_length=120)
    location_address: str = Field(max_length=120)
    fees: str = Field(max_length=120)
    org: str = Field(max_length=120)
    url: str | None = None
    style_concept: str = Field(max_length=120)
    style_preset: str = Field(max_length=120)
    color_accent: str = "#F59E0B"

    @field_validator("color_accent")
    @classmethod
    def _validate_hex_color(cls, v: str) -> str:
        if not _HEX_COLOR_RE.match(v):
            msg = f"color_accent must be a 6-digit hex color (e.g. #F59E0B), got {v!r}"
            raise ValueError(msg)
        return v
```

**Target evolution** (CONTEXT lines 46-52):

```python
class FlyerInput(BaseModel):
    """Structured flyer input — event-or-info.

    All event-specific fields are optional; `subtype` drives which are
    expected. Vision prompt, composer, and template resolver branch on
    `subtype` to avoid rendering empty event fields for info flyers.
    """

    title: str = Field(max_length=120)
    subtype: Literal["event", "info"] = "event"
    # Event-only — optional in FlyerInput; worker/vision prompt validate
    # presence when subtype == "event".
    date: str | None = Field(default=None, max_length=120)
    time: str | None = Field(default=None, max_length=120)
    location_name: str | None = Field(default=None, max_length=120)
    location_address: str | None = Field(default=None, max_length=120)
    fees: str | None = Field(default=None, max_length=120)
    # Info-only
    description: str | None = Field(default=None, max_length=600)
    call_to_action: str | None = Field(default=None, max_length=120)
    # Shared
    org: str = Field(max_length=120)
    url: str | None = None
    style_concept: str = Field(max_length=120)
    style_preset: str = Field(max_length=120)
    color_accent: str = "#F59E0B"

    @field_validator("color_accent")
    @classmethod
    def _validate_hex_color(cls, v: str) -> str:
        if not _HEX_COLOR_RE.match(v):
            msg = f"color_accent must be a 6-digit hex color (e.g. #F59E0B), got {v!r}"
            raise ValueError(msg)
        return v


# Backward-compat alias. Marked deprecated in docstring; keep at least through
# Phase 23 so external callers aren't broken mid-milestone.
EventInput = FlyerInput
```

**Also update** `flyer_generator/__init__.py` line 12 + line 37 `__all__`: add `FlyerInput` export alongside `EventInput`. Keep `EventInput` in `__all__` as the deprecated alias.

---

### `flyer_generator/api/schemas/flyers.py::FlyerCreateRequest` (HTTP request schema)

**Analog:** `flyer_generator/api/schemas/brochures.py::BrochureCreateRequest` (has the `template: str` field we need to graft on)

**Brochure pattern** (brochures.py lines 15-34):

```python
class BrochureCreateRequest(BaseModel):
    """Body of POST /api/v1/brochures."""

    model_config = ConfigDict(extra="forbid")

    content: BrochureContent
    template: str = Field(min_length=1, max_length=64)
    brand_kit_slug: str | None = Field(default=None, max_length=64)
    generate_images: bool = True
    workflow: str = "turbo_landscape"
    style_preset: str = "photorealistic"

    @field_validator("brand_kit_slug")
    @classmethod
    def _validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SLUG_RE.match(v):
            raise ValueError("brand_kit_slug must match ^[a-z0-9][a-z0-9-]*$")
        return v
```

**Apply to flyer schema** — graft `template: str` onto the existing flyers.py (lines 14-37):

```python
class FlyerCreateRequest(BaseModel):
    """Body of POST /api/v1/flyers.

    Re-uses FlyerInput verbatim (no field-by-field redefinition). Adds API-layer
    options: template slug, optional brand-kit slug, optional accent override,
    optional max background retry cap.
    """

    model_config = ConfigDict(extra="forbid")

    event: FlyerInput
    template: str = Field(min_length=1, max_length=64)   # NEW — mirror BrochureCreateRequest
    preset: str = Field(min_length=1, max_length=64)
    brand_kit_slug: str | None = Field(default=None, max_length=64)
    accent: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    max_bg_attempts: int | None = Field(default=None, ge=1, le=10)

    @field_validator("brand_kit_slug")
    @classmethod
    def _validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SLUG_RE.match(v):
            raise ValueError("brand_kit_slug must match ^[a-z0-9][a-z0-9-]*$")
        return v
```

**Note:** 22-CONTEXT line 41 locks "no enum" — validation happens at worker-time `load_template()`, not in this schema. `template: str = Field(min_length=1, max_length=64)` is intentional and mirrors brochure.

---

### `flyer_generator/api/tasks/flyer.py::task_generate_flyer` (arq worker task)

**Analog:** `flyer_generator/api/tasks/brochure.py::task_generate_brochure` (has late-binding `load_template()` exactly where we need it)

**Pattern to mirror — late-binding template + module-scope import** (brochure.py lines 22-34 + 56-66):

```python
# NOTE: The following three imports must stay at module scope so direct-
# invocation tests can patch them via ``patch("flyer_generator.api.tasks.brochure.X")``.
# ...
from flyer_generator.brochure.schema_renderer.loader import load_template
# ...

async def task_generate_brochure(ctx: dict, *, job_id: str, payload: dict) -> str | None:
    # ...
    try:
        content = BrochureContent.model_validate(payload["content"])
        template_name = payload["template"]
        slug = payload.get("brand_kit_slug")

        # Load brand kit if requested (raises BrandKitNotFoundError on miss).
        kit = None
        if slug is not None:
            kit = load_brand_kit(slug, base_dir=Path(settings.brand_kits_dir))

        template = load_template(template_name)
```

**Apply to flyer.py** — graft `template` loading + thread through to `FlyerGenerator.generate`:

```python
from flyer_generator import FlyerGenerator
from flyer_generator.api.models import FlyerRecord, RenderRecord
from flyer_generator.api.tasks._state import mark_failed, mark_running, mark_succeeded
from flyer_generator.models import FlyerInput  # renamed from EventInput

# Module-scope so tests can patch via
# patch("flyer_generator.api.tasks.flyer.load_template")
from flyer_generator.flyer.schema_renderer.loader import load_template


async def task_generate_flyer(ctx: dict, *, job_id: str, payload: dict) -> str | None:
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]
    http_client = ctx["http_client"]

    log = logger.bind(job_id=job_id, kind="flyer")
    log.info("task_start")
    await mark_running(sessionmaker, job_id)

    try:
        flyer_input = FlyerInput.model_validate(payload["event"])
        template_name = payload["template"]
        template = load_template(template_name)

        gen = FlyerGenerator(settings=settings, http_client=http_client)
        out = await gen.generate(flyer_input, template=template)   # NEW template kwarg

        artifact_path = Path(settings.artifact_root_flyer) / f"{job_id}.png"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        out.save(artifact_path)

        # Render kind now subtype-aware (CONTEXT line 75-78)
        render_kind = (
            "flyer_event_final" if flyer_input.subtype == "event" else "flyer_info_final"
        )

        async with sessionmaker() as s:
            render = RenderRecord(
                kind=render_kind,
                file_path=str(artifact_path.resolve()),
                comfy_job_id=getattr(out, "comfy_job_id", None),
                vision_verdict=(
                    out.final_vision_verdict.model_dump(mode="json")
                    if getattr(out, "final_vision_verdict", None) is not None
                    else None
                ),
            )
            s.add(render)
            await s.flush()

            flyer = FlyerRecord(
                title=flyer_input.title,
                template=template_name,   # NEW column
                preset=payload["preset"],
                brand_kit_slug=payload.get("brand_kit_slug"),
                event_payload=payload,
                render_id=render.id,
            )
            s.add(flyer)
            await s.commit()
            render_id = render.id

        await mark_succeeded(sessionmaker, job_id, result_ref=render_id)
        return render_id

    except Exception as exc:
        log.exception("task_failed")
        await mark_failed(sessionmaker, job_id, exc)
        raise
```

**Key grafts from brochure** (not in current flyer task):
1. Module-scope `load_template` import with the BLOCKER-2 comment (tests patch this path).
2. `template_name = payload["template"]` early extraction.
3. `load_template(template_name)` call that surfaces `FileNotFoundError` / `ValidationError` before any Comfy work.
4. Kind derivation from `flyer_input.subtype` (new — no brochure peer).

---

### `flyer_generator/pipeline.py::FlyerGenerator.generate` (pipeline orchestrator)

**Analog:** self — current `FlyerGenerator.generate` at `flyer_generator/pipeline.py` lines 60-149, specifically the plug-in point on line 110-113.

**Current pipeline code** (lines 108-116):

```python
                # Stage 5: Resolve zone labels to pixel coordinates
                layout = self._layout.resolve(verdict.zones)

                # Stage 6: Compose SVG
                svg = self._composer.compose(event, background, verdict, layout)

                # Stage 7: Rasterize SVG to PNG
                png_bytes = self._rasterizer.rasterize(svg)
```

**Target change** (CONTEXT lines 66-68: plug-in point at line ~111 between `resolve()` and `compose()`):

```python
    async def generate(
        self,
        event: FlyerInput,   # renamed from EventInput
        *,
        template: FlyerTemplateSchema | None = None,   # NEW keyword arg
    ) -> FlyerOutput:
        # ...
        # ... inside the approved branch ...

                # Stage 5: Resolve zone labels to pixel coordinates
                layout = self._layout.resolve(verdict.zones)

                # Stage 6: Compose SVG — now template-driven
                svg = self._composer.compose(event, background, verdict, layout, template=template)

                # Stage 7: Rasterize SVG to PNG
                png_bytes = self._rasterizer.rasterize(svg)
```

**Also**: update the vision stage construction (line 55) so it can branch on subtype. Pass `subtype` into a new `VisionEvaluator.evaluate(..., subtype=event.subtype)` call at pipeline line 100, OR construct a subtype-specific evaluator in `__init__`. See the vision section below.

**Back-compat:** `template` is keyword-only and defaults to `None`. When `None`, `PosterComposer.compose` falls back to the hardcoded behavior currently in place (see composer excerpt below). This keeps CLI / direct-API callers who omit a template working.

---

### `flyer_generator/stages/composer.py::PosterComposer.compose` (SVG composer)

**Analog:** self — current `PosterComposer.compose` at `flyer_generator/stages/composer.py` lines 159-475. The refactor is: **extract hardcoded typography/scrim/accent lookups into template-driven methods**, keeping the existing flow when no template is supplied.

**Current signature + entry** (lines 159-194):

```python
    def compose(
        self,
        event: EventInput,
        background: GeneratedBackground,
        verdict: VisionVerdict,
        layout: ResolvedLayout,
    ) -> str:
        try:
            return self._build_svg(event, background, verdict, layout)
        except CompositionError:
            raise
        except Exception as exc:
            msg = f"SVG composition failed: {exc}"
            raise CompositionError(msg) from exc
```

**Target signature + dispatch**:

```python
    def compose(
        self,
        event: FlyerInput,
        background: GeneratedBackground,
        verdict: VisionVerdict,
        layout: ResolvedLayout,
        *,
        template: FlyerTemplateSchema | None = None,
    ) -> str:
        try:
            return self._build_svg(event, background, verdict, layout, template=template)
        except CompositionError:
            raise
        except Exception as exc:
            msg = f"SVG composition failed: {exc}"
            raise CompositionError(msg) from exc
```

**Hardcoded values to parameterize — reference list**:

| Currently hardcoded | Source line(s) | Replace with |
|---|---|---|
| `_title_params` step-function font sizes (52/62/72/82 by length) | `composer.py` 29-66 | `template.typography.cover_title_size` scaled by length bucket |
| Title font family `'Arial Black', 'Helvetica Neue', Arial, sans-serif` | line 247 | `template.typography.heading_family` |
| Details font family `'Arial, sans-serif'` | lines 353-365 | `template.typography.body_family` |
| Scrim opacity (`0.75`, `0.85`, `0.6`) | `_gradient_defs` lines 134-149 | `template.palette.extras["scrim_opacity_top"]` etc., OR a new `template.scrim: ScrimConfig` sub-model |
| Layout variant (centered/editorial/sidebar/minimal) | `_select_layout_variant` lines 117-129 + the four variant branches 269-303 | `template` carries a `layout_variant: Literal[...]` field that wins over the zone-derived heuristic |
| Accent stripe `rect x="0" y="1908" width="1080" height="12"` | lines 444-448 | template-declared accent shape (kept as-is when template doesn't declare one) |

**Recommended refactor pattern** — introduce `_template_typography(template)`, `_template_scrim_opacity(template, row)`, `_template_accent_for(template, layout_variant)` as private helpers. Each returns the current hardcoded value when `template is None` (back-compat). The existing `_build_svg` method becomes:

```python
def _build_svg(self, event, background, verdict, layout, *, template=None):
    title_font_family = (
        template.typography.heading_family if template
        else "'Arial Black', 'Helvetica Neue', Arial, sans-serif"
    )
    # ... etc for every hardcoded knob
```

**Subtype handling in composer**:

When `event.subtype == "info"`: skip `fee_elements` entirely (no fee badge on info flyers per CONTEXT lines 57-60), and replace the details block with `event.description` + `event.call_to_action`. The zone `verdict.zones.fee_badge` should be `None` for info-subtype vision verdicts (see vision section below); the composer must gracefully handle that.

Existing flow for `fees_esc` (composer.py line 378 `if fees_esc:`) already no-ops on empty strings — reuse that pattern: set `fees_esc = ""` when subtype is info and omit fee rendering.

---

### `flyer_generator/stages/vision.py::VisionEvaluator` + `VISION_SYSTEM_PROMPT` (vision LLM wrapper)

**Analog:** self — current `VISION_SYSTEM_PROMPT` (vision.py lines 30-62) + `VisionEvaluator.__init__` pattern that already supports custom system_prompt (lines 75-84).

**Existing extensibility hook** (lines 75-84):

```python
    def __init__(
        self,
        settings: Settings,
        *,
        system_prompt: str | None = None,
        require_zones: bool = True,
    ) -> None:
        self._settings = settings
        self._system_prompt = system_prompt or VISION_SYSTEM_PROMPT
        self._require_zones = require_zones
```

This already exists because brochure re-uses `VisionEvaluator` with a different system prompt (see `evaluate_cover` lines 126-141 which docstring-mentions `require_zones=False` + brochure-specific `system_prompt`). We graft the same pattern: a second (info-subtype) system prompt constant and a `subtype` kwarg on `evaluate()`.

**Target change — add subtype-branching prompt** (CONTEXT lines 54-60):

```python
# Existing event prompt (rename the constant)
VISION_SYSTEM_PROMPT_EVENT = """You are a professional graphic designer evaluating ... [existing text lines 30-62]"""

# NEW — info subtype prompt (no DETAILS, no FEE_BADGE zones)
VISION_SYSTEM_PROMPT_INFO = """You are a professional graphic designer evaluating AI-generated background images for informational flyers (announcements, public notices, educational posters — no specific event date). ...

Text elements to place:
- TITLE (largest): the headline
- DESCRIPTION (multi-line body): the core message
- ORG_CREDIT (tiny): sponsor/issuer line at very bottom

Return ONLY valid JSON with zones.title, zones.description, zones.org_credit.
zones.details and zones.fee_badge MUST be omitted.
"""

# Alias for back-compat with existing imports
VISION_SYSTEM_PROMPT = VISION_SYSTEM_PROMPT_EVENT
```

**Evaluate signature change** — thread subtype:

```python
    async def evaluate(
        self,
        background: GeneratedBackground,
        event: FlyerInput,
    ) -> VisionVerdict:
        # Select prompt + user text per subtype
        if event.subtype == "info":
            system_prompt_override = VISION_SYSTEM_PROMPT_INFO
            user_text = (
                f"Headline: {event.title}\n"
                f"Description: {event.description or ''}\n"
                f"Call to action: {event.call_to_action or ''}\n"
                f"Organizer: {event.org}\n"
                f"Style: {event.style_concept}"
            )
        else:
            system_prompt_override = VISION_SYSTEM_PROMPT_EVENT
            user_text = (
                f"Event: {event.title}\n"
                f"Date: {event.date or ''}\n"
                f"Time: {event.time or ''}\n"
                f"Venue: {event.location_name or ''}\n"
                f"Address: {event.location_address or ''}\n"
                f"Fees: {event.fees or ''}\n"
                f"Organizer: {event.org}\n"
                f"Style: {event.style_concept}"
            )
        return await self._evaluate_with_text(
            background.image_bytes, user_text, system_prompt_override=system_prompt_override
        )
```

**Note:** The cleanest implementation swaps `self._system_prompt` for a per-call override in `_call_anthropic` / `_call_ollama`. Alternative: construct one `VisionEvaluator` per subtype inside `FlyerGenerator.__init__`, but that wastes httpx clients. Planner should prefer the per-call override.

**`VisionVerdict.zones` shape divergence**: info flyers produce `zones` where `details` and `fee_badge` are `None`. Current `LayoutZones` (models.py lines 71-77) declares those as required. Per CONTEXT line 61 "Both subtypes use the same VisionVerdict schema; zones map keys are subtype-specific" — either relax `LayoutZones.details`/`fee_badge` to `ZoneName | None = None` OR introduce a second `LayoutZones` variant. Relaxing to Optional is less invasive and matches how the composer will handle missing keys (already explained above).

---

### `flyer_generator/api/models/flyer.py::FlyerRecord` (SQLAlchemy model)

**Analog:** `flyer_generator/api/models/brochure.py::BrochureRecord` (has `template` column — lines 19-20 of that file)

**Brochure pattern** (brochure.py lines 14-23):

```python
class BrochureRecord(Base):
    __tablename__ = "brochures"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    template: Mapped[str] = mapped_column(String(64), nullable=False)   # ← graft
    brand_kit_slug: Mapped[str | None] = mapped_column(
        ForeignKey("brand_kits.slug", ondelete="SET NULL"), nullable=True, index=True
    )
    # BrochureContent.model_dump(mode="json") plus workflow/style_preset knobs.
    content_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
```

**Apply to FlyerRecord** — add the `template` column between `preset` and `brand_kit_slug`:

```python
class FlyerRecord(Base):
    __tablename__ = "flyers"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    template: Mapped[str] = mapped_column(String(64), nullable=False)   # NEW
    preset: Mapped[str] = mapped_column(String(64), nullable=False)
    brand_kit_slug: Mapped[str | None] = mapped_column(
        ForeignKey("brand_kits.slug", ondelete="SET NULL"), nullable=True, index=True
    )
    event_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    render_id: Mapped[str | None] = mapped_column(
        ForeignKey("renders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    render: Mapped[RenderRecord | None] = relationship("RenderRecord", lazy="joined")
```

**Migration must backfill `template`** for existing flyer rows (see migration section below). CONTEXT doesn't specify a default — pick `"editorial_classic"` as the safe default (matches the first-shipped template).

---

### `flyer_generator/api/models/render.py::RenderKind` (enum/string list)

**Analog:** self — current `RenderRecord.kind` has an inline comment enumerating kinds (render.py lines 22-24).

**Current state**:

```python
    kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    # Valid kinds: "flyer_final", "brochure_front", "brochure_back",
    # "brochure_pdf", "social_post_image", "brand_kit_logo"
```

**Target state** — update the comment + extend the set of valid strings. There is no `RenderKind` enum class today (`render.py` uses a string column); CONTEXT + plan line 92 reference "RenderKind enum" conceptually but the actual code uses a string constant list in the comment + frontend `KINDS` tuple. Planner has TWO options:

**Option A (minimal):** just extend the comment, rely on string values:

```python
    # Valid kinds: "flyer_event_final", "flyer_info_final", "brochure_front",
    # "brochure_back", "brochure_pdf", "social_post_image", "brand_kit_logo"
    # Deprecated (migrated): "flyer_final" — rewritten to flyer_event_final or
    # flyer_info_final by alembic migration NNNN.
```

**Option B (introduce enum):** add `RenderKind(str, enum.Enum)` alongside `JobKind`. Cleaner but broader blast radius (requires changes in every task.py that sets `kind=...`). **Option A is recommended** — matches current code shape and is what 22-CONTEXT line 114 expects.

**Also update** the writer: every call site of `RenderRecord(kind="flyer_final", ...)` — the only one is `flyer_generator/api/tasks/flyer.py` line 49 — must be updated to use the subtype-derived kind (see task.py excerpt above: `render_kind = "flyer_event_final" if subtype == "event" else "flyer_info_final"`).

---

### `alembic/versions/NNNN_flyer_template_and_subtype_split.py` (migration)

**Analog:** `alembic/versions/0001_initial_schema.py` (the only existing migration — shows `batch_alter_table` + `op.create_index` conventions)

**Pattern to mirror from existing migration** (0001_initial_schema.py lines 7-18 for header + 100-114 for the `flyers` table CREATE):

```python
"""flyer template and subtype split

Revision ID: <auto-assigned>
Revises: 2f5971e114b3
Create Date: 2026-04-24 ...

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '<auto-assigned>'
down_revision: Union[str, Sequence[str], None] = '2f5971e114b3'   # initial schema
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**Upgrade body — two operations per CONTEXT lines 74-78**:

```python
def upgrade() -> None:
    # 1. Add template column to flyers, default 'editorial_classic' for backfill
    with op.batch_alter_table('flyers', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('template', sa.String(length=64), nullable=False,
                      server_default='editorial_classic')
        )

    # 2. Rewrite render.kind for flyer rows, subtype-derived.
    # Idempotent (CONTEXT line 155): only touches rows where kind='flyer_final'.
    # Subtype lookup is via the FlyerRecord.event_payload JSON — defaults to 'event'
    # when the payload doesn't carry a subtype (pre-Phase-22 rows).
    #
    # Uses raw SQL with a subquery joining flyers.render_id to renders.id.
    # The JSON path syntax differs by backend; the query below targets SQLite
    # (json_extract) — the repo's default. For Postgres adapt to (event_payload->>'subtype').
    connection = op.get_bind()
    dialect = connection.dialect.name

    if dialect == 'sqlite':
        subtype_expr = "json_extract(f.event_payload, '$.event.subtype')"
    else:  # postgresql
        subtype_expr = "f.event_payload->'event'->>'subtype'"

    connection.execute(sa.text(f"""
        UPDATE renders
           SET kind = CASE
               WHEN (
                   SELECT COALESCE({subtype_expr}, 'event')
                   FROM flyers f
                   WHERE f.render_id = renders.id
               ) = 'info' THEN 'flyer_info_final'
               ELSE 'flyer_event_final'
           END
         WHERE kind = 'flyer_final'
    """))


def downgrade() -> None:
    # Reverse: collapse both kinds back to 'flyer_final', drop the template column.
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE renders
           SET kind = 'flyer_final'
         WHERE kind IN ('flyer_event_final', 'flyer_info_final')
    """))

    with op.batch_alter_table('flyers', schema=None) as batch_op:
        batch_op.drop_column('template')
```

**Idempotency safeguard** (CONTEXT line 155): the `WHERE kind = 'flyer_final'` clause makes upgrade idempotent — re-running finds zero rows to migrate. The `UPDATE renders.kind` derives from `flyers.event_payload` which contains the EventInput dict with nested `subtype` under `event.subtype` (see the current worker in `flyer_generator/api/tasks/flyer.py` line 65: `event_payload=payload` — `payload` is the raw request body, which nests `event` under key `"event"`).

**NOT a blocker:** no `renders.id`→`flyers` back-pointer exists today; we use the existing `flyers.render_id` FK in the subquery (fine since it's indexed — 0001 migration line 114).

---

### `frontend/src/pages/flyers/new.tsx` (React form)

**Analog:** current `frontend/src/pages/flyers/new.tsx` (self; needs the template + subtype additions) + `frontend/src/pages/brochures/new.tsx` (has the `template` pattern)

**Brochure pattern — template as a zod field + Input** (brochures/new.tsx lines 67-78 + 187-200):

```typescript
const BrochureFormSchema = z
  .object({
    contentJson: z.string()...,
    template: z.string().min(1).max(64),   // ← graft this shape onto flyer
    brand_kit_slug: z.string().regex(SLUG, "...").max(64).optional(),
    generate_images: z.boolean(),
    workflow: z.string().min(1).max(64),
    style_preset: z.string().min(1).max(64),
  })
  .strict();

// ... later in JSX ...
<FormField
  control={form.control}
  name="template"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Template</FormLabel>
      <FormControl>
        <Input placeholder="editorial_classic" {...field} />
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

**Apply to flyers/new.tsx — three distinct additions** (CONTEXT lines 81-83):

**1. Template `<Select>` (hardcoded list, same approach as brochure per CONTEXT line 23-24):**

```typescript
const TEMPLATES = [
  "editorial_classic",
  "bold_modern",
  "minimal_photo",
  "retro_poster",
  "zine",
  "tight_typographic",
] as const;

const SUBTYPES = ["event", "info"] as const;
```

```typescript
<FormField
  control={form.control}
  name="template"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Template</FormLabel>
      <Select value={field.value} onValueChange={field.onChange}>
        <FormControl>
          <SelectTrigger><SelectValue placeholder="Select a template" /></SelectTrigger>
        </FormControl>
        <SelectContent>
          {TEMPLATES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
        </SelectContent>
      </Select>
      <FormMessage />
    </FormItem>
  )}
/>
```

Note: brochure uses `<Input>` for template (brochures/new.tsx lines 189-200); flyer should use `<Select>` per CONTEXT line 81. Pattern for `<Select>` already exists in flyers/new.tsx lines 291-316 (the preset Select) — copy THAT shape for the template Select.

**2. Subtype `<Select>` + conditional field rendering (new — no exact analog; pattern is zod discriminated union):**

```typescript
const EventFields = z.object({
  subtype: z.literal("event"),
  date: z.string().min(1).max(120),
  time: z.string().min(1).max(120),
  location_name: z.string().min(1).max(120),
  location_address: z.string().min(1).max(120),
  fees: z.string().max(120),
});

const InfoFields = z.object({
  subtype: z.literal("info"),
  description: z.string().min(1).max(600),
  call_to_action: z.string().max(120).optional(),
});

const EventInputSchema = z.discriminatedUnion("subtype", [
  EventFields.merge(CommonFields),
  InfoFields.merge(CommonFields),
]);
```

**Alternative** per CONTEXT line 85 "z.discriminatedUnion OR conditional refinement" — if the discriminated union proves clunky with RHF's resolver (see plan 21-06 deviation #1 comment in flyers/new.tsx line 73 about `.default()` + `.strict()`), use `.superRefine()` instead:

```typescript
const EventInputSchema = z.object({
  subtype: z.enum(["event", "info"]).default("event"),
  // All optional at zod level — refinement below enforces subtype rules
  title: z.string().min(1).max(120),
  date: z.string().max(120).optional(),
  // ... etc
}).superRefine((val, ctx) => {
  if (val.subtype === "event") {
    for (const req of ["date", "time", "location_name", "location_address"] as const) {
      if (!val[req]) ctx.addIssue({ code: "custom", path: [req], message: "required for event flyers" });
    }
  } else {
    if (!val.description) ctx.addIssue({ code: "custom", path: ["description"], message: "required for info flyers" });
  }
});
```

**3. Conditional render for event-only fields** — use `form.watch("event.subtype")` and wrap the event-field JSX (lines 199-277) in `{subtype === "event" && (...)}`.

Pattern for `useWatch` — the file doesn't currently import `useWatch` but RHF exposes it; easier to use `form.watch("event.subtype")`:

```typescript
const subtype = form.watch("event.subtype");

// ... inside JSX ...
{subtype === "event" && (
  <>
    <div className="grid grid-cols-2 gap-8">
      <FormField control={form.control} name="event.date" render={...} />
      <FormField control={form.control} name="event.time" render={...} />
    </div>
    <FormField control={form.control} name="event.location_name" render={...} />
    <FormField control={form.control} name="event.location_address" render={...} />
    <FormField control={form.control} name="event.fees" render={...} />
  </>
)}

{subtype === "info" && (
  <>
    <FormField control={form.control} name="event.description" render={...} />
    <FormField control={form.control} name="event.call_to_action" render={...} />
  </>
)}
```

---

### `frontend/src/pages/renders/gallery.tsx::KINDS` (FE filter list)

**Analog:** self — `frontend/src/pages/renders/gallery.tsx` lines 25-32.

**Current state**:

```typescript
const KINDS = [
  "flyer_final",
  "brochure_front",
  "brochure_back",
  "brochure_pdf",
  "social_post_image",
  "brand_kit_logo",
] as const;
```

**Target state** — replace `flyer_final` with the two new kinds (plan line 96 + CONTEXT lines 74-78):

```typescript
const KINDS = [
  "flyer_event_final",
  "flyer_info_final",
  "brochure_front",
  "brochure_back",
  "brochure_pdf",
  "social_post_image",
  "brand_kit_logo",
] as const;
```

After the migration runs, no `flyer_final` rows exist; dropping it from the filter is safe. If the planner wants transitional kindness, keep `"flyer_final"` in the list for one release — but it will just produce an empty filter result and clutter the UI. Prefer the clean break.

---

### `frontend/src/pages/jobs/list.tsx::KINDS` (FE filter list)

**Analog:** self — `frontend/src/pages/jobs/list.tsx` lines 27-33.

**No change required.** The job kinds enum (`JobKind`) is separate from the render kinds enum. Flyer remains `"flyer"` on the Jobs page. The file is listed in CONTEXT "Modified files" only because the planner should *confirm* no change is needed and leave a comment noting the explicit decision.

```typescript
const KINDS = [
  "brand_kit",
  "flyer",           // ← unchanged; subtype is not a separate JobKind
  "brochure",
  "social_post",
  "social_campaign",
] as const;
```

Similarly `statusPathFor` (lines 42-56) stays unchanged — both subtypes route to `/flyers/:id`. The Flyer status page already handles whatever kind the render ends up being.

---

### `frontend/src/api/openapi.snapshot.json` + `schema.gen.ts` (FE generated types)

**Analog:** self — these are generated artifacts; no template to reference.

**Regenerate after BE changes** (plan line 94 — the backend must land first, then the FE regen):

```bash
# Typical regen command (verify against repo root / scripts):
cd frontend && pnpm run schema:gen
# or: npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.gen.ts
```

Expected delta:
- `FlyerCreateRequest` type gains `template: string` + `event.subtype` + optional `event.date/time/...`
- `FlyerInput` (was `EventInput`) appears with the new optional field shapes
- Anything the FE calls as `FlyerCreateRequestBody` auto-updates via `components["schemas"]["FlyerCreateRequest"]`

Do NOT hand-edit `schema.gen.ts`; it must always be a byproduct of the OpenAPI schema.

---

### `tests/flyer/schema_renderer/test_loader.py` (loader test)

**Analog:** `tests/brochure/schema_renderer/test_loader.py` (entire 60-line file)

**Pattern to mirror verbatim — only change the module paths + template names** (brochure test file lines 1-60):

```python
"""Flyer template loader tests."""

from __future__ import annotations

import pytest

from flyer_generator.flyer.schema_renderer.loader import (
    list_templates,
    load_template,
)


def test_list_templates_contains_starters():
    names = list_templates()
    assert "editorial_classic" in names
    assert "bold_modern" in names
    assert "minimal_photo" in names


def test_load_editorial_classic():
    t = load_template("editorial_classic")
    assert t.name == "editorial_classic"
    assert t.canvas.width == 1080
    assert t.canvas.height == 1920
    # Single-panel for flyer
    assert "hero" in t.panels
    assert len(t.panels["hero"].elements) > 0


def test_load_unknown_raises():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_template("nonexistent_template_xyz")


def test_load_by_path(tmp_path):
    t = load_template("editorial_classic")
    path = tmp_path / "copy.json"
    path.write_text(t.model_dump_json())
    t2 = load_template(str(path))
    assert t2.name == t.name


def test_malformed_json_rejected(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text('{"schema_version": "1", "name": "x"}')
    with pytest.raises(Exception):
        load_template(str(bad))
```

---

### `tests/flyer/schema_renderer/test_schema_model.py` (Pydantic validation test)

**Analog:** `tests/brochure/schema_renderer/test_schema_model.py` (entire 160-line file — especially the `_minimal_template()` helper at lines 20-35, the `TestTemplateSchema` class at 38-67, and `TestShapeElement` at 70-116)

**Pattern to mirror — key helper + class structure** (brochure test lines 20-35 + 38-67):

```python
"""Flyer template schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flyer_generator.flyer.schema_renderer.schema_model import (
    FlyerTemplateSchema,
    ShapeElement,
    SolidFill,
    TextElement,
)


def _minimal_template() -> dict:
    return {
        "schema_version": "1",
        "name": "test_template",
        "description": "test",
        "canvas": {"width": 1080, "height": 1920},
        "palette": {"accent_default": "#1E3A5F"},
        "panels": {
            "hero": {"elements": []},
        },
    }


class TestFlyerTemplateSchema:
    def test_minimal_template_loads(self):
        t = FlyerTemplateSchema.model_validate(_minimal_template())
        assert t.name == "test_template"
        assert t.canvas.width == 1080
        assert "hero" in t.panels

    def test_missing_hero_panel_rejected(self):
        data = _minimal_template()
        del data["panels"]["hero"]
        with pytest.raises(ValidationError, match="missing panels"):
            FlyerTemplateSchema.model_validate(data)

    def test_schema_version_must_be_1(self):
        data = _minimal_template()
        data["schema_version"] = "2"
        with pytest.raises(ValidationError):
            FlyerTemplateSchema.model_validate(data)

    def test_name_must_be_snake_case(self):
        data = _minimal_template()
        data["name"] = "BadName"
        with pytest.raises(ValidationError):
            FlyerTemplateSchema.model_validate(data)

    def test_palette_rejects_invalid_hex(self):
        data = _minimal_template()
        data["palette"]["accent_default"] = "not-a-color"
        with pytest.raises(ValidationError):
            FlyerTemplateSchema.model_validate(data)

    def test_subtype_compat_defaults_to_both(self):
        t = FlyerTemplateSchema.model_validate(_minimal_template())
        assert set(t.subtype_compat) == {"event", "info"}

    def test_subtype_compat_event_only(self):
        data = _minimal_template()
        data["subtype_compat"] = ["event"]
        t = FlyerTemplateSchema.model_validate(data)
        assert t.subtype_compat == ["event"]
```

**Reuse the primitive-level tests** (TestShapeElement, TestTextElement, TestBulletsElement from brochure lines 70-160) only if the flyer schema_model does NOT reuse brochure primitives (if it imports them, the brochure tests already cover them and duplication is pointless). Per the schema_model section above, the planner should decide: if primitives are duplicated into flyer schema_model, copy these tests; if imported from brochure, skip them.

---

### `tests/flyer/schema_renderer/test_render_smoke.py` (rendering smoke test)

**Analog:** `tests/brochure/schema_renderer/test_renderer.py` (lines 1-60 + the parameterized render tests 62-133)

**Flyer differs** from brochure: brochure has a dedicated `render_schema_brochure(template, content)` function; flyer uses `PosterComposer.compose(event, background, verdict, layout, template=...)`. The smoke test must stand up the minimal pipeline artifacts (FakeBackground, a synthetic VisionVerdict, a LayoutResolver call) or, simpler, test that `load_template` + composer integration produces a non-empty SVG.

**Pattern to mirror — parameterized render assertions** (brochure lines 62-99, flyer-adapted):

```python
"""End-to-end render smoke test for all shipped flyer templates."""

from __future__ import annotations

import pytest

from flyer_generator.flyer.schema_renderer import load_template, list_templates
from flyer_generator.models import FlyerInput, GeneratedBackground, LayoutZones, VisionVerdict, ComfyJob
from flyer_generator.stages.composer import PosterComposer
from flyer_generator.stages.layout import LayoutResolver
from datetime import datetime, timezone

STARTERS = ["editorial_classic", "bold_modern", "minimal_photo", "retro_poster", "zine", "tight_typographic"]


def _sample_event() -> FlyerInput:
    return FlyerInput(
        title="Test Event",
        subtype="event",
        date="2026-05-01",
        time="7:00 PM",
        location_name="The Hall",
        location_address="1 Main St",
        fees="Free",
        org="Acme Test Co",
        style_concept="summer vibes",
        style_preset="photorealistic",
    )


def _sample_info() -> FlyerInput:
    return FlyerInput(
        title="Public Notice",
        subtype="info",
        description="Road closure on Main St effective May 1.",
        call_to_action="Plan alternate routes.",
        org="City of Example",
        style_concept="civic bulletin",
        style_preset="photorealistic",
    )


def _fake_background() -> GeneratedBackground:
    return GeneratedBackground(
        image_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,  # PNG magic bytes + filler
        source_dimensions=(832, 1472),
        final_dimensions=(1080, 1920),
        comfy_job=ComfyJob(
            prompt_id="fake",
            submitted_at=datetime.now(timezone.utc),
            positive_prompt="",
            negative_prompt="",
            seed=0,
            attempt_number=1,
        ),
    )


def _fake_verdict(subtype: str) -> VisionVerdict:
    if subtype == "event":
        zones = LayoutZones(title="TOP_CENTER", details="BOTTOM_CENTER", fee_badge="TOP_RIGHT", org_credit="BOTTOM_CENTER")
    else:
        # Info flyers omit fee_badge / details (CONTEXT line 57-60). See vision section — LayoutZones is relaxed to Optional.
        zones = LayoutZones(title="TOP_CENTER", details=None, fee_badge=None, org_credit="BOTTOM_CENTER")
    return VisionVerdict(approved=True, confidence=0.9, zones=zones, text_color="white", raw_response="{}")


@pytest.mark.parametrize("template_name", STARTERS)
def test_template_renders_event_flyer(template_name: str):
    template = load_template(template_name)
    event = _sample_event()
    bg = _fake_background()
    verdict = _fake_verdict("event")
    layout = LayoutResolver().resolve(verdict.zones)
    svg = PosterComposer().compose(event, bg, verdict, layout, template=template)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    # Event fields appear
    assert "Test Event" in svg or "TEST EVENT" in svg


@pytest.mark.parametrize("template_name", STARTERS)
def test_template_renders_info_flyer(template_name: str):
    template = load_template(template_name)
    flyer = _sample_info()
    bg = _fake_background()
    verdict = _fake_verdict("info")
    layout = LayoutResolver().resolve(verdict.zones)
    svg = PosterComposer().compose(flyer, bg, verdict, layout, template=template)
    assert svg.startswith("<svg")
    # Info flyer must NOT contain fee/date markup
    # (fee_badge elements are generated inside a badge <rect> — absence check)
    # See composer.py lines 404-413: fee_elements only populated when fees_esc truthy.
    assert "Public Notice" in svg or "PUBLIC NOTICE" in svg
```

**Key difference from brochure's `test_renderer.py`**: no `render_schema_brochure()` one-call; must assemble `FlyerInput` + `GeneratedBackground` + `VisionVerdict` + `ResolvedLayout` and invoke `PosterComposer.compose()`. The fake fixture pattern (`FakeOut`, `FakeGen` in `tests/api/test_worker_tasks.py` lines 198-213) shows how similar fakes are constructed in the codebase.

---

## Shared Patterns

### Pydantic v2 `extra="forbid"` on every request/response model

**Source:** every file under `flyer_generator/api/schemas/*.py` and `flyer_generator/brochure/schema_renderer/schema_model.py`

**Apply to:** `FlyerInput`, `FlyerTemplateSchema`, every new Pydantic model.

```python
from pydantic import BaseModel, ConfigDict

class MyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

### Structured logging with `structlog.get_logger().bind(job_id=...)`

**Source:** `flyer_generator/api/tasks/brochure.py:35` + `flyer_generator/api/tasks/flyer.py:19`

**Apply to:** all new/modified worker and pipeline code.

```python
import structlog
logger = structlog.get_logger()
# ...
log = logger.bind(job_id=job_id, kind="flyer", subtype=flyer_input.subtype)
log.info("task_start")
```

### Error handling pattern in worker tasks — mark_failed then re-raise

**Source:** `flyer_generator/api/tasks/brochure.py:151-154` + `flyer_generator/api/tasks/flyer.py:77-80`

**Apply to:** modified `task_generate_flyer` — preserve the existing pattern unchanged:

```python
except Exception as exc:
    log.exception("task_failed")
    await mark_failed(sessionmaker, job_id, exc)
    raise
```

This funnels all failures (including `FileNotFoundError` from `load_template` and `pydantic.ValidationError`) into `JobRecord.error_detail` via `mark_failed`, which sanitizes to `{type, message}` (see `tests/api/test_worker_tasks.py:67-91`).

### Module-scope imports for test patching (BLOCKER-2 pattern)

**Source:** `flyer_generator/api/tasks/brochure.py:22-33`

**Apply to:** `flyer_generator/api/tasks/flyer.py` — add the new `load_template` import at module scope with the same comment so direct-invocation worker tests can patch `flyer_generator.api.tasks.flyer.load_template`.

```python
# NOTE: Module-scope so direct-invocation tests can patch via
# patch("flyer_generator.api.tasks.flyer.load_template").
# (Mirrors BLOCKER-2 pattern from brochure.py lines 22-33.)
from flyer_generator.flyer.schema_renderer.loader import load_template
```

### SQLAlchemy `Base` + `new_ulid` + `utcnow` helpers

**Source:** `flyer_generator/api/models/base.py` (imported in every Record model)

**Apply to:** the new `template` column on `FlyerRecord` (no new model needed — just the column).

### Frontend `<Select>` + `FormField` + `zodResolver` composition

**Source:** current `frontend/src/pages/flyers/new.tsx` lines 291-316 (the Preset Select)

**Apply to:** both the new Template Select and Subtype Select.

```tsx
<FormField
  control={form.control}
  name="template"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Template</FormLabel>
      <Select value={field.value} onValueChange={field.onChange}>
        <FormControl>
          <SelectTrigger><SelectValue placeholder="Select a template" /></SelectTrigger>
        </FormControl>
        <SelectContent>
          {TEMPLATES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
        </SelectContent>
      </Select>
      <FormMessage />
    </FormItem>
  )}
/>
```

### Frontend zod `.strict()` matching backend `extra="forbid"`

**Source:** `frontend/src/pages/flyers/new.tsx` lines 94 + 105; `frontend/src/pages/brochures/new.tsx` line 78

**Apply to:** every form schema addition. The phase-21 comment (flyers/new.tsx lines 72-78) explains why `.default()` is forbidden inside `.strict()` — seed defaults via RHF `defaultValues`, never `z.xxx().default()`.

---

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| — | — | Every Phase-22 file has a direct analog either in the brochure subsystem (preferred), on the file itself (self-evolution), or among tests. |

---

## Metadata

**Analog search scope:** `flyer_generator/brochure/`, `flyer_generator/api/{tasks,schemas,models,routes}/`, `flyer_generator/stages/`, `flyer_generator/models.py`, `flyer_generator/pipeline.py`, `tests/brochure/schema_renderer/`, `tests/api/`, `frontend/src/pages/{brochures,flyers,renders,jobs}/`, `frontend/src/api/`, `alembic/versions/`

**Files scanned:** ~40

**Pattern extraction date:** 2026-04-24
