# Phase 20: FastAPI + SQLAlchemy Backend — Context

**Gathered:** 2026-04-22
**Status:** Ready for planning
**Source:** Inline AskUserQuestion (6 architectural decisions) + HANDOFF.md §7 spec

<domain>
## Phase Boundary

Phase 20 delivers an async HTTP API and relational persistence layer that wrap the four existing creative subsystems (flyer / brochure / brand_kit / social). It is strictly a **backend** phase — no UI.

- In scope: FastAPI app skeleton, SQLAlchemy 2.x async + Alembic, arq worker over Redis, REST endpoints for every existing generator, job polling, render artifact streaming, OpenAPI docs.
- Out of scope: Frontend (deferred to Phase 21), auth (none for v1), multi-tenancy (deferred), publishing (out of scope indefinitely per Phase 19 SOC-11).
- Reuses: every existing Python entrypoint — no reimplementation. `.brand-kits/` + `.social-campaigns/` filesystem roots remain canonical artifact stores; DB stores metadata + path references.

</domain>

<decisions>
## Implementation Decisions

### Tenancy
- **Single-user v1** — no `Organization` model, no tenant FKs on any table. `User` table is minimal (or optional) for v1; reserved for Phase 21+ auth work.
- **Why:** Simpler schema, faster to ship. Adding tenancy later is a one-migration change when a real multi-user story exists.

### Auth
- **No auth for v1** — the API trusts private-network access (localhost / VPN / private IP).
- No login, no sessions, no tokens in Phase 20.
- **Why:** Shortest path to a working end-to-end system. Auth is a phase of its own when a real user story exists.

### Database
- **SQLite for dev (`sqlite+aiosqlite:///./flyer.db`), Postgres for prod (`postgresql+asyncpg://...`)**
- Same SQLAlchemy code path; `FLYER_DATABASE_URL` switches engines.
- Alembic must work against both (no Postgres-only features like JSONB — use SQLAlchemy's generic `JSON` type).
- **Why:** Zero-dep local dev; deterministic prod engine. Standard Python-stack pattern.

### Job Queue
- **arq + Redis** — async-native, lightweight, Pydantic-friendly.
- Worker: `uv run arq flyer_generator.api.worker.WorkerSettings`.
- Redis URL from `FLYER_REDIS_URL` (default `redis://localhost:6379`).
- No Celery, no BackgroundTasks fallback.
- **Why:** FastAPI async stack; ComfyCloud jobs are 60–300s, too long for request lifetime. arq is the idiomatic choice for async Python.

### Deployment
- **Local dev only for Phase 20.** No cloud deploy in scope.
- `docker-compose.yml` for `postgres:16` + `redis:7` services (named `flyer-postgres` + `flyer-redis`).
- Two-command boot: `uvicorn flyer_generator.api:app --reload` + `arq flyer_generator.api.worker.WorkerSettings`.
- **Why:** Get the API working end-to-end first; deploy story belongs in a later phase.

### Frontend
- **Deferred to Phase 21** (React + Vite + ShadCN + Tailwind, full dashboard, all four subsystems).
- Phase 20 exposes only the OpenAPI schema + `/docs` UI for manual testing.

### HTTP Surface
- Versioned prefix: `/api/v1/*`.
- CORS from `FLYER_CORS_ORIGINS` (default `http://localhost:5173` — Vite dev server port).
- Request-ID middleware injects `trace_id` into structlog ContextVars.
- OpenAPI docs at `/docs` + `/redoc`, driven by existing Pydantic v2 models.

### Error Mapping
A single error-to-HTTPException mapper (FastAPI exception handlers):

| Exception family                              | HTTP status |
|-----------------------------------------------|-------------|
| `BrandKitNotFoundError`                       | 404         |
| `BrandKitError`, `FlyerError`, `BrochureError`, `SocialError`, `ValidationError` | 400 / 422 |
| `BrandVoiceViolationError`                    | 422         |
| `ComfyError`, `VisionAPIError`, `LLMAPIError` | 502         |
| `LLMRateLimitError`                           | 503 (with `Retry-After`) |
| Unmapped                                      | 500         |

Every response body: `{detail, error_type, trace_id}`.

### Database Schema
ORM models under `flyer_generator/api/models/`:

- `BrandKitRecord` (slug PK, source_url, scraped_at, palette/typography/voice JSON)
- `FlyerRecord`, `BrochureRecord`, `CampaignRecord`, `PostRecord`
- `RenderRecord` (id, kind, file_path, comfy_job_id, vision_verdict JSON, created_at)
- `JobRecord` (ULID id, kind enum, status enum, started_at, completed_at, error_detail, result_ref, input_payload JSON)

Relationships:
- `Campaign 1-N Post`
- Each creative row `1-1 Render`
- `Job` is polymorphic via `kind` + `result_ref` (ULID pointing at the creative row)

### Storage Strategy
- DB holds **metadata + path references** only.
- Actual artifact bytes remain on disk under existing roots: `.brand-kits/<slug>/`, `.social-campaigns/<slug>/<campaign_id>/`, plus a configurable `FLYER_OUTPUT_ROOT` for flyer/brochure output.
- `GET /api/v1/renders/{id}/image` streams from disk with path-traversal rejection and root-containment check.

### Testing
- New suite: `tests/api/` — route-level tests via `httpx.AsyncClient(transport=ASGITransport(app=app))`.
- DB fixture: `sqlite+aiosqlite:///:memory:` (per-test scope).
- Worker fixture: in-process arq `WorkerSettings` OR direct task-function invocation (whichever simpler per test).
- External calls (ComfyCloud, Ollama/Anthropic) mocked via `respx` — existing Phase-1..19 pattern.
- Target: ≥ 50 new tests. Existing 1136 tests remain green.

### Claude's Discretion
The following are implementation details the planner may decide:

- Module layout inside `flyer_generator/api/` (routes subpackage structure, models subpackage vs single file, etc.)
- Specific ULID generation location (could be DB-side default or Python-side)
- `Enum` implementation style (Python `Enum` vs SQLAlchemy `Enum` vs string checks)
- Precise `JobRecord.status` transitions + whether to use a state-machine library or plain enum assignments
- Whether to emit WebSocket job streaming in v1 (default: NO — `GET /jobs/{id}` polling is enough for Phase 21)
- Whether to add per-request structlog middleware as a library dep or hand-rolled
- Whether to use `fastapi-pagination` or roll a small pagination helper for `GET /brand-kits`
- Alembic initial migration: single "create all" migration vs one-per-model — planner's call
- Exact `uv` recipe name for the dev-server launcher (e.g. `serve`, `dev`, `up`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Python APIs that will be wrapped (no reimplementation)
- `flyer_generator/__init__.py` — `FlyerGenerator`, `generate_flyer`, `EventInput`, `FlyerOutput`
- `flyer_generator/brochure/__init__.py` + `flyer_generator/brochure/schema_renderer/__init__.py` — `render_schema_brochure`, `generate_template_images`, content models
- `flyer_generator/brand_kit/__init__.py` — `fetch_brand_kit`, `load_brand_kit`, `apply_brand_kit`, `BrandKit` + sub-models
- `flyer_generator/social/__init__.py` — `generate_post`, `generate_campaign`, `PostBrief`, `Post`, `Campaign`, `ValidationReport`, `PlatformRules`
- `flyer_generator/config.py` — existing `Settings` (pydantic-settings, `FLYER_` prefix) — Phase 20 extends via `AppSettings`
- `flyer_generator/errors.py` — complete error hierarchy to map onto HTTPException
- `flyer_generator/stages/llm_retry.py` — existing retry primitive (API must not break its behavior)

### Existing patterns that the API must mirror
- Pydantic v2 models are used everywhere — response models should reuse existing ones where possible (e.g. `EventInput` is already a valid FastAPI request body)
- structlog ContextVars are already used for `trace_id` binding — API middleware should set, not replace, the existing pattern
- httpx is already the HTTP client for outbound calls — don't mix in `requests` or `aiohttp`
- `.env` is read by pydantic-settings — don't add a parallel config system

### Phase 19 Handoff (source-of-truth spec)
- `HANDOFF.md` §7 — full Phase 20 architecture sketch + 6 open questions (all 6 are now answered above)
- `.planning/phases/19-social-media-posting-system/*` — reference for plan/CONTEXT/VERIFICATION artifact layout

### Project conventions
- `CLAUDE.md` — project tech stack, Python 3.11+, uv, Pillow, CairoSVG, Pydantic v2, httpx, structlog, typer. FastAPI + SQLAlchemy + arq extend this; no other new framework deps.

</canonical_refs>

<specifics>
## Specific Ideas

- Reuse `EventInput` as the flyer-route request body directly (Pydantic v2 FastAPI integration handles this).
- Reuse `PostBrief` / `Campaign` input models as route bodies where they exist.
- `JobRecord.id` is a ULID string (26 chars) — matches the existing `python-ulid` dep from Phase 19.
- Error-mapping handler registered once at app init — don't sprinkle try/except across routes.
- arq task functions live in `flyer_generator/api/tasks/*.py` (one file per subsystem) — import the existing generators, don't reimplement.
- Alembic `alembic/env.py` must use `engine_from_config` with async support (reference: Alembic async-how-to docs).
- `GET /api/v1/brand-kits` should fuse DB rows with any `.brand-kits/*/` directories that predate the DB — gracefully import existing kits on first read.

</specifics>

<deferred>
## Deferred Ideas

- **Auth** — Magic-link or OAuth is a later phase.
- **Multi-tenancy** — `Organization` model is a later phase.
- **WebSocket job streaming** — Phase 20 uses polling (`GET /jobs/{id}`); live streams can land later if job-UX demands it.
- **Cloud storage (S3/R2)** — filesystem path-adapter in Phase 20; S3 adapter is a later phase.
- **Cloud deploy (Fly.io / Railway / Render / self-host Docker prod)** — Phase 20 is local-dev only.
- **Rate limiting** — no public surface for v1; add when auth/public-IP lands.
- **Metrics / Prometheus / OpenTelemetry** — structlog JSON logs are enough for v1.
- **Job cancellation endpoint** — can add in a later phase when user flows demand it.
- **Scheduled campaigns** — out of scope per Phase 19 SOC-11 and this phase.

</deferred>

---

*Phase: 20-fastapi-sqlalchemy-backend*
*Context gathered: 2026-04-22 via inline 6-question architectural survey + HANDOFF.md §7 source spec*
