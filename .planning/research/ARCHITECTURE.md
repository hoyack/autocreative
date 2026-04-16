# Architecture Patterns

**Domain:** AI-powered flyer generation pipeline
**Researched:** 2026-04-16

## Recommended Architecture

**Pattern:** Linear async pipeline with a single retry loop, dependency-injected stages, and typed Pydantic contracts at every boundary.

The system is NOT a DAG, event bus, or microservice mesh. It is a sequential pipeline with one control-flow branch (vision rejection triggers regeneration). This simplicity is deliberate -- there are no parallelizable stages, and over-engineering the orchestration would add complexity with zero throughput benefit for a single flyer.

```
EventInput (Pydantic model)
    |
    v
[StylePromptBuilder]     Pure function: preset + event -> ComfyCloud workflow JSON
    |
    v
[ComfyClient]            Async HTTP: submit workflow, poll status, download PNG bytes
    |
    v
[ImagePreprocessor]      Pillow: resize 832x1472 -> 1080x1920 via LANCZOS
    |
    v
[VisionEvaluator]        Async HTTP: Claude vision API -> VisionVerdict
    |
    +-- rejected? ------> increment attempt, feed refinement_hint back to
    |                      StylePromptBuilder, loop (max N attempts)
    v (approved)
[LayoutResolver]         Pure function: zone labels -> pixel coords
    |
    v
[PosterComposer]         Pure function: event data + background + layout -> SVG string
    |
    v
[Rasterizer]             cairosvg: SVG string -> PNG bytes
    |
    v
FlyerOutput (PNG bytes + metadata)
```

### Component Boundaries

| Component | Responsibility | Input Type | Output Type | Side Effects | Communicates With |
|-----------|---------------|------------|-------------|--------------|-------------------|
| **StylePromptBuilder** | Assemble ComfyCloud workflow JSON from preset + event + refinement hint | `EventInput`, attempt number, hint string | `ComfyWorkflow` | None (pure) | PresetRegistry (reads presets) |
| **PresetRegistry** | Store and retrieve named style presets | preset name | `StylePreset` | None (pure) | StylePromptBuilder |
| **ComfyClient** | Submit workflow, poll until done, download image | `ComfyWorkflow` | `GeneratedBackground` (raw bytes) | HTTP to ComfyCloud API | External: ComfyCloud |
| **ImagePreprocessor** | Upscale raw image to target dimensions | raw PNG bytes | `GeneratedBackground` (1080x1920 bytes) | None (CPU-bound) | None |
| **VisionEvaluator** | Evaluate background suitability, determine zones and text color | `GeneratedBackground` + `EventInput` | `VisionVerdict` | HTTP to Anthropic API | External: Claude API |
| **LayoutResolver** | Map zone labels to pixel coordinates | `LayoutZones` | `ResolvedLayout` | None (pure) | zones.py (zone coordinate data) |
| **PosterComposer** | Build SVG document with text overlays, scrims, badges | Event + background + verdict + layout | SVG string | None (pure) | None |
| **Rasterizer** | Convert SVG to final PNG | SVG string | PNG bytes | CPU-bound rendering | cairosvg library |
| **FlyerGenerator** (orchestrator) | Wire stages together, own retry loop, bind trace_id | `EventInput` | `FlyerOutput` | Delegates to stages | All stages |

### Data Flow

**Forward path (happy path):**

```
EventInput
  -> StylePromptBuilder.build(event, attempt=1, hint="")
  -> ComfyWorkflow {node_graph_json, positive_prompt, negative_prompt, seed}
  -> ComfyClient.generate(workflow)
     [HTTP POST /api/prompt -> prompt_id]
     [HTTP GET /api/job/{id}/status -> poll until "completed"]
     [HTTP GET /api/view?filename=... -> raw PNG bytes]
  -> GeneratedBackground {image_bytes: bytes, source_dims, final_dims, comfy_job}
  -> ImagePreprocessor.upscale(raw_bytes)
  -> GeneratedBackground {image_bytes: 1080x1920 PNG}
  -> VisionEvaluator.evaluate(background, event)
     [HTTP POST Anthropic messages API with base64 image + system prompt]
     [Parse JSON from response -> VisionVerdict]
  -> VisionVerdict {approved=True, zones, text_color, confidence}
  -> LayoutResolver.resolve(verdict.zones)
  -> ResolvedLayout {title: ZoneCoord, details: ZoneCoord, ...}
  -> PosterComposer.compose(event, background, verdict, layout)
  -> SVG string (~2MB with base64-embedded background)
  -> Rasterizer.rasterize(svg)
  -> PNG bytes (1080x1920)
  -> FlyerOutput {png_bytes, dimensions, attempts_used, trace_id, ...}
```

**Retry path (vision rejection):**

```
VisionVerdict {approved=False, refinement_hint="too cluttered in upper third", rejection_reasons=[...]}
  -> FlyerGenerator stores hint, increments attempt counter
  -> StylePromptBuilder.build(event, attempt=N, hint=refinement_hint)
  -> ... (full forward path repeats)
  -> After max_bg_attempts exhausted: raise MaxAttemptsExceededError
```

**Key data characteristics:**
- Image bytes are the largest data object (~1-3MB PNG). They are passed by reference (Python bytes), not serialized between stages.
- The SVG string with embedded base64 background is transiently ~2MB. It exists only between PosterComposer and Rasterizer, then is discarded.
- All cross-stage contracts are Pydantic models defined in `models.py`. Changing a shape means changing one file.

### External API Interactions

**ComfyCloud API (image generation):**
- Auth: `X-API-Key` header on every request
- Submit: `POST https://cloud.comfy.org/api/prompt` with `{"prompt": workflow_json}` -> returns `prompt_id`
- Poll: `GET https://cloud.comfy.org/api/job/{prompt_id}/status` -> `pending | in_progress | completed | failed | cancelled`
- Download: `GET https://cloud.comfy.org/api/view?filename=...&type=output` -> 302 redirect to signed URL -> PNG bytes
- Latency: 15-30s per generation
- Concurrency limits by tier (1-5 concurrent jobs)

**Anthropic Claude API (vision evaluation):**
- Auth: `x-api-key` header + `anthropic-version` header
- Single `POST /v1/messages` call with image content block (base64) + text block
- Returns structured JSON inside text response (needs parsing from markdown fences)
- Latency: 3-5s per call
- Cost: dominant per-attempt cost due to large image input tokens

## Patterns to Follow

### Pattern 1: Dependency-Injected Stages

**What:** Each stage class receives its dependencies (settings, HTTP client, preset registry) at construction time. The orchestrator (`FlyerGenerator`) wires them together.

**Why:** Every stage is independently testable by injecting fakes. No global state, no singletons, no module-level clients.

**Example:**
```python
class ComfyClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._client = http_client

    async def generate(self, workflow: ComfyWorkflow) -> GeneratedBackground:
        prompt_id = await self._submit(workflow)
        await self._wait_for_completion(prompt_id)
        return await self._download_result(prompt_id)
```

### Pattern 2: Single Shared httpx.AsyncClient

**What:** One `httpx.AsyncClient` instance shared across all stages that make HTTP calls (ComfyClient, VisionEvaluator). Created at `FlyerGenerator` construction, closed at teardown.

**Why:** Connection pooling. Creating a new client per request wastes TCP connections and DNS lookups. httpx is designed for client reuse.

**Example:**
```python
class FlyerGenerator:
    def __init__(self, settings: Settings, ...):
        self._http = http_client or httpx.AsyncClient(timeout=60.0)
        self._comfy = ComfyClient(settings, self._http)
        self._vision = VisionEvaluator(settings, self._http)
```

### Pattern 3: Typed Error Hierarchy

**What:** Every failure mode has a specific exception type inheriting from `FlyerGeneratorError`. Exceptions carry context (attempt number, trace_id, last known state).

**Why:** Callers can catch at the granularity they need. `except ComfyJobTimeoutError` vs `except ComfyError` vs `except FlyerGeneratorError`. Log correlation is automatic because exceptions carry trace_id.

### Pattern 4: Pydantic Models as Stage Contracts

**What:** All data flowing between stages is a Pydantic BaseModel. Defined centrally in `models.py`.

**Why:** Runtime validation at every boundary catches shape mismatches early. Serialization is free (for logging, debugging, caching later). Type checkers (mypy) catch contract violations at development time.

### Pattern 5: Vision Response Defensive Parsing

**What:** The VisionEvaluator does not trust Claude's JSON output. It strips markdown fences, extracts the JSON substring, validates against the Pydantic model, and retries once on parse failure.

**Why:** LLM outputs are inherently non-deterministic. Even with explicit JSON schema instructions, responses sometimes include prose wrapping, malformed fields, or unexpected structures. Defensive parsing is not optional -- it is a core reliability requirement.

**Example:**
```python
def _parse_vision_response(self, raw: str) -> VisionVerdict:
    # Strip markdown code fences
    text = re.sub(r"```json\s*", "", raw)
    text = re.sub(r"```\s*$", "", text)
    # Extract JSON substring
    start = text.index("{")
    end = text.rindex("}") + 1
    json_str = text[start:end]
    return VisionVerdict.model_validate_json(json_str)
```

### Pattern 6: Structured Logging with Trace ID

**What:** Every pipeline run generates a UUID trace_id. All log entries within that run include the trace_id. Key events logged: attempt_start, comfy_submitted, comfy_completed, vision_approved/rejected, flyer_generated.

**Why:** When running concurrent generations (via asyncio.gather), logs interleave. Without trace_id, debugging a specific run is impossible. structlog's bound logger pattern makes this ergonomic.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Global httpx Client or Module-Level State

**What:** Creating `httpx.AsyncClient()` at module import time or as a global variable.
**Why bad:** Cannot be garbage collected, cannot inject test doubles, lifetime unclear in async contexts.
**Instead:** Inject the client through constructors. Let the orchestrator own the lifecycle.

### Anti-Pattern 2: Recursive Retry Logic

**What:** Implementing the regeneration loop via recursion (`generate -> evaluate -> rejected -> generate`).
**Why bad:** Stack depth grows with attempts. Harder to reason about, harder to set a cap, harder to log attempt numbers.
**Instead:** Explicit `for attempt in range(1, max + 1)` loop in the orchestrator. Clear, bounded, loggable.

### Anti-Pattern 3: Embedding SVG Templates in Python Strings Without Escaping

**What:** Using f-strings to inject user text directly into SVG XML.
**Why bad:** XML injection. A title containing `<` or `&` breaks the SVG or creates security issues.
**Instead:** Use `xml.sax.saxutils.escape()` on every user-supplied string before embedding in SVG.

### Anti-Pattern 4: Polling Without Backoff or Cap

**What:** Tight polling loop on ComfyCloud status with no delay, no cap, no exponential backoff on errors.
**Why bad:** Wastes API quota, creates load, can loop forever on stuck jobs.
**Instead:** Initial wait (3s), fixed interval (4s), max attempts (20 = ~80s total), exponential backoff on 5xx errors.

### Anti-Pattern 5: Swallowing Vision Parse Errors

**What:** If Claude returns unparseable JSON, silently using default zones or auto-approving.
**Why bad:** Hides model degradation. Produces flyers with poorly placed text. Silent failures compound.
**Instead:** Retry once with a "JSON only" follow-up prompt. If still unparseable, raise `VisionResponseParseError` and let the caller decide.

### Anti-Pattern 6: Monolithic Compose Function

**What:** One 500-line function that handles title sizing, scrim generation, badge rendering, accent lines, and SVG assembly.
**Why bad:** Untestable, unmaintainable. Any change risks breaking unrelated layout elements.
**Instead:** Break into focused helpers: `_build_title_block()`, `_build_scrim()`, `_build_fee_badge()`, `_build_accent_line()`, each returning an SVG fragment string. The main `compose()` method assembles them.

## Scalability Considerations

| Concern | Single user (1 flyer) | Moderate (10 concurrent) | High (100+ concurrent) |
|---------|----------------------|-------------------------|----------------------|
| **Latency** | 20-40s (dominated by ComfyCloud) | Same per-flyer, but ComfyCloud tier limits queue jobs | Queueing system needed; ComfyCloud Pro allows 5 concurrent |
| **Memory** | ~10MB peak (2MB SVG + image buffers) | ~100MB with 10 concurrent (acceptable) | Need streaming or worker pools; 1GB+ otherwise |
| **API costs** | ~$0.02-0.05 per flyer (Claude vision dominant) | Linear scaling | Batch pricing negotiation, consider caching approved backgrounds |
| **CPU** | Pillow upscale + cairosvg rasterize: <1s | Negligible | Still negligible; I/O-bound, not CPU-bound |
| **Rate limits** | Not a concern | ComfyCloud concurrency is the bottleneck | Need job queue + rate limiter; Anthropic rate limits may also apply |

**Key insight:** This pipeline is I/O-bound (waiting for ComfyCloud and Claude), not CPU-bound. Concurrency scaling means managing API concurrency limits, not adding compute. asyncio with semaphores is the right tool for throttling concurrent flyer generation.

## Suggested Build Order

Build order follows data flow. Each phase produces a testable, runnable increment.

### Phase 1: Foundation (no external APIs)
**Build:** `models.py`, `config.py`, `errors.py`, `logging_config.py`, `presets.py`, `zones.py`
**Why first:** These are the contracts and configuration that every other component depends on. Building them first ensures type safety from day one. All are pure Python with no side effects -- fast to write, fast to test.
**Test:** Unit tests for model validation, preset registration, zone coordinate lookups, config loading.
**Dependency:** None.

### Phase 2: Prompt Building (no external APIs)
**Build:** `stages/prompt_builder.py`
**Why second:** It is the pipeline entry point after EventInput. It depends only on Phase 1 (models, presets). Testing is straightforward -- snapshot-test prompt strings.
**Test:** Verify prompt assembly for each preset, refinement hint injection, seed generation.
**Dependency:** Phase 1.

### Phase 3: ComfyCloud Integration (first external API)
**Build:** `stages/comfy_client.py`
**Why third:** First external dependency. Isolating it here means the polling logic, error handling, and retry behavior can be thoroughly tested with pytest-httpx mocks before anything else depends on it.
**Test:** Mock submit/poll/download. Test timeout, failure, and cancellation paths. One live smoke test behind env flag.
**Dependency:** Phase 1 (models, config, errors).

### Phase 4: Image Preprocessing
**Build:** `stages/preprocessor.py`
**Why here:** Simple Pillow resize. Quick to implement, needed before vision evaluation.
**Test:** Feed a known 832x1472 test image, assert output is 1080x1920, assert LANCZOS quality.
**Dependency:** Phase 1.

### Phase 5: Vision Evaluation (second external API)
**Build:** `stages/vision.py`
**Why here:** This is the most complex stage due to LLM response parsing uncertainty. Build it after the simpler stages are solid.
**Test:** Heavy focus on response parsing -- valid JSON, markdown-fenced JSON, missing fields, invalid zone names, low confidence flipping. Mock Anthropic API with pytest-httpx.
**Dependency:** Phase 1, Phase 4 (needs a GeneratedBackground to evaluate).

### Phase 6: Layout + Composition + Rasterization
**Build:** `stages/layout.py`, `stages/composer.py`, `stages/rasterizer.py`
**Why together:** These three stages are tightly coupled in the data flow (layout -> compose -> rasterize) and each is relatively small. Building them together enables end-to-end visual testing with a fixture background + fixture vision verdict.
**Test:** Layout resolution (pure function tests). SVG snapshot tests for composer. Rasterizer output dimension assertions. Visual diff test with a known-good PNG.
**Dependency:** Phase 1 (models, zones).

### Phase 7: Pipeline Orchestration + CLI
**Build:** `pipeline.py`, `__init__.py`, `__main__.py`
**Why last:** The orchestrator wires all stages together. All stages must exist first. The CLI is a thin wrapper over the public API.
**Test:** Integration test with all stages mocked. End-to-end live smoke test. CLI argument parsing tests.
**Dependency:** All previous phases.

### Dependency Graph

```
Phase 1 (Foundation)
  |
  +---> Phase 2 (Prompt Builder)
  |
  +---> Phase 3 (ComfyClient)
  |
  +---> Phase 4 (Preprocessor)
  |       |
  |       v
  +---> Phase 5 (Vision Evaluator)
  |
  +---> Phase 6 (Layout + Composer + Rasterizer)
  |
  v
Phase 7 (Pipeline Orchestrator + CLI)
```

Phases 2-6 can technically be built in parallel after Phase 1 (except Phase 5 depends on Phase 4 for its input type). Phase 7 must come last.

## Key Technical Decisions

### cairosvg Data URI Handling
CairoSVG 2.7.0 initially broke base64 data URI rendering (required `unsafe=True`), but this was fixed in a subsequent release. Data URIs now work in safe mode. Use `cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=1080, output_height=1920)` without the unsafe flag. Pin cairosvg >= 2.7.1 to ensure the fix is present.

**Confidence:** HIGH (verified via GitHub issue #383 resolution and Context7 docs)

### httpx Transport Retry Strategy
httpx does not have built-in retry middleware for application-level retries (e.g., retry on 500). The transport-level `retries` parameter only handles connection failures. For 5xx retries on ComfyCloud, implement application-level retry with exponential backoff inside `ComfyClient` methods.

**Confidence:** HIGH (verified via Context7 httpx docs)

### Async Architecture
The entire pipeline is async (`async def` throughout). This is correct because:
1. ComfyCloud polling is I/O-wait-dominant (15-30s).
2. Claude vision call is I/O-wait (3-5s).
3. asyncio enables future concurrent flyer generation via `asyncio.gather()` with semaphores.

Pillow upscale and cairosvg rasterize are synchronous CPU operations. Wrap in `asyncio.to_thread()` only if profiling shows they block the event loop meaningfully (unlikely at <1s each).

**Confidence:** HIGH

## Sources

- [ComfyCloud API Overview](https://docs.comfy.org/development/cloud/overview) - API endpoints and authentication
- [CairoSVG Issue #383](https://github.com/Kozea/CairoSVG/issues/383) - Data URI rendering fix confirmed
- [CairoSVG Documentation](https://cairosvg.org/documentation/) - svg2png API reference
- Context7: httpx /encode/httpx - Async client patterns, timeout handling, transport retries
- Context7: cairosvg /kozea/cairosvg - svg2png API, low-level surface API
- Context7: pytest-httpx /colin-b/pytest_httpx - Mock patterns for async HTTP testing
- `docs/spec.md` - Full technical specification (primary architecture source)
- `docs/n8n.json` - Working n8n workflow with exact prompts and ComfyCloud workflow JSON
