# Flyer Generator

## What This Is

A Python + React application for automated creative-asset generation. It composes AI-generated imagery (via ComfyCloud), vision-evaluated text layout (via Claude), and brand-kit conditioning into print-ready deliverables. v1 shipped flyers, brochures, social posts, social campaigns, and brand-kit scraping as a FastAPI backend with an editorial React dashboard. v1.1 expands the creative catalog with flyer templates + subtypes (event / info) and adds three new asset primitives (postcard, poster, invitation), hardened by a dedicated adversarial test suite.

## Core Value

Given structured event or informational data, a style preset, and optionally a brand kit, produce a polished, print-ready creative asset — flyer, brochure, postcard, poster, invitation, social post, or campaign — every time, without manual design work.

## Current Milestone: v1.1 Creative Expansion

**Goal:** Template-driven flyer rendering + event/info subtype split, plus 3 new creative primitives (postcard, poster, invitation), plus the codebase's first adversarial test suite.

**Target features:**
- Flyer templates: JSON-schema registry mirroring brochure templates; 5+ flyer templates shipping at launch
- Flyer subtypes: `event` (current) and `info` (announcement / educational / non-date-bound) from one `FlyerInput` model
- Postcard primitive: 2-sided direct-mail format (front PNG + back PNG + print PDF)
- Poster primitive: larger-canvas flyer variant with size presets (18×24 / 24×36 / 27×40)
- Invitation primitive: 5×7 portrait RSVP format with heavy brand-kit conditioning
- Adversarial hardening: prompt injection, path traversal, unicode stress, oversize payloads, PDF bombs, concurrent enqueue, visual regression — across the entire catalog

**Key context:** Every new asset mirrors the brochure pattern (parallel-id, compensating enqueue, 3-artifact detail route) and lands in the editorial Phase 21 dashboard (creator page + status page + Jobs/Renders filter entries). This milestone is scoped as 5 phases (22–26), each ending at a verified end-to-end state.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Generate AI background images via ComfyCloud API from style presets + event concepts
- [ ] Evaluate backgrounds with Claude vision for appropriateness and optimal text placement zones
- [ ] Composite event text (title, date, venue, fee, org) onto backgrounds using vision-derived zone coordinates
- [ ] Regenerate backgrounds up to N times if vision rejects, with refinement hints fed back
- [ ] Support 6 built-in style presets (photorealistic, anime, western_cartoon, scifi, watercolor, retro_poster)
- [ ] Upscale from 832x1472 latent to 1080x1920 final output
- [ ] Adaptive text color (white/dark) based on vision analysis
- [ ] Zone-specific scrim gradients for text readability
- [ ] Title auto-sizing and word-wrap with widow-line merge
- [ ] Fee badge pill shape with dynamic width
- [ ] Accent line and accent stripe from configurable color
- [ ] SVG composition with base64-embedded background, rasterized to PNG via cairosvg
- [ ] CLI entrypoint (`python -m flyer_generator`) with full argument support
- [ ] Event JSON file input for scripted usage
- [ ] `--list-presets` and `--dry-run` CLI modes
- [ ] Importable public API: `generate_flyer()`, `FlyerGenerator`, `EventInput`, `FlyerOutput`
- [ ] Custom preset registration via `PresetRegistry`
- [ ] Structured logging with trace IDs (structlog, JSON or text format)
- [ ] Typed exception hierarchy for every failure mode
- [ ] Environment-variable driven configuration via Pydantic Settings

### Out of Scope

- Batch generation orchestration — design permits it, but orchestration lives elsewhere
- Web UI — wrap with FastAPI later if needed
- Alternative image models beyond ComfyCloud — extension point exists but not implemented
- Animation or video output
- Font diversity beyond Arial/Helvetica fallback chain
- Multi-language / RTL / CJK text layout
- Image content safety / NSFW detection (vision checks suitability, not moderation)
- Caching layer — belongs at a higher level

## Context

This project ports an existing n8n workflow (documented in `docs/n8n.json`) to a standalone Python application. The n8n workflow is proven and working — the Python version should replicate its logic faithfully while adding proper typing, error handling, testability, and extensibility.

Key references:
- `docs/spec.md` — Full technical specification with module layout, data models, stage specs
- `docs/n8n.json` — Working n8n workflow with exact prompts, ComfyCloud workflow JSON, vision system prompt, SVG composition logic, and style presets

The ComfyCloud workflow uses the Lumina2 model (`z_image_turbo_bf16.safetensors`) with `qwen_3_4b.safetensors` CLIP and 8-step KSampler at 832x1472 latent resolution.

## Constraints

- **Python:** 3.11+ required
- **Image Processing:** Pillow for upscale, cairosvg for SVG-to-PNG rasterization (resvg-py as fallback)
- **HTTP:** httpx (async) for all API calls
- **Models:** Pydantic v2 for all data contracts, pydantic-settings for config
- **Logging:** structlog
- **CLI:** typer
- **No Node.js deps in the Python stack:** No sharp, no Puppeteer for image processing — Python uses Pillow + cairosvg only.
- **Optional frontend (Phase 21):** Node.js >= 22 + pnpm >= 9 are REQUIRED to develop the optional `frontend/` React dashboard. The Python API + CLI remain the source of truth and are usable without the dashboard. The frontend depends on Phase 20's API running locally.
- **System deps:** Cairo + libffi required for cairosvg

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Port from n8n to Python | Standalone CLI + importable module, better testing, no n8n dependency | — Pending |
| Pillow over sharp for upscale | Pure Python, installs reliably everywhere, adequate for ~30% linear upscale | — Pending |
| cairosvg over Puppeteer for rasterization | Lightweight, no headless browser, server-friendly | — Pending |
| 832x1472 latent → 1080x1920 upscale | Model-friendly multiples of 64, reduces artifacts vs native resolution | — Pending |
| SVG composition with base64-embedded background | Transient large SVG acceptable since it never ships as SVG | — Pending |
| Single Claude vision call for approval + zones + color | Minimizes API calls and cost per attempt | — Pending |
| structlog for logging | JSON output for prod, pretty text for dev, trace_id binding | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-16 after initialization*
