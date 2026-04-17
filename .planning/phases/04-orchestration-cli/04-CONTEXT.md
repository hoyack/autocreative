# Phase 4: Orchestration & CLI - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire all pipeline stages into a complete FlyerGenerator orchestrator with regeneration loop, implement the CLI entrypoint via typer, and finalize the public API surface. This is the integration phase — all individual stages exist from Phases 1-3; this phase connects them.

</domain>

<decisions>
## Implementation Decisions

### Pipeline Orchestration (pipeline.py)
- **D-01:** FlyerGenerator class per spec §7 — constructor takes Settings, optional PresetRegistry, optional httpx.AsyncClient
- **D-02:** generate() method is async, runs the full pipeline: prompt → comfy → upscale → vision → (reject? → refine → loop) → layout → compose → rasterize → return FlyerOutput
- **D-03:** Regeneration loop: for attempt in range(1, max_bg_attempts + 1), feeding verdict.refinement_hint back to prompt_builder on rejection
- **D-04:** Each run generates trace_id = uuid.uuid4().hex, bound into structlog logger context
- **D-05:** On exhausting max attempts, raise MaxAttemptsExceededError with rejection_history
- **D-06:** All stage instances created in __init__ via dependency injection — trivial to swap for fakes in tests

### CLI (__main__.py)
- **D-07:** CLI via typer with all args from spec §10: --title, --date, --time, --venue, --address, --fees, --org, --concept, --preset, --accent, --output
- **D-08:** --event-json loads EventInput from JSON file
- **D-09:** --list-presets enumerates available styles and exits
- **D-10:** --dry-run builds prompt and prints it without calling ComfyCloud
- **D-11:** --max-attempts overrides settings.max_bg_attempts
- **D-12:** CLI runs asyncio.run() on the async generate() method

### Public API (__init__.py)
- **D-13:** generate_flyer() convenience function: constructs FlyerGenerator with defaults, runs once
- **D-14:** Full __init__.py exports: FlyerGenerator, EventInput, FlyerOutput, Settings, PresetRegistry, StylePreset, FlyerGeneratorError, MaxAttemptsExceededError, VisionResponseParseError, ComfyJobTimeoutError
- **D-15:** generate_flyer() is async — callers use asyncio.run() or await

### Structured Logging
- **D-16:** Key events logged per spec §9: attempt_start, comfy_submitted (with prompt_id), comfy_completed (with elapsed), vision_approved/rejected (with confidence + zones or reasons), flyer_generated (with size + attempts)
- **D-17:** No API keys or base64 payloads in logs — log prompt hash at info level, full prompt at debug only

### Claude's Discretion
- How to structure the FlyerGenerator.__init__ (whether to accept individual stage instances or construct them internally)
- Error message formatting for CLI user-facing output
- Test approach for the pipeline integration test (mock all stages vs selective mocking)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Specification
- `docs/spec.md` §7 — Pipeline orchestration (FlyerGenerator class, generate() loop, stage wiring)
- `docs/spec.md` §10 — CLI (__main__.py, all flags, event-json, dry-run, list-presets)
- `docs/spec.md` §11 — Public API (generate_flyer(), exports)
- `docs/spec.md` §9 — Logging (trace_id, key events, what not to log)

### Reference Implementation
- `docs/n8n.json` — Full workflow connection graph showing stage ordering

### All Stage Modules (Phases 1-3 output)
- `flyer_generator/stages/prompt_builder.py` — StylePromptBuilder, ComfyWorkflow
- `flyer_generator/stages/comfy_client.py` — ComfyClient
- `flyer_generator/stages/preprocessor.py` — ImagePreprocessor
- `flyer_generator/stages/vision.py` — VisionEvaluator
- `flyer_generator/stages/layout.py` — LayoutResolver
- `flyer_generator/stages/composer.py` — PosterComposer
- `flyer_generator/stages/rasterizer.py` — Rasterizer
- `flyer_generator/models.py` — All data models
- `flyer_generator/config.py` — Settings
- `flyer_generator/errors.py` — All exceptions
- `flyer_generator/presets.py` — PresetRegistry, build_default_registry()
- `flyer_generator/logging_config.py` — configure_logging(), get_logger()

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- All 7 stage classes are complete and tested (145 tests passing)
- Settings class has all configuration values needed by the orchestrator
- PresetRegistry with build_default_registry() factory
- configure_logging() and get_logger() from logging_config.py
- All Pydantic models with validation

### Established Patterns
- Stage classes take Settings + optional dependencies in __init__
- Async methods for I/O stages (ComfyClient, VisionEvaluator)
- Sync methods for pure stages (PromptBuilder, Preprocessor, LayoutResolver, Composer, Rasterizer)
- structlog with bind() for context

### Integration Points
- pipeline.py imports all stage classes and wires them
- __main__.py imports FlyerGenerator and EventInput
- __init__.py re-exports the public API surface

</code_context>

<specifics>
## Specific Ideas

- The pipeline.py generate() method should closely mirror the pseudocode in spec §7
- CLI should use typer.Typer() app with a single main command
- --dry-run should still call StylePromptBuilder to show the actual prompt that would be sent
- FlyerOutput.save() already exists from Phase 1 — CLI just calls it

</specifics>

<deferred>
## Deferred Ideas

None — this is the final phase

</deferred>

---

*Phase: 04-orchestration-cli*
*Context gathered: 2026-04-16 via manual mode*
