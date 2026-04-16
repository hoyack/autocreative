# Technology Stack

**Project:** Flyer Generator (AI-powered event flyer pipeline)
**Researched:** 2026-04-16
**Overall Confidence:** HIGH

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

The PROJECT.md references ComfyCloud specifically (not self-hosted ComfyUI). ComfyCloud's API is:
- REST-based with X-API-Key auth
- POST workflow JSON to `/api/prompt`, get `prompt_id`
- Poll `/api/job/{id}/status` or listen on WebSocket `/ws`
- Download outputs via `/api/view`

This is 4 endpoints. A thin async httpx wrapper class (50-80 lines) is preferable to depending on `comfy-api-simplified` (which targets local ComfyUI and may have different semantics for cloud). The ComfyCloud API docs themselves note it is "experimental" and "subject to change" -- owning the client code makes adapting to changes trivial.

## System Dependencies

```bash
# Required for CairoSVG
# Ubuntu/Debian:
sudo apt-get install libcairo2-dev libffi-dev

# macOS:
brew install cairo libffi

# Alpine (Docker):
apk add cairo-dev libffi-dev
```

## Project Setup

```bash
# Initialize with uv
uv init flyer-generator
cd flyer-generator

# Core dependencies
uv add pydantic pydantic-settings httpx anthropic structlog typer pillow cairosvg

# Fallback rasterizer (optional)
uv add resvg-py

# Dev dependencies
uv add --dev pytest pytest-asyncio respx ruff pyright

# Run
uv run python -m flyer_generator
```

## pyproject.toml Configuration Sketch

```toml
[project]
name = "flyer-generator"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.13",
    "pydantic-settings>=2.13",
    "httpx>=0.28",
    "anthropic>=0.87",
    "structlog>=25.5",
    "typer>=0.24",
    "pillow>=12.2",
    "cairosvg>=2.9",
]

[project.optional-dependencies]
resvg = ["resvg-py>=0.3"]
dev = [
    "pytest>=9.0",
    "pytest-asyncio>=1.3",
    "respx>=0.22",
    "ruff>=0.11",
    "pyright",
]

[project.scripts]
flyer-generator = "flyer_generator.cli:app"

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 99

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
```

## Version Pinning Strategy

Pin **minimum** versions in pyproject.toml (e.g., `>=2.13`). Use `uv lock` to generate a reproducible lockfile with exact versions. This allows `uv add --upgrade` for updates while ensuring CI reproducibility.

Do NOT pin exact versions in pyproject.toml -- that fights the resolver and makes security updates harder.

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
