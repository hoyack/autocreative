# Phase 2: Image Pipeline - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the image generation and evaluation pipeline: StylePromptBuilder composes prompts from presets, ComfyClient submits/polls/downloads from ComfyCloud API, ImagePreprocessor upscales to final resolution, and VisionEvaluator calls Claude vision for approval + layout zones + text color. No SVG composition, no pipeline orchestration — those are Phase 3 and Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Prompt Building (stages/prompt_builder.py)
- **D-01:** StylePromptBuilder is a class taking PresetRegistry in __init__, with a build() method returning a ComfyWorkflow object
- **D-02:** Positive prompt composed by: preset positive_fragments (with {concept} substituted) + FLYER_DIRECTIVES + optional refinement hint
- **D-03:** Negative prompt composed by: UNIVERSAL_NEGATIVE + preset negative_fragment
- **D-04:** Seed generated via secrets.randbelow(2**31) per spec
- **D-05:** ComfyWorkflow wraps the node-graph dict from COMFY_WORKFLOW_TEMPLATE in presets.py, injecting positive/negative prompts and seed

### ComfyCloud Integration (stages/comfy_client.py)
- **D-06:** ComfyClient uses injected httpx.AsyncClient for testability
- **D-07:** Submit via POST /api/prompt with X-API-Key header, returns prompt_id
- **D-08:** Poll via GET /api/job/{prompt_id}/status — initial wait 3s, then poll every 4s, max 20 attempts
- **D-09:** Statuses: "success" → done; "failed"/"cancelled" → raise ComfyJobFailedError; anything else → keep polling
- **D-10:** 5xx responses trigger exponential backoff (3 retries, starting at 1s) before raising ComfySubmitError
- **D-11:** Download via GET /api/history_v2/{prompt_id} to find filename, then GET /api/view to download. Returns first image found.
- **D-12:** generate() method orchestrates submit → wait_for_completion → download_result, returns GeneratedBackground

### Image Preprocessing (stages/preprocessor.py)
- **D-13:** ImagePreprocessor.upscale() takes raw PNG bytes, returns GeneratedBackground with 1080x1920 image_bytes
- **D-14:** Uses Pillow Image.resize((1080, 1920), Image.Resampling.LANCZOS)
- **D-15:** Records source_dimensions (832, 1472) and final_dimensions (1080, 1920) in the model

### Vision Evaluation (stages/vision.py)
- **D-16:** VisionEvaluator uses injected httpx.AsyncClient (or Anthropic SDK — Claude's discretion on which is cleaner)
- **D-17:** System prompt stored as module-level constant, verbatim from n8n workflow's Build Vision Payload node
- **D-18:** User message is structured content: base64-encoded PNG image + text block describing the event
- **D-19:** Response parsing: strip markdown fences → extract first { to last } → json.loads → Pydantic VisionVerdict validation
- **D-20:** On parse failure: one retry with same image and "Return valid JSON only, no prose" follow-up
- **D-21:** Confidence gate: if approved=True but confidence < settings.vision_confidence_threshold, flip approved to False
- **D-22:** Zone validation: reject approved verdicts where zones is null or contains invalid zone names

### Claude's Discretion
- Whether to use httpx directly or the Anthropic Python SDK for vision calls — SDK may be cleaner for structured messages
- Exact test structure for mocking ComfyCloud and Anthropic APIs (use respx or pytest-httpx)
- Whether ComfyWorkflow should be a Pydantic model or a simple dataclass wrapping a dict

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Specification
- `docs/spec.md` §6.1 — StylePromptBuilder spec (signature, behavior, testability)
- `docs/spec.md` §6.3 — ComfyClient spec (polling logic, HTTP, download)
- `docs/spec.md` §6.4 — ImagePreprocessor spec (upscale, Pillow)
- `docs/spec.md` §6.5 — VisionEvaluator spec (system prompt, parsing, confidence gate, zone validation)

### Reference Implementation
- `docs/n8n.json` — Build Background Prompt node (prompt composition logic), Submit/Poll/Download nodes (API endpoints), Build Vision Payload node (system prompt, user message structure), Parse Vision Response node (JSON extraction logic)

### Foundation (Phase 1 output)
- `flyer_generator/models.py` — ComfyJob, GeneratedBackground, VisionVerdict, LayoutZones models
- `flyer_generator/config.py` — Settings with all ComfyCloud and vision tunable values
- `flyer_generator/errors.py` — ComfySubmitError, ComfyJobFailedError, ComfyJobTimeoutError, ComfyDownloadError, VisionAPIError, VisionResponseParseError
- `flyer_generator/presets.py` — PresetRegistry, StylePreset, FLYER_DIRECTIVES, UNIVERSAL_NEGATIVE, COMFY_WORKFLOW_TEMPLATE

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `flyer_generator/presets.py` — COMFY_WORKFLOW_TEMPLATE dict, FLYER_DIRECTIVES list, UNIVERSAL_NEGATIVE string, PresetRegistry with 6 presets
- `flyer_generator/models.py` — ComfyJob, GeneratedBackground, VisionVerdict already defined with validators
- `flyer_generator/config.py` — Settings with poll_initial_wait_seconds, poll_interval_seconds, poll_max_attempts, vision_model, vision_max_tokens, vision_timeout_seconds, vision_confidence_threshold
- `flyer_generator/errors.py` — All Comfy* and Vision* exception classes ready to use

### Established Patterns
- Pydantic v2 models with SettingsConfigDict (not deprecated class Config)
- SecretStr for API keys
- Module-level constants for prompt data

### Integration Points
- stages/prompt_builder.py imports from presets.py (PresetRegistry, FLYER_DIRECTIVES, UNIVERSAL_NEGATIVE, COMFY_WORKFLOW_TEMPLATE)
- stages/comfy_client.py imports from models.py (ComfyJob, GeneratedBackground), config.py (Settings), errors.py (Comfy* errors)
- stages/preprocessor.py imports from models.py (GeneratedBackground)
- stages/vision.py imports from models.py (VisionVerdict, GeneratedBackground), config.py (Settings), errors.py (Vision* errors)

</code_context>

<specifics>
## Specific Ideas

- ComfyCloud workflow JSON uses specific model files: z_image_turbo_bf16.safetensors (UNet), qwen_3_4b.safetensors (CLIP), ae.safetensors (VAE) ��� these are already in COMFY_WORKFLOW_TEMPLATE
- Vision system prompt is ~1000 words describing 3x3 grid, JSON schema, confidence semantics — carry over verbatim from n8n Build Vision Payload node
- Polling should log each attempt with elapsed time for debugging slow generations
- The n8n workflow uses /api/job/{id}/status for polling (not /api/history), and /api/history_v2/{prompt_id} + /api/view for download

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-image-pipeline*
*Context gathered: 2026-04-16 via auto mode*
