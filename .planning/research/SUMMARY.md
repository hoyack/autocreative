# Project Research Summary

**Project:** Flyer Generator (AI-powered event flyer pipeline)
**Domain:** AI-powered image generation + vision-guided layout composition
**Researched:** 2026-04-16
**Confidence:** HIGH

## Executive Summary

This is a sequential async pipeline that generates event flyers by combining AI image generation (ComfyCloud/Lumina2) with vision-guided text layout (Claude). The product targets developer automation pipelines, not GUI users -- it competes with Bannerbear-style APIs rather than Canva/Adobe. The core architectural innovation is using a vision language model to analyze each generated background and determine optimal text placement zones, adaptive text color, and layout suitability, rather than relying on fixed templates. Academic research (PosterIQ, AutoPP, TextLap) validates this approach but few production tools implement it.

The recommended stack is pure Python 3.11+ with uv for package management, Pydantic v2 for all data contracts, httpx for async HTTP, and CairoSVG for SVG-to-PNG rasterization. The architecture is deliberately simple: a linear pipeline with one retry branch (vision rejection triggers regeneration). Every stage is a dependency-injected class with typed Pydantic contracts at boundaries. One shared httpx.AsyncClient handles all external HTTP. The retry loop is an explicit for loop in the orchestrator (not recursive), capped at max attempts. The system generates one flyer at a time and is I/O-bound (waiting on ComfyCloud and Claude APIs), not CPU-bound.

The three highest-risk areas are: (1) CairoSVG silently dropping base64-embedded background images on certain versions, producing blank outputs that pass dimension checks, (2) Claude vision JSON parsing fragility -- the project should use structured outputs (constrained decoding) rather than string extraction, and (3) font rendering differences between dev machines and Linux containers causing silent text layout breakage. All three have concrete mitigations documented in PITFALLS.md, and all three must be addressed in the earliest possible phase, not deferred.

## Key Findings

### Recommended Stack

The stack is Python-only with no Node.js dependencies. uv replaces pip/pip-tools/virtualenv as the package manager. All libraries are current (April 2026) with high-confidence version pins.

**Core technologies:**
- **Python 3.12 (min 3.11):** Runtime -- tomllib, ExceptionGroup support, performance; avoid 3.13+ due to Cairo C binding lag
- **Pydantic v2 (>=2.13):** All data contracts and config validation -- fast, native JSON schema generation
- **httpx (>=0.28):** Async HTTP for ComfyCloud polling and Claude API calls -- shared client with connection pooling
- **anthropic SDK (>=0.87):** Claude vision API -- structured outputs for reliable JSON responses
- **CairoSVG (>=2.9):** SVG to PNG rasterization -- with resvg-py (>=0.3) as fallback for Cairo-free environments
- **Pillow (>=12.2):** Image upscale from 832x1472 to 1080x1920 via LANCZOS resampling
- **structlog (>=25.5):** Structured JSON logging with trace ID binding for async safety
- **typer (>=0.24):** Type-hint-driven CLI framework
- **ruff + pyright:** Linting, formatting, and type checking in CI

### Expected Features

**Must have (table stakes):**
- AI background image generation from text prompt via ComfyCloud
- Text overlay on generated background with readable contrast (4.5:1 ratio)
- Multiple style presets (6 defined: photorealistic, anime, western_cartoon, scifi, watercolor, retro_poster)
- Correct output resolution (1080x1920 PNG)
- CLI interface with structured error handling
- All core event data fields (title, date, venue, fee, org)

**Should have (differentiators):**
- Vision-driven zone detection via Claude (the key innovation)
- Regeneration loop with vision feedback (up to N retries with refinement hints)
- Adaptive text color from vision analysis
- Zone-specific scrim gradients
- Title auto-sizing with widow-line merge
- Importable Python API (generate_flyer(), FlyerGenerator)
- Structured logging with trace IDs

**Defer (v2+):**
- Custom preset registration via PresetRegistry
- GUI/web editor, template marketplace, font diversity, multi-language/RTL, batch orchestration, animation, caching, A/B testing

### Architecture Approach

Linear async pipeline with a single retry loop. Nine components with strict Pydantic-typed boundaries, wired together by a FlyerGenerator orchestrator. All stages are dependency-injected and independently testable. One shared httpx.AsyncClient handles all external HTTP. The retry loop is an explicit for loop in the orchestrator (not recursive), capped at max attempts.

**Major components:**
1. **StylePromptBuilder** -- Assembles ComfyCloud workflow JSON from preset + event + refinement hint (pure function)
2. **ComfyClient** -- Async HTTP: submit workflow, poll status, download PNG bytes from ComfyCloud
3. **ImagePreprocessor** -- Pillow resize 832x1472 to 1080x1920
4. **VisionEvaluator** -- Claude vision API call returning approval, zones, text color, confidence
5. **LayoutResolver** -- Maps zone labels to pixel coordinates (pure function)
6. **PosterComposer** -- Builds SVG with text overlays, scrims, badges from event data + vision output
7. **Rasterizer** -- CairoSVG renders SVG string to final PNG bytes
8. **FlyerGenerator** -- Orchestrator: wires stages, owns retry loop, binds trace ID
9. **PresetRegistry** -- Stores and retrieves named style presets

### Critical Pitfalls

1. **CairoSVG silently drops base64 images** -- Pin >=2.7.1, add visual regression test (check pixel luminance), maintain resvg-py fallback
2. **Claude vision JSON parsing fragility** -- Use structured outputs (constrained decoding) or strict tool_use instead of string extraction; check stop_reason for truncation/refusal
3. **Font fallback fails silently on Linux** -- Install fonts-liberation in Docker, add startup font check via fc-list, consider bundling Liberation Sans
4. **SVG text not XML-escaped** -- Create centralized escape_text() utility, call on every user string at SVG composition boundary, validate SVG with lxml before rasterizing
5. **ComfyCloud polling timeout without diagnostics** -- Log every poll response, include last status in timeout error, use exponential backoff, make poll settings configurable

## Implications for Roadmap

Based on combined research, the architecture's dependency graph and feature priorities suggest 7 phases. Phases 2-6 are parallelizable after Phase 1 but are presented sequentially for solo-developer clarity.

### Phase 1: Foundation (Models, Config, Errors, Presets, Zones)
**Rationale:** Every other component depends on these data contracts and configuration. Pure Python, no external APIs, fast to write and test. Establishing Pydantic models first enforces type safety across the entire codebase from day one.
**Delivers:** models.py, config.py, errors.py, logging_config.py, presets.py, zones.py, pyproject.toml with all deps
**Addresses:** Structured error handling (table stakes), style presets data model, all Pydantic contracts
**Avoids:** Schema drift (Pitfall 12) by defining models once and deriving schemas from them

### Phase 2: Prompt Building
**Rationale:** First pipeline stage after EventInput. Depends only on Phase 1 models and presets. Testable with snapshot tests of prompt strings, no external API needed.
**Delivers:** stages/prompt_builder.py -- converts preset + event + refinement hint into ComfyCloud workflow JSON
**Addresses:** Style presets (table stakes), prompt-driven generation
**Avoids:** N/A (pure function, low risk)

### Phase 3: ComfyCloud Integration
**Rationale:** First external API integration. Must be thoroughly tested in isolation before anything downstream depends on it. Polling logic, error handling, and retry behavior are the most operationally complex parts.
**Delivers:** stages/comfy_client.py -- submit, poll, download with exponential backoff
**Addresses:** AI background generation (table stakes, everything depends on it)
**Avoids:** Polling timeout without diagnostics (Pitfall 5), duplicate submissions on 5xx (Pitfall 6), wrong image format (Pitfall 9)

### Phase 4: Image Preprocessing + Rasterizer
**Rationale:** Group these because both are image processing with no external API calls. The rasterizer is where CairoSVG pitfalls manifest, so it must be validated early with visual regression tests before integration testing begins.
**Delivers:** stages/preprocessor.py (Pillow upscale) + stages/rasterizer.py (CairoSVG + resvg-py fallback)
**Addresses:** Correct output resolution (table stakes), PNG export (table stakes)
**Avoids:** CairoSVG base64 image drop (Pitfall 1), font fallback failure (Pitfall 2). Must include visual regression tests and font availability checks.

### Phase 5: Vision Evaluation
**Rationale:** Most complex stage due to LLM response parsing uncertainty. Build after simpler stages are solid. Design decision on structured outputs vs string parsing must be made here.
**Delivers:** stages/vision.py -- Claude vision API call with structured output parsing, approval/rejection, zone detection, color recommendation
**Addresses:** Vision-driven zone detection (key differentiator), adaptive text color (differentiator)
**Avoids:** Fragile JSON parsing (Pitfall 3), schema drift (Pitfall 12), overly strict confidence threshold (Pitfall 7)

### Phase 6: Layout + SVG Composition
**Rationale:** Depends on Phase 5 output (zones, color) and Phase 4 (rasterizer must work). Tightly coupled layout-compose-render chain. XML escaping pitfall is critical here.
**Delivers:** stages/layout.py, stages/composer.py -- SVG document with text overlays, scrims, badges, fee pill
**Addresses:** Text overlay (table stakes), text readability/scrims (table stakes), title auto-sizing (differentiator), fee badge (differentiator)
**Avoids:** SVG XML injection (Pitfall 4), widow-line merge overflow (Pitfall 10), base64 SVG memory bloat (Pitfall 8)

### Phase 7: Pipeline Orchestration + CLI
**Rationale:** Wires all stages together. Must come last since it depends on every stage. Includes retry loop, trace ID binding, CLI entry point, and public API surface.
**Delivers:** pipeline.py, __init__.py, __main__.py, CLI with generate, --list-presets, --dry-run
**Addresses:** CLI interface (table stakes), regeneration loop with vision feedback (differentiator), importable Python API (differentiator), structured logging with trace IDs (differentiator)
**Avoids:** httpx client lifecycle issues (Pitfall 11), recursive retry (anti-pattern), excessive regen loops on artistic presets (Pitfall 7)

### Phase Ordering Rationale

- Phase 1 first because all Pydantic models, error types, and config are used by every subsequent phase. Changing models after dependent code exists causes cascading updates.
- Phases 2-3 before 5 because vision evaluation needs a generated background image to evaluate. The prompt builder and ComfyClient produce the input for vision.
- Phase 4 early because the CairoSVG pitfalls (base64 image drop, font fallback) are the highest-severity silent failures. Catching them early prevents building on a broken foundation.
- Phase 5 before 6 because the SVG composer depends on vision output (zones, color, approval). Without vision data, the composer would need fake fixtures -- better to have the real data source.
- Phase 7 last because the orchestrator integrates all stages. Building it before stages exist means constant refactoring.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (ComfyCloud):** ComfyCloud API is documented as "experimental and subject to change." The exact response format for /api/history_v2 and /api/view should be verified with live API calls before finalizing the client implementation. Idempotency behavior on 5xx is unknown.
- **Phase 5 (Vision Evaluation):** Structured outputs availability for Claude's vision endpoint should be confirmed. Prompt engineering for zone detection needs iterative tuning with real generated images. Confidence threshold calibration requires empirical data per preset.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Pydantic models, config, error hierarchies -- well-documented, established patterns.
- **Phase 2 (Prompt Builder):** Pure function assembling JSON -- straightforward.
- **Phase 4 (Image Processing):** Pillow resize and CairoSVG rasterization -- well-documented APIs, just need version pinning and regression tests.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries verified on PyPI with April 2026 releases. Version compatibility confirmed. |
| Features | HIGH | Feature landscape well-researched against competitors and academic work. Clear table stakes vs differentiator separation. |
| Architecture | HIGH | Linear pipeline is the correct pattern. Build order follows natural data flow. Spec document provides detailed component contracts. |
| Pitfalls | HIGH | Critical pitfalls backed by specific GitHub issues and CVEs. Moderate pitfalls based on sound engineering inference. |

**Overall confidence:** HIGH

### Gaps to Address

- **ComfyCloud API stability:** API is "experimental." Response formats may change. Build the ComfyClient with an adapter layer to isolate API changes. Verify exact endpoint behavior with live calls during Phase 3.
- **Vision confidence calibration:** The 0.6 threshold is a guess. Needs empirical testing across all 6 presets with real generated images. Plan a tuning sprint after Phase 5 initial implementation.
- **resvg-py production readiness:** Listed as fallback rasterizer but version 0.3.0 is new (April 2026). Test thoroughly with the project's specific SVG patterns (base64 backgrounds, text, scrims) before relying on it in CI.
- **ComfyCloud cost model:** Per-flyer cost (~$0.02-0.05 for Claude vision, plus ComfyCloud credits) needs validation. If regeneration loops average 2-3 attempts, costs multiply.

## Sources

### Primary (HIGH confidence)
- [Pydantic v2 docs](https://docs.pydantic.dev/) -- model validation, JSON schema, settings
- [httpx docs](https://www.python-httpx.org/) -- async client patterns, timeout handling
- [CairoSVG issue #383](https://github.com/Kozea/CairoSVG/issues/383) -- data URI rendering fix
- [CairoSVG issues #273, #324](https://github.com/Kozea/CairoSVG/issues/273) -- font fallback behavior
- [Claude structured outputs docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) -- constrained decoding
- [Claude vision docs](https://platform.claude.com/docs/en/build-with-claude/vision) -- base64 image support
- Academic: [PosterIQ](https://arxiv.org/html/2603.24078), [AutoPP](https://arxiv.org/html/2512.21921), [TextLap](https://arxiv.org/html/2410.12844v1)

### Secondary (MEDIUM confidence)
- [ComfyCloud API reference](https://docs.comfy.org/development/cloud/api-reference) -- experimental, subject to change
- [RunComfy error codes](https://docs.runcomfy.com/serverless/error-codes) -- polling and error behavior
- [DevOpsSchool AI poster tools comparison](https://www.devopsschool.com/blog/top-10-ai-poster-flyer-design-tools-in-2025-features-pros-cons-comparison/) -- competitive landscape
- [resvg-py PyPI](https://pypi.org/project/resvg_py/) -- v0.3.0, new release

### Tertiary (LOW confidence)
- Vision confidence threshold calibration -- inference, needs empirical validation
- ComfyCloud idempotency behavior on 5xx -- standard distributed systems concern, not verified for this specific API

---
*Research completed: 2026-04-16*
*Ready for roadmap: yes*
