<!-- GSD:project-start source:PROJECT.md -->
## Project

**Flyer Generator**

A Python application that generates event flyers as 1080x1920 PNG images by combining AI-generated background images (via ComfyCloud) with vision-evaluated text layout (via Claude). Each flyer is visually distinct — zone placement, text color, and scrim composition all adapt to the generated background. Designed as both a CLI tool and importable module.

**Core Value:** Given structured event data and a style preset, produce a polished, print-ready 1080x1920 event flyer with AI-generated artwork and intelligently placed text — every time, without manual design work.

### Constraints

- **Python:** 3.11+ required
- **Image Processing:** Pillow for upscale, cairosvg for SVG-to-PNG rasterization (resvg-py as fallback)
- **HTTP:** httpx (async) for all API calls
- **Models:** Pydantic v2 for all data contracts, pydantic-settings for config
- **Logging:** structlog
- **CLI:** typer
- **No Node.js deps in the Python stack:** No sharp, no Puppeteer for image processing — Python uses Pillow + cairosvg only.
- **Optional frontend (Phase 21):** Node.js >= 22 + pnpm >= 9 are REQUIRED to develop the optional `frontend/` React dashboard. The Python API + CLI remain the source of truth and are usable without the dashboard. The frontend depends on Phase 20's API running locally.
- **System deps:** Cairo + libffi required for cairosvg
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Runtime
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | 3.11+ (target 3.12) | Runtime | 3.11 minimum for ExceptionGroup + tomllib; 3.12 for f-string improvements and performance. Do NOT require 3.13+ yet -- cairosvg/Cairo C bindings lag on newest Pythons. | HIGH |
| uv | >=0.11 | Package/project manager | 100x faster than pip, lockfile support, replaces pip + pip-tools + virtualenv in one tool. From Astral (same team as Ruff). Use `uv init`, `uv add`, `pyproject.toml` native. | HIGH |
### Core Application
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pydantic | >=2.13.1 | Data models, validation | All data contracts (EventInput, FlyerOutput, VisionResponse, PresetConfig) use Pydantic v2 models. Faster than v1, native JSON schema generation. | HIGH |
| pydantic-settings | >=2.13.1 | Config from env vars | Reads COMFYCLOUD_API_KEY, ANTHROPIC_API_KEY, log level, retry counts from environment. Validates config at startup, not runtime. | HIGH |
| httpx | >=0.28.1 | HTTP client (async) | Async-first for ComfyCloud polling loop + Claude API calls. Connection pooling, timeout configuration, retry hooks. The Anthropic SDK uses httpx internally so no extra dependency. | HIGH |
| anthropic | >=0.87.0 | Claude vision API | Official SDK for vision evaluation calls. Supports base64 image content blocks, structured response parsing. Use `messages.create()` with image content type "base64". | HIGH |
| structlog | >=25.5.0 | Structured logging | JSON output for production, pretty ConsoleRenderer for dev. Bind trace_id per flyer generation run. ContextVar-based for async safety. | HIGH |
| typer | >=0.24.1 | CLI framework | Type-hint-driven CLI from the FastAPI author. Auto-generates --help, supports subcommands (generate, list-presets), validates arguments via type hints. | HIGH |
### Image Processing
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Pillow | >=12.2.0 | Image upscale (832x1472 to 1080x1920) | Pure Python install, no system deps beyond libjpeg/zlib. LANCZOS resampling for the ~30% upscale is visually adequate. Also used for base64 encoding of generated images before Claude vision call. | HIGH |
| CairoSVG | >=2.9.0 | SVG to PNG rasterization | Primary rasterizer. Handles SVG with embedded base64 background images, text elements, shapes. Requires system Cairo + libffi. Well-maintained (Kozea/WeasyPrint ecosystem). | HIGH |
| resvg_py | >=0.3.0 | Fallback SVG rasterizer | Rust-based resvg bindings. No system Cairo dependency -- pure wheel install. Use as fallback when Cairo is unavailable (CI, minimal containers). Updated April 2026. | MEDIUM |
### Dev & Testing
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pytest | >=9.0.3 | Test runner | Industry standard. Requires Python >=3.10 (fine with our 3.11+ target). | HIGH |
| pytest-asyncio | >=1.3.0 | Async test support | Required for testing async httpx calls to ComfyCloud and Anthropic. Use `mode="auto"` in pytest config to avoid per-test decorators. | HIGH |
| respx | >=0.22.0 | HTTPX mocking | Purpose-built for mocking httpx. Mock ComfyCloud API responses, Claude vision responses, without hitting real APIs. Supports async. | HIGH |
| ruff | >=0.11 | Linter + formatter | Replaces flake8 + black + isort in a single Rust-based tool. 100x faster. Configure in pyproject.toml. | HIGH |
| pyright | latest | Static type checker | Microsoft's type checker. Faster than mypy, better Pydantic v2 support, incremental analysis. Run in CI via `pyright --pythonversion 3.12`. | HIGH |
## Alternatives Considered
| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| HTTP client | httpx | aiohttp | httpx has sync+async unified API, cleaner timeout handling, used internally by anthropic SDK. aiohttp is heavier and callback-based. |
| HTTP client | httpx | requests | requests is sync-only. ComfyCloud polling loop and Claude calls benefit from async concurrency. |
| SVG rasterizer | CairoSVG | Puppeteer/Playwright | Headless browser is 100x heavier, requires Node.js or browser binary, slow startup. CairoSVG is a Python function call. |
| SVG rasterizer | CairoSVG | svglib + reportlab | Worse SVG spec coverage, particularly with embedded base64 images and CSS properties. |
| SVG rasterizer | CairoSVG (primary) + resvg_py (fallback) | resvg_py only | resvg_py is newer (0.3.0), less battle-tested with complex SVG patterns. CairoSVG has years of production use. Keep resvg_py as escape hatch for Cairo-free environments. |
| CLI | typer | click | Typer wraps Click with type hints. Same underlying engine but less boilerplate. Since we use Pydantic everywhere, type-hint-driven CLI is consistent. |
| CLI | typer | argparse | Verbose, no auto-completion, manual help text. Typer generates everything from type annotations. |
| Formatter | ruff | black + isort + flake8 | Three tools vs one. Ruff is faster and configured in a single pyproject.toml section. |
| Type checker | pyright | mypy | Pyright is faster, better incremental analysis, superior Pydantic v2 plugin support. |
| Package manager | uv | pip + pip-tools | uv is dramatically faster, has native lockfile, replaces the entire pip + venv + pip-tools chain. |
| Package manager | uv | poetry | Poetry is slower, its resolver is notoriously slow on large dependency trees. uv is a drop-in improvement. |
| Logging | structlog | loguru | structlog produces structured JSON natively, integrates with stdlib logging, supports ContextVar bindings for trace IDs. loguru is prettier for scripts but worse for structured production logs. |
| Image upscale | Pillow | sharp (Node.js) | Project constraint: no Node.js deps. Pillow LANCZOS is sufficient for a 30% linear upscale. |
| Vision API | anthropic SDK | direct httpx calls | SDK handles auth, retries, streaming, type-safe responses. No reason to hand-roll API calls. |
| ComfyCloud client | Direct httpx calls | comfy-api-simplified | The wrapper library (v1.6.0) targets local ComfyUI, not ComfyCloud specifically. ComfyCloud's REST API is simple enough (POST /api/prompt, poll status, GET output) that a thin httpx wrapper is cleaner and avoids a dependency that may not match ComfyCloud's experimental API semantics. |
## Stack Rationale: Why NOT a ComfyUI Client Library
- REST-based with X-API-Key auth
- POST workflow JSON to `/api/prompt`, get `prompt_id`
- Poll `/api/job/{id}/status` or listen on WebSocket `/ws`
- Download outputs via `/api/view`
## System Dependencies
# Required for CairoSVG
# Ubuntu/Debian:
# macOS:
# Alpine (Docker):
## Project Setup
# Initialize with uv
# Core dependencies
# Fallback rasterizer (optional)
# Dev dependencies
# Run
## pyproject.toml Configuration Sketch
## Version Pinning Strategy
## Sources
- [pydantic PyPI](https://pypi.org/project/pydantic/) -- v2.13.1, April 15, 2026
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) -- v2.13.1, Feb 19, 2026
- [httpx PyPI](https://pypi.org/project/httpx/) -- v0.28.1
- [anthropic PyPI](https://pypi.org/project/anthropic/) -- v0.87.0, March 31, 2026
- [structlog docs](https://www.structlog.org/) -- v25.5.0, Oct 27, 2025
- [typer docs](https://typer.tiangolo.com/) -- v0.24.1
- [Pillow PyPI](https://pypi.org/project/pillow/) -- v12.2.0, April 1, 2026
- [CairoSVG PyPI](https://pypi.org/project/CairoSVG/) -- v2.9.0, March 13, 2026
- [resvg_py PyPI](https://pypi.org/project/resvg_py/) -- v0.3.0, April 10, 2026
- [pytest PyPI](https://pypi.org/project/pytest/) -- v9.0.3, April 7, 2026
- [pytest-asyncio PyPI](https://pypi.org/project/pytest-asyncio/) -- v1.3.0 stable
- [respx GitHub](https://github.com/lundberg/respx) -- v0.22.0
- [ruff docs](https://docs.astral.sh/ruff/) -- actively updated April 2026
- [uv docs](https://docs.astral.sh/uv/) -- v0.11.6, April 9, 2026
- [ComfyCloud API docs](https://docs.comfy.org/development/cloud/api-reference) -- experimental REST API
- [Claude Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision) -- base64 image support
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

## LLM Resilience

Ollama-backed calls (vision + text) are wrapped by `flyer_generator/stages/llm_retry.py::_call_with_retry`. Behavior:

- **Retryable** (exponential backoff + jitter, `llm_retry_max_attempts` per model): timeouts, connect errors, HTTP 429 (honors `Retry-After`), 500/502/503.
- **Model fallthrough** (no retry on same model, advance to next in chain): HTTP 404 or response body indicating the model is not loaded.
- **Fatal** (raise immediately, no retry, no fallback): HTTP 400/401/403.
- **Model chain:** primary from `settings.ollama_vision_model` / `settings.ollama_text_model`, then `settings.ollama_vision_model_fallbacks` / `settings.ollama_text_model_fallbacks`.

Env var knobs (all `FLYER_`-prefixed):

| Env var | Default | Meaning |
|---|---|---|
| `FLYER_LLM_RETRY_MAX_ATTEMPTS` | `3` | Attempts per model before advancing chain. |
| `FLYER_LLM_RETRY_BASE_DELAY` | `1.0` | Base backoff seconds; delay = min(max, base × 2^(n-1)) + jitter. |
| `FLYER_LLM_RETRY_MAX_DELAY` | `10.0` | Upper clamp for backoff and Retry-After. |
| `FLYER_OLLAMA_TEXT_MODEL_FALLBACKS` | `kimi-k2.6:cloud,qwen3.6:35b` | Comma-separated fallback text models. |
| `FLYER_OLLAMA_VISION_MODEL_FALLBACKS` | `kimi-k2.6:cloud,qwen3.6:35b` | Comma-separated fallback vision models. |

Typed errors: `LLMAPIError` (base), `LLMRateLimitError`, `LLMServiceUnavailableError`, `LLMTimeoutError`, `LLMModelUnavailableError` — all in `flyer_generator/errors.py`. `VisionAPIError` is preserved as an alias for `LLMAPIError` for backwards compatibility with existing `except VisionAPIError` sites.

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
