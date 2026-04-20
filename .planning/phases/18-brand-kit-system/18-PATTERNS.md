# Phase 18: Brand Kit System - Pattern Map

**Mapped:** 2026-04-20
**Files analyzed:** 16 new/modified files + 8 test files
**Analogs found:** 15 / 16 new files have exact/role analogs; `contrast.py` is pure-function module (analog = `text_fit.py`); `audit.py` is new pattern (analog = `image_gate.py` verdict shape)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `flyer_generator/brand_kit/__init__.py` | package-init / public-API | import-reexport | `flyer_generator/brochure/schema_renderer/__init__.py` | exact |
| `flyer_generator/brand_kit/models.py` | Pydantic v2 data contracts | model-validation (round-trip JSON) | `flyer_generator/brochure/schema_renderer/schema_model.py` + `content_model.py` | exact |
| `flyer_generator/brand_kit/scraper.py` | async I/O (httpx + Playwright) | request-response + file-I/O | `flyer_generator/brochure/schema_renderer/image_gate.py` | role-match (async httpx, retry-on-error, 180s timeout, structlog) |
| `flyer_generator/brand_kit/contrast.py` | pure-function utility (dataclass results) | transform | `flyer_generator/brochure/schema_renderer/text_fit.py` | role-match (pure functions + frozen dataclass) |
| `flyer_generator/brand_kit/applier.py` | immutable transform on Pydantic model | transform | `flyer_generator/brochure/schema_renderer/renderer.py:724-759` (accent_override path) | exact (model_copy(deep=True) pattern) |
| `flyer_generator/brand_kit/storage.py` | filesystem I/O, JSON → Pydantic | file-I/O | `flyer_generator/brochure/schema_renderer/loader.py` | exact (read JSON + `model_validate`) |
| `flyer_generator/brand_kit/audit.py` | orchestration + structured verdict | batch / event-driven | `flyer_generator/brochure/schema_renderer/image_gate.py` (verdict + retry) | role-match (orchestrator + structlog + soft-fail) |
| `flyer_generator/brand_kit/__main__.py` | typer CLI, multi-subcommand | request-response | `flyer_generator/brochure/schema_renderer/__main__.py` + `flyer_generator/__main__.py` | exact (typer.Typer() + multiple @app.command) |
| `flyer_generator/errors.py` (augmented) | typed exception hierarchy | exception | self-augmentation — extend existing style | exact |
| `flyer_generator/brochure/schema_renderer/__main__.py` (augmented) | CLI flag addition | request-response | commit `bb52f65` (same file, `--color-accent` addition) | exact (step-for-step same pattern) |
| `flyer_generator/brochure/schemas/*.json` (13 edits) | template typography uplift | config-data | Existing `typography.body_size: 34` etc. in schemas | exact |
| `.brand-kit-template.json` | schema reference (repo-tracked) | config-data | N/A — new concept; parallel to `docs/brochure/sample-content/*.json` for shape | partial |
| `.gitignore` (augmented) | config | config-data | Existing `.gitignore` additions style | exact |
| `pyproject.toml` (augmented) | build config | config-data | Existing `[project] dependencies` block | exact |
| `tests/brand_kit/test_models.py` | test (Pydantic round-trip) | model-validation | `tests/brochure/schema_renderer/test_text_gen.py` + `test_loader.py` | exact |
| `tests/brand_kit/test_scraper.py` | test (async http mocking) | request-response | `tests/test_comfy_client.py` (respx) + `tests/brochure/schema_renderer/test_image_gate.py` (AsyncMock) | exact |
| `tests/brand_kit/test_contrast.py` | test (pure function) | transform | `tests/brochure/schema_renderer/test_text_fit.py` | exact |
| `tests/brand_kit/test_applier.py` | test (model transform) | transform | `tests/brochure/schema_renderer/test_renderer.py:414-433` (`test_accent_override_*`) | exact |
| `tests/brand_kit/test_audit.py` | test (orchestration + verdict) | batch | `tests/brochure/schema_renderer/test_image_gate.py` | role-match |
| `tests/brand_kit/test_storage.py` | test (filesystem round-trip) | file-I/O | `tests/brochure/schema_renderer/test_loader.py` | exact (tmp_path) |
| `tests/brand_kit/test_cli.py` | test (typer CliRunner) | request-response | No direct analog — typer CliRunner tests are new in repo | partial |
| `tests/brand_kit/test_integration.py` | test (e2e smoke) | batch | `tests/brochure/schema_renderer/test_image_gate.py` happy-path | role-match |

---

## Pattern Assignments

### `flyer_generator/brand_kit/__init__.py` (package-init)

**Analog:** `flyer_generator/brochure/schema_renderer/__init__.py` (lines 1-66)

**Copy pattern:** module-level docstring explaining public API + flat re-exports + explicit `__all__`.

**Excerpt** (lines 1-48 of analog):
```python
"""Schema-driven brochure rendering subsystem.

Renders tri-fold brochures from a pair of JSON documents:
  ...
Public API:
    from flyer_generator.brochure.schema_renderer import (
        load_template,
        list_templates,
        render_schema_brochure,
        ...
    )
"""

from __future__ import annotations

from flyer_generator.brochure.schema_renderer.content_model import (
    BackPanelContent,
    BrochureBrief,
    BrochureContent,
    ContentSection,
    Testimonial,
)
from flyer_generator.brochure.schema_renderer.image_gate import (
    collect_image_slots,
    generate_template_images,
    resolve_concept_for_slot,
)
...

__all__ = [
    "BackPanelContent",
    "BrochureBrief",
    ...
]
```

**For brand_kit:** re-export `BrandKit`, `BrandPalette`, `BrandTypography`, `BrandLogo`, `BrandVoice`, `BrandPhotoHints`, `ColorUsage`, `ContrastReport`, `AuditReport`, `fetch_brand_kit`, `apply_brand_kit`, `audit_render`, `load_brand_kit`, `list_brand_kits`, `save_brand_kit`.

---

### `flyer_generator/brand_kit/models.py` (Pydantic v2 data contracts)

**Analog:** `flyer_generator/brochure/schema_renderer/schema_model.py` + `content_model.py`

**Imports pattern** (schema_model.py lines 1-17):
```python
"""Pydantic schema for template JSON documents.

...This model is intentionally strict (extra="forbid") so malformed templates
fail loud at load time, not at render time.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.models import validate_hex_color
```

**`model_config` + `field_validator` pattern** (schema_model.py lines 66-91 — gradient stops + hex validation):
```python
class GradientStop(BaseModel):
    """One color stop in a linear or radial gradient."""

    model_config = ConfigDict(extra="forbid")

    offset: float = Field(ge=0.0, le=1.0)
    color: str
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        return validate_hex_color(v)
```

**Literal enum + optional nested model** (schema_model.py lines 28-46 + content_model.py lines 114-132):
```python
# schema_model.py — Literal enum style
_TextRole = Literal[
    "cover_title", "cover_subtitle", "section_heading", "body", ...
]

# content_model.py — optional nested models with defaults
class BrochureContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    subtitle: str | None = None
    tagline: str | None = None
    org: str
    contact: ContactBlock | None = None
    sections: list[ContentSection] = Field(min_length=1, max_length=8)
    back_panel: BackPanelContent | None = None
    extras: dict[str, str] = Field(default_factory=dict)
```

**Cross-field validator** (schema_model.py lines 369-386 — require complete panel set):
```python
@field_validator("panels")
@classmethod
def _validate_panels_complete(
    cls, v: dict[str, PanelSchema]
) -> dict[str, PanelSchema]:
    required = {"front_cover", "back_cover", ...}
    missing = required - set(v.keys())
    if missing:
        msg = f"template missing panels: {sorted(missing)}"
        raise ValueError(msg)
    return v
```

**For brand_kit/models.py:**
- Every Pydantic model uses `model_config = ConfigDict(extra="forbid")`.
- Hex color fields MUST run through `validate_hex_color` from `flyer_generator.brochure.models`.
- `BrandLogo.variant` → `Literal["primary", "mono_dark", "mono_light", "mark_only"]`.
- `BrandLogo.format` → `Literal["png", "jpg", "svg"]`.
- `BrandKit.palette`, `BrandKit.typography`, `BrandKit.voice`, `BrandKit.photography` are all `| None` (partial scrapes must validate).
- `BrandKit.source_artifacts: list[str] = Field(default_factory=list)`.
- `BrandKit.logos: list[BrandLogo] = Field(default_factory=list)`.
- `BrandKit.size_multiplier: float = Field(default=1.0, gt=0.0, le=3.0)`.
- `BrandKit.fetched_at: datetime` (requires `from datetime import datetime`).
- Do NOT use deprecated `class Config` — use `model_config = ConfigDict(...)` per CLAUDE.md.

---

### `flyer_generator/brand_kit/scraper.py` (async I/O)

**Analog:** `flyer_generator/brochure/schema_renderer/image_gate.py` (lines 1-45, 156-282)

**Imports + logger bind pattern** (image_gate.py lines 14-44):
```python
from __future__ import annotations

import asyncio
import copy
import secrets

import httpx
import structlog

...
logger = structlog.get_logger()
```

**httpx.AsyncClient with 180s timeout** (image_gate.py lines 188-198 — the load-bearing line):
```python
_owns_http = False
if http_client is None and comfy_client is None:
    # ComfyCloud jobs regularly take 30-90s; default 5s httpx timeout
    # would ReadTimeout on every attempt. Generous 180s per request.
    http_client = httpx.AsyncClient(follow_redirects=True, timeout=180.0)
    _owns_http = True
```

**Retry-on-transient-error with `continue` (not `break`)** (image_gate.py lines 212-232):
```python
for attempt in range(1, settings.max_bg_attempts + 1):
    logger.info(
        "schema_hero_attempt",
        attempt=attempt,
        max_attempts=settings.max_bg_attempts,
        workflow=workflow_name,
    )
    try:
        wf = cover_builder.build(brochure_in, attempt, refinement_hint)
        _, raw = await comfy_client.generate(wf, attempt)
    except Exception as err:
        # Retry rather than abort — one transient download/vision
        # parse blip shouldn't burn the remaining attempts.
        logger.warning(
            "schema_hero_generate_error",
            attempt=attempt,
            error_type=type(err).__name__,
            error=str(err) or repr(err),
        )
        continue
    # ... success path
```

**Graceful-close `finally`** (image_gate.py lines 277-279):
```python
finally:
    if _owns_http and http_client is not None:
        await http_client.aclose()
```

**trace_id binding** (analog: `flyer_generator/brochure/pipeline.py:76-77`):
```python
trace_id = uuid.uuid4().hex
logger = get_logger().bind(trace_id=trace_id, brochure_title=brochure.title)
```

**For brand_kit/scraper.py:**
- Orchestrator function signature: `async def fetch_brand_kit(url: str, slug: str, *, http_client: httpx.AsyncClient | None = None, ...) -> BrandKit`.
- Inject `http_client` + `_owns_http` with `timeout=180.0` (scraping modern pages + font downloads runs long).
- Wrap Playwright launch in `try/except Exception` → `logger.warning("brand_kit_playwright_failed", ...)` → continue to BS4 fallback (the "retry not abort" discipline from `3512a35`).
- Every missing field = `None` on the model, NOT a raise. Surface misses via `source_artifacts` list and structured `logger.warning(...)` events.
- Split into `scraper.py` (orchestrator) + `scraper_playwright.py` (optional import — isolate Chromium so BS4 tests never touch it) + `scraper_bs4.py` (always importable — test-harness backbone).
- Use `structlog.get_logger().bind(trace_id=..., url=url, slug=slug)` at the top of `fetch_brand_kit`.

---

### `flyer_generator/brand_kit/contrast.py` (pure-function utility)

**Analog:** `flyer_generator/brochure/schema_renderer/text_fit.py` (lines 1-10, 106-135)

**Module docstring + free-function style** (text_fit.py lines 1-10):
```python
"""Text measurement + wrap + budget math.

No browser / canvas dependency. We use a character-width lookup table
...This is accurate to within ±8% for Latin text, which is plenty for
fit-to-bbox decisions — we deliberately leave a 10% safety margin.
"""

from __future__ import annotations

from dataclasses import dataclass
```

**Frozen dataclass result** (text_fit.py lines 106-110):
```python
@dataclass(frozen=True)
class FittedText:
    lines: list[str]
    total_height: float
    overflowed: bool  # True when content had to be truncated to fit
```

**Pure function with typed return** (text_fit.py lines 113-135):
```python
def fit_to_bbox(
    text: str,
    bbox: tuple[float, float, float, float],
    font_size: int,
    line_height: int,
    font_family: str = "",
    max_chars_per_line: int | None = None,
) -> FittedText:
    """Wrap `text` into lines that fit bbox width; truncate at bbox height."""
    _, _, w, h = bbox
    if max_chars_per_line is None:
        max_chars_per_line = chars_per_line(w, font_size, font_family)
    ...
    return FittedText(lines=all_lines, total_height=total, overflowed=overflowed)
```

**For brand_kit/contrast.py:**
- Module of pure functions; optional thin class for stateful caching if needed, but prefer the free-function style.
- `ContrastPair`, `ContrastReport` as Pydantic models (not dataclasses) so they round-trip to the audit JSON. Use `model_config = ConfigDict(extra="forbid")`.
- Critical pitfall from RESEARCH.md: `wcag_contrast_ratio.rgb(rgb1, rgb2)` takes float triples `(0.0-1.0)` NOT `(0-255)` ints. Write a `_hex_to_wcag_triple(hex_str: str) -> tuple[float, float, float]` helper and route every call through it.
- `ensure_aa(fg: str, bg: str, *, palette: BrandPalette, min_ratio: float = 4.5) -> tuple[str, str | None]` returns `(remediated_fg, remediation_note_or_None)`.
- `coloraide` 8.x API: `Color(hex).convert("oklch")` for lightness nudge; `Color.contrast(other, method="wcag21")` for ratio.

---

### `flyer_generator/brand_kit/applier.py` (immutable transform)

**Analog:** `flyer_generator/brochure/schema_renderer/renderer.py` lines 724-759 (the `accent_override` block)

**The exact `model_copy(deep=True)` pattern** (renderer.py lines 752-759):
```python
if accent_override is not None:
    template = template.model_copy(
        update={
            "palette": template.palette.model_copy(
                update={"accent_default": accent_override}
            )
        }
    )
```

**Function signature + docstring shape** (renderer.py lines 724-751):
```python
def render_schema_brochure(
    template: TemplateSchema,
    content: BrochureContent,
    *,
    images: dict[str, bytes] | None = None,
    textures: dict[str, bytes] | None = None,
    logo_bytes: bytes | None = None,
    accent_override: str | None = None,
) -> tuple[str, str]:
    """Render a template + content pair to (outside_svg, inside_svg).

    When `images` is supplied, each `image_placeholder` whose `slot` matches a
    key has the PNG bytes embedded...

    When `accent_override` is supplied (a `#RRGGBB` hex string), it replaces
    `template.palette.accent_default` for this render — lets a brochure ship
    with the brand's color without forking the template JSON.
    """
```

**For brand_kit/applier.py:**
- `def apply_brand_kit(template: TemplateSchema, kit: BrandKit) -> tuple[TemplateSchema, bytes | None]`.
- Nest `model_copy(update={...})` at the granularity of the field being swapped — exactly the `template.palette.model_copy(update=...)` pattern above, but for `palette` + `typography` at once.
- Note: `Palette` (existing) has `accent_default`, `neutral_dark`, `neutral_light`, `muted`, `extras` (schema_model.py:318-337). Map `BrandPalette.primary.hex → accent_default`, `BrandPalette.neutral_dark.hex → neutral_dark`, `BrandPalette.neutral_light.hex → neutral_light`, `BrandPalette.secondary.hex → muted` (semantic fit). Funnel `BrandPalette.extras` through `Palette.extras`.
- `Typography` (existing) has fields like `body_size: int = 34`, `heading_size: int = 64`, etc. (schema_model.py:340-352). Scale every `*_size: int` by `round(value * kit.size_multiplier)` with `size_multiplier=1.0` as no-op.
- Logo: `logo_bytes = (kit_dir / kit.logos[0].path).read_bytes()` if `kit.logos` non-empty, prefer `variant == "primary"`.
- **Never mutate** the passed-in template — always return a fresh copy.

---

### `flyer_generator/brand_kit/storage.py` (filesystem I/O)

**Analog:** `flyer_generator/brochure/schema_renderer/loader.py` (full file, 40 lines)

**Full pattern to copy** (loader.py lines 1-39):
```python
"""Template schema loader — reads JSON, validates via Pydantic."""

from __future__ import annotations

import json
from pathlib import Path

from flyer_generator.brochure.schema_renderer.schema_model import TemplateSchema

_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


def load_template(name_or_path: str) -> TemplateSchema:
    """Load a template schema by name (looks under schemas/) or file path.

    Raises:
        FileNotFoundError: No matching file found.
        pydantic.ValidationError: JSON doesn't match TemplateSchema.
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
    return TemplateSchema.model_validate(raw)


def list_templates() -> list[str]:
    """All built-in schema templates (alphabetical)."""
    if not _SCHEMAS_DIR.exists():
        return []
    return sorted(p.stem for p in _SCHEMAS_DIR.glob("*.json"))
```

**For brand_kit/storage.py:**
- Replace the `_SCHEMAS_DIR` constant with a `_brand_kits_dir()` function that reads env var. CLAUDE.md / config.py pattern says use `pydantic-settings` — but this env var is resolved at call time per kit-fetch, not at startup, so a plain helper is fine:

```python
import os
from pathlib import Path

def _brand_kits_dir() -> Path:
    """Resolve FLYER_BRAND_KITS_DIR (default `.brand-kits/` relative to CWD)."""
    return Path(os.environ.get("FLYER_BRAND_KITS_DIR", ".brand-kits"))
```

  Alternative: add `brand_kits_dir: Path = Path(".brand-kits")` to `flyer_generator/config.py:Settings` (matches existing `output_dir: Path = Path("./output")` at line 55). **Recommended: the config.py extension** — consistent with the existing prefix-based env var convention (`FLYER_` prefix, already wired).

- `save_brand_kit(kit: BrandKit, slug: str) -> Path` — writes `brand.json` + logos subdir; returns the kit dir path.
- `load_brand_kit(slug_or_path: str) -> BrandKit` — mirror `load_template`'s dual-mode signature (name-or-path).
- `list_brand_kits() -> list[str]` — identical to `list_templates()` but globbing `*/brand.json` under `_brand_kits_dir()`.
- Use `BrandKit.model_validate(json.loads(...))` + `kit.model_dump_json(indent=2)` for round-trip.

---

### `flyer_generator/brand_kit/audit.py` (orchestration + structured verdict)

**Analog:** `flyer_generator/brochure/schema_renderer/image_gate.py` (the orchestrator + verdict + soft-fail shape)

**Soft-fail discipline** (image_gate.py lines 260-268):
```python
async def _gen_spot(slot: str, hint: str) -> tuple[str, bytes] | None:
    try:
        wf = _build_spot_workflow(wf_config, presets, style_preset, hint)
        _, raw = await comfy_client.generate(wf, attempt=1)
        return (slot, raw)
    except Exception as err:
        logger.warning("schema_spot_failed", slot=slot, error=str(err))
        return None
```

**Structured verdict shape** (from `flyer_generator/models.py:VisionVerdict` referenced indirectly — fields: approved, rejection_reasons, refinement_hint).

**For brand_kit/audit.py:**
- `AuditReport` Pydantic model:
  ```python
  class AuditReport(BaseModel):
      model_config = ConfigDict(extra="forbid")
      whitespace: dict[str, float]       # panel_id → density ratio
      contrast: ContrastReport
      density: dict[str, float]           # content_key → fill % of budget
      issues: list[AuditIssue] = Field(default_factory=list)
      cycle: int = 0                      # 0 = first pass
  ```
- `AuditIssue`:
  ```python
  class AuditIssue(BaseModel):
      model_config = ConfigDict(extra="forbid")
      severity: Literal["info", "warn", "error"]
      category: Literal["whitespace", "contrast", "density"]
      panel: str | None = None
      content_key: str | None = None
      detail: str
      suggested_remediation: str | None = None
  ```
- Orchestrator function `iterate_audit_loop(content, template, ..., max_cycles: int = 3) -> tuple[AuditReport, str, str]` (returns report + final outside_svg + inside_svg).
- Whitespace detection: use `PIL.Image.open(io.BytesIO(rendered_png))` (mirror `flyer_generator/stages/rasterizer.py:37`); crop to each panel's trim rect; build grayscale histogram; count pixels within ±8 of the panel background color.
- Density per content_key: reuse `char_budget_for_bbox()` from `text_fit.py:138` to compute budget, then divide `len(resolved_content)` by budget.
- Contrast: import from `brand_kit.contrast`.
- **Soft-fail:** audit cycles that don't fully converge log `logger.warning("audit_exhausted", cycles=3, issues=[...])` and return the last report with `issues` populated — raise `BrandKitAuditError` only when caller set `strict=True`.
- Use `structlog.get_logger().bind(trace_id=uuid.uuid4().hex, slug=slug)` at the orchestrator top.

---

### `flyer_generator/brand_kit/__main__.py` (typer CLI)

**Analog:** `flyer_generator/brochure/schema_renderer/__main__.py` + `flyer_generator/brochure/__main__.py` (multi-command shape) + `flyer_generator/__main__.py`

**typer app init + imports** (schema_renderer/__main__.py lines 1-44):
```python
"""CLI entrypoint: render a brochure from a template + content JSON.

Usage:
    # Pure design render (no API calls)
    python -m flyer_generator.brochure.schema_renderer \\
        --template editorial_classic ...
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from flyer_generator.brochure.schema_renderer.content_model import BrochureContent
from flyer_generator.brochure.schema_renderer.loader import list_templates, load_template
...

app = typer.Typer(help="Schema-driven brochure renderer (design-first, no LLM/API).")
```

**Subcommand with rich typer.Option + Annotated types** (schema_renderer/__main__.py lines 46-146):
```python
@app.command()
def render(
    template: Annotated[
        Optional[str],
        typer.Option("--template", help="Template name (under schemas/) or path to a JSON file."),
    ] = None,
    content: Annotated[
        Optional[Path],
        typer.Option("--content", help="Path to a content JSON file."),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", help="Output directory."),
    ] = Path("/tmp/schema-out"),
    list_templates_only: Annotated[
        bool,
        typer.Option("--list-templates", help="List built-in template names and exit."),
    ] = False,
    ...
) -> None:
    """Render a brochure from a template schema + content JSON."""
    if list_templates_only:
        for name in list_templates():
            typer.echo(name)
        raise typer.Exit(0)
```

**Async-in-sync bridge** (schema_renderer/__main__.py lines 205-214 — the canonical `asyncio.run(...)` pattern):
```python
ct = asyncio.run(
    generate_content_from_prompt(
        tmpl,
        prompt,
        audience=audience,
        brief=brief,
        contact=supplied_contact,
        settings=Settings(),
    )
)
```

**End-of-file dispatch** (schema_renderer/__main__.py lines 310-311):
```python
if __name__ == "__main__":
    app()
```

**For brand_kit/__main__.py:**
- Three `@app.command()` functions: `fetch(url, slug)`, `list()` (aliased e.g. `list_kits`), `show(slug)`.
- `fetch` wraps an `asyncio.run(fetch_brand_kit(url, slug, ...))` call.
- `list` and `show` are sync (no async storage API needed).
- Use `typer.echo()` for output, `typer.Exit(0)`/`typer.Exit(2)` for normal/error exit.
- Error messages to stderr: `typer.echo("Error: ...", err=True)`.
- Bottom of file: `if __name__ == "__main__": app()`.

---

### `flyer_generator/errors.py` (augmentation)

**Analog:** self — `flyer_generator/errors.py` (full file, 73 lines)

**Existing hierarchy** (lines 1-74):
```python
"""Typed exception hierarchy for the flyer generator."""


class FlyerGeneratorError(Exception):
    """Base exception for all flyer generator errors."""

    def __init__(self, message: str, *, trace_id: str = "", **context: object) -> None:
        self.trace_id = trace_id
        self.context = context
        super().__init__(message)


class ConfigurationError(FlyerGeneratorError):
    """Bad settings or missing API key."""


class ComfyError(FlyerGeneratorError):
    """Base for all ComfyCloud errors."""


class ComfySubmitError(ComfyError):
    """4xx/5xx on workflow submit."""


class ComfyJobTimeoutError(ComfyError):
    """Poll max attempts exceeded."""

    def __init__(
        self, message: str, *, prompt_id: str = "", attempts: int = 0, **kwargs: object
    ) -> None:
        super().__init__(message, **kwargs)
        self.prompt_id = prompt_id
        self.attempts = attempts
```

**For the errors.py augmentation (append, don't restructure):**
```python
class BrandKitError(FlyerGeneratorError):
    """Base for all brand-kit errors."""


class BrandKitScrapeError(BrandKitError):
    """Scraper exhausted both Playwright and BS4 paths without usable data."""


class BrandKitContrastError(BrandKitError):
    """Contrast remediation exhausted options with no passing swap."""


class BrandKitAuditError(BrandKitError):
    """Audit loop hit max cycles without clean pass (only raised in strict mode)."""
```

Match the one-line-docstring style. Extra context via `**context` kwargs (inherited from `FlyerGeneratorError.__init__`). Mirror the `ComfyJobTimeoutError` extended-init pattern when a subclass needs typed extras (e.g. `BrandKitAuditError(message, cycles=3, remaining_issues=[...])`).

---

### `flyer_generator/brochure/schema_renderer/__main__.py` (augmentation — `--brand-kit`)

**Analog:** commit `bb52f65` (same file, `--color-accent` addition). Full diff already reviewed.

**Pattern — add flag (after `color_accent` option, lines 114-120 in current file):**
```python
brand_kit: Annotated[
    Optional[str],
    typer.Option(
        "--brand-kit",
        help="Apply a brand kit (scraped site → palette + typography + logo) "
        "loaded from `.brand-kits/<slug>/brand.json`. Overrides --color-accent.",
    ),
] = None,
```

**Pattern — resolve flag before render** (mirror lines 273-291 where `--logo` is resolved then passed):
```python
# Mirror how --logo is resolved before the render_schema_brochure call.
logo_bytes_from_kit: bytes | None = None
if brand_kit is not None:
    from flyer_generator.brand_kit import apply_brand_kit, load_brand_kit
    kit = load_brand_kit(brand_kit)
    if color_accent is not None:
        typer.echo(
            f"Warning: --brand-kit overrides --color-accent ({color_accent} ignored).",
            err=True,
        )
        color_accent = None
    tmpl, logo_bytes_from_kit = apply_brand_kit(tmpl, kit)
    typer.echo(f"Applied brand kit: {brand_kit}")

# Existing --logo explicit path wins over the kit's logo
if logo is not None:
    logo_bytes = logo.read_bytes()
elif logo_bytes_from_kit is not None:
    logo_bytes = logo_bytes_from_kit
```

Then the existing `render_schema_brochure(tmpl, ct, ..., logo_bytes=logo_bytes, accent_override=color_accent)` call picks up the kit'd template transparently.

**Key rules (from CONTEXT.md §CLI integration):**
- `--brand-kit` overrides `--color-accent` (kit wins; warning to stderr).
- Explicit `--logo <path>` overrides `--brand-kit` logo.
- `--brand-kit` + `--prompt` → both active; brief/voice best-effort.
- `--brand-kit` + `--brief-json` → kit layered on top of brief-driven content.

---

### `flyer_generator/brochure/schemas/*.json` (typography uplift)

**Analog:** existing `typography` block in schema (see `schema_model.py:340-352` defaults):
```python
class Typography(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading_family: str = "'Inter', 'Helvetica Neue', sans-serif"
    body_family: str = "'Inter', 'Helvetica Neue', sans-serif"
    cover_title_size: int = 112
    cover_subtitle_size: int = 48
    heading_size: int = 64
    body_size: int = 34
    body_line_height: int = 46
    body_max_chars_per_line: int = 32
    bullet_size: int = 32
    bullet_line_height: int = 44
```

**For the uplift edits:**
- Bump `body_size` from `~34` → `~40` (calibrate against shrubnet-v9 visual gallery).
- Bump `bullet_size` from `~32` → `~36-38`.
- Bump `body_line_height` and `bullet_line_height` proportionally (`body_line_height = round(body_size * 1.28)`).
- Guardrail: run `pytest tests/brochure/schema_renderer/test_gallery.py -q` (78 dynamic cells) — NO hard clipping. `fit_to_bbox` may trigger word-boundary truncation, that's acceptable.
- Touch ALL 13 schemas or explicitly document why any is skipped in the audit/report.

---

### `.brand-kit-template.json` (repo-tracked schema reference)

**Analog:** parallel to `docs/brochure/sample-content/law_firm.json` (reference-shape style). Structurally: the result of `BrandKit(name="Example Brand", ...).model_dump_json(indent=2)` with every optional field filled.

**For the file:**
- Live at repo root.
- Comprehensive example: every field populated (even the optional `voice`/`photography`), one entry in each list, `"hex"` values that are real colors (so docs-reader can paste).
- Add a top-level `"$schema_note": "Shape reference for flyer_generator.brand_kit.BrandKit — regenerate via `BrandKit(...).model_dump_json(indent=2)`"` as a comment-ish marker. **But:** `BrandKit` uses `extra="forbid"`, so you must either (a) omit this note OR (b) add it as a real field. Recommended: omit the `$schema_note`, instead add a README sentence pointing to this file.

---

### `.gitignore` (augmentation)

**Analog:** self — existing `.gitignore` (17 lines).

**Add:**
```
.brand-kits/
```

Match indent + placement style (append after `.pytest_cache/`, single line).

---

### `pyproject.toml` (augmentation)

**Analog:** self — existing `[project] dependencies` block (lines 7-18) and `dev` group (lines 20-26).

**Add to `[project] dependencies`:**
```toml
"beautifulsoup4>=4.14",
"tinycss2>=1.5",
"wcag-contrast-ratio>=0.9",
"coloraide>=8,<9",
```

**Add to `[project.optional-dependencies]` (new group `scrape`, keeps Playwright out of default install):**
```toml
scrape = [
    "playwright>=1.58",
]
```

Or make `playwright` a hard dep if CI always installs Chromium; RESEARCH.md lays out both options.

---

## Test Pattern Assignments

### `tests/brand_kit/test_models.py`

**Analog:** `tests/brochure/schema_renderer/test_loader.py:46-52` (Pydantic round-trip) + `test_text_gen.py` (synthetic template construction).

**Round-trip pattern** (test_loader.py lines 46-52):
```python
def test_load_by_path(tmp_path):
    # Round-trip: serialize a known template, reload from path
    t = load_template("editorial_classic")
    path = tmp_path / "copy.json"
    path.write_text(t.model_dump_json())
    t2 = load_template(str(path))
    assert t2.name == t.name
```

**For test_models.py:**
- `test_brand_kit_round_trip`: construct a `BrandKit` with all fields → `model_dump_json()` → `model_validate_json(raw)` → assert equality.
- `test_partial_brand_kit_validates`: construct with `palette=None`, `typography=None`, `logos=[]`, `voice=None`, `photography=None` → asserts no raise.
- `test_invalid_hex_rejected`: `BrandPalette(primary=ColorUsage(hex="not-a-color", usage_hint=None))` → `pytest.raises(ValidationError)`.
- `test_logo_variant_literal_enforced`: `BrandLogo(variant="wrong_variant", ...)` → ValidationError.
- `test_size_multiplier_bounds`: negative or >3.0 rejected.

---

### `tests/brand_kit/test_scraper.py`

**Analogs:**
- `tests/test_comfy_client.py:1-100` (respx for httpx mocking)
- `tests/brochure/schema_renderer/test_image_gate.py:96-99` (AsyncMock for injected clients)

**respx pattern** (test_comfy_client.py lines 45-66):
```python
@pytest.fixture()
def settings() -> Settings:
    return Settings(
        comfycloud_api_key="test-key-123",
        comfycloud_base_url=BASE_URL,
        ...
    )


@pytest.fixture()
def mock_router():
    with respx.mock(base_url=BASE_URL) as router:
        yield router


@pytest.fixture()
def client(settings: Settings, mock_router: respx.MockRouter) -> ComfyClient:
    http = httpx.AsyncClient(base_url=BASE_URL)
    return ComfyClient(settings=settings, http_client=http)
```

**respx route setup** (test_comfy_client.py lines 78-93):
```python
async def test_submit_posts_workflow_with_api_key(
    client: ComfyClient, mock_router: respx.MockRouter, workflow: MockWorkflow
) -> None:
    """Verify POST /api/prompt is called with correct body and X-API-Key header."""
    route = mock_router.post("/api/prompt").respond(json=SUBMIT_RESPONSE)

    await client.submit(workflow)

    assert route.called
    request = route.calls[0].request
    assert request.headers["X-API-Key"] == "test-key-123"
```

**AsyncMock injection pattern** (test_image_gate.py lines 96-99 + 307-326):
```python
def _comfy_mock(return_bytes: bytes = b"\x89PNG-fake") -> AsyncMock:
    m = AsyncMock()
    m.generate = AsyncMock(return_value=(_job(), return_bytes))
    return m

# Usage:
comfy = AsyncMock()
comfy.generate = AsyncMock(side_effect=flaky_generate)
```

**For test_scraper.py (and split files):**
- `test_scraper_bs4.py` — uses respx fixture. Mock GET of sample site URL → returns `fixtures/sample_site.html`. Mock GET of linked CSS → `fixtures/sample_site.css`. Assert scraped `BrandKit.palette.primary.hex == "#xxxxxx"` per CSS `:root` custom prop. Test null fields when logos absent.
- `test_scraper_playwright.py` — use `unittest.mock.AsyncMock` to stub the whole `playwright.async_api.async_playwright()` context manager. Example skeleton:
  ```python
  from unittest.mock import AsyncMock, MagicMock, patch

  @pytest.mark.asyncio
  async def test_playwright_scrape_extracts_screenshot(monkeypatch):
      fake_page = AsyncMock()
      fake_page.content = AsyncMock(return_value="<html>...</html>")
      fake_page.screenshot = AsyncMock(return_value=b"\x89PNG-screenshot")
      fake_page.evaluate = AsyncMock(side_effect=[...])  # one return per evaluate() call

      fake_browser = AsyncMock()
      fake_browser.new_context = AsyncMock(return_value=AsyncMock(new_page=AsyncMock(return_value=fake_page)))

      fake_playwright = MagicMock()
      fake_playwright.chromium.launch = AsyncMock(return_value=fake_browser)

      # async_playwright() returns a context manager
      fake_cm = AsyncMock()
      fake_cm.__aenter__ = AsyncMock(return_value=fake_playwright)
      fake_cm.__aexit__ = AsyncMock(return_value=None)

      monkeypatch.setattr(
          "flyer_generator.brand_kit.scraper_playwright.async_playwright",
          lambda: fake_cm,
      )
      # ... call scrape_with_playwright("https://example.com") and assert
  ```
- `test_scraper_fallback_graceful`: patch playwright to raise `ImportError` → assert BS4 path engages and returns a kit.

---

### `tests/brand_kit/test_contrast.py`

**Analog:** `tests/brochure/schema_renderer/test_text_fit.py` (pure-function tests).

**Known-pair tests:**
- `test_black_on_white_passes_aaa`: `contrast_ratio("#000000", "#FFFFFF")` → `21.0` (exact).
- `test_same_color_fails`: ratio == 1.0.
- `test_aa_threshold`: ratio == 4.5 boundary.
- `test_remediation_swaps_to_neutral`: given body `#808080` on bg `#AAAAAA` (ratio < 4.5), palette `neutral_dark="#111"`, `neutral_light="#F7F7F5"` → remediation returns `"#111"`.
- `test_remediation_exhausted_returns_flag`: neither neutral passes → returns original + `"exhausted"` note.

---

### `tests/brand_kit/test_applier.py`

**Analog:** `tests/brochure/schema_renderer/test_renderer.py:414-433` (`test_accent_override_replaces_template_default`).

**The exact pattern to mirror** (test_renderer.py lines 414-433):
```python
def test_accent_override_replaces_template_default() -> None:
    """--color-accent / accent_override swaps the palette accent_default."""
    t = load_template("editorial_classic")
    c = _sample_content()
    override = "#AABBCC"
    outside, inside = render_schema_brochure(t, c, accent_override=override)
    combined = outside + inside
    assert override in combined


def test_accent_override_none_preserves_template_default() -> None:
    t = load_template("editorial_classic")
    c = _sample_content()
    outside_default, _ = render_schema_brochure(t, c)
    outside_none, _ = render_schema_brochure(t, c, accent_override=None)
    assert outside_default == outside_none
```

**For test_applier.py:**
- `test_apply_brand_kit_swaps_palette`: construct a kit with `primary.hex="#AABBCC"` → `(new_tmpl, _) = apply_brand_kit(editorial_classic, kit)` → `assert new_tmpl.palette.accent_default == "#AABBCC"`.
- `test_apply_brand_kit_does_not_mutate_input`: `original_json = t.model_dump_json()` before apply; `assert t.model_dump_json() == original_json` after.
- `test_apply_brand_kit_scales_typography_by_multiplier`: kit with `size_multiplier=1.5` → `assert new_tmpl.typography.body_size == round(34 * 1.5)`.
- `test_apply_brand_kit_returns_logo_bytes_from_primary`: kit with `logos=[BrandLogo(variant="primary", ...)]` → assert returned bytes == `(kit_dir/primary_logo).read_bytes()`.
- `test_apply_brand_kit_partial_palette_falls_back_to_template_defaults`: kit with `palette=None` → assert palette fields unchanged.

---

### `tests/brand_kit/test_storage.py`

**Analog:** `tests/brochure/schema_renderer/test_loader.py:46-52` (tmp_path round-trip) + pattern for env-var override.

**tmp_path pattern** (test_loader.py:46-52, already excerpted above).

**For test_storage.py:**
- `test_save_and_load_round_trip(tmp_path, monkeypatch)`:
  ```python
  monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
  kit = BrandKit(name="Test", fetched_at=datetime.now(), ...)
  save_brand_kit(kit, slug="test")
  loaded = load_brand_kit("test")
  assert loaded.model_dump() == kit.model_dump()
  ```
- `test_list_brand_kits_empty_dir(tmp_path, monkeypatch)`: returns `[]`.
- `test_list_brand_kits_alphabetical(tmp_path, monkeypatch)`: three kits, assert sorted.
- `test_load_missing_kit_raises`: `load_brand_kit("nonexistent")` → `FileNotFoundError`.

---

### `tests/brand_kit/test_audit.py`

**Analog:** `tests/brochure/schema_renderer/test_image_gate.py` (orchestrator + verdict structure + soft-fail).

**For test_audit.py:**
- Build a synthetic `TemplateSchema` + `BrochureContent` + hand-rolled Pillow PNG with known whitespace (128×128 solid white → density ratio near 1.0).
- `test_audit_reports_whitespace_on_empty_panel`: assert `report.whitespace[panel_id] > 0.9`.
- `test_audit_flags_low_contrast_pair`: synthesize text `#AAAAAA` on bg `#BBBBBB` → `report.contrast.overall_aa_pass == False`.
- `test_audit_density_under_budget`: content with 10 chars in a 100-char budget → `report.density[key] ≈ 0.1`.
- `test_iterate_loop_converges`: stub rewrite path so cycle 2 returns AA-clean; assert `final.issues == []` and `cycle == 1`.
- `test_iterate_loop_exhausts_gracefully`: unreachable state, 3 cycles, `strict=False` → no raise, final report has issues.
- `test_iterate_loop_strict_raises`: same but `strict=True` → `pytest.raises(BrandKitAuditError)`.

---

### `tests/brand_kit/test_cli.py`

**Analog:** no existing typer CliRunner test in the repo — this is net-new. Reference shape:

```python
from typer.testing import CliRunner
from flyer_generator.brand_kit.__main__ import app

runner = CliRunner()


def test_list_no_kits(tmp_path, monkeypatch):
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""


def test_show_unknown_slug_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
    result = runner.invoke(app, ["show", "missing"])
    assert result.exit_code != 0


def test_fetch_calls_scraper(monkeypatch):
    # Patch scraper to a stub; assert it was called with the URL
    import flyer_generator.brand_kit.__main__ as cli_mod

    called = {}
    async def fake_fetch(url, slug, **kwargs):
        called["url"] = url
        called["slug"] = slug
        return BrandKit(name=slug, source_url=url, fetched_at=datetime.now(), ...)

    monkeypatch.setattr(cli_mod, "fetch_brand_kit", fake_fetch)
    result = runner.invoke(app, ["fetch", "https://example.com", "--slug", "ex"])
    assert result.exit_code == 0
    assert called["url"] == "https://example.com"
    assert called["slug"] == "ex"
```

---

### `tests/brand_kit/test_integration.py`

**Analog:** `tests/brochure/schema_renderer/test_image_gate.py:182-201` (happy-path orchestration with mocks).

**For test_integration.py:**
- Load a saved kit from `tests/brand_kit/fixtures/` → apply to `editorial_classic` → call `render_schema_brochure` → rasterize → run `audit_render` → assert `overall_aa_pass == True` AND `len(issues) == 0`.
- Skip or mark `@pytest.mark.slow` if the render is >2s in CI.

---

## Shared Patterns

### 1. Pydantic v2 model_config (every new model)

**Source:** `flyer_generator/brochure/schema_renderer/schema_model.py:69`, `content_model.py:117`, and 20+ other sites.

**Apply to:** every Pydantic class in `brand_kit/models.py`, `contrast.py`, `audit.py`.

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator

class MyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...
```

**Never** use `class Config:` (Pydantic v1 style). **Never** use `class Config(BaseModel.Config):`. Always `model_config = ConfigDict(...)`.

### 2. Hex color validation

**Source:** `flyer_generator/brochure/models.py:34-39` (`validate_hex_color`).

**Apply to:** every hex field on every brand_kit model.

```python
from flyer_generator.brochure.models import validate_hex_color

class ColorUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hex: str
    usage_hint: str | None = None

    @field_validator("hex")
    @classmethod
    def _validate_hex(cls, v: str) -> str:
        return validate_hex_color(v)
```

### 3. Async httpx client with 180s timeout + ownership flag

**Source:** `flyer_generator/brochure/schema_renderer/image_gate.py:188-198` + `finally` at 277-279.

**Apply to:** `scraper.py` (primary fetch + font download), wherever `httpx.AsyncClient` is constructed in-function without an injected `http_client`.

```python
_owns_http = False
if http_client is None:
    http_client = httpx.AsyncClient(follow_redirects=True, timeout=180.0)
    _owns_http = True
try:
    # ... async work ...
finally:
    if _owns_http and http_client is not None:
        await http_client.aclose()
```

### 4. Retry on transient error via `continue`, not `break`

**Source:** `image_gate.py:212-232` (commit `3512a35` rationale).

**Apply to:** scraper.py (Playwright → BS4 fallthrough), audit.py (regenerate-then-reaudit loop).

Never `break` out of a retry loop on a transient error — log a `logger.warning` with `error_type=type(err).__name__` and `continue`.

### 5. structlog trace_id bind at orchestration boundary

**Source:** `flyer_generator/brochure/pipeline.py:76-77`, `flyer_generator/brochure/generative/pipeline.py:191-192`.

**Apply to:** `fetch_brand_kit` (scraper orchestrator), `iterate_audit_loop` (audit orchestrator).

```python
import uuid
import structlog

logger = structlog.get_logger()

async def fetch_brand_kit(url: str, slug: str, ...) -> BrandKit:
    trace_id = uuid.uuid4().hex
    log = logger.bind(trace_id=trace_id, url=url, slug=slug)
    log.info("brand_kit_fetch_start")
    ...
```

Sub-calls can read from `log` passed as a kwarg, or re-bind with `log.bind(stage="playwright")`.

### 6. Typed exception with trace_id + context kwargs

**Source:** `flyer_generator/errors.py:4-10`.

**Apply to:** every `raise` inside `brand_kit/*`:

```python
from flyer_generator.errors import BrandKitScrapeError

raise BrandKitScrapeError(
    "both playwright and bs4 scraping failed",
    trace_id=trace_id,
    url=url,
    playwright_error=pw_err_str,
    bs4_error=bs4_err_str,
)
```

### 7. Immutable transforms via `model_copy(deep=True)` or `model_copy(update={...})`

**Source:** `renderer.py:752-759` (accent_override), `content_model.py` round-trips.

**Apply to:** `applier.apply_brand_kit`. Always return a fresh `TemplateSchema` — never mutate in place.

```python
new_tmpl = template.model_copy(
    update={
        "palette": template.palette.model_copy(update={"accent_default": kit.palette.primary.hex}),
        "typography": template.typography.model_copy(update={"body_size": round(template.typography.body_size * kit.size_multiplier)}),
    }
)
```

### 8. Async-in-sync typer bridge

**Source:** `schema_renderer/__main__.py:205-214` and `243-250`.

**Apply to:** `brand_kit/__main__.py` `fetch` command.

```python
@app.command()
def fetch(url: str, slug: str = typer.Option(..., "--slug")) -> None:
    kit = asyncio.run(fetch_brand_kit(url=url, slug=slug))
    typer.echo(f"Saved kit to .brand-kits/{slug}/")
```

### 9. Filesystem I/O via Path.read_text / write_text with explicit encoding

**Source:** `loader.py:31` (`path.read_text(encoding="utf-8")`) and `schema_renderer/__main__.py:225-226`, 294-295.

**Apply to:** `storage.py`, `audit.py`, everywhere file I/O happens.

```python
path.read_text(encoding="utf-8")
path.write_text(kit.model_dump_json(indent=2), encoding="utf-8")
```

### 10. Test async with `pytest.mark.asyncio` + `AsyncMock` injection

**Source:** `tests/brochure/schema_renderer/test_image_gate.py:181-201`, test_text_gen.py:232-247.

Plus global `asyncio_mode = "auto"` in `pyproject.toml:36`. That means `@pytest.mark.asyncio` is often redundant — tests work with plain `async def test_*`. But existing test files use `@pytest.mark.asyncio` anyway for visual clarity; mirror that.

### 11. Test HTTP with respx

**Source:** `tests/test_comfy_client.py:45-92`. Already in `dev` deps (`respx>=0.22.0`).

**Apply to:** BS4 scraper tests (mock GET of URL + linked CSS files).

### 12. Test CLI with `typer.testing.CliRunner`

**Source:** no existing analog in this repo. Recommended new pattern (documented in Test Pattern Assignments above).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `flyer_generator/brand_kit/contrast.py` (remediation loop internal to `coloraide` OKLCH traversal) | utility | transform | No existing color-science code in the repo. Build from scratch guided by RESEARCH.md §Pattern 2 + `coloraide` 8.8.1 docs. |
| `tests/brand_kit/test_cli.py` | test | request-response | No existing typer CliRunner tests in this repo. Pattern sketched above is net-new. |
| `.brand-kit-template.json` | config-data | static | First tracked "reference schema JSON" in the repo. `docs/brochure/sample-content/*.json` are example *content*, not schema shape references. Treat as a new concept but model shape via `BrandKit(...).model_dump_json(indent=2)`. |

---

## Metadata

**Analog search scope:**
- `/home/hoyack/work/autocreative/flyer_generator/brochure/schema_renderer/` (10 modules — primary analog source)
- `/home/hoyack/work/autocreative/flyer_generator/errors.py` (exception hierarchy)
- `/home/hoyack/work/autocreative/flyer_generator/config.py` (pydantic-settings pattern)
- `/home/hoyack/work/autocreative/flyer_generator/brochure/__main__.py` and `flyer_generator/__main__.py` (typer patterns)
- `/home/hoyack/work/autocreative/tests/brochure/schema_renderer/` (test patterns: models, mocking, async)
- `/home/hoyack/work/autocreative/tests/test_comfy_client.py` and `/home/hoyack/work/autocreative/tests/test_vision.py` (respx patterns)

**Files scanned:** 23 source files, 6 test files, 2 config files (pyproject.toml, .gitignore).

**Pattern extraction date:** 2026-04-20.

## PATTERN MAPPING COMPLETE
