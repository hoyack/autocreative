---
phase: 20-fastapi-sqlalchemy-backend
status: complete
completed: 2026-04-22
plans: 12
tests_added: 156
total_tests_passing: 1292
---

# Phase 20 — FastAPI + SQLAlchemy Backend (Phase Close)

## One-liner

Async HTTP API + async SQLAlchemy 2.0 + arq/Redis worker + Alembic migrations + 8 populated REST routes wrapping all four existing generators (flyer / brochure / brand_kit / social) — 156 new tests, 1292 total passing, single-user v1 with no auth.

## Outcome

Phase 20 landed in 5 waves across 12 plans. The creative subsystems from Phases 1–19 now have a stable HTTP surface under `/api/v1/*` with OpenAPI docs, async job queueing via arq, SQLite-for-dev / Postgres-for-prod via `FLYER_DATABASE_URL`, Alembic migrations, and a full developer-experience toolkit (docker-compose, Procfile, Makefile, README section).

A new developer can go from `git clone` to a running `/healthz` response in under 5 minutes:

```bash
uv sync --extra dev
docker compose up -d flyer-redis
make migrate
make serve
curl http://127.0.0.1:8000/healthz    # {"status":"ok"}
open http://127.0.0.1:8000/docs
```

## Plan-by-plan ledger

| Plan | Title | Wave | Key deliverables | Tests added |
|---|---|---|---|---|
| 20-01 | Dependency + scaffolding | 1 | pyproject extras (fastapi, uvicorn, sqlalchemy, alembic, aiosqlite, arq, redis, asgi-correlation-id, honcho); `flyer_generator/api/` package skeleton; AppSettings inheriting Settings | 0 (scaffolding) |
| 20-02 | Alembic + engine | 1 | `alembic/` async env.py; `db.py` with `build_engine` + `build_sessionmaker`; `FLYER_DATABASE_URL` | 0 (infra) |
| 20-03 | ORM models | 1 | 7 tables: BrandKitRecord, FlyerRecord, BrochureRecord, CampaignRecord, PostRecord, RenderRecord, JobRecord; initial `2f5971e114b3` migration | ~3 DDL smoke |
| 20-04 | Session fixture | 2 | `get_session` FastAPI dep + `get_arq_pool` dep; in-memory SQLite test fixtures | ~3 fixture smoke |
| 20-05 | Request/response schemas | 2 | `flyer_generator/api/schemas/*.py` — FlyerRequest, BrochureRequest, PostRequest, CampaignRequest, JobDetail, ResultLink, BrandKitDetail | 0 (schemas) |
| 20-06 | App wiring + error mapping | 2 | `build_app()` factory; `install_middleware` (CORS + asgi-correlation-id); `register_exception_handlers` — BrandKitNotFoundError→404, BrandVoiceViolationError→422, LLMRateLimitError→503 with Retry-After, ComfyError→502, unmapped→500; `/healthz`; ROUTERS registry | ~20 (errors + smoke) |
| 20-07 | arq worker + 5 tasks | 3 | `worker.py` with WorkerSettings (max_tries=1, max_jobs=4, job_timeout=600); `tasks/{brand_kit,flyer,brochure,post,campaign}.py` — each wraps the existing async Python generator, writes artifacts, inserts RenderRecord, flips JobRecord.status | ~4 direct-invoke |
| 20-08 | Brand-kits routes | 4 | POST `/brand-kits/fetch` (enqueue); GET `/brand-kits` (list + fuse with `.brand-kits/*/`); GET `/brand-kits/{slug}` (detail with 404) | 11 |
| 20-09 | Flyer routes | 4 | POST `/flyers` (enqueue); 422 JSON-serialization fix for RequestValidationError ctx.error ValueErrors | 8 |
| 20-10 | Brochure + social routes | 4 | POST `/brochures`, POST `/social/posts`, POST `/social/campaigns`; another 422 ctx.error serialization pass | 14 |
| 20-11 | Jobs + renders routes | 4 | GET `/jobs/{id}` with campaign-result fusion (selectinload, no N+1); GET `/renders/{id}/image` with T-1 HIGH path-traversal mitigation (Path.resolve(strict=True) + is_relative_to over allow-listed roots) | 14 |
| 20-12 | Dev-x + regression sweep | 5 | docker-compose.yml, Procfile, Makefile, README "API server (Phase 20)" section; 1292-test regression pass; arq worker importability smoke | 0 (regression) |
| **Total** | | | | **156 new tests** |

## Requirements ledger

Every API-* requirement defined in the phase plan has a closing plan:

| Requirement | Description | Closed by |
|---|---|---|
| API-01 | AppSettings extending Settings with Phase 20 fields | 20-01 |
| API-02 | Alembic async env.py + initial migration | 20-02, 20-03 |
| API-03 | 7 ORM models with correct relationships (Campaign 1-N Post, each creative 1-1 Render, Job polymorphic via kind+result_ref) | 20-03 |
| API-04 | FastAPI app factory + /healthz + OpenAPI /docs | 20-06 |
| API-05 | FastAPI dependency for AsyncSession + arq pool | 20-04 |
| API-06 | Request + response Pydantic v2 schemas | 20-05 |
| API-07 | Exception-handler mapping onto HTTPException with trace_id | 20-06 |
| API-08 | asgi-correlation-id middleware + CORS middleware | 20-06 |
| API-09 | arq worker with 5 registered tasks | 20-07 |
| API-10 | Brand-kits routes (fetch enqueue + list + detail) | 20-08 |
| API-11 | Flyer route (POST enqueue) | 20-09 |
| API-12 | Brochure + social routes (POST enqueue x 3) | 20-10 |
| API-13 | Job polling + render streaming with path-traversal guard | 20-11 |
| API-14 | Regression: existing 1136 tests green + ≥ 50 API tests | 20-12 (1292 passing, 156 new) |
| API-15 | docker-compose + Procfile + Makefile + README API section | 20-12 |

## Deferred items (and why)

Everything in CONTEXT.md `<deferred>` remains deferred:

- **Auth** — belongs in a standalone phase with a real user story. The SECURITY section in README tells public-deploy operators exactly what they're missing.
- **Multi-tenancy** — single-user v1; `Organization` FKs would need every table + every query refactored. Not a migration you want to do on spec.
- **WebSocket job streaming** — polling (`GET /jobs/{id}`) is sufficient for Phase 21's dashboard. WS can be added non-breakingly later.
- **S3/R2 cloud storage** — filesystem path-adapter is the v1 contract; a `StorageBackend` protocol with an S3 implementation can be added later without touching any route handler.
- **Cloud deploy (Fly.io / Railway / Render)** — Phase 20 is local-dev + docker-compose. The SECURITY section enumerates the 5 prereqs (auth, rate-limit, TLS, secrets, CORS) a deploy phase would address.
- **Rate limiting** — only needed when an untrusted public surface exists; the SECURITY note calls out Nginx/Caddy/Cloudflare as the right layer.
- **Metrics / Prometheus / OpenTelemetry** — structlog JSON output is adequate for v1; can add prometheus-fastapi-instrumentator trivially later.
- **Job cancellation endpoint** — no user flow demands it yet; arq supports job aborts, can add a route in a follow-up.
- **Scheduled campaigns** — out of scope per Phase 19 SOC-11 and CONTEXT.md.

## Security posture

- **T-1 (HIGH) — Path traversal on `GET /renders/{id}/image`** → MITIGATED in Plan 20-11: `Path.resolve(strict=True) + is_relative_to` over an allow-list of roots (`.brand-kits/`, `.social-campaigns/`, `artifact_root_flyer`, `artifact_root_brochure`). Every failure returns opaque 404 "render not found" — never reveals filesystem shape.
- **T-2 (HIGH) — SSRF on `POST /brand-kits/fetch`** → INHERITED from Phase 18 scraper (Phase 18 SEC-01/02 mitigations: private-IP rejection, protocol allow-list, timeout). API route does not bypass.
- **T-3 (MEDIUM) — Error-context disclosure** → MITIGATED in Plan 20-06: response bodies return only `{detail, error_type, trace_id}`; no stack traces, no error-context kwargs, no secrets.
- **T-5 (MEDIUM) — docker-compose default password** → ACCEPTED in Plan 20-12 threat register: `flyer:flyer` is dev-only; README documents prod must use secrets manager.
- **T-8 (LOW) — DoS via unauthenticated enqueue** → DOCS-ONLY MITIGATION in Plan 20-12: README SECURITY section tells operators to put a rate-limiting reverse proxy in front before going public.
- **Missing auth** → INTENTIONAL for v1. README SECURITY section makes this unmissable.

## Known stubs

None at phase close. Every route handler either executes real work or enqueues a worker task that does. The `BrandKitNotFoundError` class was added in Plan 20-08 so the 404 path is a real domain error, not a string comparison.

## Developer entry point

The README `## API server (Phase 20)` section (inserted before `## See also`) is the canonical onboarding doc. It covers:

1. `uv sync --extra dev`
2. `docker compose up -d flyer-redis` (or any local Redis)
3. `make migrate` (alembic upgrade head)
4. `make serve` (honcho launches uvicorn + arq with aggregated logs)
5. Verify via `/healthz`, browse `/docs`

Plus the env-var table, Postgres-prod path, request lifecycle walkthrough, and SECURITY prereq checklist.

## Commits at phase close

Latest commits on master:

```
5b86aa5 docs(20-12): add 'API server (Phase 20)' section to README
2216fd4 feat(20-12): add docker-compose + Procfile + Makefile for Phase 20 dev-x
6b99c85 docs(phase-20): update tracking after wave 4
e84a395 docs(20-10): add Plan 10 SUMMARY (recovered from orphan)
ceb01ba chore: merge executor worktree (worktree-agent-a1742de1 / 20-09)
```

Phase close commit (this summary) follows.

## Phase 20 → Phase 21 handoff

Phase 21 is the frontend (React + Vite + ShadCN + Tailwind). Its inputs are:

- **Stable REST contract** under `/api/v1/*` with OpenAPI at `/openapi.json` — generate a typed client with `openapi-typescript-codegen` or similar.
- **Job-polling pattern** — POST creative endpoint returns `202 {job_id}`; client polls `GET /jobs/{id}` until `status in (succeeded, failed)`; reads `result_ref` (single URL or list of `{platform, url}`); fetches image bytes via `GET /renders/{id}/image`.
- **CORS** — set `FLYER_CORS_ORIGINS` to the Vite dev server (default `http://localhost:5173` works out of the box).
- **Asset streaming** — `GET /renders/{id}/image` responds with `Content-Disposition: inline`, suitable for embedding in `<img>` / `<object>` tags directly.

Phase 21 should NOT need to touch the backend except to add routes for any new creative subsystems (e.g. if future phases introduce a Phase 22 subsystem, Plan 22-N wires up its route alongside the existing 8).
