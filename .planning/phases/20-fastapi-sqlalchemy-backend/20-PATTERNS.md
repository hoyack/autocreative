# Phase 20: FastAPI + SQLAlchemy Backend — Pattern Map

**Mapped:** 2026-04-22
**Files analyzed:** 27 new files (22 under `flyer_generator/api/`, 2 under `alembic/`, plus `docker-compose.yml`, `Procfile`, root-level settings) + 3 modified files (`flyer_generator/errors.py`, `flyer_generator/logging_config.py`, `pyproject.toml`) + 9 new test files under `tests/api/`
**Analogs found:** 18 / 27 new files have a strong or partial in-repo analog. 9 files are green-field (no existing FastAPI, no existing SQLAlchemy/Alembic anywhere in the repo).

## File Classification

### New runtime source files

| New file | Role | Data flow | Closest analog | Match quality |
|----------|------|-----------|----------------|---------------|
| `flyer_generator/api/__init__.py` | subsystem barrel + FastAPI app factory | request-response | `flyer_generator/social/__init__.py` | role-match (barrel only) |
| `flyer_generator/api/config.py` | pydantic-settings extension | config | `flyer_generator/config.py` | **exact** |
| `flyer_generator/api/db.py` | engine + sessionmaker + dep | request-response | none (no existing SQLAlchemy) | green-field |
| `flyer_generator/api/deps.py` | FastAPI dependency factories (arq pool, settings) | request-response | none (no existing FastAPI) | green-field |
| `flyer_generator/api/errors.py` | exception-handler registry | request-response | `flyer_generator/errors.py` (hierarchy only) | partial — handler side is green-field |
| `flyer_generator/api/lifespan.py` | async context manager — app startup/shutdown | request-response | none | green-field |
| `flyer_generator/api/middleware.py` | CORS + correlation-id wiring | request-response | none | green-field |
| `flyer_generator/api/models/__init__.py` | ORM models barrel | N/A | `flyer_generator/social/__init__.py` | role-match (barrel only) |
| `flyer_generator/api/models/base.py` | `DeclarativeBase` + shared types | N/A | none | green-field |
| `flyer_generator/api/models/brand_kit.py` | ORM model | CRUD | `flyer_generator/brand_kit/models.py` (field shape only) | partial — field names mirror, but ORM idiom is new |
| `flyer_generator/api/models/flyer.py` | ORM model | CRUD | `flyer_generator/models.py` `FlyerOutput` (field shape only) | partial |
| `flyer_generator/api/models/brochure.py` | ORM model | CRUD | `flyer_generator/brochure/schema_renderer/content_model.py` | partial |
| `flyer_generator/api/models/social.py` | ORM models (Campaign+Post) | CRUD | `flyer_generator/social/models.py` | partial |
| `flyer_generator/api/models/render.py` | ORM model | CRUD | none | green-field |
| `flyer_generator/api/models/job.py` | ORM model + `JobKind`/`JobStatus` enums | event-driven | none | green-field |
| `flyer_generator/api/routes/__init__.py` | router registration | request-response | `flyer_generator/social/__init__.py` | role-match |
| `flyer_generator/api/routes/brand_kits.py` | REST route set | request-response | none (no existing FastAPI) | green-field — mirror `flyer_generator/brand_kit/__main__.py` CLI shape |
| `flyer_generator/api/routes/flyers.py` | REST route | request-response | none | green-field — mirror `flyer_generator/__main__.py` CLI shape |
| `flyer_generator/api/routes/brochures.py` | REST route set | request-response | none | green-field |
| `flyer_generator/api/routes/social.py` | REST route set (posts + campaigns) | request-response | `flyer_generator/social/__main__.py` | role-match (CLI→route translation) |
| `flyer_generator/api/routes/jobs.py` | REST polling route | request-response | none | green-field |
| `flyer_generator/api/routes/renders.py` | streaming-file route | file-I/O / request-response | `flyer_generator/brand_kit/storage.py::_validate_containment` | partial — path-traversal pattern reusable |
| `flyer_generator/api/schemas/__init__.py` | Pydantic schemas barrel | N/A | `flyer_generator/social/models.py` | role-match |
| `flyer_generator/api/schemas/{brand_kits,flyers,brochures,social,jobs}.py` | API Pydantic v2 request/response schemas | request-response | `flyer_generator/models.py` `EventInput` / `flyer_generator/social/models.py` `PostBrief` | **exact** (idiom mirror; many models reused verbatim) |
| `flyer_generator/api/tasks/__init__.py` | arq task registry (list of callables) | event-driven | none | green-field |
| `flyer_generator/api/tasks/brand_kit.py` | arq task wrapping `fetch_brand_kit` | event-driven / async | `flyer_generator/pipeline.py` `FlyerGenerator.generate` | role-match (async orchestrator wrapping) |
| `flyer_generator/api/tasks/flyer.py` | arq task wrapping `FlyerGenerator.generate` | event-driven / async | `flyer_generator/pipeline.py` `FlyerGenerator.generate` | **exact** (thin wrapper) |
| `flyer_generator/api/tasks/brochure.py` | arq task wrapping `generate_template_images` + `render_schema_brochure` | event-driven (mixed async/sync) | `flyer_generator/brochure/schema_renderer/image_gate.py::generate_template_images` | **exact** (wrapped caller) |
| `flyer_generator/api/tasks/post.py` | arq task wrapping `generate_post` | event-driven / async | `flyer_generator/social/generator.py::generate_post` | **exact** |
| `flyer_generator/api/tasks/campaign.py` | arq task wrapping `generate_campaign` | event-driven / async | `flyer_generator/social/campaign.py::generate_campaign` | **exact** |
| `flyer_generator/api/worker.py` | arq `WorkerSettings` class + `on_startup`/`on_shutdown` | event-driven | none | green-field |
| `alembic.ini` | Alembic config | config | none | green-field |
| `alembic/env.py` | async migration runner | config / request-response | none | green-field |
| `alembic/versions/0001_initial_schema.py` | initial migration | CRUD (schema creation) | none | green-field (will be `alembic revision --autogenerate`-generated) |
| `docker-compose.yml` | postgres + redis services | config | none | green-field |
| `Procfile` | two-process dev launcher | config | none | green-field |

### Modified files

| Modified file | Role | Change | Analog pattern |
|---------------|------|--------|----------------|
| `flyer_generator/errors.py` | error hierarchy | **add `BrandKitNotFoundError(BrandKitError)`** | follow existing `BrandKitScrapeError(BrandKitError)` sibling class pattern (lines 127-129) |
| `flyer_generator/logging_config.py` | structlog configuration | **insert `_add_correlation` processor** before renderer | insert into `shared_processors` list at current line 13-17 (existing processor-list shape) |
| `pyproject.toml` | dependencies | **add 8 deps + `prod` optional-extra + `honcho` to dev** | existing `[project.optional-dependencies]` section is the insertion point |

### New test files

| New test file | Role | Closest analog | Match quality |
|---------------|------|----------------|---------------|
| `tests/api/__init__.py` | package marker | `tests/social/__init__.py` | exact |
| `tests/api/conftest.py` | `engine`, `app`, `client` fixtures | `tests/social/test_integration.py` (mock-client pattern); `tests/test_llm_resilience.py` (respx + async httpx.AsyncClient) | **exact** for respx; **green-field** for ASGI transport + in-memory SQLite |
| `tests/api/test_app_smoke.py` | smoke | `tests/test_public_api.py` | role-match |
| `tests/api/test_error_mapping.py` | exception-handler tests | `tests/test_llm_resilience.py` | partial |
| `tests/api/test_brand_kits_routes.py` | REST integration | `tests/social/test_integration.py` | role-match |
| `tests/api/test_flyer_routes.py` | REST integration | `tests/social/test_integration.py` | role-match |
| `tests/api/test_brochure_routes.py` | REST integration | `tests/social/test_integration.py` | role-match |
| `tests/api/test_social_routes.py` | REST integration | `tests/social/test_integration.py` | **exact** (mocked LLM + Comfy fakes directly reusable) |
| `tests/api/test_jobs_routes.py` | job-polling tests | none | green-field |
| `tests/api/test_renders_routes.py` | streaming-file tests | none | green-field (path-traversal defense mirrors brand_kit storage tests) |
| `tests/api/test_worker_tasks.py` | task-function-direct-invocation tests | `tests/social/test_campaign.py` (async test with `_FakeComfy` + `_FakeTextClient`) | **exact** |

---

## Pattern Assignments

### `flyer_generator/api/config.py` — pydantic-settings extension (EXACT match)

**Analog:** `flyer_generator/config.py` (entire file is the template)

**Why this is exact:** `AppSettings` is just new `FLYER_`-prefixed fields added alongside the existing 25 fields. Same `SettingsConfigDict(env_prefix="FLYER_", env_file=".env")`. The existing `Settings` must remain importable verbatim because every generator module (`pipeline.py`, `brand_kit/scraper.py`, `social/generator.py`, …) instantiates it directly.

**Concrete model-config + imports excerpt to copy** (`flyer_generator/config.py:1-22`):
```python
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from FLYER_-prefixed environment variables.
    ...
    """

    model_config = SettingsConfigDict(
        env_prefix="FLYER_",
        env_file=".env",
        env_file_encoding="utf-8",
    )
```

**SecretStr field pattern** (`flyer_generator/config.py:25-27, 42-45`):
```python
# API keys (SecretStr masks values in logs/repr)
anthropic_api_key: SecretStr = SecretStr("")
comfycloud_api_key: SecretStr = SecretStr("")
comfycloud_base_url: str = "https://cloud.comfy.org"
```
→ New `AppSettings` mirrors this for any future secrets (none planned in Phase 20 — Redis URL and DB URL are not secrets).

**List-from-CSV field pattern** (`flyer_generator/config.py:50-55`):
```python
ollama_text_model_fallbacks: list[str] = Field(
    default_factory=lambda: ["kimi-k2.6:cloud"]
)
```
→ Use this idiom for `cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])`. Pydantic-settings parses `FLYER_CORS_ORIGINS="http://a,http://b"` into the list automatically.

**Path-field pattern** (`flyer_generator/config.py:75-79`):
```python
output_dir: Path = Path("./output")
brand_kits_dir: Path = Path(".brand-kits")
social_campaigns_dir: Path = Path(".social-campaigns")
```
→ `artifact_root_flyer: Path = Path("./output/flyers")` and `artifact_root_brochure: Path = Path("./output/brochures")` follow the same shape. The existing `brand_kits_dir` and `social_campaigns_dir` are already correct — `AppSettings` does not need to redeclare them; instead **have `AppSettings` inherit from `Settings`** so every existing field (and its env var) is still accessible.

**Recommended extension strategy:**
```python
# flyer_generator/api/config.py
from pathlib import Path
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from flyer_generator.config import Settings


class AppSettings(Settings):
    """Phase 20 API layer settings. Inherits every existing FLYER_* knob."""

    model_config = SettingsConfigDict(
        env_prefix="FLYER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # existing Settings fields won't clash
    )

    database_url: str = "sqlite+aiosqlite:///./flyer.db"
    redis_url: str = "redis://localhost:6379"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    artifact_root_flyer: Path = Path("./output/flyers")
    artifact_root_brochure: Path = Path("./output/brochures")
```

**Testing analog:** `tests/test_config.py:17-20` shows the `monkeypatch.setenv("FLYER_MAX_BG_ATTEMPTS", "5")` pattern to assert env overrides land on the parsed model.

---

### `flyer_generator/errors.py` (MODIFIED) — add `BrandKitNotFoundError`

**Analog:** the sibling class `BrandKitScrapeError` right next to the insertion point

**Why:** Open Question Q1 in RESEARCH.md recommends this. The error table in CONTEXT.md references `BrandKitNotFoundError` but it doesn't exist yet. Adding a subclass is a 2-line change and keeps the exception-handler mapping symmetric.

**Concrete pattern to copy** (`flyer_generator/errors.py:123-133`):
```python
class BrandKitError(FlyerGeneratorError):
    """Base for all brand-kit errors."""


class BrandKitScrapeError(BrandKitError):
    """Scraper exhausted both Playwright and BS4 paths without usable data."""


class BrandKitContrastError(BrandKitError):
    """Contrast remediation exhausted options with no passing swap."""
```

**New class to insert after `BrandKitError`:**
```python
class BrandKitNotFoundError(BrandKitError):
    """Requested brand-kit slug does not resolve to a stored kit."""
```
→ Then `flyer_generator/brand_kit/storage.py::load_brand_kit` (current line 139-143, which raises `FileNotFoundError`) should be updated to raise `BrandKitNotFoundError` instead — matching callers that catch `BrandKitError` continue to work because `BrandKitNotFoundError` is a subclass.

**Context-kwarg pattern that all errors use** (`flyer_generator/errors.py:7-10`):
```python
def __init__(self, message: str, *, trace_id: str = "", **context: object) -> None:
    self.trace_id = trace_id
    self.context = context
    super().__init__(message)
```
→ `BrandKitNotFoundError` inherits this for free; callers can raise `BrandKitNotFoundError("kit not found", slug=slug, available=available)`.

---

### `flyer_generator/logging_config.py` (MODIFIED) — insert correlation-id processor

**Analog:** the existing `shared_processors` list composition (same file, lines 13-17)

**Why this is one-line-insert, not rewrite:** RESEARCH.md Pitfall 10 ("structlog's `add_log_level` already present — don't double-add") is exactly the trap to avoid. The existing chain must be preserved; only `_add_correlation` gets inserted.

**Current processor chain** (`flyer_generator/logging_config.py:13-22`):
```python
shared_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
]

if log_format == "json":
    shared_processors.append(structlog.processors.JSONRenderer())
else:
    shared_processors.append(structlog.dev.ConsoleRenderer())
```

**Insertion strategy:** `structlog.contextvars.merge_contextvars` is already line 14 — it pulls `correlation_id`'s contextvar into the event dict automatically. The `_add_correlation` helper from RESEARCH.md Pattern 8 is belt-and-suspenders; include it or rely on `merge_contextvars` alone — planner's pick. Either way, the insertion point is right after line 14, and the function `configure_logging` must not rewrite the entire function.

**Module structure reference** (keep the existing shape):
```python
def configure_logging(log_format: str = "text", log_level: str = "INFO") -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,  # <- already reads correlation_id
        # _add_correlation would go here if used
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    # ... renderer append, structlog.configure(...)
```

---

### `flyer_generator/api/models/{brand_kit,flyer,brochure,social,render,job}.py` — ORM models

**Analog (shape only):** the Pydantic v2 models under `flyer_generator/{brand_kit,social}/models.py` — use them as the **source of truth** for which fields to persist. The ORM syntax itself is green-field.

**Pydantic `ConfigDict(extra="forbid")` idiom** the Phase 20 models mirror for completeness (`flyer_generator/social/models.py:24-32`):
```python
class ImageAspect(BaseModel):
    """A single recommended image aspect for a platform."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    aspect_ratio: float = Field(gt=0.0)
    role: ImageRole
```

**Literal-as-enum pattern** (`flyer_generator/social/models.py:18-20`):
```python
Platform = Literal["linkedin", "twitter", "instagram", "facebook"]
Intent = Literal["announcement", "value-prop", "testimonial"]
```
→ For DB enums Phase 20 uses `str, enum.Enum` (RESEARCH.md Pattern "JobRecord with enums and ULID") **so `model_dump(mode="json")` emits the string value, not `"JobStatus.RUNNING"`**. Planner: keep `Literal` aliases in Pydantic API schemas (request bodies) but use `enum.Enum` in ORM column types. They interop cleanly because both serialize to the same string.

**Green-field ORM specifics (no in-repo analog):** copy RESEARCH.md §"Code Examples" verbatim for the `RenderRecord` (lines 823-840) and `JobRecord` (lines 846-881) sketches. Ensure each ORM file imports `Base` from `flyer_generator.api.models.base` and uses `Mapped[...]` + `mapped_column(...)` for every column (SQLAlchemy 2.0 idiom).

---

### `flyer_generator/api/schemas/*.py` — Pydantic request/response schemas (EXACT match)

**Analog:** `flyer_generator/models.py::EventInput`, `flyer_generator/social/models.py::PostBrief`, `flyer_generator/brochure/schema_renderer/content_model.py::BrochureContent`

**Why this is exact:** RESEARCH.md §"Summary" §Architectural Responsibility Map notes: *"Existing `EventInput` / `PostBrief` / `BrochureContent` are already Pydantic v2 — reuse as request bodies."* The API `schemas/` directory holds **wrapper** models that compose these (e.g. `FlyerCreateRequest` bundles `event: EventInput` with optional `brand_kit_slug: str | None`).

**EventInput definition to import verbatim** (`flyer_generator/models.py:27-48`):
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

**Wrapper-schema idiom to apply in Phase 20:**
```python
# flyer_generator/api/schemas/flyers.py
from pydantic import BaseModel, ConfigDict, Field
from flyer_generator.models import EventInput


class FlyerCreateRequest(BaseModel):
    """Body of POST /api/v1/flyers."""

    model_config = ConfigDict(extra="forbid")

    event: EventInput
    brand_kit_slug: str | None = Field(default=None, max_length=64)
    max_bg_attempts: int | None = Field(default=None, ge=1, le=10)


class JobCreated(BaseModel):
    """Response body for any async-job-starting endpoint."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
```

Reuse `PostBrief` (`flyer_generator/social/models.py`) verbatim as the body for `POST /api/v1/social/posts`; reuse `BrochureContent` as the body for `POST /api/v1/brochures`; reuse `BrandKit` (`flyer_generator/brand_kit/models.py`) as the response model for `GET /api/v1/brand-kits/{slug}`.

---

### `flyer_generator/api/tasks/flyer.py` — arq task wrapping `FlyerGenerator.generate` (EXACT)

**Analog:** `flyer_generator/pipeline.py::FlyerGenerator` (the object the task wraps)

**Key excerpt — constructor parameters that must flow from `ctx`** (`flyer_generator/pipeline.py:35-49`):
```python
def __init__(
    self,
    settings: Settings,
    presets: PresetRegistry | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> None:
    self.settings = settings

    if presets is None:
        presets = build_default_registry()

    self._owns_http = False
    if http_client is None:
        http_client = httpx.AsyncClient(follow_redirects=True)
        self._owns_http = True
```
→ The worker owns a long-lived `httpx.AsyncClient` via `ctx["http_client"]` (set up in `on_startup`, RESEARCH.md Pattern 3). The task constructs `FlyerGenerator(ctx["settings"], http_client=ctx["http_client"])` so the client is shared across jobs. The `_owns_http` flag remains `False`.

**Trace-id + logger.bind() pattern to mirror** (`flyer_generator/pipeline.py:72-75`):
```python
trace_id = uuid.uuid4().hex
logger: structlog.stdlib.BoundLogger = get_logger().bind(
    trace_id=trace_id, event_title=event.title
)
```
→ In the arq task, **do NOT generate a new trace_id** — use `job_id` from the task arguments. But the bind-pattern is identical: `log = get_logger().bind(job_id=job_id, kind="flyer")`.

**Full task shape** is given in RESEARCH.md §Pattern 4 (lines 329-395) — planner should copy that sketch with minor edits (`FlyerRecord(... )` placeholder filled in with actual columns; `comfy_job_id` sourced from the generator's returned `FlyerOutput.final_vision_verdict` or via a pipeline-level change in a later phase).

---

### `flyer_generator/api/tasks/brand_kit.py` — arq task wrapping `fetch_brand_kit`

**Analog:** `flyer_generator/brand_kit/scraper.py::fetch_brand_kit` (line 274)

**Function signature the task must call** (`flyer_generator/brand_kit/scraper.py:274-281`):
```python
async def fetch_brand_kit(
    url: str,
    slug: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    base_dir: Path | None = None,
    force: bool = False,
) -> BrandKit:
```
→ Task passes `ctx["http_client"]` directly; `base_dir` comes from `ctx["settings"].brand_kits_dir`. Returned `BrandKit` is `model_dump(mode="json")`-ed into `BrandKitRecord.palette/typography/voice` JSON columns.

**Error translation in the task** — existing behavior (`flyer_generator/brand_kit/scraper.py:297-303`):
```python
if not ok:
    raise BrandKitScrapeError(
        "url blocked by SSRF policy",
        trace_id=trace_id,
        url=url,
        reason=reason,
    )
```
→ In the task, this propagates up naturally. The `except FlyerGeneratorError` handler in the task's state-transition block (RESEARCH.md Pattern 4, lines 382-394) catches it and writes `JobRecord.status=FAILED` + `error_detail={"type": "BrandKitScrapeError", "message": str(err)}`.

---

### `flyer_generator/api/tasks/brochure.py` — arq task wrapping brochure subsystem

**Analogs:** `flyer_generator/brochure/schema_renderer/image_gate.py::generate_template_images` (line 197, async) AND `flyer_generator/brochure/schema_renderer/renderer.py::render_schema_brochure` (line 724, **sync**)

**RESEARCH.md Open Question Q2** explicitly calls this out: the second call is synchronous. The task must wrap it in `asyncio.to_thread(...)`:
```python
# Async call — existing:
images = await generate_template_images(template, content, http_client=ctx["http_client"], ...)
# Sync call — wrap in to_thread:
outside_svg, inside_svg = await asyncio.to_thread(
    render_schema_brochure, template, content, images=images, ...
)
```

**Signature of the sync call** (`flyer_generator/brochure/schema_renderer/renderer.py:724-732`):
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
```

---

### `flyer_generator/api/tasks/post.py` + `campaign.py` — arq tasks wrapping social subsystem (EXACT)

**Analog:** `flyer_generator/social/generator.py::generate_post` (line 98) and `flyer_generator/social/campaign.py::generate_campaign` (line 125).

**Signature the post task calls** (`flyer_generator/social/generator.py:98-108`):
```python
async def generate_post(
    brief: PostBrief,
    brand_kit: BrandKit,
    *,
    template: PostTemplate | None = None,
    settings: Settings | None = None,
    text_client: Any | None = None,
    comfy_client: Any | None = None,
    audit: bool = False,
    style_preset: str = "social_graphic",
) -> Post:
```
→ Task-side invocation: `await generate_post(brief, kit, settings=ctx["settings"], audit=True)`. The `text_client` + `comfy_client` params are test injection hooks — they stay `None` in production. `kit` is re-hydrated via `load_brand_kit(body.brand_kit_slug)`.

**Trace-id bind pattern** (`flyer_generator/social/generator.py:113-118`):
```python
trace_id = uuid.uuid4().hex
log = logger.bind(
    trace_id=trace_id,
    platform=brief.platform,
    intent=brief.intent,
    topic=brief.topic[:40],
)
```
→ Reuse this inside the task with `job_id` added to the bind dict.

---

### `flyer_generator/api/routes/renders.py` — path-traversal-safe artifact streaming

**Analog for the containment check:** `flyer_generator/brand_kit/storage.py::_validate_containment` (lines 49-75)

**Concrete excerpt to copy** (`flyer_generator/brand_kit/storage.py:49-75`):
```python
def _validate_containment(kit_dir: Path, base: Path) -> None:
    """Guard against path traversal + unsafe system paths.

    Either the resolved kit_dir must be inside CWD or inside Path.home(),
    OR the env var FLYER_BRAND_KITS_ALLOW_SYSTEM=1 must be set explicitly.
    """
    if os.environ.get(_ALLOW_SYSTEM_ENV) == "1":
        return
    resolved = kit_dir.resolve()
    cwd = Path.cwd().resolve()
    home = Path.home().resolve()
    try:
        resolved.relative_to(cwd)
        return
    except ValueError:
        pass
    try:
        resolved.relative_to(home)
        return
    except ValueError:
        pass
    raise BrandKitError(
        "resolved brand-kit path is outside CWD and HOME; "
        f"set {_ALLOW_SYSTEM_ENV}=1 to override",
        resolved=str(resolved),
        base=str(base),
    )
```

**Adaptation for the renders route** (RESEARCH.md Pattern 6, lines 458-506): **do not copy verbatim**. The brand-kit version raises a domain error; the renders route translates failures into `HTTPException(404)` **so the filesystem shape is not leaked**. The key idiom to reuse is the `Path.resolve(strict=True).relative_to(root.resolve(strict=True))` containment check. Every traversal attempt → 404, not 500, not error text.

**Slug-regex pattern to copy for any `{slug}` path param validation:** `flyer_generator/brand_kit/storage.py:26`:
```python
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
```
→ Route handlers for `/brand-kits/{slug}` use this regex via `Path(..., pattern=r"^[a-z0-9][a-z0-9-]*$")` in the FastAPI signature, or Pydantic `constr(pattern=...)`. This is the same regex Phase 18 storage already enforces, so the API surface is guaranteed consistent with the filesystem.

---

### `flyer_generator/api/routes/social.py` — CLI→route translation (role-match)

**Analog:** `flyer_generator/social/__main__.py` — the typer CLI already maps every subsystem operation to a public call

**Typer command → FastAPI route translation pattern.** Existing CLI `post` command (`flyer_generator/social/__main__.py:43-117`):
```python
@app.command()
def post(
    brand_kit: Annotated[str, typer.Option("--brand-kit", ...)],
    platform: Annotated[str, typer.Option("--platform", ...)],
    intent: Annotated[str, typer.Option("--intent", ...)],
    topic: Annotated[str, typer.Option("--topic", ...)],
    # ...
) -> None:
    """Generate one post and write artifacts under --output."""
    try:
        kit = load_brand_kit(brand_kit)
    except BrandKitError as err:
        typer.echo(f"Error loading brand kit: {err}", err=True)
        raise typer.Exit(2) from err

    cid = campaign_id or str(ULID())
    brief = PostBrief(topic=topic, intent=intent, platform=platform, ...)
    try:
        post_obj = asyncio.run(
            generate_post(brief, kit, audit=audit, style_preset=style_preset)
        )
    except SocialError as err:
        typer.echo(f"Error: {err}", err=True)
```

**FastAPI route equivalent (Phase 20 target):**
```python
# flyer_generator/api/routes/social.py
@router.post("/social/posts", status_code=status.HTTP_202_ACCEPTED, response_model=JobCreated)
async def create_post(
    body: PostBrief,                       # reused verbatim — no new schema
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JobCreated:
    job_id = str(ULID())
    session.add(JobRecord(
        id=job_id, kind=JobKind.SOCIAL_POST, status=JobStatus.QUEUED,
        input_payload=body.model_dump(mode="json"),
    ))
    await session.commit()
    await request.app.state.arq_pool.enqueue_job(
        "task_generate_post", job_id=job_id, payload=body.model_dump(mode="json"),
    )
    return JobCreated(job_id=job_id)
```
→ The CLI's `load_brand_kit(brand_kit)` step moves **inside** `task_generate_post`, not in the route. The route only enqueues. Errors raised by the task map through exception handlers (see Shared Patterns §Error Handling).

---

### `flyer_generator/api/__init__.py` — subsystem barrel + app factory

**Analog (barrel portion):** `flyer_generator/social/__init__.py` (sorted `__all__` list, explicit `from ... import ...` lines)

**Barrel shape** (`flyer_generator/social/__init__.py:15-80`):
```python
from __future__ import annotations

# Audit
from flyer_generator.social.audit import SocialAuditReport, audit_post

# Campaign orchestrator
from flyer_generator.social.campaign import generate_campaign

# Single-post orchestrator
from flyer_generator.social.generator import generate_post

# Data models
from flyer_generator.social.models import (
    Campaign, ImageAspect, Intent, Platform,
    PlatformRules, Post, PostBrief, PostCopy,
    PostSpec, ValidationIssue, ValidationReport,
)
# ... more sub-imports ...

__all__ = sorted([
    "Campaign", "ImageAspect", "ImageSlot", ...
])
```

**`flyer_generator/api/__init__.py` target shape** (mixes barrel + app factory):
```python
"""Phase 20 HTTP API — wraps existing generators. No new generator logic."""

from __future__ import annotations

from flyer_generator.api.lifespan import lifespan
from flyer_generator.api.middleware import install_middleware
from flyer_generator.api.errors import register_exception_handlers
from flyer_generator.api.routes import brand_kits, brochures, flyers, jobs, renders, social_
from flyer_generator.api.config import AppSettings

from fastapi import FastAPI


def build_app() -> FastAPI:
    settings = AppSettings()
    app = FastAPI(
        title="flyer-generator API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    install_middleware(app, settings)
    register_exception_handlers(app)
    for router_module in (brand_kits, flyers, brochures, social_, jobs, renders):
        app.include_router(router_module.router, prefix="/api/v1")
    return app


app = build_app()

__all__ = ["app", "build_app", "AppSettings"]
```

**Why `app = build_app()` at module scope is safe:** uvicorn imports `flyer_generator.api:app`. The FastAPI `lifespan` engine/sessionmaker are **not** built here — they are built inside `lifespan` (RESEARCH.md Pitfall 1 "Shared engine across uvicorn worker processes"). So multi-worker uvicorn spawning is safe.

---

### `tests/api/conftest.py` — test fixtures (EXACT respx pattern, green-field ASGI transport)

**Analog #1 — respx boundary mock:** `tests/test_llm_resilience.py` (full file, esp. lines 71-78)

**Excerpt to copy** (`tests/test_llm_resilience.py:51-78`):
```python
@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=BASE, timeout=5.0) as c:
        yield c


def _ok(content: str = "hi") -> dict:
    return {...}


@pytest.mark.asyncio
async def test_single_200_no_retry(
    client: httpx.AsyncClient, captured_sleeps: list[float]
) -> None:
    with respx.mock(base_url=BASE) as mock_api:
        route = mock_api.post("/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_ok("yes"))
        )
```
→ Phase 20 API tests MUST **not** mock the worker's outbound ComfyCloud / Ollama calls a second time — the existing respx pattern already covers them. Instead, API-level tests mock at the `arq.enqueue_job` boundary (run the task function inline — RESEARCH.md Pitfall 6 recommends this).

**Analog #2 — mock-client fakes for integration tests:** `tests/social/test_integration.py` (lines 29-51)

**Fakes to reuse verbatim** (`tests/social/test_integration.py:29-51`):
```python
class _FakeTextClient:
    def __init__(self, response: str) -> None:
        self._response = response
        self.calls = 0

    async def complete(self, *, system: str, user: str, response_format: str) -> str:
        self.calls += 1
        return self._response

    async def aclose(self) -> None: ...


class _FakeComfy:
    def __init__(self, png: bytes) -> None:
        self._png = png
        self.calls = 0

    async def generate_image(
        self, *, workflow_name: str, prompt: str, brand_kit
    ) -> bytes:
        self.calls += 1
        return self._png
```
→ `tests/api/test_social_routes.py` can import `_FakeTextClient` / `_FakeComfy` (or re-define them in `tests/api/conftest.py`) and inject them via the existing `generate_post(..., text_client=..., comfy_client=...)` hooks. **This is why Phase 20 testing is mostly a boundary problem, not a reinvention problem.**

**`_seeded_kit()` helper** (`tests/social/test_integration.py:60-77`) builds a complete `BrandKit` in-memory and is directly reusable by API brand-kit-route tests as a seeded-record factory.

**Green-field ASGI + in-memory SQLite parts:** copy RESEARCH.md §Code Examples §"Test fixture — in-memory SQLite + ASGI transport" (lines 778-817) verbatim. The `StaticPool` + `check_same_thread=False` combo is non-obvious but canonical.

---

### `tests/api/test_worker_tasks.py` — direct-invocation task tests

**Analog:** `tests/social/test_campaign.py` (full file — async tests with `_FakeComfy` + `_FakeTextClient`, no Redis)

**Pattern:** call the task function with a hand-rolled `ctx` dict, no arq queue involved:
```python
@pytest.mark.asyncio
async def test_task_generate_post_happy_path(tmp_path, async_session_maker):
    ctx = {
        "sessionmaker": async_session_maker,
        "settings": _test_settings(tmp_path),
        "http_client": None,  # unused — fakes short-circuit
    }
    # Seed the JobRecord row first, as the route would.
    # ... (INSERT queued job) ...
    result_ref = await task_generate_post(ctx, job_id="01HTEST...", payload={...})
    # Assert JobRecord status=SUCCEEDED, RenderRecord row exists, file_path points to tmp_path
```

**Existing async test boilerplate** (`tests/social/test_campaign.py:40-80`) — same `_make_kit()`, `_make_png()`, `_FakeTextClient`, `_FakeComfy` helpers, all reusable.

---

## Shared Patterns

### Authentication
**Status:** NOT APPLICABLE FOR PHASE 20. `CONTEXT.md` §Auth: *"No auth for v1 — the API trusts private-network access."* Every route is effectively public on localhost. No auth middleware, no guards, no decorators. Phase 21+ will revisit.

### Error Handling — single exception-handler bank
**Source:** `flyer_generator/errors.py` (entire hierarchy) + RESEARCH.md §Pattern 5 (the handler bank itself)
**Apply to:** every route module (routes never `try/except` domain errors — they raise naturally; handlers translate to HTTP)

**Concrete error-tree excerpt that handlers must cover** (`flyer_generator/errors.py:4-205`):
```python
class FlyerGeneratorError(Exception):
    """Base exception for all flyer generator errors."""
    def __init__(self, message: str, *, trace_id: str = "", **context: object) -> None:
        self.trace_id = trace_id
        self.context = context
        super().__init__(message)

# ... 30+ subclasses ...

class LLMAPIError(FlyerGeneratorError): ...
class LLMRateLimitError(LLMAPIError):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None, **kwargs: object) -> None:
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds

class BrandKitError(FlyerGeneratorError): ...
class BrandVoiceViolationError(BrandKitError): ...

class SocialError(FlyerGeneratorError): ...

VisionAPIError = LLMAPIError   # back-compat alias — still caught by the LLMAPIError handler
```

**Handler-registration idiom** — RESEARCH.md §Pattern 5 (lines 401-454) is the canonical target. **Ordering matters** (more-specific classes first): `LLMRateLimitError → 503` before `LLMAPIError → 502`; `BrandVoiceViolationError → 422` before `BrandKitError → 400`; `BrandKitNotFoundError → 404` before `BrandKitError → 400`; everything above `FlyerGeneratorError → 400` as final catch-all.

**Response body shape** (one shape across every error):
```python
{"detail": str(exc), "error_type": type(exc).__name__, "trace_id": correlation_id.get() or ""}
```
`exc.context` (the kwargs passed at raise-time) is **deliberately NOT serialized** — it may contain SecretStr values or private scraper reasons (RESEARCH.md §Security Domain §"Secrets leaked in error responses").

### Request-ID / structlog correlation — library-backed
**Source:** `asgi-correlation-id` (new dep) + existing `flyer_generator/logging_config.py:14`
**Apply to:** `flyer_generator/api/middleware.py` (middleware registration) + `flyer_generator/logging_config.py` (processor addition — one line)

**Existing processor-chain evidence** (`flyer_generator/logging_config.py:13-17`):
```python
shared_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,  # <- already reads correlation_id contextvar
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
]
```
Because `merge_contextvars` is already first, `asgi_correlation_id.correlation_id` ContextVar flows into every log line automatically — **no code changes inside generator modules**. This is the single most important cross-cutting invariant: every existing `logger = structlog.get_logger()` call (27 files) inherits trace_id for free.

### httpx.AsyncClient dependency injection — reuse the existing pattern
**Source:** `flyer_generator/stages/comfy_client.py:45-49` (the idiom) + every generator's `http_client: httpx.AsyncClient | None = None` signature
**Apply to:** worker `on_startup` (builds the shared client; RESEARCH.md Pattern 3) + every task function (threads `ctx["http_client"]` through).

**ComfyClient constructor pattern** (`flyer_generator/stages/comfy_client.py:42-49`):
```python
class ComfyClient:
    """Async client for ComfyCloud: submit, poll, download."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client
        self._base_url = settings.comfycloud_base_url.rstrip("/")
        self._headers = {"X-API-Key": settings.comfycloud_api_key.get_secret_value()}
```

**Caller-owns-the-client pattern** (`flyer_generator/pipeline.py:46-49`):
```python
self._owns_http = False
if http_client is None:
    http_client = httpx.AsyncClient(follow_redirects=True)
    self._owns_http = True
```
→ In the worker, `http_client` is owned by `on_startup`; tasks pass it in so `_owns_http` stays `False` (no extra connections, no close races).

### Async generator orchestration — task wraps generator
**Source:** all five existing generator entrypoints — every one is async (or has async sibling) with `settings: Settings` + `http_client: httpx.AsyncClient | None` injectables
**Apply to:** every file under `flyer_generator/api/tasks/`

**Canonical invocation shape for flyer:** `await FlyerGenerator(settings, http_client=ctx["http_client"]).generate(event)`
**Canonical invocation shape for brand-kit:** `await fetch_brand_kit(url, slug, http_client=ctx["http_client"], base_dir=settings.brand_kits_dir)`
**Canonical invocation shape for social post:** `await generate_post(brief, kit, settings=settings, audit=True)`
**Canonical invocation shape for social campaign:** `await generate_campaign(kit, topic=topic, platforms=platforms, settings=settings, audit=True)`
**Canonical invocation shape for brochure (mixed sync+async):**
```python
images = await generate_template_images(template, content, settings=settings, http_client=ctx["http_client"])
outside_svg, inside_svg = await asyncio.to_thread(
    render_schema_brochure, template, content, images=images
)
```

### Typer CLI entrypoint (optional Phase 20 addition)
**Source:** `flyer_generator/social/__main__.py` + `flyer_generator/__main__.py`
**Apply to:** an optional `flyer_generator/api/cli.py` or `flyer_generator/api/__main__.py` if the planner wants a `flyer-api serve` / `flyer-api alembic upgrade` wrapper (RESEARCH.md §"Claude's Discretion" §"Exact uv recipe name for the dev-server launcher")

**App-declaration + command pattern** (`flyer_generator/social/__main__.py:31-37`):
```python
app = typer.Typer(
    help=(
        "Social-media posting system (Phase 19). Produces artifacts only -- "
        "no publishing."
    ),
    no_args_is_help=True,
)
logger = structlog.get_logger()
```

**Error-to-exit-code pattern** (`flyer_generator/social/__main__.py:80-88`):
```python
try:
    kit = load_brand_kit(brand_kit)
except BrandKitError as err:
    typer.echo(f"Error loading brand kit: {err}", err=True)
    raise typer.Exit(2) from err
except FileNotFoundError as err:
    typer.echo(f"Error loading brand kit: {err}", err=True)
    raise typer.Exit(2) from err
```

### Pydantic v2 `ConfigDict(extra="forbid")` discipline
**Source:** every Pydantic v2 model in the repo
**Apply to:** every new API schema (request + response). Rationale: the existing subsystems enforce strictness; API bodies must match so payloads that round-trip through JobRecord.input_payload JSON columns don't mysteriously gain extra keys on reload.

**Exemplar** (`flyer_generator/brand_kit/models.py:100-114`):
```python
class BrandKit(BaseModel):
    """Top-level brand kit. Optional nested models allow partial scrapes."""

    model_config = ConfigDict(extra="forbid")

    name: str
    source_url: str | None = None
    fetched_at: datetime
    palette: BrandPalette | None = None
    typography: BrandTypography | None = None
    logos: list[BrandLogo] = Field(default_factory=list)
    voice: BrandVoice | None = None
    photography: BrandPhotoHints | None = None
    source_artifacts: list[str] = Field(default_factory=list)
    size_multiplier: float = Field(default=1.0, gt=0.0, le=3.0)
```

---

## No Analog Found

Files with no close match in the existing codebase. Planner **should use RESEARCH.md §Code Examples + §Architecture Patterns verbatim** for these; the repo offers no reference implementation.

| File | Role | Data Flow | Reason for no analog |
|------|------|-----------|----------------------|
| `flyer_generator/api/lifespan.py` | async context manager | request-response | No existing FastAPI. Target: RESEARCH.md §Pattern 1 (lines 223-247). |
| `flyer_generator/api/db.py` | SQLAlchemy engine + sessionmaker + `get_session` | request-response | No existing SQLAlchemy anywhere. Target: RESEARCH.md §Pattern 2 (lines 251-286). |
| `flyer_generator/api/deps.py` | FastAPI `Depends(...)` factories | request-response | No FastAPI DI precedent. Target: RESEARCH.md §Code Examples for the `get_arq_pool` + `get_settings` shape. |
| `flyer_generator/api/middleware.py` | `CorrelationIdMiddleware` + `CORSMiddleware` wiring | request-response | No existing middleware anywhere. Target: RESEARCH.md §Pattern 8 (lines 568-600). |
| `flyer_generator/api/models/base.py` | `DeclarativeBase` subclass + `ULIDString` type | N/A | No existing ORM. Target: SQLAlchemy 2.0 docs + RESEARCH.md §"Schema modeling" (lines 823-840). |
| `flyer_generator/api/models/render.py` | `RenderRecord` ORM | CRUD | Entirely new concept (metadata pointer to on-disk artifact). Target: RESEARCH.md §"Schema modeling — RenderRecord" (lines 823-840). |
| `flyer_generator/api/models/job.py` | `JobRecord` + `JobStatus`/`JobKind` enums | event-driven | Entirely new concept. Target: RESEARCH.md §"JobRecord with enums and ULID" (lines 846-881). |
| `flyer_generator/api/routes/jobs.py` | `GET /jobs/{id}` polling | request-response | Novel endpoint — no in-repo precedent. Simple read-only SQLA query pattern; derive from RESEARCH.md §Code Examples. |
| `flyer_generator/api/worker.py` | arq `WorkerSettings` | event-driven | No existing queue system. Target: RESEARCH.md §Pattern 3 (lines 290-322). **Note `max_tries=1` discipline from Pitfall 4.** |
| `alembic/env.py` | async migration runner | config | No existing migration tooling. Target: RESEARCH.md §Pattern 7 (lines 510-563). Generated by `uv run alembic init -t async alembic` then edited. |
| `alembic.ini` | alembic config | config | Generated by `alembic init`; no in-repo precedent. |
| `alembic/versions/0001_initial_schema.py` | initial migration | CRUD | Generated via `uv run alembic revision --autogenerate -m "initial schema"` after the ORM models are in place. |
| `docker-compose.yml` | postgres:16 + redis:7 | config | No existing compose file. Straightforward — 2 services, named volumes, port 5432 + 6379. |
| `Procfile` | two-process dev launcher | config | No existing one. Target: RESEARCH.md §"Two-process Procfile for honcho" (lines 887-891). |

---

## Metadata

**Analog search scope:**
- `flyer_generator/` — all subpackages (stages/, brand_kit/, brochure/, social/) scanned for analogs
- `tests/` — `tests/social/`, `tests/test_llm_resilience.py`, `tests/conftest.py`, `tests/test_public_api.py`, `tests/test_config.py` scanned for test patterns
- `pyproject.toml` — scanned for dependency-declaration shape

**Files scanned:** 32 source files read (entire or targeted line ranges), 6 test files read.

**Key insight — why the analog coverage is ~66%:**
Phase 20 is mostly **new infrastructure** (FastAPI, SQLAlchemy, Alembic, arq) that the repo has never used. But it is **thin infrastructure wrapping existing generators** — the business-logic files (`tasks/*.py`, `schemas/*.py`) have strong analogs because they just re-expose the existing async generators through new transports. The files with no analog are all boilerplate that should follow RESEARCH.md patterns directly, which are themselves drawn from official FastAPI / SQLAlchemy / Alembic / arq documentation with specific version pins verified on PyPI 2026-04-22.

**Pattern extraction date:** 2026-04-22

**Critical cross-reference — don't re-research these in planning:**
- `asgi-correlation-id` + existing `structlog.contextvars.merge_contextvars` integration — **1 line of existing code** (`flyer_generator/logging_config.py:14`) already does the work; only add the processor.
- `http_client: httpx.AsyncClient | None = None` — present in **every existing generator signature**, so the worker just threads `ctx["http_client"]` through. No generator changes needed.
- `PostBrief` / `EventInput` / `BrochureContent` as request bodies — **zero wrapper code**; Pydantic v2 models are FastAPI-native.
- `load_brand_kit(slug_or_path, *, base_dir=None)` raises `FileNotFoundError` today (`flyer_generator/brand_kit/storage.py:139-143`) — the one-and-only error-hierarchy edit is to change that to `BrandKitNotFoundError` (a subclass of `BrandKitError`), preserving all existing `except BrandKitError` sites.
