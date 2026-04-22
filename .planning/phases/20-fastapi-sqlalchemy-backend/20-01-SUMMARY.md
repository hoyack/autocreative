---
phase: 20-fastapi-sqlalchemy-backend
plan: 01
subsystem: infra
tags: [fastapi, sqlalchemy, alembic, arq, redis, uvicorn, aiosqlite, asyncpg, asgi-correlation-id, structlog, errors, gitignore]

# Dependency graph
requires:
  - phase: 18-brand-kit-system
    provides: "BrandKitError hierarchy + load_brand_kit raise site"
  - phase: 19-social-media-posting-system
    provides: "structlog processor chain + async generator patterns"
provides:
  - "8 new runtime deps installed: fastapi, uvicorn[standard], sqlalchemy, alembic, aiosqlite, arq, redis, asgi-correlation-id"
  - "asyncpg pinned in `prod` optional-extra for Postgres-backed prod engine"
  - "honcho pinned in `dev` optional-extra for two-process Procfile launcher (Plan 20-12)"
  - "BrandKitNotFoundError subclass of BrandKitError for HTTP 404 mapping in Plan 20-06"
  - "load_brand_kit raises BrandKitNotFoundError on missing kit (preserves `except BrandKitError` callers)"
  - "structlog `_add_correlation` processor normalizes trace_id from asgi-correlation-id ContextVar across all log lines"
  - ".gitignore now silences flyer.db + *.sqlite + alembic __pycache__"
affects: [20-fastapi-sqlalchemy-backend all downstream plans, Phase 21+ API consumers]

# Tech tracking
tech-stack:
  added:
    - fastapi>=0.136.0
    - uvicorn[standard]>=0.45.0
    - sqlalchemy>=2.0.49
    - alembic>=1.18.4
    - aiosqlite>=0.22.1
    - arq>=0.28.0
    - "redis>=5.0.0,<6"
    - asgi-correlation-id>=4.3.4
    - asyncpg>=0.31.0 (prod extra)
    - honcho>=2.0.0 (dev extra)
  patterns:
    - "Subclass-based error hierarchy: BrandKitNotFoundError(BrandKitError) preserves Liskov substitution so existing `except BrandKitError` callers continue to catch the narrower type without code churn."
    - "Guarded import of optional dep in logging_config.py: `try: from asgi_correlation_id import correlation_id` with graceful fallback so logging still loads during partial-install bootstraps."
    - "Processor-chain insertion (not rewrite): `_add_correlation` slotted after existing `merge_contextvars`, preserving all other processors unchanged."

key-files:
  created: []
  modified:
    - "pyproject.toml (8 runtime deps + `prod` extra + honcho dev dep)"
    - "uv.lock (regenerated — 20 new transitive packages)"
    - "flyer_generator/errors.py (BrandKitNotFoundError subclass)"
    - "flyer_generator/brand_kit/storage.py (load_brand_kit raises BrandKitNotFoundError)"
    - "flyer_generator/brochure/schema_renderer/__main__.py (CLI now catches BrandKitError, preserving exit-code-2 contract)"
    - "flyer_generator/logging_config.py (_add_correlation processor + guarded import)"
    - "tests/brand_kit/test_storage.py (asserts BrandKitNotFoundError + subclass relationship)"
    - ".gitignore (Phase 20 db artifact exclusions)"

key-decisions:
  - "redis pinned to >=5.0.0,<6 (not >=7.4.0 as planned): arq 0.28.0 constrains redis<6; the plan conflated Redis server version with the Python client. 5.x is the arq-compatible client range."
  - "Added `_add_correlation` helper in addition to the existing merge_contextvars: belt-and-suspenders normalization of trace_id key across log lines, per RESEARCH.md Pattern 8."
  - "load_brand_kit context bag carries slug/expected_path/available kwargs but is deliberately NOT serialized to clients (per PATTERNS.md T-3 mitigation)."

patterns-established:
  - "Error-hierarchy extension: new typed errors land as subclasses of the nearest BrandKitError/SocialError/FlyerGeneratorError ancestor so HTTP handlers can map specific classes to specific status codes while preserving existing catch sites."
  - "CLI error-handling upgrade: when a raise site changes type, every `except OldType` downstream must be audited. Here the brochure schema_renderer CLI only caught FileNotFoundError; Rule 1 auto-fix added BrandKitError to its except tuple."

requirements-completed:
  - API-02

# Metrics
duration: ~10 min
completed: 2026-04-22
---

# Phase 20 Plan 01: Foundation Prerequisites Summary

**FastAPI + SQLAlchemy + arq dep block landed, BrandKitNotFoundError added for HTTP 404 mapping, and structlog chain made asgi-correlation-id-compatible — 1136 existing tests remain green.**

## Performance

- **Duration:** ~10 min (3 tasks)
- **Started:** 2026-04-22T22:02:00Z (approx)
- **Completed:** 2026-04-22T22:12:35Z
- **Tasks:** 3 / 3
- **Files modified:** 8 (including uv.lock)

## Accomplishments

- Installed 8 new runtime deps + asyncpg prod extra + honcho dev extra via `uv sync`; `uv.lock` regenerated with 20 new transitive packages (httptools, hiredis, mako, markupsafe, pyjwt, starlette, uvloop, watchfiles, websockets, etc.).
- Added `BrandKitNotFoundError(BrandKitError)` and rewired `load_brand_kit` to raise it with `slug`/`expected_path`/`available` context; old `except BrandKitError` callers still match.
- Normalized structlog's processor chain for asgi-correlation-id compatibility by inserting `_add_correlation` after `merge_contextvars`; guarded the dep import so partial-install bootstraps still load.
- Updated `.gitignore` to silence `flyer.db`, `*.sqlite`, and `alembic/versions/__pycache__/`.
- Fixed downstream test that asserted `FileNotFoundError` from `load_brand_kit` (`tests/brand_kit/test_storage.py::test_load_missing_raises`).
- Full `pytest -m "not slow"` still reports 1136 passed / 0 failures (baseline preserved).

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-executor worktree protocol):

1. **Task 1: Add Phase 20 dependencies to pyproject.toml** — `5cddcf5` (feat)
2. **Task 2: Add BrandKitNotFoundError + point load_brand_kit at it** — `8dc280a` (feat)
3. **Task 3: Structlog correlation-id compatibility + .gitignore additions** — `4602242` (feat)

_Plan-metadata commit (SUMMARY.md) pending post-summary; orchestrator will handle STATE.md/ROADMAP.md updates._

## Files Created/Modified

- `pyproject.toml` — 8 new runtime deps, `prod` optional-extra (asyncpg), honcho added to `dev` extra
- `uv.lock` — regenerated (20 new transitive packages)
- `flyer_generator/errors.py` — `BrandKitNotFoundError(BrandKitError)` inserted after `BrandKitError` base
- `flyer_generator/brand_kit/storage.py` — `load_brand_kit` now raises `BrandKitNotFoundError` with slug/path/available context; docstring updated
- `flyer_generator/brochure/schema_renderer/__main__.py` — CLI now catches `BrandKitError` (covers new subclass) in addition to legacy `FileNotFoundError`, preserving exit-code-2 contract
- `flyer_generator/logging_config.py` — `_add_correlation` processor + guarded `from asgi_correlation_id import correlation_id` import
- `tests/brand_kit/test_storage.py` — `test_load_missing_raises` now asserts `BrandKitNotFoundError` + confirms `BrandKitError` subclass relationship + "not found" in message
- `.gitignore` — Phase 20 db artifact exclusions (`flyer.db`, `*.sqlite`, alembic `__pycache__`)

## Decisions Made

- **redis client pin is `>=5.0.0,<6`** (not the plan's `>=7.4.0`). arq 0.28.0's own `redis[hiredis]>=4.2.0,<6` constraint means the plan's pin was infeasible; the plan conflated Redis server version 7.x with the Python `redis` client major version. 5.x is the modern arq-compatible client and works fine against Redis 7 servers.
- **Added `_add_correlation` helper in addition to `merge_contextvars`.** The plan explicitly flagged this as optional but recommended belt-and-suspenders per RESEARCH.md Pattern 8. Shipping it now keeps the trace_id key name normalized across all log lines regardless of what the middleware names the ContextVar.
- **Preserved the legacy `except FileNotFoundError` branch in `brochure/schema_renderer/__main__.py`** alongside the new `except BrandKitError` branch rather than deleting it. Tiny defensive cost; keeps the door open if other callers ever pass raw brand.json file paths outside of the `load_brand_kit` entrypoint.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Redis version pin conflict with arq 0.28.0**

- **Found during:** Task 1 (`uv sync` after adding deps)
- **Issue:** Plan requested `redis>=7.4.0` but arq 0.28.0 constrains `redis[hiredis]>=4.2.0,<6`. uv reported an unsatisfiable resolution.
- **Fix:** Changed `redis>=7.4.0` → `redis>=5.0.0,<6` in `pyproject.toml`. This is the arq-compatible client range; it is fully interoperable with Redis 7 server instances (client/server versions are decoupled).
- **Files modified:** `pyproject.toml`
- **Verification:** `uv sync` succeeded; `redis==5.3.1` and `arq==0.28.0` both installed; all 1136 tests pass.
- **Committed in:** `5cddcf5` (Task 1 commit)

**2. [Rule 1 - Bug] brochure schema_renderer CLI swallowed new BrandKitError subclass**

- **Found during:** Task 2 (`pytest` after swapping the raise site)
- **Issue:** `tests/brand_kit/test_schema_renderer_integration.py::test_brand_kit_missing_exits_2` failed. The CLI in `flyer_generator/brochure/schema_renderer/__main__.py` only caught `FileNotFoundError`; once `load_brand_kit` started raising `BrandKitNotFoundError` (a sibling of `Exception`, not of `FileNotFoundError`), the exception propagated up to typer and the process exited 1 instead of 2.
- **Fix:** Added an `except BrandKitError as err:` branch (which covers the new subclass) immediately before the legacy `FileNotFoundError` branch, preserving the exit-code-2 contract and the "not found" stderr text.
- **Files modified:** `flyer_generator/brochure/schema_renderer/__main__.py`
- **Verification:** Full `pytest -m "not slow"` reports 1136 passed.
- **Committed in:** `8dc280a` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes were required to complete the task. The redis pin change is a correctness fix against the arq 0.28.0 constraint; the CLI catch fix is a Liskov-substitution correction. No scope creep — neither edit touched files outside the plan's `files_modified` frontmatter except the brochure CLI, which was a direct downstream consequence of the `load_brand_kit` raise-site change.

## Issues Encountered

- `VIRTUAL_ENV=...` warning during every `uv run` because the active shell env is pointed at the main repo's `.venv` while uv operates on the worktree's `.venv`. Not a blocker — uv ignores the env var and uses the project-local path as intended.

## Threat Flags

None. The plan's `<threat_model>` (T-3, T-5, supply-chain) was addressed as specified:

- **T-3 (BrandKitNotFoundError context leakage):** context kwargs (`slug`, `expected_path`, `available`) ride on the base-class `**context` bag and are NOT serialized to clients. Plan 20-06 will validate this in `test_error_mapping.py`.
- **T-5 (structlog correlation-id):** `_add_correlation` reads only `asgi_correlation_id.correlation_id` (a ULID, not a secret). Import is guarded so no new failure modes in bootstrap.
- **Supply chain:** all 10 new deps are pinned with lower bounds + locked in `uv.lock` with exact versions; all are well-known PyPI packages (fastapi, sqlalchemy, alembic, arq, uvicorn, aiosqlite, redis, asgi-correlation-id, asyncpg, honcho).

## Known Stubs

None. This plan is pure foundation — no new modules, no UI data paths, nothing that could stub.

## User Setup Required

None — no external service configuration required at this stage. (Redis + Postgres Docker services land in Plan 20-11; dev launcher lands in Plan 20-12.)

## Next Phase Readiness

- **Plan 20-02 (SQLAlchemy base + ORM models)** can proceed: SQLAlchemy 2.0.49 + aiosqlite 0.22.1 are installed and importable.
- **Plan 20-03 (Alembic scaffolding)** can proceed: alembic 1.18.4 is installed.
- **Plan 20-06 (exception-handler bank)** can proceed: `BrandKitNotFoundError` exists and is importable; error-to-HTTPException mapping table in `20-CONTEXT.md` now matches reality.
- **Plan 20-08 (middleware)** can proceed: asgi-correlation-id 4.3.4 is installed; structlog chain already routes its ContextVar into every log line via both `merge_contextvars` and `_add_correlation`.
- **Plan 20-11 (docker-compose)** should pin the Redis server service to a version the 5.x Python client supports (Redis 6/7 both fine).
- **Plan 20-12 (Procfile + honcho)** can proceed: honcho 2.0.0 is installed in the dev extra.

## Self-Check: PASSED

**Files verified to exist:**

- `pyproject.toml` — FOUND (modified, contains `fastapi>=0.136.0`, `sqlalchemy>=2.0.49`, `arq>=0.28.0`, `asgi-correlation-id>=4.3.4`)
- `uv.lock` — FOUND (regenerated, contains 3 occurrences of `name = "fastapi"`)
- `flyer_generator/errors.py` — FOUND (contains `class BrandKitNotFoundError(BrandKitError):`)
- `flyer_generator/brand_kit/storage.py` — FOUND (contains `raise BrandKitNotFoundError`, 0 `raise FileNotFoundError`)
- `flyer_generator/logging_config.py` — FOUND (contains `_add_correlation` + `merge_contextvars`; `add_log_level` appears exactly once)
- `flyer_generator/brochure/schema_renderer/__main__.py` — FOUND (contains `except BrandKitError`)
- `tests/brand_kit/test_storage.py` — FOUND (asserts `BrandKitNotFoundError`)
- `.gitignore` — FOUND (contains `flyer.db`, `flyer.db-journal`, `*.sqlite`, `alembic/versions/__pycache__/`)

**Commits verified to exist in git log:**

- `5cddcf5` — FOUND (`feat(20-01): add Phase 20 API + DB + queue dependencies`)
- `8dc280a` — FOUND (`feat(20-01): add BrandKitNotFoundError + raise from load_brand_kit`)
- `4602242` — FOUND (`feat(20-01): structlog correlation-id + Phase 20 .gitignore entries`)

---

*Phase: 20-fastapi-sqlalchemy-backend*
*Completed: 2026-04-22*
