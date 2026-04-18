# Flyer Generator — Python Script Specification

**Version:** 1.0
**Target:** Python 3.11+
**Status:** Design spec (pre-implementation)

---

## 1. Purpose & Scope

A Python application that generates event flyers as 1080×1920 PNG images. Each flyer is produced by:

1. Generating an AI background image via ComfyCloud from a style preset + event concept.
2. Evaluating that background with a vision LLM (Claude) for appropriateness and optimal text placement zones.
3. Compositing event text (title, date, venue, fee, org credit) onto the background using vision-derived zone coordinates.
4. Regenerating the background up to N times if vision rejects it, with refinement hints fed back into the next prompt.

The output is visually distinct on each run — zone placement, text color, and scrim composition all adapt to the generated background.

**In scope:**
- Single-flyer generation from a structured event input.
- CLI entrypoint for ad-hoc runs.
- Importable module for pipeline integration.
- Local file output; optional hooks for remote upload.

**Out of scope (v1):**
- Batch generation (design should not preclude it, but batch orchestration lives elsewhere).
- A web UI.
- Alternative image models beyond ComfyCloud.
- Animation or video output.

---

## 2. High-Level Architecture

The system is a linear pipeline of stages, with one control-flow loop (the regeneration retry). Each stage is a pure-ish async function that takes a typed input and produces a typed output. Side effects (HTTP, file I/O) are isolated at stage boundaries.

```
EventInput
    │
    ▼
[StylePromptBuilder] ──── builds ComfyCloud workflow JSON + prompts
    │
    ▼
[ComfyClient] ─────────── submits job, polls, downloads raw bytes
    │
    ▼
[ImagePreprocessor] ───── upscales 832×1472 → 1080×1920
    │
    ▼
[VisionEvaluator] ─────── single Claude call: approval + zones + color
    │
    ├── approved? no ──> [RegenDecider] ──> refine prompt, loop back
    │
    ▼ (approved)
[LayoutResolver] ──────── maps zones → pixel coordinates
    │
    ▼
[PosterComposer] ──────── builds SVG with text + scrims
    │
    ▼
[Rasterizer] ──────────── SVG → PNG via cairosvg or resvg
    │
    ▼
FlyerOutput (PNG bytes + metadata)
```

Each arrow is a typed dataclass/Pydantic model. Each stage is independently testable with fake inputs.

---

## 3. Module Layout

```
flyer_generator/
├── __init__.py              # Public API: generate_flyer(), FlyerGenerator class
├── __main__.py              # CLI entrypoint: python -m flyer_generator
├── config.py                # Settings, env var loading, validation
├── models.py                # Pydantic models for all cross-stage data
├── presets.py               # Style presets registry (extensible)
├── zones.py                 # Zone grid definition + pixel resolution
├── stages/
│   ├── __init__.py
│   ├── prompt_builder.py    # StylePromptBuilder
│   ├── comfy_client.py      # ComfyClient (submit + poll + download)
│   ├── preprocessor.py      # ImagePreprocessor (upscale)
│   ├── vision.py            # VisionEvaluator (Claude API)
│   ├── layout.py            # LayoutResolver (zones → pixels)
│   ├── composer.py          # PosterComposer (SVG build)
│   └── rasterizer.py        # Rasterizer (SVG → PNG)
├── pipeline.py              # Orchestrator: runs stages, handles regen loop
├── errors.py                # Exception hierarchy
├── logging_config.py        # Structured logging setup
└── tests/
    ├── test_prompt_builder.py
    ├── test_vision_parsing.py
    ├── test_zones.py
    ├── test_composer.py
    └── fixtures/             # Sample events, fake vision responses, sample images
```

**Rationale for split:** each stage file is <300 lines. `models.py` is the contract hub — if you change a cross-stage shape, you change it there and nowhere else. `presets.py` and `zones.py` are extension points; new styles/layouts don't touch stage code.

---

## 4. Data Models (Pydantic)

All cross-stage data is typed. Defined in `models.py`.

### 4.1 Input

```python
class EventInput(BaseModel):
    title: str                        # "Neighborhood Clean-Up Day"
    date: str                         # "Saturday, May 2, 2026" (pre-formatted string)
    time: str                         # "9:00 AM – 12:00 PM"
    location_name: str                # "Riverside Park Pavilion"
    location_address: str             # "123 Park Rd, San Antonio, TX 78205"
    fees: str                         # "FREE" or "$20" — kept short, badge-sized
    org: str                          # "Friends of Riverside Park"
    url: str | None = None            # optional event URL
    style_concept: str                # scene description for the image model
    style_preset: StylePresetName     # Literal enum — see presets.py
    color_accent: str = "#F59E0B"     # hex, used for accent line + fee badge
```

Validation: hex color regex on `color_accent`; max lengths on text fields to catch accidental novella-sized titles (reject > 120 chars).

### 4.2 Intermediate

```python
class ComfyJob(BaseModel):
    prompt_id: str
    submitted_at: datetime
    positive_prompt: str              # kept for logging/debugging
    negative_prompt: str
    seed: int
    attempt_number: int               # 1-indexed, for loop tracking

class GeneratedBackground(BaseModel):
    image_bytes: bytes                # final 1080×1920 PNG
    source_dimensions: tuple[int, int]  # (832, 1472)
    final_dimensions: tuple[int, int]   # (1080, 1920)
    comfy_job: ComfyJob
```

### 4.3 Vision contract

```python
class LayoutZones(BaseModel):
    title: ZoneName                   # Literal["TOP_LEFT", "TOP_CENTER", ...]
    details: ZoneName
    fee_badge: ZoneName
    org_credit: ZoneName = "BOTTOM_CENTER"  # default — rarely moves

class VisionVerdict(BaseModel):
    approved: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rejection_reasons: list[str] = []
    refinement_hint: str = ""
    zones: LayoutZones | None = None
    text_color: Literal["white", "dark"] = "white"
    mood_tags: list[str] = []
    raw_response: str                 # kept for debugging, truncated to 500 chars
```

`LayoutZones` is required when `approved=True`; validator enforces this.

### 4.4 Output

```python
class FlyerOutput(BaseModel):
    png_bytes: bytes
    dimensions: tuple[int, int]       # (1080, 1920)
    file_size_kb: int
    event_title: str
    attempts_used: int
    final_vision_verdict: VisionVerdict
    zones_used: LayoutZones
    trace_id: str                     # UUID for log correlation

    def save(self, path: Path) -> None: ...  # convenience
```

---

## 5. Configuration

Environment-variable driven, loaded via Pydantic `Settings`. No hardcoded secrets.

```python
class Settings(BaseSettings):
    anthropic_api_key: SecretStr
    comfycloud_api_key: SecretStr
    comfycloud_base_url: str = "https://cloud.comfy.org"

    # Vision model
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

    class Config:
        env_file = ".env"
        env_prefix = "FLYER_"
```

Every tunable lives here. No magic numbers scattered across stages.

---

## 6. Stage Specifications

### 6.1 StylePromptBuilder

**Location:** `stages/prompt_builder.py`

**Responsibility:** Given an `EventInput` + attempt context, produce the ComfyCloud workflow JSON and the positive/negative prompts.

**Signature:**
```python
class StylePromptBuilder:
    def __init__(self, presets: PresetRegistry): ...

    def build(
        self,
        event: EventInput,
        attempt: int,
        refinement_hint: str = "",
    ) -> ComfyWorkflow: ...
```

**Behavior:**
- Load the preset by `event.style_preset` from the registry. Unknown preset → raise `UnknownPresetError`.
- Compose positive prompt: preset directive lines (with `{concept}` substituted) + flyer-universal directives (bokeh zones, no text, 9:16) + optional refinement hint if provided.
- Compose negative prompt: universal negatives + preset-specific negatives.
- Generate a random seed (via `secrets.randbelow(2**31)` — `random` is fine but `secrets` is free here).
- Return a `ComfyWorkflow` object that wraps the node-graph dict.

**Latent dimensions:** fixed at 832×1472 (model-friendly 9:16). Upscaling to 1080×1920 happens in the preprocessor.

**Testability:** pure function of inputs. Snapshot-test prompt strings against a few fixture events.

### 6.2 PresetRegistry

**Location:** `presets.py`

**Responsibility:** Registry of named style presets. Each preset is a `StylePreset` dataclass with positive fragments, negative fragment, and metadata.

```python
class StylePreset(BaseModel):
    name: str
    positive_fragments: list[str]     # with {concept} placeholder
    negative_fragment: str
    description: str                  # human-readable, for CLI --list-presets

class PresetRegistry:
    def register(self, preset: StylePreset) -> None: ...
    def get(self, name: str) -> StylePreset: ...
    def list_names(self) -> list[str]: ...
```

**Built-in presets (v1):** `photorealistic`, `anime`, `western_cartoon`, `scifi`, `watercolor`, `retro_poster`. Exact prompt text carried over from the n8n workflow.

**Extension:** users can register custom presets before calling `generate_flyer()`. This is the primary extension point.

### 6.3 ComfyClient

**Location:** `stages/comfy_client.py`

**Responsibility:** Submit a workflow to ComfyCloud, poll until complete, download the resulting image bytes.

**Signature:**
```python
class ComfyClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient): ...

    async def submit(self, workflow: ComfyWorkflow) -> str:
        """Returns prompt_id."""

    async def wait_for_completion(self, prompt_id: str) -> None:
        """Polls until status=success. Raises ComfyJobFailedError or ComfyJobTimeoutError."""

    async def download_result(self, prompt_id: str) -> bytes:
        """Returns raw PNG bytes of the generated image."""

    async def generate(self, workflow: ComfyWorkflow) -> GeneratedBackground:
        """Orchestrates submit → wait → download. Primary entry point."""
```

**Polling logic:**
- Initial wait: `settings.poll_initial_wait_seconds` (default 3s).
- Poll interval: `settings.poll_interval_seconds` (default 4s).
- Max attempts: `settings.poll_max_attempts` (default 20).
- Statuses: `success` → done; `failed` / `cancelled` → raise; anything else (`pending`, `running`, `queued`, or unknown) → keep polling until the cap.

**HTTP:** uses injected `httpx.AsyncClient` so tests can swap in a fake. All requests include the `X-API-Key` header; 5xx responses trigger exponential backoff (3 retries, starting at 1s) before giving up.

**Download:** uses the `/api/history_v2/{prompt_id}` endpoint to locate the output filename, then `/api/view` to download. Returns the first image found.

### 6.4 ImagePreprocessor

**Location:** `stages/preprocessor.py`

**Responsibility:** Upscale raw 832×1472 bytes to 1080×1920 PNG bytes.

**Signature:**
```python
class ImagePreprocessor:
    def upscale(self, raw_bytes: bytes) -> GeneratedBackground: ...
```

**Implementation:** Uses Pillow. `Image.resize((1080, 1920), Image.Resampling.LANCZOS)`. Lanczos is the right choice here — we're upscaling ~30% linearly and want sharpness.

**Why Pillow, not sharp:** Pillow is pure Python-friendly, installs reliably on every platform, and is adequate for this non-artistic upscale. `sharp` was an n8n artifact.

### 6.5 VisionEvaluator

**Location:** `stages/vision.py`

**Responsibility:** Single Claude API call that returns `VisionVerdict`.

**Signature:**
```python
class VisionEvaluator:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient): ...

    async def evaluate(
        self,
        background: GeneratedBackground,
        event: EventInput,
    ) -> VisionVerdict: ...
```

**System prompt:** stored as a module-level constant (or loaded from a file — `prompts/vision_system.txt` — for easier iteration). Describes the two jobs (approval + zones), the 3×3 grid, the output JSON schema, and confidence semantics. Carry over verbatim from the n8n version, with the schema tightened to match `VisionVerdict`.

**User message:** structured content list with the base64-encoded PNG first, then a text block describing the event.

**Response parsing:** robust to markdown fences and surrounding prose. Strategy:
1. Strip ` ```json ` / ` ``` ` fences.
2. Extract substring between first `{` and last `}`.
3. `json.loads()` → Pydantic validation into `VisionVerdict`.
4. On parse failure: one retry with the *same* image and a short follow-up prompt ("Return valid JSON only, no prose."). If second attempt also fails, raise `VisionResponseParseError`.

**Confidence gate:** if `approved=True` but `confidence < settings.vision_confidence_threshold`, flip `approved` to `False` and append "low confidence" to `rejection_reasons`.

**Zone validation:** reject approved verdicts where `zones` is null or contains invalid zone names. Treat as malformed response (retry path above).

### 6.6 LayoutResolver

**Location:** `stages/layout.py` (small — could live in `zones.py`, but separating keeps the "zones are data" / "resolver is logic" split clean).

**Responsibility:** Translate zone labels into pixel coordinates + text anchors.

**Data:** `zones.py` defines:
```python
ZONE_COORDS: dict[ZoneName, ZoneCoord] = {
    "TOP_LEFT":      ZoneCoord(x=180,  y=320,  anchor="start"),
    "TOP_CENTER":    ZoneCoord(x=540,  y=320,  anchor="middle"),
    # ... nine entries
}
```

`ZoneCoord` is a dataclass with `x`, `y`, `anchor`. The anchor maps to SVG's `text-anchor` attribute — `start`, `middle`, `end`.

**Signature:**
```python
def resolve(zones: LayoutZones) -> ResolvedLayout: ...

class ResolvedLayout(BaseModel):
    title: ZoneCoord
    details: ZoneCoord
    fee_badge: ZoneCoord
    org_credit: ZoneCoord
```

Pure function. No I/O. Heavily unit-tested.

### 6.7 PosterComposer

**Location:** `stages/composer.py`

**Responsibility:** Build the final SVG string combining background + text + scrims.

**Signature:**
```python
class PosterComposer:
    def compose(
        self,
        event: EventInput,
        background: GeneratedBackground,
        verdict: VisionVerdict,
        layout: ResolvedLayout,
    ) -> str:
        """Returns SVG document as a string."""
```

**Key behaviors:**

- **Title sizing:** font size + wrap-width derived from `len(title)`. Widow-line merge (if last wrapped line is < 40% the previous, merge back). Carried over from n8n version.
- **Text color:** `white` or `dark` from `verdict.text_color`. Stroke color is the opposite with ~50% opacity for outline contrast.
- **Scrim composition:** only darken regions actually used by title/details. If title is MIDDLE_LEFT, add a middle radial scrim; if details are BOTTOM_CENTER, add bottom gradient. Don't blanket-darken the whole image — that kills the point of picking zones.
- **Accent line:** 200×4px rectangle under the title, positioned per title anchor.
- **Fee badge:** pill shape, width clamped `[140, 400]`; font shrinks if text > 15 chars.
- **Org credit:** always at y=1840, center-anchored. Not driven by vision — semantic placement is always "bottom credit line."
- **Accent stripe:** 12px solid bar at y=1908 in `event.color_accent`.

**Rendering strategy:** SVG as a single string built via f-strings or a small templating helper. Not Jinja2 — overkill for this. Use `xml.sax.saxutils.escape()` on every user-supplied string (title, venue, org, url) to prevent XML injection.

**Background embedding:** base64-encode the PNG bytes into a `data:image/png;base64,...` URL on the `<image>` element. Yes, this makes the SVG large (~2MB), but it only exists transiently before rasterization — it never ships as SVG.

### 6.8 Rasterizer

**Location:** `stages/rasterizer.py`

**Responsibility:** Convert SVG string to PNG bytes.

**Signature:**
```python
class Rasterizer:
    def rasterize(self, svg: str) -> bytes:
        """Returns PNG bytes at 1080×1920."""
```

**Implementation choice:** `cairosvg` as primary. Fallback to `resvg-py` if cairosvg has issues with the base64-embedded image (it sometimes does on older versions). Decision criteria documented in code comments. **Not** Puppeteer / headless Chrome — heavyweight and brittle in server environments.

```python
import cairosvg
png_bytes = cairosvg.svg2png(
    bytestring=svg.encode("utf-8"),
    output_width=1080,
    output_height=1920,
)
```

**Sanity check:** assert resulting PNG dimensions are 1080×1920 (via Pillow `Image.open().size`). Raise `RasterizationError` on mismatch.

---

## 7. Pipeline Orchestration

**Location:** `pipeline.py`

The orchestrator wires stages together and owns the regeneration loop.

```python
class FlyerGenerator:
    def __init__(
        self,
        settings: Settings,
        presets: PresetRegistry | None = None,
        http_client: httpx.AsyncClient | None = None,
    ): ...

    async def generate(self, event: EventInput) -> FlyerOutput:
        trace_id = uuid.uuid4().hex
        logger = get_logger().bind(trace_id=trace_id, event_title=event.title)

        refinement_hint = ""
        rejection_history: list[str] = []

        for attempt in range(1, self.settings.max_bg_attempts + 1):
            logger.info("attempt_start", attempt=attempt, hint=refinement_hint)

            workflow = self.prompt_builder.build(event, attempt, refinement_hint)
            background = await self.comfy_client.generate(workflow)
            background = self.preprocessor.upscale(background.image_bytes)
            verdict = await self.vision_evaluator.evaluate(background, event)

            if verdict.approved:
                logger.info("vision_approved", confidence=verdict.confidence, zones=verdict.zones.model_dump())
                layout = self.layout_resolver.resolve(verdict.zones)
                svg = self.composer.compose(event, background, verdict, layout)
                png_bytes = self.rasterizer.rasterize(svg)
                return FlyerOutput(
                    png_bytes=png_bytes,
                    dimensions=(1080, 1920),
                    file_size_kb=len(png_bytes) // 1024,
                    event_title=event.title,
                    attempts_used=attempt,
                    final_vision_verdict=verdict,
                    zones_used=verdict.zones,
                    trace_id=trace_id,
                )

            # rejected — log and prep next attempt
            logger.warning(
                "vision_rejected",
                attempt=attempt,
                reasons=verdict.rejection_reasons,
                hint=verdict.refinement_hint,
            )
            rejection_history.extend(verdict.rejection_reasons)
            refinement_hint = verdict.refinement_hint

        raise MaxAttemptsExceededError(
            f"Vision rejected {self.settings.max_bg_attempts} backgrounds. "
            f"Rejection history: {rejection_history}"
        )
```

**Notes:**
- Each stage is a dependency injected at construction — trivial to swap for fakes in tests.
- Loop is explicit; no recursion, no goto-ish control flow.
- Every failure mode raises a typed exception; callers can catch and handle.

---

## 8. Error Hierarchy

**Location:** `errors.py`

```
FlyerGeneratorError (base)
├── ConfigurationError        # bad settings, missing API key
├── InputValidationError      # malformed EventInput
├── UnknownPresetError
├── ComfyError (base)
│   ├── ComfySubmitError      # 4xx/5xx on submit
│   ├── ComfyJobFailedError   # job returned status=failed/cancelled
│   ├── ComfyJobTimeoutError  # poll_max_attempts exceeded
│   └── ComfyDownloadError    # history/view endpoint issues
├── VisionError (base)
│   ├── VisionAPIError                # 4xx/5xx from Anthropic
│   └── VisionResponseParseError      # JSON unsalvageable after retry
├── CompositionError          # SVG build failure
├── RasterizationError
└── MaxAttemptsExceededError  # regen budget exhausted
```

Every exception carries enough context (attempt number, trace_id, last known state) to debug from logs alone.

---

## 9. Logging

**Location:** `logging_config.py`

- Library: `structlog` configured to emit either JSON (for prod / ingestion) or pretty text (for dev), based on `settings.log_format`.
- Every pipeline run generates a `trace_id` (UUID4 hex) bound into the logger context.
- Key events logged: `attempt_start`, `comfy_submitted` (with prompt_id), `comfy_completed` (with elapsed), `vision_approved` / `vision_rejected` (with confidence + zones or reasons), `flyer_generated` (with size + attempts).
- No API keys, no base64 payloads, no full prompt text by default (log prompt *hash* instead; full prompt goes to debug level only).

---

## 10. CLI

**Location:** `__main__.py`

```bash
python -m flyer_generator \
    --title "Neighborhood Clean-Up Day" \
    --date "Saturday, May 2, 2026" \
    --time "9:00 AM – 12:00 PM" \
    --venue "Riverside Park Pavilion" \
    --address "123 Park Rd, San Antonio, TX 78205" \
    --fees FREE \
    --org "Friends of Riverside Park" \
    --concept "community outdoor event, park setting, sunny morning" \
    --preset photorealistic \
    --accent "#F59E0B" \
    --output ./output/cleanup_day.png
```

Also supports:
- `--event-json path/to/event.json` to load an `EventInput` from a file (for scripting).
- `--list-presets` to enumerate available styles.
- `--max-attempts N` to override the regen cap.
- `--dry-run` to build the prompt and print it without calling ComfyCloud.

Framework: `typer` (or `argparse` if you want zero deps — typer is friendlier).

---

## 11. Public API

**Location:** `__init__.py`

The importable surface is deliberately small:

```python
from flyer_generator import (
    FlyerGenerator,
    EventInput,
    FlyerOutput,
    Settings,
    PresetRegistry,
    StylePreset,
    # Errors:
    FlyerGeneratorError,
    MaxAttemptsExceededError,
    VisionResponseParseError,
    ComfyJobTimeoutError,
)

# Convenience function for one-shot usage:
async def generate_flyer(event: EventInput, settings: Settings | None = None) -> FlyerOutput:
    """Construct a FlyerGenerator with defaults and run once."""
```

Users who want custom presets or injected HTTP clients instantiate `FlyerGenerator` directly. Everyone else uses `generate_flyer()`.

---

## 12. Dependencies

```toml
[project.dependencies]
httpx = "^0.27"                  # async HTTP
pydantic = "^2.5"                # models + settings
pydantic-settings = "^2.1"       # .env loading
pillow = "^10.0"                 # image upscale
cairosvg = "^2.7"                # SVG → PNG primary
structlog = "^24.1"              # logging
typer = "^0.12"                  # CLI

[project.optional-dependencies]
resvg = ["resvg-py"]             # fallback rasterizer
dev = ["pytest", "pytest-asyncio", "pytest-httpx", "mypy", "ruff"]
```

No `sharp`, no Node. cairosvg handles base64-embedded images fine in recent versions; resvg is there if needed.

**System deps for cairosvg:** Cairo + libffi. On Debian/Ubuntu: `apt install libcairo2 libffi-dev`. Document in README.

---

## 13. Testing Strategy

- **Unit tests** for every pure stage: `prompt_builder`, `layout`, `composer`, zone resolution, vision response parsing (especially malformed inputs — markdown fences, surrounding prose, missing fields, invalid zone names).
- **Integration tests** with `pytest-httpx` mocking ComfyCloud and Anthropic endpoints. Run the full pipeline against canned responses.
- **Snapshot tests** for SVG output: given fixed event + fixed vision verdict, the SVG string should be byte-stable. Detects regressions in the composer.
- **Smoke test** behind an env flag (`FLYER_RUN_LIVE_TESTS=1`) that hits real APIs with a single cheap event — for CI nightly, not PR checks.
- **Coverage target:** 85%+ on stages and pipeline; 100% on zone resolution and vision parsing (both are high-bug-density by nature).

---

## 14. Performance & Cost Notes

- **Per-flyer cost (approx):** one ComfyCloud generation + one Claude vision call. At current pricing, Claude vision with a ~1MB image input is the dominant line item per retry.
- **Per-flyer latency (approx):** Comfy ~15-30s + vision ~3-5s + local processing <1s = ~20-40s end-to-end on a first-attempt success. Each regeneration adds ~20s.
- **Concurrency:** a single `FlyerGenerator` instance is safe to run multiple `generate()` calls concurrently via `asyncio.gather()` since all stage state is per-call. Share one `httpx.AsyncClient`.

---

## 15. Extension Points (Designed For)

These are where you'll want to change things later; the design keeps them isolated:

- **New style presets:** add to `PresetRegistry`. Zero changes elsewhere.
- **New zones / different grid:** update `ZONE_COORDS` in `zones.py` + expand `ZoneName` literal. Composer reads from resolved coords, doesn't care about the grid shape.
- **Different vision model or provider:** swap `VisionEvaluator` implementation behind the same interface. Pipeline doesn't care.
- **Alternative image backend (local ComfyUI, Replicate, fal.ai):** same — replace `ComfyClient`, keep the `GeneratedBackground` contract.
- **S3 / cloud output:** `FlyerOutput.save()` is a convenience for local; add `save_to_s3()` or similar as a separate concern — don't pollute the pipeline.
- **FastAPI wrapper:** trivial — the public API is already async, Pydantic-typed, and exception-clean. Wrap `generate_flyer()` in a POST endpoint; done.

---

## 16. Explicit Non-Goals (v1)

- No font diversity — Arial/Helvetica fallback chain is the only font stack. Adding web fonts requires font file management and cairosvg font config; out of scope.
- No multi-language layout — right-to-left scripts, CJK wrapping, complex text shaping are not handled.
- No image-content safety check — vision approval is about *suitability*, not NSFW detection. Add a separate moderation stage if needed.
- No caching — each call generates fresh. Caching belongs at a higher layer if desired.

---

## 17. Open Questions

These should be resolved before implementation starts:

1. **Settings source precedence.** Env vars only, or env + config file + CLI override? Spec currently says env + CLI override (via typer); config file can be deferred.
2. **Retry refinement loop: replace or augment prompt?** Current spec *appends* the refinement hint to the original prompt. Alternative: replace the original concept with a hint-augmented version. Appending is simpler; revisit if quality suffers.
3. **What to do if vision returns `approved=true` but omits zones?** Current spec: treat as parse failure, retry once. Acceptable, but could be "approve with default zones" if we want to be more lenient.
4. **Rasterizer choice — cairosvg vs resvg by default?** Spec picks cairosvg for installability; resvg is faster and more accurate but has heavier install. Leaving as cairosvg unless early testing shows issues.