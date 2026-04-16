# Phase 1: Foundation - Research

**Researched:** 2026-04-16
**Domain:** Python data contracts, configuration, error hierarchies, style presets
**Confidence:** HIGH

## Summary

Phase 1 establishes the shared vocabulary for the entire flyer generation pipeline: Pydantic v2 data models, environment-driven configuration, a typed exception hierarchy, a style presets registry, and zone coordinate definitions. This is a greenfield phase with no external API calls and no I/O -- pure data contracts and project scaffolding.

The spec and n8n workflow provide exact, verifiable reference implementations for every data structure. The style preset prompts, ComfyCloud workflow node graph, zone pixel coordinates, and vision system prompt are all extractable verbatim from `docs/n8n.json`. The primary risk is deviation from these proven patterns.

**Primary recommendation:** Implement models.py, config.py, errors.py, presets.py, and zones.py exactly as specified in docs/spec.md Sections 3-8, with preset prompt text copied verbatim from the n8n workflow's Build Background Prompt node.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Follow the module layout from `docs/spec.md` Section 3 exactly -- `flyer_generator/` package with `stages/` subpackage, `models.py` as the contract hub, `presets.py` and `zones.py` as extension points
- **D-02:** Use uv for dependency management with pyproject.toml -- no setup.py, no requirements.txt
- **D-03:** Include dev dependencies (pytest, pytest-asyncio, mypy, ruff) in `[project.optional-dependencies]`
- **D-04:** Python 3.11+ minimum -- use `from __future__ import annotations` is not needed
- **D-05:** All cross-stage data defined in `models.py` -- EventInput, ComfyJob, GeneratedBackground, VisionVerdict, LayoutZones, ResolvedLayout, FlyerOutput per spec Section 4
- **D-06:** Use Pydantic v2 BaseModel throughout; validators enforce hex color regex on color_accent, max lengths on text fields (reject > 120 chars)
- **D-07:** ZoneName is a Literal type with 9 values (TOP_LEFT, TOP_CENTER, TOP_RIGHT, MIDDLE_LEFT, MIDDLE_CENTER, MIDDLE_RIGHT, BOTTOM_LEFT, BOTTOM_CENTER, BOTTOM_RIGHT)
- **D-08:** VisionVerdict validator enforces zones required when approved=True
- **D-09:** FlyerOutput includes a `save(path: Path)` convenience method
- **D-10:** Use Pydantic Settings (pydantic-settings) with `env_prefix = "FLYER_"` and `.env` file support per spec Section 5
- **D-11:** All tunable values in Settings class -- no magic numbers in stage code
- **D-12:** SecretStr for API keys (anthropic_api_key, comfycloud_api_key)
- **D-13:** Exception hierarchy per spec Section 8 -- FlyerGeneratorError as base, with ComfyError and VisionError as intermediate bases
- **D-14:** Every exception carries context (attempt number, trace_id, last known state)
- **D-15:** Six presets carried over verbatim from n8n workflow: photorealistic, anime, western_cartoon, scifi, watercolor, retro_poster
- **D-16:** StylePreset is a Pydantic BaseModel with name, positive_fragments (list[str] with {concept} placeholder), negative_fragment, description
- **D-17:** PresetRegistry class with register(), get(), list_names() methods -- extensible by users before calling generate_flyer()
- **D-18:** ZONE_COORDS dict in zones.py maps ZoneName to ZoneCoord(x, y, anchor) per spec Section 6.6
- **D-19:** ZoneCoord is a simple dataclass with x (int), y (int), anchor (Literal["start", "middle", "end"])
- **D-20:** Zone pixel values: TOP row y=320, MIDDLE row y=960, BOTTOM row y=1600; LEFT x=180, CENTER x=540, RIGHT x=900

### Claude's Discretion
- Logging configuration setup details (structlog initialization) -- follow spec Section 9 guidance
- Exact `__init__.py` public API surface -- follow spec Section 11
- Test fixture organization within `tests/fixtures/`

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FOUND-01 | Project uses Python 3.11+ with uv for dependency management and pyproject.toml config | Standard stack section covers uv setup, pyproject.toml structure; environment audit confirms uv 0.11.7 available |
| FOUND-02 | All cross-stage data contracts defined as Pydantic v2 models | Architecture patterns section provides exact model definitions from spec + n8n workflow; Pydantic v2 API verified via Context7 |
| FOUND-03 | Configuration loaded from environment variables via Pydantic Settings with FLYER_ prefix | Code examples section provides verified pydantic-settings pattern with SettingsConfigDict |
| FOUND-04 | Typed exception hierarchy covering every failure mode | Architecture patterns section documents full hierarchy from spec Section 8 with context-carrying pattern |
| FOUND-05 | Six built-in style presets registered with exact prompt text from n8n workflow | Code examples section provides verbatim preset data extracted from docs/n8n.json Build Background Prompt node |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Python 3.11+** required
- **Pillow** for image upscale, **cairosvg** for SVG-to-PNG rasterization (resvg-py as fallback)
- **httpx** (async) for all API calls
- **Pydantic v2** for all data contracts, **pydantic-settings** for config
- **structlog** for logging
- **typer** for CLI
- **No Node.js deps** -- no sharp, no Puppeteer, pure Python stack
- **System deps:** Cairo + libffi required for cairosvg
- **uv** for package/project management (not pip, not poetry)
- **ruff** for linting + formatting
- **pyright** for type checking

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Data contracts (models.py) | Application core | -- | Pure Python types, no I/O, imported by all stages |
| Configuration (config.py) | Application core | OS environment | Pydantic Settings reads env vars at startup |
| Error hierarchy (errors.py) | Application core | -- | Exception classes, no dependencies |
| Style presets (presets.py) | Application core | -- | Registry pattern, pure data + logic |
| Zone coordinates (zones.py) | Application core | -- | Static data mapping, no I/O |
| Logging setup (logging_config.py) | Application core | -- | structlog configuration, called once at startup |
| Package scaffold (pyproject.toml) | Build system | -- | uv manages dependencies |

## Standard Stack

### Core (Phase 1 only)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | >=2.13.1 | Data models, validation | All cross-stage contracts; v2 with model_config pattern [VERIFIED: pip3 index] |
| pydantic-settings | >=2.13.1 | Env var config | BaseSettings with env_prefix, SecretStr, .env file support [VERIFIED: pip3 index] |
| structlog | >=25.5.0 | Structured logging | JSON or pretty output, ContextVar-based for async safety [VERIFIED: pip3 index] |

### Dev
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=9.0.3 | Test runner | All unit tests [VERIFIED: STACK.md] |
| pytest-asyncio | >=1.3.0 | Async test support | Any async test (not needed for Phase 1 but install now) [VERIFIED: STACK.md] |
| ruff | >=0.11 | Linter + formatter | Every file, configured in pyproject.toml [VERIFIED: ruff 0.14.10 installed] |
| pyright | latest | Type checker | Static analysis of all models [VERIFIED: STACK.md] |

### Not Yet Needed (installed but not used in Phase 1)
| Library | Version | Purpose | Phase |
|---------|---------|---------|-------|
| httpx | >=0.28.1 | HTTP client | Phase 2+ |
| anthropic | >=0.87.0 | Claude SDK | Phase 2+ |
| Pillow | >=12.2.0 | Image processing | Phase 2+ |
| cairosvg | >=2.9.0 | SVG rasterization | Phase 3+ |
| typer | >=0.24.1 | CLI | Phase 4 |

**Installation (full project, Phase 1 focus):**
```bash
uv init --name flyer-generator
uv add pydantic pydantic-settings structlog httpx anthropic pillow cairosvg typer
uv add --optional dev pytest pytest-asyncio ruff
```

## Architecture Patterns

### System Architecture Diagram

```
pyproject.toml (uv project definition)
        |
        v
flyer_generator/
        |
        +-- __init__.py (public API surface)
        |
        +-- models.py <--- ALL cross-stage data contracts
        |     |
        |     +-- EventInput --> StylePromptBuilder (Phase 2)
        |     +-- ComfyJob --> ComfyClient (Phase 2)
        |     +-- GeneratedBackground --> VisionEvaluator (Phase 2)
        |     +-- VisionVerdict + LayoutZones --> LayoutResolver (Phase 3)
        |     +-- ResolvedLayout --> PosterComposer (Phase 3)
        |     +-- FlyerOutput --> Pipeline + CLI (Phase 4)
        |
        +-- config.py <--- Settings from env vars (FLYER_ prefix)
        |
        +-- errors.py <--- Typed exception hierarchy
        |
        +-- presets.py <--- StylePreset + PresetRegistry (6 built-ins)
        |
        +-- zones.py <--- ZoneName Literal + ZONE_COORDS dict + ZoneCoord
        |
        +-- logging_config.py <--- structlog setup (JSON or text)
        |
        +-- stages/ (empty __init__.py, populated in later phases)
```

### Recommended Project Structure
```
flyer_generator/
├── __init__.py              # Public API: generate_flyer(), FlyerGenerator, models, errors
├── __main__.py              # CLI entrypoint (Phase 4)
├── config.py                # Settings via pydantic-settings
├── models.py                # ALL Pydantic models
├── presets.py               # StylePreset + PresetRegistry
├── zones.py                 # ZoneName, ZoneCoord, ZONE_COORDS
├── errors.py                # Exception hierarchy
├── logging_config.py        # structlog configuration
├── stages/
│   └── __init__.py          # Empty for now
└── py.typed                 # PEP 561 marker for type checking
tests/
├── __init__.py
├── test_models.py           # Model validation tests
├── test_config.py           # Settings loading tests
├── test_errors.py           # Exception hierarchy tests
├── test_presets.py          # Preset registry tests
├── test_zones.py            # Zone coordinate tests
└── fixtures/
    └── sample_events.py     # Fixture EventInput instances
```

### Pattern 1: Pydantic v2 BaseModel with model_config
**What:** All models use Pydantic v2's `model_config` dict pattern, not the deprecated inner `class Config`
**When to use:** Every model in models.py
**Example:**
```python
# Source: Context7 /websites/pydantic_dev_validation + /pydantic/pydantic-settings
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal

ZoneName = Literal[
    "TOP_LEFT", "TOP_CENTER", "TOP_RIGHT",
    "MIDDLE_LEFT", "MIDDLE_CENTER", "MIDDLE_RIGHT",
    "BOTTOM_LEFT", "BOTTOM_CENTER", "BOTTOM_RIGHT",
]

class EventInput(BaseModel):
    title: str = Field(max_length=120)
    date: str = Field(max_length=120)
    time: str = Field(max_length=120)
    location_name: str = Field(max_length=120)
    location_address: str = Field(max_length=120)
    fees: str = Field(max_length=120)
    org: str = Field(max_length=120)
    url: str | None = None
    style_concept: str
    style_preset: str  # validated against PresetRegistry at runtime
    color_accent: str = "#F59E0B"

    @field_validator("color_accent")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            raise ValueError(f"color_accent must be a 6-digit hex color, got {v!r}")
        return v
```

### Pattern 2: Pydantic Settings with SettingsConfigDict
**What:** Configuration via env vars with FLYER_ prefix, using the v2 SettingsConfigDict pattern
**When to use:** config.py
**Example:**
```python
# Source: Context7 /pydantic/pydantic-settings
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FLYER_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # API keys
    anthropic_api_key: SecretStr
    comfycloud_api_key: SecretStr
    comfycloud_base_url: str = "https://cloud.comfy.org"

    # Vision
    vision_model: str = "claude-sonnet-4-5"
    vision_max_tokens: int = 1024
    vision_timeout_seconds: int = 60

    # Regen policy
    max_bg_attempts: int = 3
    vision_confidence_threshold: float = 0.6

    # Comfy polling
    poll_initial_wait_seconds: float = 3.0
    poll_interval_seconds: float = 4.0
    poll_max_attempts: int = 20

    # Output
    output_dir: Path = Path("./output")
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"
```

### Pattern 3: model_validator for Cross-Field Validation
**What:** VisionVerdict requires zones when approved=True
**When to use:** VisionVerdict model
**Example:**
```python
# Source: Context7 /websites/pydantic_dev_validation
from typing_extensions import Self
from pydantic import BaseModel, Field, model_validator

class VisionVerdict(BaseModel):
    approved: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rejection_reasons: list[str] = []
    refinement_hint: str = ""
    zones: LayoutZones | None = None
    text_color: Literal["white", "dark"] = "white"
    mood_tags: list[str] = []
    raw_response: str = Field(max_length=500)

    @model_validator(mode="after")
    def zones_required_when_approved(self) -> Self:
        if self.approved and self.zones is None:
            raise ValueError("zones must be provided when approved=True")
        return self
```

### Pattern 4: Exception Hierarchy with Context
**What:** Every exception carries structured context for debugging from logs alone
**When to use:** errors.py
**Example:**
```python
class FlyerGeneratorError(Exception):
    """Base exception for all flyer generator errors."""
    def __init__(self, message: str, *, trace_id: str = "", **context: object) -> None:
        self.trace_id = trace_id
        self.context = context
        super().__init__(message)

class ComfyError(FlyerGeneratorError):
    """Base for all ComfyCloud errors."""

class ComfyJobTimeoutError(ComfyError):
    """Poll max attempts exceeded."""
    def __init__(self, message: str, *, prompt_id: str = "", attempts: int = 0, **kwargs: object) -> None:
        super().__init__(message, **kwargs)
        self.prompt_id = prompt_id
        self.attempts = attempts
```

### Pattern 5: structlog Configuration
**What:** Dual-mode logging (JSON for prod, pretty for dev)
**When to use:** logging_config.py
**Example:**
```python
# Source: Context7 /hynek/structlog
import structlog

def configure_logging(log_format: str = "text", log_level: str = "INFO") -> None:
    """Configure structlog for the application."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if log_format == "json":
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog, log_level.upper(), 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger() -> structlog.stdlib.BoundLogger:
    return structlog.get_logger()
```

### Anti-Patterns to Avoid
- **Inner `class Config` in Pydantic v2:** Use `model_config = SettingsConfigDict(...)` instead. The inner class is deprecated in v2. [VERIFIED: Context7]
- **Hardcoded prompt text:** All preset prompts MUST come verbatim from n8n workflow. Do not paraphrase or "improve" proven prompts.
- **Magic numbers in code:** All tunable values (latent dimensions, zone coordinates, polling intervals) belong in constants or config, not scattered in stage code.
- **Mutable default arguments:** Use `Field(default_factory=list)` for list/dict defaults in Pydantic models, not `= []`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Env var loading | Custom os.environ parsing | pydantic-settings BaseSettings | Handles type coercion, validation, .env files, SecretStr masking |
| Data validation | Manual if/else checks | Pydantic v2 field_validator / model_validator | Composable, generates JSON schema, clear error messages |
| Hex color validation | Manual regex in multiple places | Pydantic field_validator on color_accent | Single source of truth, tested once |
| Structured logging | print() or stdlib logging | structlog | ContextVar bindings, JSON output, processor pipeline |
| CLI framework | argparse | typer (Phase 4) | Type-hint driven, auto-help, consistent with Pydantic |

## Common Pitfalls

### Pitfall 1: Pydantic v2 model_config vs class Config
**What goes wrong:** Using `class Config:` inside a Pydantic v2 BaseModel or BaseSettings -- this is the v1 pattern and is deprecated.
**Why it happens:** Many tutorials and LLM training data show the v1 pattern.
**How to avoid:** Always use `model_config = SettingsConfigDict(...)` for settings, `model_config = ConfigDict(...)` for regular models.
**Warning signs:** Deprecation warnings at runtime. [VERIFIED: Context7 /websites/pydantic_dev_validation]

### Pitfall 2: Mutable Defaults in Pydantic Models
**What goes wrong:** Using `rejection_reasons: list[str] = []` can cause shared state across instances in some edge cases.
**Why it happens:** Pydantic v2 actually handles this correctly (copies defaults), but using `Field(default_factory=list)` is more explicit and conventional.
**How to avoid:** Use `Field(default_factory=list)` for list/dict/set defaults.
**Warning signs:** Unexpected data sharing between model instances.

### Pitfall 3: Forgetting env_prefix Interaction with SecretStr
**What goes wrong:** Setting `env_prefix="FLYER_"` means the env var must be `FLYER_ANTHROPIC_API_KEY`, not just `ANTHROPIC_API_KEY`.
**Why it happens:** Easy to forget the prefix when writing .env files.
**How to avoid:** Document the full env var names in .env.example. Test config loading early.
**Warning signs:** `ValidationError` on Settings() instantiation about missing required fields. [VERIFIED: Context7 /pydantic/pydantic-settings]

### Pitfall 4: Preset Prompt Drift from n8n Reference
**What goes wrong:** Paraphrasing or "improving" the proven prompt text from the n8n workflow.
**Why it happens:** Developer instinct to clean up or optimize text.
**How to avoid:** Copy verbatim. The prompts are tuned for the specific model (z_image_turbo_bf16.safetensors) and have been tested in production.
**Warning signs:** Generated images differ in quality or style from the n8n workflow output.

### Pitfall 5: Python 3.14 Compatibility Concerns
**What goes wrong:** The system has Python 3.14.4 installed, but the project targets 3.11+. Some dependencies (especially C extensions like cairosvg) may not have wheels for 3.14 yet.
**Why it happens:** Python 3.14 is very new.
**How to avoid:** Use `uv` with `--python 3.12` to create a venv targeting 3.12 specifically, or verify all dependencies build on 3.14.
**Warning signs:** Build failures during `uv sync`. [ASSUMED]

## Code Examples

### Verbatim Style Presets from n8n Workflow

Extracted from `docs/n8n.json`, Build Background Prompt & Workflow node:

```python
# Source: docs/n8n.json, Build Background Prompt & Workflow node (lines 52-100)
BUILTIN_PRESETS: dict[str, dict] = {
    "photorealistic": {
        "positive_fragments": [
            "A cinematic photograph: {concept}.",
            "Shot on 35mm film, shallow depth of field, golden hour lighting.",
            "Professional color grading, warm tones, inviting atmosphere.",
        ],
        "negative_fragment": "cartoon, illustration, painting, anime, 3d render, cgi, drawing, sketch",
        "description": "Cinematic photograph with film grain and golden hour lighting",
    },
    "anime": {
        "positive_fragments": [
            "A vibrant anime illustration: {concept}.",
            "Studio Ghibli inspired, cel-shaded, rich saturated palette.",
            "Soft ambient lighting, detailed background art, dreamy atmosphere.",
        ],
        "negative_fragment": "photorealistic, photograph, 3d render, cgi, western cartoon, low detail",
        "description": "Studio Ghibli-inspired anime illustration with rich colors",
    },
    "western_cartoon": {
        "positive_fragments": [
            "A stylized cartoon illustration: {concept}.",
            "Bold outlines, flat color fills, playful exaggerated proportions.",
            "Bright cheerful palette, clean vector-style rendering.",
        ],
        "negative_fragment": "photorealistic, photograph, anime, 3d render, dark, gritty",
        "description": "Bold cartoon illustration with flat colors and clean outlines",
    },
    "scifi": {
        "positive_fragments": [
            "A futuristic sci-fi scene: {concept}.",
            "Neon accents, holographic elements, sleek metallic surfaces.",
            "Dramatic volumetric lighting, cyberpunk atmosphere, high-tech environment.",
        ],
        "negative_fragment": "cartoon, hand-drawn, vintage, rustic, low-tech, blurry",
        "description": "Futuristic sci-fi scene with neon and volumetric lighting",
    },
    "watercolor": {
        "positive_fragments": [
            "A delicate watercolor painting: {concept}.",
            "Soft washes of color, visible paper texture, gentle bleeding edges.",
            "Impressionistic detail, pastel and muted tones, artistic brushwork.",
        ],
        "negative_fragment": "photorealistic, photograph, sharp lines, 3d render, digital art, cartoon",
        "description": "Delicate watercolor painting with soft washes and paper texture",
    },
    "retro_poster": {
        "positive_fragments": [
            "A vintage retro poster illustration: {concept}.",
            "Mid-century modern aesthetic, limited color palette, screen-print texture.",
            "Bold geometric shapes, grain overlay, nostalgic warm tones.",
        ],
        "negative_fragment": "photorealistic, photograph, 3d render, anime, hyper-detailed",
        "description": "Vintage mid-century poster with screen-print texture",
    },
}
```

### Universal Flyer Directives (from n8n workflow)

```python
# Source: docs/n8n.json, Build Background Prompt & Workflow node (lines 79-85)
FLYER_DIRECTIVES: list[str] = [
    "Smooth clean bokeh areas in the upper third and lower third of the frame.",
    "Main subject centered in middle third of composition.",
    "No text, no writing, no letters, no signs, no symbols.",
    "Pure background art with no graphic design elements.",
    "Tall portrait composition 9:16.",
]

UNIVERSAL_NEGATIVE: str = (
    "text, writing, letters, words, numbers, watermark, logo, signs, symbols, "
    "UI, overlay, graphic design, borders, captions, labels, "
    "blurry, low quality, deformed, disfigured, noisy, grainy, "
    "cluttered composition, busy background, overlapping subjects"
)
```

### Zone Coordinates (from n8n workflow)

```python
# Source: docs/n8n.json, Zones to Pixel Coords node (lines 333-340)
# Also confirmed in docs/spec.md Section 6.6
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class ZoneCoord:
    x: int
    y: int
    anchor: Literal["start", "middle", "end"]

ZONE_COORDS: dict[str, ZoneCoord] = {
    "TOP_LEFT":      ZoneCoord(x=180,  y=320,  anchor="start"),
    "TOP_CENTER":    ZoneCoord(x=540,  y=320,  anchor="middle"),
    "TOP_RIGHT":     ZoneCoord(x=900,  y=320,  anchor="end"),
    "MIDDLE_LEFT":   ZoneCoord(x=180,  y=960,  anchor="start"),
    "MIDDLE_CENTER": ZoneCoord(x=540,  y=960,  anchor="middle"),
    "MIDDLE_RIGHT":  ZoneCoord(x=900,  y=960,  anchor="end"),
    "BOTTOM_LEFT":   ZoneCoord(x=180,  y=1600, anchor="start"),
    "BOTTOM_CENTER": ZoneCoord(x=540,  y=1600, anchor="middle"),
    "BOTTOM_RIGHT":  ZoneCoord(x=900,  y=1600, anchor="end"),
}
```

### ComfyCloud Workflow Node Graph (data structure for later phases)

```python
# Source: docs/n8n.json, Build Background Prompt & Workflow node
# This is the exact ComfyUI node graph submitted to ComfyCloud API
# Captured here as a data structure for Phase 2, but defined as a constant in Phase 1
COMFY_WORKFLOW_TEMPLATE = {
    "model_files": {
        "unet": "z_image_turbo_bf16.safetensors",
        "clip": "qwen_3_4b.safetensors",
        "vae": "ae.safetensors",
    },
    "sampler_config": {
        "steps": 8,
        "cfg": 1,
        "sampler_name": "res_multistep",
        "scheduler": "simple",
        "denoise": 1,
    },
    "latent_dimensions": {
        "width": 832,
        "height": 1472,
    },
    "model_sampling_shift": 3,
}
```

### Exception Hierarchy (full tree from spec Section 8)

```python
# Source: docs/spec.md Section 8
class FlyerGeneratorError(Exception):
    """Base exception."""

class ConfigurationError(FlyerGeneratorError): ...
class InputValidationError(FlyerGeneratorError): ...
class UnknownPresetError(FlyerGeneratorError): ...

class ComfyError(FlyerGeneratorError):
    """Base for ComfyCloud errors."""
class ComfySubmitError(ComfyError): ...
class ComfyJobFailedError(ComfyError): ...
class ComfyJobTimeoutError(ComfyError): ...
class ComfyDownloadError(ComfyError): ...

class VisionError(FlyerGeneratorError):
    """Base for vision evaluation errors."""
class VisionAPIError(VisionError): ...
class VisionResponseParseError(VisionError): ...

class CompositionError(FlyerGeneratorError): ...
class RasterizationError(FlyerGeneratorError): ...
class MaxAttemptsExceededError(FlyerGeneratorError): ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `class Config` | Pydantic v2 `model_config = ConfigDict(...)` | Pydantic 2.0 (June 2023) | Must use v2 pattern exclusively |
| pydantic-settings inner `class Config` | `model_config = SettingsConfigDict(...)` | pydantic-settings 2.0 | Same migration as above |
| `from __future__ import annotations` | Not needed with Python 3.11+ | Python 3.10+ | Union syntax `X \| Y` works natively |
| `Field(default=[])` | `Field(default_factory=list)` or just `= []` (Pydantic v2 handles safely) | Pydantic 2.0 | Pydantic v2 copies defaults, but explicit factory is conventional |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Python 3.14.4 may have compatibility issues with C extensions (cairosvg) | Pitfall 5 | Phase 1 only uses pure Python deps so LOW risk; becomes relevant in Phase 3 |
| A2 | structlog `make_filtering_bound_logger` accepts log level as int (20 for INFO) | Code Examples | Minor -- may need to use logging level constants instead |

## Open Questions

1. **Python version for venv**
   - What we know: System Python is 3.14.4, project targets 3.11+
   - What's unclear: Whether uv should create a 3.12 venv or use 3.14
   - Recommendation: Use `uv python install 3.12` and `uv init --python 3.12` to ensure maximum compatibility with all dependencies (especially cairosvg in later phases)

2. **StylePresetName type**
   - What we know: Spec Section 4.1 shows `style_preset: StylePresetName` as a "Literal enum"
   - What's unclear: Whether to use a Literal type (static, limited) or a plain str validated at runtime against PresetRegistry (dynamic, extensible)
   - Recommendation: Use plain `str` on EventInput and validate against PresetRegistry at runtime in the prompt builder. This supports the D-17 extensibility requirement (users can register custom presets).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.14.4 (system) | uv python install 3.12 for compat |
| uv | Package management | Yes | 0.11.7 | -- |
| ruff | Linting/formatting | Yes | 0.14.10 | -- |
| pyright | Type checking | No | -- | Install via uv tool install pyright or npx |
| Cairo (libcairo2) | cairosvg (Phase 3) | Not checked | -- | Not needed for Phase 1 |

**Missing dependencies with no fallback:**
- None for Phase 1

**Missing dependencies with fallback:**
- pyright: Install via `uv tool install pyright` or `npx pyright`

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/pydantic_dev_validation` - field_validator, model_validator, model_config patterns
- Context7 `/pydantic/pydantic-settings` - BaseSettings, SettingsConfigDict, SecretStr, env_prefix
- Context7 `/hynek/structlog` - configure(), processors, JSONRenderer, ConsoleRenderer
- `docs/spec.md` - Full technical specification (Sections 3-8)
- `docs/n8n.json` - Working n8n workflow with exact preset prompts, zone coordinates, workflow structure

### Secondary (MEDIUM confidence)
- pip3 index versions - Verified current versions of pydantic (2.13.1), pydantic-settings (2.13.1), structlog (25.5.0), typer (0.24.1)
- System checks - Python 3.14.4, uv 0.11.7, ruff 0.14.10 confirmed available

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all versions verified against PyPI, all APIs verified via Context7
- Architecture: HIGH - spec and n8n workflow provide exact reference implementation
- Pitfalls: HIGH - Pydantic v2 migration patterns well-documented, preset data extraction verified

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (stable domain, Pydantic v2 API is mature)
