# Phase 1: Foundation - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the shared vocabulary every pipeline stage depends on: Pydantic data models, environment-driven configuration, typed exception hierarchy, style presets registry, and zone coordinate definitions. No external API calls, no I/O — pure data contracts and project scaffolding.

</domain>

<decisions>
## Implementation Decisions

### Project Structure
- **D-01:** Follow the module layout from `docs/spec.md` Section 3 exactly — `flyer_generator/` package with `stages/` subpackage, `models.py` as the contract hub, `presets.py` and `zones.py` as extension points
- **D-02:** Use uv for dependency management with pyproject.toml — no setup.py, no requirements.txt
- **D-03:** Include dev dependencies (pytest, pytest-asyncio, mypy, ruff) in `[project.optional-dependencies]`
- **D-04:** Python 3.11+ minimum — use `from __future__ import annotations` is not needed

### Pydantic Models
- **D-05:** All cross-stage data defined in `models.py` — EventInput, ComfyJob, GeneratedBackground, VisionVerdict, LayoutZones, ResolvedLayout, FlyerOutput per spec Section 4
- **D-06:** Use Pydantic v2 BaseModel throughout; validators enforce hex color regex on color_accent, max lengths on text fields (reject > 120 chars)
- **D-07:** ZoneName is a Literal type with 9 values (TOP_LEFT, TOP_CENTER, TOP_RIGHT, MIDDLE_LEFT, MIDDLE_CENTER, MIDDLE_RIGHT, BOTTOM_LEFT, BOTTOM_CENTER, BOTTOM_RIGHT)
- **D-08:** VisionVerdict validator enforces zones required when approved=True
- **D-09:** FlyerOutput includes a `save(path: Path)` convenience method

### Configuration
- **D-10:** Use Pydantic Settings (pydantic-settings) with `env_prefix = "FLYER_"` and `.env` file support per spec Section 5
- **D-11:** All tunable values in Settings class — no magic numbers in stage code
- **D-12:** SecretStr for API keys (anthropic_api_key, comfycloud_api_key)

### Error Hierarchy
- **D-13:** Exception hierarchy per spec Section 8 — FlyerGeneratorError as base, with ComfyError and VisionError as intermediate bases
- **D-14:** Every exception carries context (attempt number, trace_id, last known state)

### Style Presets
- **D-15:** Six presets carried over verbatim from n8n workflow (see `docs/n8n.json` Build Background Prompt node): photorealistic, anime, western_cartoon, scifi, watercolor, retro_poster
- **D-16:** StylePreset is a Pydantic BaseModel with name, positive_fragments (list[str] with {concept} placeholder), negative_fragment, description
- **D-17:** PresetRegistry class with register(), get(), list_names() methods — extensible by users before calling generate_flyer()

### Zone Coordinates
- **D-18:** ZONE_COORDS dict in zones.py maps ZoneName to ZoneCoord(x, y, anchor) per spec Section 6.6
- **D-19:** ZoneCoord is a simple dataclass with x (int), y (int), anchor (Literal["start", "middle", "end"])
- **D-20:** Zone pixel values: TOP row y=320, MIDDLE row y=960, BOTTOM row y=1600; LEFT x=180, CENTER x=540, RIGHT x=900

### Claude's Discretion
- Logging configuration setup details (structlog initialization) — follow spec Section 9 guidance
- Exact `__init__.py` public API surface — follow spec Section 11
- Test fixture organization within `tests/fixtures/`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Specification
- `docs/spec.md` — Full technical specification: module layout (§3), data models (§4), configuration (§5), stage specs (§6), pipeline orchestration (§7), error hierarchy (§8), logging (§9), CLI (§10), public API (§11), dependencies (§12)

### Reference Implementation
- `docs/n8n.json` — Working n8n workflow with exact style preset prompts (Build Background Prompt node), ComfyCloud workflow JSON structure, vision system prompt, zone coordinates, SVG composition logic

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None yet — this phase establishes the patterns

### Integration Points
- All subsequent phases import from this foundation (models.py, config.py, errors.py, presets.py, zones.py)

</code_context>

<specifics>
## Specific Ideas

- Preset prompt text must be carried over verbatim from the n8n workflow — do not paraphrase or "improve" the proven prompts
- The ComfyCloud workflow JSON structure (node graph with specific model files: z_image_turbo_bf16.safetensors, qwen_3_4b.safetensors, ae.safetensors) should be captured as a data structure, not hardcoded strings
- Latent dimensions fixed at 832x1472 — this is a model constraint, not a config option

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-04-16 via auto mode*
