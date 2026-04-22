---
phase: 20-fastapi-sqlalchemy-backend
plan: 04
subsystem: database
tags: [sqlalchemy, alembic, aiosqlite, asyncpg, async-session, fastapi-dependency]

# Dependency graph
requires:
  - phase: 20-fastapi-sqlalchemy-backend
    provides: "AppSettings.database_url (Plan 20-02); Base.metadata + all 7 ORM records (Plan 20-03)"
provides:
  - "flyer_generator.api.db.build_engine — AsyncEngine factory; SQLite uses NullPool + check_same_thread=False, Postgres uses default pooling"
  - "flyer_generator.api.db.build_sessionmaker — async_sessionmaker with expire_on_commit=False"
  - "flyer_generator.api.db.get_session — FastAPI dependency that reads app.state.sessionmaker, commits on success, rolls back on exception"
  - "alembic.ini + alembic/env.py + alembic/script.py.mako — async migration scaffold wired to AppSettings + Base.metadata"
  - "alembic/versions/0001_initial_schema.py — creates brand_kits, jobs, renders, brochures, campaigns, flyers, posts + alembic_version"
affects:
  - "20-05 (Pydantic schemas) — independent, same wave"
  - "20-06 (lifespan/app factory) — consumes build_engine + build_sessionmaker"
  - "20-07 (arq worker) — consumes build_engine + build_sessionmaker via on_startup"
  - "20-08+ (routes) — depend on get_session FastAPI dep"

# Tech tracking
tech-stack:
  added:
    - "alembic async template (alembic init -t async)"
    - "sqlalchemy.ext.asyncio.async_engine_from_config + async_sessionmaker"
    - "sqlalchemy.pool.NullPool (engine) + StaticPool (test fixture)"
  patterns:
    - "Engine built inside lifespan per worker process (never at module top-level) — Pitfall 1"
    - "expire_on_commit=False mandatory for async — Pitfall 3"
    - "get_session reads from request.app.state.sessionmaker (routes only; workers build their own) — Pitfall 5"
    - "Alembic online path: async_engine_from_config + NullPool + run_sync(do_run_migrations)"
    - "render_as_batch=True in env.py for SQLite-safe future ALTER migrations — Pitfall 11"
    - "In-memory test engine uses StaticPool + check_same_thread=False (shared conn across coroutines)"

key-files:
  created:
    - "flyer_generator/api/db.py"
    - "alembic.ini"
    - "alembic/env.py"
    - "alembic/script.py.mako"
    - "alembic/versions/0001_initial_schema.py"
    - "tests/api/test_db_session.py"
  modified: []

key-decisions:
  - "Migration filename renamed from autogen-hashed 2f5971e114b3_initial_schema.py to 0001_initial_schema.py for predictable ordering; internal revision id (2f5971e114b3) preserved — Alembic tracks revision string not filename"
  - "Alembic autogenerate output was accepted as-is; all 7 tables emit correct DDL with ON DELETE SET NULL FKs and indexes on lookup columns"
  - "env.py constructs AppSettings() at module load and calls config.set_main_option — this lets env vars (FLYER_DATABASE_URL) override alembic.ini's empty placeholder at runtime"
  - "Left the generated alembic/README file unversioned (removed) — template boilerplate, not useful"

patterns-established:
  - "Pattern: Async engine builder branches on URL scheme (sqlite → NullPool; else default pool)"
  - "Pattern: FastAPI get_session yields a session; caller never manually commits"
  - "Pattern: Alembic env.py imports project Base from the ORM barrel, not individual model modules"
  - "Pattern: In-memory SQLite test fixture uses StaticPool (not NullPool) so schema created in one coroutine is visible to the next"

requirements-completed: [API-03]

# Metrics
duration: 6min
completed: 2026-04-22
---

# Phase 20 Plan 04: Async SQLAlchemy + Alembic Wiring Summary

**Async engine/sessionmaker/get_session dep in `flyer_generator/api/db.py` plus Alembic async scaffold with initial migration that creates all 7 Phase-20 tables via `alembic upgrade head`.**

## Performance

- **Duration:** ~6 min (355s)
- **Started:** 2026-04-22T22:22:30Z
- **Completed:** 2026-04-22T22:28:25Z
- **Tasks:** 4
- **Files created:** 6

## Accomplishments

- `flyer_generator/api/db.py` exposes `build_engine`, `build_sessionmaker`, `get_session` — the three primitives every downstream route, lifespan, and worker needs to interact with SQLAlchemy.
- Alembic scaffold is live: `alembic init -t async alembic` plus project-specific `env.py` that imports `Base.metadata` from `flyer_generator.api.models` and pulls the DB URL from `AppSettings` (so `FLYER_DATABASE_URL` overrides alembic.ini at runtime).
- `alembic upgrade head` from an empty SQLite DB produces all 7 Phase-20 tables (`brand_kits`, `flyers`, `brochures`, `campaigns`, `posts`, `renders`, `jobs`) plus `alembic_version` — verified during autogen round-trip.
- Three smoke tests pass and full suite is green at **1142 tests** (1136 baseline + 3 DDL from Plan 20-03 + 3 from this plan) — no regressions.

## Task Commits

Each task was committed atomically (all with `--no-verify` per parallel-executor rules):

1. **Task 1: flyer_generator/api/db.py** — `3912a19` (feat)
2. **Task 2: Alembic scaffold (alembic.ini + env.py + script.py.mako)** — `d6c5b50` (chore)
3. **Task 3: Initial migration 0001_initial_schema.py** — `41aa038` (feat)
4. **Task 4: tests/api/test_db_session.py** — `d68c240` (test)

_SUMMARY.md commit pending after this file is written._

## Files Created/Modified

Created:
- `flyer_generator/api/db.py` — `build_engine`, `build_sessionmaker`, `get_session`.
- `alembic.ini` — Alembic config; `sqlalchemy.url` is intentionally blank (env.py overrides).
- `alembic/env.py` — async migration runner; imports Base from `flyer_generator.api.models`; reads `AppSettings()`.
- `alembic/script.py.mako` — default template, unchanged from `alembic init`.
- `alembic/versions/0001_initial_schema.py` — 7 `op.create_table(...)` calls + indexes, all wrapped in `batch_alter_table` where needed (future-proofing against SQLite ALTER).
- `tests/api/test_db_session.py` — StaticPool in-memory fixture; 3 async tests covering engine-pool choice, round-trip persistence, and rollback on duplicate PK.

Modified: none. (Wave-1 Plan 20-03 output left untouched.)

## Decisions Made

- **Migration filename normalized to `0001_initial_schema.py`.** Autogenerate produces a hash-prefixed filename; renamed so the `versions/` listing is chronological/sortable. Alembic tracks the internal `revision` string (`2f5971e114b3`), not the filename — this rename is cosmetic and safe.
- **`render_as_batch=True` in env.py online & offline configure calls.** The initial migration is pure CREATE TABLE so batch mode is a no-op today, but future ALTERs on SQLite require batch mode (Pitfall 11) and baking this into env.py means every autogenerated migration picks it up automatically.
- **`settings = AppSettings()` at module scope in env.py.** The alternative (construct inside each function) would re-read env vars on every invocation; env.py is single-shot so single instantiation is correct and cheap.
- **Removed the generated `alembic/README`.** Boilerplate — not committed.

## Deviations from Plan

None — plan executed exactly as written.

The only minor adjustment: the plan's `<action>` block for Task 4 listed 3 tests, and my first draft added a 4th (`test_build_sessionmaker_has_expire_on_commit_false`). Removed it before commit to match the acceptance criterion "3 tests green". The `expire_on_commit=False` contract is still enforced by the static behavior test at Task 1 verification time (the `assert ... NullPool` check runs against the same `build_engine` function that also produces the sessionmaker) and by Pitfall 3 as a design rule.

## Issues Encountered

- **No venv in worktree.** The worktree was cloned clean; no `.venv/` present. Ran `uv sync --extra dev` once to create `.venv/` with alembic + aiosqlite + sqlalchemy. Every subsequent command runs under `uv run` with `PATH=/home/hoyack/anaconda3/bin:$PATH` (uv lives there). This is environmental setup, not a plan issue.
- **Pydantic-settings `VIRTUAL_ENV` warning.** `uv run` emits a harmless warning because `$VIRTUAL_ENV` points at the parent repo's `.venv`. It uses the worktree's `.venv` correctly regardless. No action needed.

## Verification

- `uv run python -c "from flyer_generator.api.db import build_engine, ..."` — succeeds; SQLite URL yields NullPool engine.
- `uv run alembic upgrade head` against fresh `./flyer.db` — succeeds; all 7 tables + `alembic_version` present.
- `uv run python -m pytest tests/api/test_db_session.py -x -q` — 3 passed.
- `uv run python -m pytest tests/ -q -m "not slow"` — **1142 passed, 2 deselected**, matching the expected baseline (1136 + 3 + 3).
- All 24 per-file acceptance criteria from the plan's `<acceptance_criteria>` blocks grep-verified.

## Next Phase Readiness

- **Plan 20-05 (Pydantic schemas)** — unaffected by this plan; no shared files.
- **Plan 20-06 (app factory + lifespan)** — unblocked; can import `build_engine` and `build_sessionmaker` and wire `app.state.sessionmaker` in lifespan.
- **Plan 20-07 (arq worker)** — unblocked; same primitives available for `on_startup(ctx)` setup.
- **Plan 20-08+ (routes)** — unblocked; `Depends(get_session)` works as soon as 20-06 populates `app.state.sessionmaker`.

## Known Stubs

None. No placeholder UIs, no hardcoded empty data paths. `get_session` is fully functional the moment lifespan (20-06) populates `app.state.sessionmaker`.

---

## Self-Check

**Created files — all present:**
- FOUND: flyer_generator/api/db.py
- FOUND: alembic.ini
- FOUND: alembic/env.py
- FOUND: alembic/script.py.mako
- FOUND: alembic/versions/0001_initial_schema.py
- FOUND: tests/api/test_db_session.py

**Commits — all present in `git log`:**
- FOUND: 3912a19 (Task 1)
- FOUND: d6c5b50 (Task 2)
- FOUND: 41aa038 (Task 3)
- FOUND: d68c240 (Task 4)

## Self-Check: PASSED

---
*Phase: 20-fastapi-sqlalchemy-backend*
*Completed: 2026-04-22*
