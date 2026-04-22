---
phase: 20-fastapi-sqlalchemy-backend
plan: "06"
subsystem: api
tags: [fastapi, middleware, exception-handlers, lifespan, test-scaffolding]
requires:
  - 20-01 (BrandKitNotFoundError + logging _add_correlation processor)
  - 20-02 (AppSettings + flyer_generator/api/__init__.py placeholder)
  - 20-03 (ORM models Base + records)
  - 20-04 (build_engine + build_sessionmaker + get_session)
  - 20-05 (request/response Pydantic schemas)
provides:
  - "flyer_generator.api:app (FastAPI instance, uvicorn entrypoint)"
  - "flyer_generator.api.build_app() (app factory)"
  - "flyer_generator.api.lifespan.lifespan (engine + arq pool lifespan)"
  - "flyer_generator.api.middleware.install_middleware (CORS + CorrelationId)"
  - "flyer_generator.api.errors.register_exception_handlers (9-handler bank)"
  - "flyer_generator.api.deps.get_settings / get_arq_pool"
  - "flyer_generator.api.routes.ROUTERS (6 empty APIRouter stubs)"
  - "tests/api fixtures: engine, sessionmaker_fx, fake_arq_pool, app, client + _FakeArqPool"
affects:
  - "tests/api baseline grew from 78 to 98 (8 smoke + 12 error-mapping)"
  - "full tests suite: 1214 -> 1234 passed, 0 regressions"
tech-stack:
  added:
    - "fastapi 0.136.0 (app factory, routing, exception handlers)"
    - "asgi-correlation-id 4.x CorrelationIdMiddleware (validator=None for ULID trace-id support)"
    - "arq.create_pool + arq.connections.RedisSettings.from_dsn (lifespan wiring)"
  patterns:
    - "Most-specific-first exception-handler ordering (FastAPI matches FIRST isinstance match)"
    - "_payload() helper omits exc.context to avoid leaking SecretStr / filesystem paths / SSRF reasons"
    - "module-level app = build_app() is safe for uvicorn --workers N because per-process state is built in lifespan, not at import"
    - "ASGITransport(app=app) + StaticPool :memory: SQLite pattern for tests; lifespan is NOT executed under tests"
key-files:
  created:
    - flyer_generator/api/lifespan.py
    - flyer_generator/api/middleware.py
    - flyer_generator/api/errors.py
    - flyer_generator/api/deps.py
    - flyer_generator/api/routes/__init__.py
    - flyer_generator/api/routes/brand_kits.py
    - flyer_generator/api/routes/flyers.py
    - flyer_generator/api/routes/brochures.py
    - flyer_generator/api/routes/social.py
    - flyer_generator/api/routes/jobs.py
    - flyer_generator/api/routes/renders.py
    - tests/api/conftest.py
    - tests/api/test_app_smoke.py
    - tests/api/test_error_mapping.py
  modified:
    - flyer_generator/api/__init__.py (placeholder -> build_app() + module-level app + /healthz)
decisions:
  - "CorrelationIdMiddleware installed with validator=None so Phase 20 ULID trace IDs (26 chars) and arbitrary upstream-gateway trace IDs are echoed verbatim (default UUID4-only validator broke the must_haves 'X-Request-ID echoed' truth for non-UUID callers)"
  - "9 exception handlers registered (8 domain + 1 RequestValidationError) in most-specific-first order: 503 rate-limit -> 502 LLM -> 502 Comfy -> 422 BrandVoice -> 404 BrandKitNotFound -> 400 BrandKit -> 400 Social -> 400 FlyerGeneratorError -> 422 Pydantic validation"
  - "/healthz lives outside /api/v1 (infra liveness, not versioned API surface); does NOT touch DB or Redis (v1 only needs liveness)"
  - "Test fixture uses StaticPool (not NullPool) for :memory: SQLite so coroutines share state; lifespan is NOT executed under ASGITransport -- fixtures inject test doubles directly"
metrics:
  duration: "~20 minutes (single-pass)"
  completed_date: "2026-04-22"
  tasks_completed: 4
  tests_added: 20
  commits:
    - "ec70871 feat(20-06): lifespan + middleware + errors + deps + 6 route stubs"
    - "c779bee feat(20-06): wire build_app() factory with /healthz + OpenAPI docs"
    - "cdf9cd5 test(20-06): tests/api/conftest.py async fixtures + _FakeArqPool"
    - "c1dbc63 test(20-06): smoke + error-mapping tests + validator=None deviation fix"
---

# Phase 20 Plan 06: FastAPI app skeleton + exception handlers + test scaffolding

**One-liner:** Wires the FastAPI app factory (`build_app()` + module-level `app = build_app()`), lifespan-managed engine/sessionmaker/arq pool, correlation-id + CORS middleware, a 9-handler exception bank (most-specific-first), 6 empty `APIRouter` stubs for Plans 20-08..11, and the shared `tests/api/` fixture backbone (in-memory SQLite + ASGI transport + `_FakeArqPool`) — so `uvicorn flyer_generator.api:app` boots, `/docs` + `/openapi.json` render, every domain error maps to its documented HTTP status, and downstream route plans inherit a ready test fixture stack.

## What was built

### Runtime surface (6 new modules + 1 rewrite under `flyer_generator/api/`)

- **`lifespan.py`** — `@asynccontextmanager` that builds `AppSettings()`, `build_engine(settings)`, `build_sessionmaker(engine)`, and `arq.create_pool(RedisSettings.from_dsn(...))` per uvicorn worker process. Disposes the engine and closes the arq pool on shutdown. Stashes every runtime handle on `app.state` for `Depends()` consumers.
- **`middleware.py::install_middleware`** — registers `CorrelationIdMiddleware` FIRST (with `validator=None`) then `CORSMiddleware` sourcing `allow_origins` from `settings.cors_origins`, `allow_credentials=True`, `expose_headers=["X-Request-ID"]`. CorrelationId-first is load-bearing so CORS responses also carry the request ID.
- **`errors.py::register_exception_handlers`** — 9 `@app.exception_handler` decorators registered in most-specific-first order:

  | Order | Exception | Status | Extra |
  |---|---|---|---|
  | 1 | `LLMRateLimitError` | 503 | `Retry-After: {retry_after_seconds}` |
  | 2 | `LLMAPIError` | 502 | catches `VisionAPIError` alias + subclasses |
  | 3 | `ComfyError` | 502 | all Comfy subclasses |
  | 4 | `BrandVoiceViolationError` | 422 | |
  | 5 | `BrandKitNotFoundError` | 404 | |
  | 6 | `BrandKitError` | 400 | scrape / contrast / audit |
  | 7 | `SocialError` | 400 | all social subclasses |
  | 8 | `FlyerGeneratorError` | 400 | domain catch-all |
  | 9 | `RequestValidationError` | 422 | pydantic body/query/path |

  All 9 responses share the `{detail, error_type, trace_id}` shape; `exc.context` is deliberately NOT serialized (T-3 mitigation).
- **`deps.py`** — `get_settings(request)` and `get_arq_pool(request)` pull from `app.state`, mirroring the Plan 20-04 `get_session` idiom.
- **`routes/__init__.py` + 6 stubs (`brand_kits.py`, `flyers.py`, `brochures.py`, `social.py`, `jobs.py`, `renders.py`)** — each stub exports `router = APIRouter(tags=[...])` so Plans 20-08..11 can land route handlers without touching the app factory. `ROUTERS = [...]` is the ordered list `build_app()` iterates.
- **`__init__.py` (rewrite)** — replaces the Plan 20-02 placeholder with `build_app()` that assembles everything above, plus an inline `/healthz` route outside `/api/v1` (liveness probe, does NOT touch DB or Redis). Module-level `app = build_app()` is the uvicorn entrypoint.

### Test scaffolding (3 new files under `tests/api/`)

- **`conftest.py`** — 5 async fixtures downstream plans inherit:
  - `engine` — in-memory SQLite with `StaticPool` + `check_same_thread=False` (per-test DDL via `Base.metadata.create_all`)
  - `sessionmaker_fx` — `async_sessionmaker(engine, expire_on_commit=False)`
  - `fake_arq_pool` — `_FakeArqPool` stub that records `enqueue_job` calls (`pool.calls: list[tuple[str, tuple, dict]]`) and returns a `_FakeJob` whose `job_id` echoes the caller's kwarg
  - `app` — `build_app()` with test-local state injected directly to `app.state` (lifespan is NOT executed under ASGI transport)
  - `client` — `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`
- **`test_app_smoke.py` (8 tests)** — `/healthz`, `/docs`, `/openapi.json`, 404 on unknown path, X-Request-ID echo + generate, CORS allow (`http://localhost:5173`) + disallow (`http://evil.example`).
- **`test_error_mapping.py` (12 tests)** — every domain error family maps to its documented status; `LLMRateLimitError` carries `Retry-After: 5`; `test_brand_kit_not_found_maps_to_404` asserts `"slug" not in body` and `"expected_path" not in body` — proof that the error `context` kwargs bag is NOT serialized (T-3 mitigation proof).

## Verification

- `python -c "from flyer_generator.api import app; print(len(app.routes))"` -> **5 routes** (healthz + /docs + /openapi.json + /redoc + /docs/oauth2-redirect)
- `pytest tests/api/` -> **98 passed** (78 baseline from Waves 1+2 + 20 new)
- `pytest tests/ -m "not slow"` -> **1234 passed**, 2 deselected, 0 regressions (baseline was 1214 before this plan)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] CorrelationIdMiddleware `validator=None` to echo ULID / opaque trace IDs verbatim**

- **Found during:** Task 4 (`test_request_id_echoed_when_supplied` failed)
- **Issue:** `asgi-correlation-id` v4's default validator accepts only UUID4 strings; any non-UUID X-Request-ID (including the ULID-style `01HTEST...` IDs in the plan's test body, and more importantly the ULID `job_id` values Phase 20 emits for `JobRecord`) is silently overwritten with a freshly-generated UUID. Runtime log line: `Generated new request ID (…), since request header value failed validation`. This directly contradicts the plan's `must_haves.truths`: "X-Request-ID header is echoed on every response".
- **Fix:** Passed `validator=None` to `CorrelationIdMiddleware` in `flyer_generator/api/middleware.py`. The library explicitly documents `validator=None` as the escape hatch for accepting arbitrary client-supplied IDs.
- **Files modified:** `flyer_generator/api/middleware.py`
- **Commit:** `c1dbc63`

### Plan acceptance-criterion nuance (not a deviation, noted for the record)

The plan's Task 1 acceptance criterion states:
> `grep -c "@app.exception_handler" flyer_generator/api/errors.py` returns exactly 8

But the plan body File C explicitly specifies 9 `@app.exception_handler` decorators (8 domain + 1 `RequestValidationError`). The code matches the plan body (9). The "8" in the criterion is a typo in the criterion, not a drift in the implementation — RESEARCH.md Pattern 5 also specifies 9 handlers. No action taken.

## Auth gates

None — this plan touched no external network services.

## Known Stubs

The 6 route modules intentionally export empty `APIRouter(tags=[...])` instances. Plans 20-08..11 will land handlers:

| File | Plan that fills it | Tag |
|---|---|---|
| `routes/brand_kits.py` | 20-08 | `brand-kits` |
| `routes/flyers.py` | 20-09 | `flyers` |
| `routes/brochures.py` | 20-10 | `brochures` |
| `routes/social.py` | 20-10 | `social` |
| `routes/jobs.py` | 20-11 | `jobs` |
| `routes/renders.py` | 20-11 | `renders` |

These stubs are load-bearing for `build_app()` — `app.include_router(router, prefix="/api/v1")` requires `router` to be an `APIRouter` instance at import time. The docstring of each stub names the follow-on plan so reviewers know where the handlers will appear.

## Threat register status

- **T-3 (Info Disclosure, exception bodies)** — mitigated and *verified*. `test_brand_kit_not_found_maps_to_404` asserts `"slug" not in body` and `"expected_path" not in body`.
- **T-4 (CORS misconfig)** — mitigated and *verified*. `test_cors_disallowed_origin` asserts no `Access-Control-Allow-Origin` header for `http://evil.example`.
- **T-5 (structlog leakage)** — logs go to stdout, never to response bodies. Phase 20-12 README should advise `.env` chmod 600 / secrets manager in prod; out of scope here.
- **T-8 (expensive-endpoint DoS)** — docs-only mitigation for v1 (private-network trust per CONTEXT.md). Phase 20-12 README must document the "add a rate limiter before public deploy" prereq.

## Self-Check: PASSED

Verified via `git log` + `ls`:

```
FOUND: flyer_generator/api/lifespan.py
FOUND: flyer_generator/api/middleware.py
FOUND: flyer_generator/api/errors.py
FOUND: flyer_generator/api/deps.py
FOUND: flyer_generator/api/routes/__init__.py
FOUND: flyer_generator/api/routes/brand_kits.py
FOUND: flyer_generator/api/routes/flyers.py
FOUND: flyer_generator/api/routes/brochures.py
FOUND: flyer_generator/api/routes/social.py
FOUND: flyer_generator/api/routes/jobs.py
FOUND: flyer_generator/api/routes/renders.py
FOUND: flyer_generator/api/__init__.py (rewritten)
FOUND: tests/api/conftest.py
FOUND: tests/api/test_app_smoke.py
FOUND: tests/api/test_error_mapping.py

FOUND: commit ec70871 (Task 1)
FOUND: commit c779bee (Task 2)
FOUND: commit cdf9cd5 (Task 3)
FOUND: commit c1dbc63 (Task 4)
```
