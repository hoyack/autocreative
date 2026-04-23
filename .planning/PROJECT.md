# Flyer Generator

## What This Is

A Python application that generates event flyers as 1080x1920 PNG images by combining AI-generated background images (via ComfyCloud) with vision-evaluated text layout (via Claude). Each flyer is visually distinct — zone placement, text color, and scrim composition all adapt to the generated background. Designed as both a CLI tool and importable module.

## Core Value

Given structured event data and a style preset, produce a polished, print-ready 1080x1920 event flyer with AI-generated artwork and intelligently placed text — every time, without manual design work.

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
