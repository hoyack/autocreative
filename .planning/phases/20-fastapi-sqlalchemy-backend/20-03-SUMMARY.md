---
phase: 20-fastapi-sqlalchemy-backend
plan: 03
subsystem: database
tags: [sqlalchemy, orm, ulid, enum, json, pydantic]

# Dependency graph
requires:
  - phase: 20-fastapi-sqlalchemy-backend
    provides: python-ulid dep (Phase 19) + SQLAlchemy dep block (Plan 20-01)
provides:
  - Phase 20 ORM layer — 7 Record classes + 2 enums + DeclarativeBase
  - Shared ULID + UTC helpers for every downstream model
  - Smoke DDL test proving Base.metadata.create_all() works against SQLite
affects:
  - 20-04-alembic-initial-migration
  - 20-05-session-dependency
  - 20-06-db-fixture
  - 20-07-job-state-machine
  - 20-08-brand-kit-routes
  - 20-09-flyer-brochure-routes
  - 20-10-social-routes
  - 20-11-job-routes

# Tech tracking
tech-stack:
  added: [sqlalchemy-2.0-orm-idiom]
  patterns:
    - "SQLAlchemy 2.0 Mapped[T] + mapped_column() for every column"
    - "str, enum.Enum for DB enums so model_dump(mode='json') emits plain strings"
    - "Generic JSON column (not JSONB) for SQLite + Postgres parity"
    - "ULID 26-char string PKs via python-ulid v3 (ulid.ULID() constructor)"
    - "brand_kit FKs use ondelete=SET NULL, campaign→post uses ondelete=CASCADE"
    - "lazy='joined' for single-row rels; lazy='selectin' for 1-N to avoid N+1"

key-files:
  created:
    - flyer_generator/api/models/__init__.py
    - flyer_generator/api/models/base.py
    - flyer_generator/api/models/job.py
    - flyer_generator/api/models/render.py
    - flyer_generator/api/models/brand_kit.py
    - flyer_generator/api/models/flyer.py
    - flyer_generator/api/models/brochure.py
    - flyer_generator/api/models/social.py
    - tests/api/__init__.py
    - tests/api/test_models_ddl.py
  modified: []

key-decisions:
  - "BrandKitRecord uses slug as natural string PK (matches .brand-kits/<slug>/ on disk); every other Record uses ULID string PK"
  - "BrochureRecord carries three separate render FKs (front, back, pdf) rather than a single multi-valued relationship, matching Phase 17 brochure triad"
  - "PostRecord.campaign_id is nullable so standalone posts (non-campaign) are allowed"
  - "CampaignRecord.posts uses cascade='all, delete-orphan' so deleting a campaign removes its posts atomically"
  - "Named SAEnum types (name='jobkind', name='jobstatus') so Postgres gets typed enum columns; SQLite ignores and stores VARCHAR"

patterns-established:
  - "Shared Base + new_ulid + utcnow helpers in flyer_generator/api/models/base.py"
  - "One Record per sibling file + barrel __init__.py re-export"
  - "str-subclass enums so JobStatus.QUEUED.value == 'queued' (not 'JobStatus.QUEUED')"

requirements-completed: [API-04]

# Metrics
duration: 4m22s
completed: 2026-04-22
---

# Phase 20 Plan 03: ORM Models Summary

**Seven SQLAlchemy 2.0 Record classes (BrandKit/Flyer/Brochure/Campaign/Post/Render/Job) with ULID PKs, string-enum job state, and SET-NULL/CASCADE FK policy matching Phase 20 lifecycle rules.**

## Performance

- **Duration:** 4m22s
- **Started:** 2026-04-22T22:05:07Z
- **Completed:** 2026-04-22T22:09:29Z
- **Tasks:** 3
- **Files created:** 10

## Accomplishments
- Shared ORM base (`Base(DeclarativeBase)` + `new_ulid()` + `utcnow()`) landed under `flyer_generator/api/models/base.py`
- `JobRecord` + `JobKind` + `JobStatus` enums with correct str-subclass behavior — `JobStatus.QUEUED.value == "queued"`, direct string comparison works
- `RenderRecord` metadata pointer to on-disk artifact (file_path + comfy_job_id + vision_verdict JSON)
- Five creative Records wired with bidirectional Campaign↔Post relationship and three-way Brochure→Render FKs
- Barrel `flyer_generator/api/models/__init__.py` re-exports everything downstream code needs as a single import
- DDL smoke test (`tests/api/test_models_ddl.py`) proves `Base.metadata.create_all()` cleanly produces all 7 tables on SQLite

## Task Commits

Each task was committed atomically (all with `--no-verify` per parallel-executor protocol):

1. **Task 1: Shared base — base.py + job.py + render.py** — `e30b3fb` (feat)
2. **Task 2: Creative records — brand_kit.py + flyer.py + brochure.py + social.py** — `694c422` (feat)
3. **Task 3: Barrel + smoke DDL test** — `2594bf1` (test)

**Plan metadata:** _committed as part of the final SUMMARY commit below_

_Note: No TDD cycle here — the plan is `type: execute`, not `type: tdd`. DDL smoke tests were added alongside the barrel in Task 3 as a self-verification artifact, not a gate._

## Files Created/Modified

### Created
- `flyer_generator/api/models/base.py` — `Base(DeclarativeBase)` + `new_ulid()` + `utcnow()`
- `flyer_generator/api/models/job.py` — `JobRecord` + `JobKind` + `JobStatus` str-subclass enums, SAEnum with named Postgres types
- `flyer_generator/api/models/render.py` — `RenderRecord` (id ULID default, file_path, comfy_job_id, vision_verdict JSON)
- `flyer_generator/api/models/brand_kit.py` — `BrandKitRecord` (slug natural PK, payload JSON cache)
- `flyer_generator/api/models/flyer.py` — `FlyerRecord` (ULID PK, brand_kit_slug SET NULL, render FK joined)
- `flyer_generator/api/models/brochure.py` — `BrochureRecord` (three render FKs: front/back/pdf)
- `flyer_generator/api/models/social.py` — `CampaignRecord` 1-N `PostRecord`, selectin load, delete-orphan cascade
- `flyer_generator/api/models/__init__.py` — barrel re-export (Base + 7 Records + 2 enums + helpers)
- `tests/api/__init__.py` — package marker (empty)
- `tests/api/test_models_ddl.py` — 3 smoke tests (table creation, enum string values, class existence)

### Modified
None. This is a green-field plan.

## Decisions Made
- **Natural-key slug PK for BrandKitRecord** — matches on-disk `.brand-kits/<slug>/` structure so DB reads/writes can use the same identifier the filesystem already carries. Every other Record uses ULID.
- **Three-way brochure render FK split** — Phase 17 already produces three distinct artifacts (front PNG, back PNG, print PDF); modeling them as three explicit FKs keeps each render individually addressable via `GET /api/v1/renders/{id}/image` without an extra join table.
- **`str, enum.Enum` inheritance** — follows RESEARCH.md §"JobRecord with enums and ULID" so `model_dump(mode="json")` and direct string comparison both emit/accept plain lowercase values; validated by `test_enums_serialize_to_strings`.
- **Named SAEnum types** (`name="jobkind"`, `name="jobstatus"`) — gives Postgres a typed enum column; SQLite silently stores VARCHAR, so SQLite tests still pass.

## Deviations from Plan

None — plan executed exactly as written. All task actions, verify blocks, and acceptance criteria ran green on the first pass.

**Note on Plan 20-01 dependency:** SQLAlchemy is not yet in `pyproject.toml` (Plan 20-01, running in parallel, adds it). To verify DDL locally within this worktree, SQLAlchemy 2.0.49 was installed into the shared `.venv` via `pip`. This is a verification-only step — it is NOT a code change, does not touch `pyproject.toml`, and the orchestrator's merge of 20-01 will supply the permanent `uv sync`-driven install. The worktree diff contains zero dependency-file modifications.

**Total deviations:** 0
**Impact on plan:** None.

## Issues Encountered

- **No `uv` CLI inside WSL worktree.** The project `.venv` was present at `/home/hoyack/work/autocreative/.venv` with Python 3.12 + Phase-19 deps, but `uv` itself was not on `PATH`. Resolution: invoked the venv Python directly (`/home/hoyack/work/autocreative/.venv/bin/python -m pytest …`) for all verification steps. This is a worktree-environment quirk, not a code issue.

## Verification Evidence

```
$ /home/hoyack/work/autocreative/.venv/bin/python -m pytest tests/api/test_models_ddl.py -x -q
... 3 passed in 1.34s

$ /home/hoyack/work/autocreative/.venv/bin/python -m pytest tests/ -q -m "not slow" -x
... 1139 passed, 2 deselected, 1 warning in 80.28s
```

1136 pre-existing tests remain green; 3 new DDL-smoke tests pass. Net delta: +3 tests.

## User Setup Required

None — no external service configuration required. This is a pure-code plan.

## Next Phase Readiness

- **Plan 20-04 (Alembic initial migration)** can `import Base; target_metadata = Base.metadata` directly from the barrel.
- **Plan 20-05 (AsyncSession dependency)** can import `Base` + any Record and know the DDL will match.
- **Plan 20-06 (async DB fixture)** can use `Base.metadata.create_all(engine)` for in-memory SQLite setup per test.
- **Plans 20-07..11 (task state machine, routes)** have every Record + enum they need for task/route signatures.

All seven ORM classes, two enums, and three helpers are importable from `flyer_generator.api.models` as a single top-level barrel. No blockers for any downstream wave.

## Self-Check: PASSED

Verified the following files exist on disk:
- `flyer_generator/api/models/base.py` — FOUND
- `flyer_generator/api/models/job.py` — FOUND
- `flyer_generator/api/models/render.py` — FOUND
- `flyer_generator/api/models/brand_kit.py` — FOUND
- `flyer_generator/api/models/flyer.py` — FOUND
- `flyer_generator/api/models/brochure.py` — FOUND
- `flyer_generator/api/models/social.py` — FOUND
- `flyer_generator/api/models/__init__.py` — FOUND
- `tests/api/__init__.py` — FOUND
- `tests/api/test_models_ddl.py` — FOUND

Verified commits exist in git log:
- `e30b3fb` (Task 1) — FOUND
- `694c422` (Task 2) — FOUND
- `2594bf1` (Task 3) — FOUND

---
*Phase: 20-fastapi-sqlalchemy-backend*
*Plan: 03*
*Completed: 2026-04-22*
