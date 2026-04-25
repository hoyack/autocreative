---
phase: 24-poster-primitive
plan: 03
subsystem: api
tags: [pydantic, sqlalchemy, alembic, postgres, sqlite, parallel-id, literal-enum]

# Dependency graph
requires:
  - phase: 23-postcard-primitive
    provides: parallel-id ORM contract, compensating-enqueue pattern, alembic JobKind extension recipe
  - phase: 22-flyer-templates-and-subtype-split
    provides: alembic head f22t01, JobKind enum precedent
provides:
  - PosterCreateRequest Pydantic schema with locked size Literal["18x24","24x36","27x40"]
  - PosterRecord ORM model with parallel-id contract (no default factory on id)
  - JobKind.POSTER enum value
  - alembic migration f24t01 (down_revision=f23t01) — posters table + jobkind enum extension
  - render.py kind comment lists "poster_final"
affects: [24-04 (worker task_generate_poster), 24-05 (POST /api/v1/posters route), 24-06 (FE poster creator), 26 (adversarial sweep)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Locked Literal enum pattern: typing.Literal[...] for closed-set request fields (size)"
    - "Parallel-id ORM regression guard: explicit `assert id_col.default is None and id_col.server_default is None` test"
    - "Postgres ALTER TYPE jobkind wrapped in autocommit_block + IF NOT EXISTS (idempotent + transaction-safe)"

key-files:
  created:
    - flyer_generator/api/schemas/posters.py
    - flyer_generator/api/models/poster.py
    - alembic/versions/f24t01_poster_primitive.py
    - tests/api/test_poster_schemas.py
    - tests/api/test_poster_models_ddl.py
    - tests/api/test_migrations_poster.py
  modified:
    - flyer_generator/api/schemas/__init__.py
    - flyer_generator/api/models/__init__.py
    - flyer_generator/api/models/job.py
    - flyer_generator/api/models/render.py

key-decisions:
  - "Single render_id (not 3) — posters ship as a single PNG, no front/back/pdf split"
  - "size column stored as String(8) literal (e.g. '18x24') for FE display + audit; canvas-dim mapping deferred to worker (24-04)"
  - "JobKind.POSTER inserted between POSTCARD and SOCIAL_POST to keep enum ordering stable"
  - "Schema-level template validation only enforces max_length=64; worker (24-04) owes the path-traversal slug guard per T-24-08"

patterns-established:
  - "Closed-set request fields: typing.Literal for request validation; T-24-07 mitigation"
  - "render.py kind comment is the single source of truth for valid render kinds; updated whenever a new asset primitive lands"

requirements-completed: [PO-01]

# Metrics
duration: 6min
completed: 2026-04-25
---

# Phase 24 Plan 03: Poster Primitive — Schema + ORM + Migration Summary

**PosterCreateRequest with locked 3-value size Literal, PosterRecord parallel-id ORM, JobKind.POSTER enum extension, and alembic f24t01 — establishes the API/DB layer so the 24-04 worker can write `PosterRecord(id=job_id, ...)` and the route can serve `POST /api/v1/posters` with size validation at the Pydantic boundary.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-25T07:32:16Z
- **Completed:** 2026-04-25T07:37:43Z
- **Tasks:** 2 (each TDD: RED + GREEN)
- **Commits:** 4 (2 RED + 2 GREEN)
- **Files created:** 6
- **Files modified:** 4
- **Tests added:** 39 (22 schema + 11 ORM/DDL + 6 migration)
- **Full tests/api/ regression:** 333 passed, 0 failed

## Accomplishments

- `PosterCreateRequest` schema with `size: Literal["18x24","24x36","27x40"]` (T-24-07 mitigation), max_length on every str field (T-24-06), brand_kit_slug regex `^[a-z0-9][a-z0-9-]*$` (T-24-09), and `extra="forbid"` (T-24-06).
- `PosterRecord` ORM with parallel-id contract — `id Mapped[str]` has NO default factory. Explicit DDL test (`test_poster_record_id_has_no_default_factory`) regresses against accidental `default=new_ulid` re-introduction (T-24-11 mitigation).
- `JobKind.POSTER = "poster"` added between POSTCARD and SOCIAL_POST.
- Alembic migration `f24t01_poster_primitive.py` (down_revision=`f23t01`) creates the `posters` table with 7 columns + 2 indexes (brand_kit_slug, render_id), and extends the Postgres `jobkind` enum inside `autocommit_block` with `IF NOT EXISTS` (T-24-10 mitigation, idempotent + non-blocking).
- `render.py` kind-comment now enumerates `"poster_final"` alongside the other render kinds.
- Both schema and model barrels (`flyer_generator/api/schemas/__init__.py`, `flyer_generator/api/models/__init__.py`) export the new symbols in sorted `__all__`.

## Task Commits

Each task was committed atomically per the TDD cycle:

1. **Task 1 RED — Failing schema tests** — `7fde2ae` (test)
2. **Task 1 GREEN — PosterCreateRequest + PosterSize schema** — `d109ddc` (feat)
3. **Task 2 RED — Failing ORM/DDL + migration tests** — `8fc88ec` (test)
4. **Task 2 GREEN — PosterRecord + JobKind.POSTER + alembic f24t01** — `9e6e0c0` (feat)

## Files Created/Modified

### Created
- `flyer_generator/api/schemas/posters.py` — `PosterCreateRequest` + `PosterSize` Literal alias
- `flyer_generator/api/models/poster.py` — `PosterRecord` ORM with parallel-id pattern, single `render` relationship
- `alembic/versions/f24t01_poster_primitive.py` — creates `posters` table + extends `jobkind` enum on Postgres
- `tests/api/test_poster_schemas.py` — 22 Pydantic schema tests (size enum, length boundaries, regex, extra-forbid, barrel)
- `tests/api/test_poster_models_ddl.py` — 11 ORM/DDL tests (parallel-id regression guard, 7-column shape, single-render relationship, in-memory SQLite round-trip)
- `tests/api/test_migrations_poster.py` — 6 alembic migration tests (table+indexes, JobKind.POSTER round-trip, downgrade drops cleanly, head pointer is f24t01)

### Modified
- `flyer_generator/api/schemas/__init__.py` — added `PosterCreateRequest`, `PosterSize` to imports + sorted `__all__`
- `flyer_generator/api/models/__init__.py` — added `PosterRecord` to imports + sorted `__all__`
- `flyer_generator/api/models/job.py` — added `JobKind.POSTER = "poster"` between POSTCARD and SOCIAL_POST
- `flyer_generator/api/models/render.py` — kind-comment block now enumerates `"poster_final"` (and `"postcard_front"`, `"postcard_back"`, `"postcard_pdf"` which were missing from the comment despite being valid)

## Decisions Made

- **Single render_id (not a triple):** Posters are single-canvas PNGs; the postcard's front/back/pdf trio does not apply. The schema and ORM both reflect this — `render_id: Mapped[str | None]` + a single `render` relationship.
- **size stored as String(8) literal, not int dimensions:** Storing the literal preserves audit/UX clarity ("18x24" appears verbatim in the FE). The canvas-dim mapping (300 DPI: 5400×7200, etc.) lives in the worker per CONTEXT D-XX, keeping this layer free of pipeline knowledge.
- **render.py comment expanded with postcard kinds too:** During the `poster_final` addition I noticed the comment was missing `"postcard_front"`, `"postcard_back"`, and `"postcard_pdf"` (added in Phase 23 but not propagated to the comment). Bringing the comment in line with reality is documentation correctness, not a deviation — `String(40)` column is unchanged.

## Deviations from Plan

None — plan executed exactly as written. The render.py comment expansion to include the postcard kinds (alongside the planned `poster_final`) is a documentation-correctness adjustment in the same comment block being edited; the comment was already inconsistent with the codebase before this plan.

## Issues Encountered

None.

## Threat Mitigations Implemented

| Threat ID | Mitigation | Verified by |
|-----------|------------|-------------|
| T-24-06 | max_length on every str field; `extra="forbid"` | `test_extra_forbid_rejects_unknown_keys`, `test_headline_max_length_120_boundary`, `test_subheading_max_length_200`, `test_cta_text_max_length_120`, `test_image_hint_max_length_500`, `test_style_preset_required_and_max_length_64`, `test_template_required_and_max_length_64`, `test_brand_kit_slug_max_length_64` |
| T-24-07 | size: Literal["18x24","24x36","27x40"] | `test_size_accepted_*`, `test_size_rejected_36x48`, `test_size_rejected_invalid_format_18_x_24`, `test_size_rejected_empty_string` |
| T-24-08 | accepted (deferred to 24-04 worker — schema enforces only max_length=64 on template) | n/a — owed by 24-04 |
| T-24-09 | brand_kit_slug regex `^[a-z0-9][a-z0-9-]*$` | `test_brand_kit_slug_regex_rejects_uppercase`, `test_brand_kit_slug_regex_rejects_special_chars`, `test_brand_kit_slug_regex_accepts_dashes`, `test_brand_kit_slug_regex_accepts_lowercase_alnum` |
| T-24-10 | Postgres ALTER TYPE inside autocommit_block + IF NOT EXISTS | code review of `f24t01_poster_primitive.py::upgrade()`; SQLite branch verified by `test_jobkind_poster_round_trips` |
| T-24-11 | DDL regression test asserts `id_col.default is None and id_col.server_default is None` | `test_poster_record_id_has_no_default_factory` |

## TDD Gate Compliance

Both tasks followed the full RED → GREEN cycle:

- Task 1 RED commit `7fde2ae` (failing import) → GREEN commit `d109ddc` (22 schema tests pass).
- Task 2 RED commit `8fc88ec` (failing import + missing migration) → GREEN commit `9e6e0c0` (17 ORM + migration tests pass).

No REFACTOR commits — code was clean from initial GREEN.

## Verification Results

| Check | Result |
|-------|--------|
| `pytest tests/api/test_poster_schemas.py tests/api/test_poster_models_ddl.py tests/api/test_migrations_poster.py -v` | 39 passed |
| `alembic heads` | `f24t01 (head)` |
| `python -c "from flyer_generator.api.schemas import PosterCreateRequest, PosterSize; from flyer_generator.api.models import PosterRecord, JobKind; assert JobKind.POSTER.value == 'poster'; print('OK')"` | `OK` |
| `grep -c "POSTER" flyer_generator/api/models/job.py` | 1 |
| `grep -c "PosterRecord" flyer_generator/api/models/__init__.py` | 2 (import + `__all__`) |
| `grep -c "poster_final" flyer_generator/api/models/render.py` | 1 |
| `pytest tests/api/ -q` | 333 passed, 0 failed (no regressions vs. f23t01 baseline) |

## Known Stubs

None. Every column, field, and validator is wired and tested. The worker-side template-slug guard (T-24-08) is intentionally owed by 24-04 — the threat register documents the disposition.

## Next Phase Readiness

Ready for plan 24-04 (worker `task_generate_poster`):
- `PosterRecord(id=job_id, ...)` is insertable from a worker.
- `JobKind.POSTER` round-trips through both SQLite and (per migration) Postgres.
- `PosterCreateRequest.model_dump(mode="json")` is the canonical input payload shape for `content_payload`.
- Worker still owes: module-scope `load_template` import (BLOCKER-2 mirror), `_validate_template_slug` guard (T-24-08), `FlyerGenerator(canvas_dimensions=size_to_dim(size))` integration.

## Self-Check: PASSED

**Files:**
- FOUND: flyer_generator/api/schemas/posters.py
- FOUND: flyer_generator/api/models/poster.py
- FOUND: alembic/versions/f24t01_poster_primitive.py
- FOUND: tests/api/test_poster_schemas.py
- FOUND: tests/api/test_poster_models_ddl.py
- FOUND: tests/api/test_migrations_poster.py

**Commits:**
- FOUND: 7fde2ae (Task 1 RED)
- FOUND: d109ddc (Task 1 GREEN)
- FOUND: 8fc88ec (Task 2 RED)
- FOUND: 9e6e0c0 (Task 2 GREEN)

---
*Phase: 24-poster-primitive*
*Completed: 2026-04-25*
