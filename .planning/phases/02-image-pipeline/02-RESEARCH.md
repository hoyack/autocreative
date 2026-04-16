# Phase 2: Image Pipeline - Research

**Researched:** 2026-04-16
**Domain:** ComfyCloud image generation + Claude vision evaluation
**Confidence:** HIGH

## Summary

Phase 2 implements four stage modules: StylePromptBuilder (prompt composition), ComfyClient (ComfyCloud submit/poll/download), ImagePreprocessor (Pillow upscale), and VisionEvaluator (Claude vision API call + response parsing). All data models, configuration, error types, and presets already exist from Phase 1 -- this phase is pure stage implementation against well-defined contracts.

The two external API integrations are ComfyCloud (REST, experimental) and Anthropic Claude (via official Python SDK, well-documented). The ComfyCloud API is simple (3 endpoints: submit, poll status, download via history+view) but has a critical status value discrepancy between the n8n reference implementation and official docs. The Anthropic SDK is mature and handles vision natively with base64 image content blocks.

**Primary recommendation:** Use the Anthropic Python SDK (AsyncAnthropic) for vision calls -- it handles auth, retries, structured messages, and timeouts natively. Use raw httpx for ComfyCloud since it's a simple REST API with custom polling logic.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** StylePromptBuilder is a class taking PresetRegistry in __init__, with a build() method returning a ComfyWorkflow object
- **D-02:** Positive prompt composed by: preset positive_fragments (with {concept} substituted) + FLYER_DIRECTIVES + optional refinement hint
- **D-03:** Negative prompt composed by: UNIVERSAL_NEGATIVE + preset negative_fragment
- **D-04:** Seed generated via secrets.randbelow(2**31) per spec
- **D-05:** ComfyWorkflow wraps the node-graph dict from COMFY_WORKFLOW_TEMPLATE in presets.py, injecting positive/negative prompts and seed
- **D-06:** ComfyClient uses injected httpx.AsyncClient for testability
- **D-07:** Submit via POST /api/prompt with X-API-Key header, returns prompt_id
- **D-08:** Poll via GET /api/job/{prompt_id}/status -- initial wait 3s, then poll every 4s, max 20 attempts
- **D-09:** Statuses: "success" -> done; "failed"/"cancelled" -> raise ComfyJobFailedError; anything else -> keep polling
- **D-10:** 5xx responses trigger exponential backoff (3 retries, starting at 1s) before raising ComfySubmitError
- **D-11:** Download via GET /api/history_v2/{prompt_id} to find filename, then GET /api/view to download. Returns first image found.
- **D-12:** generate() method orchestrates submit -> wait_for_completion -> download_result, returns GeneratedBackground
- **D-13:** ImagePreprocessor.upscale() takes raw PNG bytes, returns GeneratedBackground with 1080x1920 image_bytes
- **D-14:** Uses Pillow Image.resize((1080, 1920), Image.Resampling.LANCZOS)
- **D-15:** Records source_dimensions (832, 1472) and final_dimensions (1080, 1920) in the model
- **D-16:** VisionEvaluator uses injected httpx.AsyncClient (or Anthropic SDK -- Claude's discretion)
- **D-17:** System prompt stored as module-level constant, verbatim from n8n workflow's Build Vision Payload node
- **D-18:** User message is structured content: base64-encoded PNG image + text block describing the event
- **D-19:** Response parsing: strip markdown fences -> extract first { to last } -> json.loads -> Pydantic VisionVerdict validation
- **D-20:** On parse failure: one retry with same image and "Return valid JSON only, no prose" follow-up
- **D-21:** Confidence gate: if approved=True but confidence < settings.vision_confidence_threshold, flip approved to False
- **D-22:** Zone validation: reject approved verdicts where zones is null or contains invalid zone names

### Claude's Discretion
- Whether to use httpx directly or the Anthropic Python SDK for vision calls -- SDK may be cleaner for structured messages
- Exact test structure for mocking ComfyCloud and Anthropic APIs (use respx or pytest-httpx)
- Whether ComfyWorkflow should be a Pydantic model or a simple dataclass wrapping a dict

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IGEN-01 | StylePromptBuilder composes positive/negative prompts from preset + event concept + optional refinement hint | D-01 through D-05; prompt composition logic fully specified in n8n workflow and presets.py |
| IGEN-02 | ComfyClient submits workflow JSON to ComfyCloud API with X-API-Key header | D-06, D-07; ComfyCloud POST /api/prompt endpoint verified via official docs |
| IGEN-03 | ComfyClient polls job status with configurable interval and max attempts, with exponential backoff on 5xx | D-08, D-09, D-10; polling logic from n8n + status values from ComfyCloud docs |
| IGEN-04 | ComfyClient downloads result image via history_v2 + view endpoints | D-11; download flow from n8n Extract Image URL + Download Background nodes |
| IGEN-05 | ImagePreprocessor upscales 832x1472 to 1080x1920 using Pillow LANCZOS | D-13, D-14, D-15; Pillow 12.2.0 verified installed |
| VISN-01 | VisionEvaluator sends background + event context to Claude in a single API call | D-16, D-17, D-18; Anthropic SDK AsyncAnthropic verified with vision support |
| VISN-02 | Vision response parsed into VisionVerdict with approved, confidence, zones, text_color, rejection_reasons | D-19; parsing logic from n8n Parse Vision Response node |
| VISN-03 | Confidence gate flips approved to False when confidence < configurable threshold (default 0.6) | D-21; threshold from Settings.vision_confidence_threshold |
| VISN-04 | Parse failure triggers one retry with "return valid JSON only" follow-up prompt | D-20; retry pattern from spec section 6.5 |
| VISN-05 | Zone validation rejects approved verdicts with null or invalid zone names | D-22; ZoneName Literal type already defined in zones.py |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Prompt composition | Application logic | -- | Pure data transformation: preset + event -> workflow JSON. No I/O. |
| ComfyCloud submission/polling | API / Backend (external) | -- | HTTP calls to external ComfyCloud REST API |
| Image upscale | Application logic | -- | Local Pillow operation, no network |
| Vision evaluation | API / Backend (external) | Application logic | HTTP call to Anthropic API + local response parsing |
| Response parsing + validation | Application logic | -- | JSON extraction + Pydantic validation, no I/O |

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.96.0 | Claude vision API calls | Official SDK, handles auth/retries/types, already installed [VERIFIED: uv run import check] |
| httpx | 0.28.1 | ComfyCloud HTTP client | Async HTTP, injected for testability, already installed [VERIFIED: uv run import check] |
| Pillow | 12.2.0 | Image upscale 832x1472 -> 1080x1920 | LANCZOS resampling, already installed [VERIFIED: uv run import check] |
| pydantic | 2.13.1+ | VisionVerdict, ComfyWorkflow validation | All models defined in Phase 1 [VERIFIED: pyproject.toml] |

### Supporting (already installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| respx | 0.23.1 | HTTPX request mocking | All ComfyCloud HTTP tests [VERIFIED: uv run import check] |
| structlog | 25.5.0+ | Structured logging per poll/attempt | Each polling attempt, vision call timing [VERIFIED: pyproject.toml] |

**Installation:** No new packages needed. All dependencies were installed in Phase 1.

## Architecture Patterns

### System Architecture Diagram

```
EventInput + PresetName
       |
       v
[StylePromptBuilder] -- reads PresetRegistry, FLYER_DIRECTIVES, UNIVERSAL_NEGATIVE
       |                  injects prompts + seed into COMFY_WORKFLOW_TEMPLATE
       v
   ComfyWorkflow (node-graph dict)
       |
       v
[ComfyClient.submit()] -- POST /api/prompt --> prompt_id
       |
       v
[ComfyClient.wait_for_completion()] -- poll GET /api/job/{id}/status
       |                                 loop: 3s initial, then 4s intervals, max 20
       v
[ComfyClient.download_result()] -- GET /api/history_v2/{id} --> filename
       |                           GET /api/view?filename=...  --> raw PNG bytes
       v
   Raw PNG (832x1472)
       |
       v
[ImagePreprocessor.upscale()] -- Pillow resize LANCZOS
       |
       v
   GeneratedBackground (1080x1920)
       |
       v
[VisionEvaluator.evaluate()] -- base64 encode image
       |                        build system prompt + user message
       |                        AsyncAnthropic.messages.create()
       |                        parse JSON from response text
       |                        confidence gate + zone validation
       v
   VisionVerdict (approved/rejected, zones, text_color)
```

### Recommended Project Structure
```
flyer_generator/
  stages/
    __init__.py          # exists (empty)
    prompt_builder.py    # NEW: StylePromptBuilder class
    comfy_client.py      # NEW: ComfyClient class
    preprocessor.py      # NEW: ImagePreprocessor class
    vision.py            # NEW: VisionEvaluator class
tests/
    test_prompt_builder.py  # NEW
    test_comfy_client.py    # NEW
    test_preprocessor.py    # NEW
    test_vision.py          # NEW
    fixtures/
        sample_vision_response.json       # NEW
        sample_vision_rejected.json       # NEW
        sample_comfy_submit_response.json # NEW
        sample_comfy_status_response.json # NEW
        sample_comfy_history_response.json # NEW
```

### Pattern 1: Injected AsyncClient for Testability
**What:** Each stage that makes HTTP calls takes an httpx.AsyncClient as constructor argument.
**When to use:** ComfyClient (all ComfyCloud calls), and if using raw httpx for vision.
**Example:**
```python
# Source: CONTEXT.md D-06, spec section 6.3
class ComfyClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client
        self._base_url = settings.comfycloud_base_url
        self._headers = {
            "X-API-Key": settings.comfycloud_api_key.get_secret_value(),
        }
```

### Pattern 2: Anthropic SDK for Vision (Recommended Discretion Choice)
**What:** Use AsyncAnthropic client instead of raw httpx for Claude API calls.
**When to use:** VisionEvaluator -- the SDK handles auth headers, API versioning, retry on rate limits, structured content blocks, and timeout configuration natively.
**Example:**
```python
# Source: Context7 /anthropics/anthropic-sdk-python
from anthropic import AsyncAnthropic

class VisionEvaluator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.vision_timeout_seconds,
        )

    async def evaluate(self, background: GeneratedBackground, event: EventInput) -> VisionVerdict:
        response = await self._client.messages.create(
            model=self._settings.vision_model,
            max_tokens=self._settings.vision_max_tokens,
            system=VISION_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(background.image_bytes).decode(),
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }],
        )
        raw_text = response.content[0].text
        return self._parse_response(raw_text)
```

### Pattern 3: ComfyWorkflow as Pydantic Model (Recommended Discretion Choice)
**What:** Lightweight Pydantic model wrapping the workflow dict, with validation.
**When to use:** Return type from StylePromptBuilder.build().
**Example:**
```python
class ComfyWorkflow(BaseModel):
    """ComfyCloud workflow JSON with injected prompts and seed."""
    workflow: dict  # The node-graph dict ready for POST /api/prompt
    positive_prompt: str  # For logging/debugging
    negative_prompt: str
    seed: int
```
**Rationale:** Pydantic model is consistent with every other data contract in the project. A plain dataclass would also work but Pydantic gives free serialization and schema generation.

### Anti-Patterns to Avoid
- **Hardcoded API URLs in stage code:** All URLs derived from `settings.comfycloud_base_url`. The n8n workflow hardcodes `https://cloud.comfy.org` -- extract to settings.
- **Polling without elapsed time logging:** Each poll iteration MUST log attempt count and elapsed seconds (per CONTEXT.md specifics). Silent polling makes debugging slow generations impossible.
- **Catching generic Exception in response parsing:** Use specific json.JSONDecodeError and pydantic.ValidationError catches. Generic catches hide real bugs.
- **Building workflow JSON with string formatting:** Use copy.deepcopy of the template dict and inject values programmatically. String formatting on JSON is fragile and error-prone.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Anthropic API auth + retries | Custom httpx headers + retry logic | `anthropic.AsyncAnthropic` SDK | Handles API versioning, rate limit retries, auth, timeouts, content block types [VERIFIED: Context7] |
| Base64 encoding for vision | Custom encoding pipeline | `base64.b64encode()` + SDK content blocks | SDK expects standard base64 string in `source.data` field [VERIFIED: Context7] |
| JSON extraction from markdown | Custom regex parser | Simple `{` to `}` extraction + json.loads | Regex for markdown fences is over-engineering; the brace-extraction approach from n8n is battle-tested |

## Common Pitfalls

### Pitfall 1: ComfyCloud Status Value Mismatch
**What goes wrong:** The n8n reference workflow checks for `status === "success"`, but ComfyCloud official documentation lists the completion status as `"completed"`.
**Why it happens:** The n8n workflow was written against an earlier version of the API. The API may have changed status values, or the n8n version may be checking a different field.
**How to avoid:** Implement the client to check for BOTH `"success"` and `"completed"` as terminal success states. Log the actual status value received so discrepancies are caught immediately. The CONTEXT.md says D-09 uses "success" -- honor this but add "completed" as a safety net.
**Warning signs:** Jobs that complete successfully but the client times out waiting.
[VERIFIED: ComfyCloud docs at docs.comfy.org/development/cloud/api-reference show "completed"; n8n.json line 123 checks "success"]

### Pitfall 2: history_v2 Endpoint May Not Exist in Official API
**What goes wrong:** The n8n workflow uses `/api/history_v2/{prompt_id}` for finding output filenames, but this endpoint does not appear in the official ComfyCloud API documentation.
**Why it happens:** The endpoint may be undocumented, or the n8n workflow may have been using a beta/internal endpoint.
**How to avoid:** Implement the download flow as specified (D-11), but add error handling that catches 404 responses with a clear error message. Consider falling back to `/api/history/{prompt_id}` if history_v2 fails. Log the full response for debugging.
**Warning signs:** 404 errors on the download step after successful job completion.
[VERIFIED: Official docs do NOT document history_v2; n8n.json line 199 uses it]

### Pitfall 3: Vision Response Contains Markdown Fences
**What goes wrong:** Claude sometimes wraps JSON in ` ```json ``` ` fences or adds explanatory prose before/after, despite instructions to return "ONLY valid JSON."
**Why it happens:** LLM behavior is non-deterministic. Even with explicit instructions, models sometimes add formatting.
**How to avoid:** The 3-step parsing pipeline from the n8n workflow is robust: (1) strip ` ```json ` / ` ``` ` fences, (2) extract substring between first `{` and last `}`, (3) json.loads. This handles all observed response formats.
**Warning signs:** VisionResponseParseError on the first attempt but success on retry.
[VERIFIED: n8n Parse Vision Response node implements this exact strategy]

### Pitfall 4: Large Base64 Images Bloat Memory
**What goes wrong:** A 1080x1920 PNG can be 2-4MB. Base64 encoding adds ~33% overhead. The image exists in memory as bytes, base64 string, and inside the API request body simultaneously.
**Why it happens:** Unavoidable with base64 image transmission, but manageable.
**How to avoid:** Don't keep multiple copies. Encode to base64 at the point of use (inside evaluate()), don't store the base64 string on the model. The GeneratedBackground stores raw bytes only.
**Warning signs:** Memory usage > 50MB per concurrent generation.

### Pitfall 5: Anthropic SDK vs Raw httpx for Testing
**What goes wrong:** If using the Anthropic SDK, respx cannot intercept its HTTP calls directly since the SDK manages its own httpx client internally.
**Why it happens:** The SDK creates its own transport layer.
**How to avoid:** Mock at the SDK level, not the HTTP level. Use `unittest.mock.patch` or `unittest.mock.AsyncMock` on `AsyncAnthropic.messages.create()`. Alternatively, the SDK accepts a custom `httpx.AsyncClient` via the `http_client` parameter -- inject a respx-mocked client there.
**Warning signs:** Tests that pass but don't actually test API interaction.
[ASSUMED -- SDK internals may vary; verify custom http_client injection support]

## Code Examples

### Prompt Composition (from n8n Build Background Prompt node)
```python
# Source: docs/n8n.json, Build Background Prompt & Workflow node
import copy
import secrets
from flyer_generator.presets import (
    COMFY_WORKFLOW_TEMPLATE, FLYER_DIRECTIVES, UNIVERSAL_NEGATIVE,
    PresetRegistry, StylePreset,
)

class StylePromptBuilder:
    def __init__(self, presets: PresetRegistry) -> None:
        self._presets = presets

    def build(self, event: EventInput, attempt: int, refinement_hint: str = "") -> ComfyWorkflow:
        preset = self._presets.get(event.style_preset)

        # D-02: positive = preset fragments (concept substituted) + directives + hint
        positive_parts = [
            frag.replace("{concept}", event.style_concept)
            for frag in preset.positive_fragments
        ]
        positive_parts.extend(FLYER_DIRECTIVES)
        if refinement_hint:
            positive_parts.append(f"Additional direction: {refinement_hint}")
        positive_prompt = " ".join(positive_parts)

        # D-03: negative = universal + preset-specific
        negative_prompt = f"{UNIVERSAL_NEGATIVE}, {preset.negative_fragment}"

        # D-04: seed
        seed = secrets.randbelow(2**31)

        # D-05: build workflow dict from template
        workflow = self._build_workflow_dict(positive_prompt, negative_prompt, seed)
        return ComfyWorkflow(
            workflow=workflow,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed=seed,
        )
```

### ComfyCloud Polling (from n8n Poll/Retry nodes)
```python
# Source: docs/n8n.json, Poll Job Status + Retry Guard nodes
import asyncio
import structlog

logger = structlog.get_logger()

async def wait_for_completion(self, prompt_id: str) -> None:
    await asyncio.sleep(self._settings.poll_initial_wait_seconds)
    start = asyncio.get_event_loop().time()

    for attempt in range(1, self._settings.poll_max_attempts + 1):
        elapsed = asyncio.get_event_loop().time() - start
        resp = await self._http.get(
            f"{self._base_url}/api/job/{prompt_id}/status",
            headers=self._headers,
        )
        resp.raise_for_status()
        status = resp.json().get("status", "unknown")

        logger.info("comfy_poll", prompt_id=prompt_id, attempt=attempt,
                     elapsed_s=round(elapsed, 1), status=status)

        if status in ("success", "completed"):
            return
        if status in ("failed", "cancelled"):
            raise ComfyJobFailedError(
                f"ComfyCloud job {status}: {prompt_id}",
                prompt_id=prompt_id,
            )
        await asyncio.sleep(self._settings.poll_interval_seconds)

    raise ComfyJobTimeoutError(
        f"ComfyCloud job timed out after {self._settings.poll_max_attempts} polls",
        prompt_id=prompt_id,
        attempts=self._settings.poll_max_attempts,
    )
```

### Vision System Prompt (verbatim from n8n Build Vision Payload)
```python
# Source: docs/n8n.json, Build Vision Payload node (line 256)
VISION_SYSTEM_PROMPT = """You are a professional graphic designer evaluating AI-generated background images for event flyers. Your job has two parts:

1. APPROPRIATENESS: Determine if the image is suitable for the given event. Consider subject match, mood/tone, visual quality (not blurry/deformed), and absence of unwanted elements (text, watermarks, people with distorted features).

2. LAYOUT: If approved, identify the optimal placement zones for flyer text elements. The canvas is 1080 wide x 1920 tall (9:16 portrait). Classify zones using a 3x3 grid:
   - Rows: TOP (0-640px), MIDDLE (640-1280px), BOTTOM (1280-1920px)
   - Cols: LEFT (0-360px), CENTER (360-720px), RIGHT (720-1080px)

For each text element, pick the ZONE with the cleanest visual area (smooth, low-detail, good contrast for white text).

Text elements to place:
- TITLE (largest, 3-4 lines max): the event name
- DETAILS (date, time, venue): supporting info block
- FEE_BADGE (small pill): price/cost indicator
- ORG_CREDIT (tiny): presenter line at very bottom

Return ONLY valid JSON. No prose, no markdown fences. Schema:
{
  "approved": true|false,
  "confidence": 0.0-1.0,
  "rejection_reasons": [] | ["specific issue 1", ...],
  "refinement_hint": "" | "guidance for regeneration, e.g. 'more sky area at top, less visual clutter'",
  "zones": {
    "title": "TOP_CENTER" | "TOP_LEFT" | "TOP_RIGHT" | "MIDDLE_CENTER" | ...,
    "details": "BOTTOM_CENTER" | ...,
    "fee_badge": "TOP_RIGHT" | "BOTTOM_LEFT" | ...,
    "org_credit": "BOTTOM_CENTER"
  },
  "text_color": "white" | "dark",
  "mood_tags": ["warm", "energetic", ...]
}

If approved is false, zones can be omitted. Confidence below 0.6 should trigger rejection."""
```

### Vision Response Parsing (from n8n Parse Vision Response)
```python
# Source: docs/n8n.json, Parse Vision Response node (line 291)
import json
import re
from pydantic import ValidationError

def _parse_response(self, raw_text: str) -> VisionVerdict:
    # Step 1: strip markdown fences
    cleaned = re.sub(r"```json\s*", "", raw_text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    # Step 2: extract first {...} block
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace < 0 or last_brace <= first_brace:
        raise VisionResponseParseError(f"No JSON object found in: {raw_text[:200]}")
    json_str = cleaned[first_brace:last_brace + 1]

    # Step 3: parse + validate
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise VisionResponseParseError(f"Invalid JSON: {e}") from e

    # D-21: confidence gate
    if data.get("approved") and isinstance(data.get("confidence"), (int, float)):
        if data["confidence"] < self._settings.vision_confidence_threshold:
            data["approved"] = False
            data.setdefault("rejection_reasons", []).append(
                f"Low confidence: {data['confidence']}"
            )

    try:
        return VisionVerdict(
            **data,
            raw_response=raw_text[:500],
        )
    except ValidationError as e:
        raise VisionResponseParseError(f"VisionVerdict validation failed: {e}") from e
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| anthropic SDK raw httpx headers | AsyncAnthropic with vision content blocks | SDK 0.87+ (March 2026) | No need to manage anthropic-version header or content block schemas manually [VERIFIED: Context7] |
| `claude-3-sonnet` model | `claude-sonnet-4-5` model | Sep 2025 | Settings.vision_model defaults to claude-sonnet-4-5 [VERIFIED: config.py] |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Anthropic SDK accepts custom httpx.AsyncClient via `http_client` param for testing | Pitfall 5 | Tests would need different mocking strategy (mock at SDK method level instead) -- low risk, both approaches work |
| A2 | ComfyCloud history_v2 endpoint exists and returns the format used in n8n workflow | Pitfall 2 | Download step would fail -- medium risk, need runtime verification |
| A3 | ComfyCloud status "success" vs "completed" -- the actual API may return either | Pitfall 1 | Polling would time out if only checking wrong value -- mitigated by checking both |

## Open Questions

1. **ComfyCloud status value: "success" vs "completed"**
   - What we know: n8n workflow checks "success" (D-09), official docs say "completed"
   - What's unclear: Which value the current API actually returns
   - Recommendation: Check for both values. Log actual status on each poll so we catch this in testing.

2. **history_v2 endpoint availability**
   - What we know: n8n workflow uses `/api/history_v2/{prompt_id}`, official docs don't mention it
   - What's unclear: Whether this is an undocumented endpoint or deprecated
   - Recommendation: Implement as specified (D-11), add fallback to `/api/history/{prompt_id}`, and robust error handling with clear logs.

3. **Anthropic SDK custom http_client injection**
   - What we know: The SDK likely supports this based on standard patterns in OpenAI-style SDKs
   - What's unclear: Exact constructor parameter name and behavior
   - Recommendation: For testing, mock at `AsyncAnthropic.messages.create()` level (simpler, guaranteed to work). Reserve custom client injection as an optimization.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.14.4 | -- |
| uv | Package management | Yes | 0.11.7 | -- |
| anthropic SDK | VisionEvaluator | Yes | 0.96.0 | -- |
| httpx | ComfyClient | Yes | 0.28.1 | -- |
| Pillow | ImagePreprocessor | Yes | 12.2.0 | -- |
| respx | Test mocking | Yes | 0.23.1 | -- |

**Missing dependencies with no fallback:** None
**Missing dependencies with fallback:** None

## Sources

### Primary (HIGH confidence)
- Context7 `/anthropics/anthropic-sdk-python` -- vision image base64 usage, async client, error handling
- `docs/n8n.json` -- exact prompt composition, polling logic, vision payload, response parsing (reference implementation)
- `docs/spec.md` sections 6.1, 6.3, 6.4, 6.5 -- stage specifications
- `flyer_generator/models.py`, `config.py`, `errors.py`, `presets.py` -- existing Phase 1 contracts

### Secondary (MEDIUM confidence)
- [ComfyCloud API Reference](https://docs.comfy.org/development/cloud/api-reference) -- endpoint documentation, status values (experimental API)

### Tertiary (LOW confidence)
- ComfyCloud history_v2 endpoint format -- only evidenced in n8n workflow, not in official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages installed, versions verified
- Architecture: HIGH -- all patterns derived from locked decisions and reference implementation
- Pitfalls: HIGH -- status value discrepancy verified against two sources; parsing pitfalls from n8n reference

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (30 days -- APIs are stable, ComfyCloud is experimental so watch for changes)
