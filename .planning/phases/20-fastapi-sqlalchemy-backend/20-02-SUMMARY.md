---
phase: 20-fastapi-sqlalchemy-backend
plan: 02
subsystem: api
tags: [fastapi, pydantic-settings, config, cors, sqlalchemy, arq, redis]

# Dependency graph
requires:
  - phase: pre-existing
    provides: "flyer_generator.config.Settings (BaseSettings, FLYER_ prefix, 25 fields)"
provides:
  - "flyer_generator/api/ subpackage (importable, re-exports AppSettings)"
  - "AppSettings class extending Settings with database_url, redis_url, cors_origins, artifact_root_flyer, artifact_root_brochure"
  - "NoDecode + field_validator idiom for CSV-or-JSON list[str] env vars under pydantic-settings 2.13.1"
affects: [20-03, 20-04, 20-05, 20-06, 20-07, 20-08, 20-09, 20-10, 20-11, 20-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AppSettings inherits from existing Settings (no parallel config system)"
    - "NoDecode annotation + @field_validator(mode='before') for CSV list[str] env fields (pydantic-settings 2.x complex-type workaround)"

key-files:
  created:
    - flyer_generator/api/__init__.py
    - flyer_generator/api/config.py
    - .planning/phases/20-fastapi-sqlalchemy-backend/deferred-items.md
  modified: []

key-decisions:
  - "Decision: Annotate cors_origins with NoDecode + @field_validator so bare CSV env strings parse without JSONDecodeError under pydantic-settings 2.13.1. Plan claimed the existing ollama_text_model_fallbacks CSV idiom worked — it does not, as verified against installed version."
  - "Decision: Keep SecretStr count at 0 in AppSettings (database_url + redis_url are NOT treated as secrets in v1 per plan; localhost-only per CONTEXT.md Auth section)."
  - "Decision: Defer fixing the pre-existing CSV-env-var bug on Settings.ollama_*_fallbacks to a follow-up plan (out of 20-02 scope)."

patterns-established:
  - "CSV-env list[str] under pydantic-settings 2.x: `Annotated[list[str], NoDecode]` + `@field_validator(mode='before')` handles both bare CSV and JSON array inputs."
  - "AppSettings extension pattern: subclass existing Settings with only new fields; inherit all FLYER_* knobs without redeclaration."

requirements-completed: [API-13]

# Metrics
duration: ~26min
completed: 2026-04-22
---

# Phase 20 Plan 02: AppSettings Foundation Summary

**AppSettings subclass of existing Settings adds 5 Phase 20 fields (database_url, redis_url, cors_origins, artifact_root_flyer, artifact_root_brochure); inherits all 25 FLYER_* knobs; CSV env parsing works under pydantic-settings 2.13.1 via NoDecode annotation.**

## Performance

- **Duration:** ~26 min
- **Started:** 2026-04-22T21:42:00Z (approx, worktree spawn)
- **Completed:** 2026-04-22T22:08:31Z
- **Tasks:** 2 of 2
- **Files created:** 3 (2 runtime + 1 deferred-items log)
- **Files modified:** 0

## Accomplishments

- `flyer_generator.api` package is importable with `from flyer_generator.api import AppSettings` working.
- `AppSettings` extends `Settings` with 5 Phase 20 fields and preserves every existing `FLYER_*` env knob via inheritance (verified for `anthropic_api_key`, `brand_kits_dir`, `comfycloud_api_key`, `output_dir`).
- `FLYER_DATABASE_URL=postgresql+asyncpg://u:p@h/d` overrides default SQLite DSN.
- `FLYER_CORS_ORIGINS="http://a,http://b"` parses into `["http://a","http://b"]` (plus JSON-array, single-value, and whitespace-trimmed variants).
- Existing test suite: **1136 passed, 2 deselected** — zero regressions.

## Task Commits

1. **Task 1: create `flyer_generator/api/__init__.py` package marker** — `519c6bd` (feat)
2. **Task 2: implement `AppSettings` in `flyer_generator/api/config.py`** — `fa3100c` (feat)
3. **Deferred-items log for pre-existing CSV-env bug** — `3587217` (docs)

## Files Created/Modified

- `flyer_generator/api/__init__.py` — placeholder subpackage barrel, re-exports `AppSettings`. Plan 20-06 will replace with `build_app()` + module-level `app`.
- `flyer_generator/api/config.py` — `AppSettings(Settings)` with 5 new fields; `cors_origins` uses `Annotated[list[str], NoDecode]` + `@field_validator(mode="before")` to accept both CSV and JSON array env input.
- `.planning/phases/20-fastapi-sqlalchemy-backend/deferred-items.md` — records the pre-existing CSV-env-var bug in `Settings.ollama_*_fallbacks` (discovered but out of scope for 20-02).

## Decisions Made

- **Plan-deviation decision (cors_origins parser):** The plan stated `Field(default_factory=lambda: [...])` would parse CSV env input "identically" to the existing `ollama_text_model_fallbacks` idiom. Empirically, under the installed `pydantic-settings==2.13.1`, a bare `list[str]` env field is JSON-decoded and raises `SettingsError` on any non-JSON value (including the plan's own `must_have` example `http://a,http://b`). Added `NoDecode` annotation + `@field_validator(mode="before")` that handles CSV, JSON, single value, and whitespace-trimmed inputs. The existing `ollama_*_fallbacks` fields have the same latent bug on `master` but that fix is out of 20-02 scope (logged to `deferred-items.md`).
- **No `SecretStr` for database_url / redis_url in v1** (per CONTEXT.md Auth decision: localhost-only, no credentials in default DSN). Phase 22 can tighten if prod deploy demands redaction.
- **`extra="ignore"`** on `SettingsConfigDict` so `.env` files carrying unrelated keys don't crash startup.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `cors_origins` CSV env parsing broken under pydantic-settings 2.13.1**

- **Found during:** Task 2 (AppSettings implementation) — failure of the plan's own `FLYER_CORS_ORIGINS=http://a,http://b` must_have assertion.
- **Issue:** The plan claimed `Field(default_factory=lambda: ["http://localhost:5173"])` on a `list[str]` field would parse bare CSV env input "identically to existing `ollama_text_model_fallbacks`". In pydantic-settings 2.13.1 (the installed version), any bare `list[str]` env field is treated as a complex type and JSON-decoded inside the env source, raising `pydantic_settings.exceptions.SettingsError` before model validators run. Verified by testing both `AppSettings().cors_origins` and the pre-existing `Settings().ollama_text_model_fallbacks` with CSV env input — both fail identically.
- **Fix:**
  - Annotated the field as `Annotated[list[str], NoDecode]` (pydantic-settings escape hatch that tells the env source to pass the raw string through).
  - Added `@field_validator("cors_origins", mode="before")` that handles CSV (split + strip), JSON arrays (`json.loads`), single values, and whitespace.
  - Added `import json` + `from typing import Annotated` + `from pydantic_settings import NoDecode` + `from pydantic import field_validator` at module top.
- **Files modified:** `flyer_generator/api/config.py` (the file I was already creating in Task 2).
- **Verification:** 8 env-override permutations now pass: CSV 2-value, CSV single, CSV whitespace-trimmed, JSON array, default, plus `FLYER_DATABASE_URL` / `FLYER_REDIS_URL` / `FLYER_BRAND_KITS_DIR` / `FLYER_ANTHROPIC_API_KEY` inherited-field overrides. Existing 1136 tests pass.
- **Acceptance-criterion side-effect:** The plan's grep acceptance line `grep -n "cors_origins: list\[str\]"` no longer matches exactly because the field is now `cors_origins: Annotated[list[str], NoDecode]`. The semantic intent (a `list[str]` field named `cors_origins`) is preserved, but the strict text match would fail. This is a cosmetic acceptance-text mismatch, not a must_have violation — every must_have in the plan's frontmatter passes.
- **Committed in:** `fa3100c` (Task 2 commit).

---

**Total deviations:** 1 auto-fixed (1 bug fix; Rule 1).
**Impact on plan:** Necessary for the plan's own stated must_have to hold. No scope creep beyond the single file Task 2 already owns. A pre-existing identical bug on `Settings.ollama_*_fallbacks` is intentionally NOT fixed here (logged to `deferred-items.md`) per the executor SCOPE BOUNDARY rule.

## Issues Encountered

- `uv` not present on worktree PATH; the project's `.venv/bin/python` was on PATH directly, so verification commands ran under the venv Python without invoking `uv run`. Result equivalent.
- Hook "READ-BEFORE-EDIT" reminder fired on the first `Edit` to the just-created `config.py` (even though the file was created via `Write` in the same session and the tool responses showed the edits succeeded). Re-read the file before each subsequent edit to stay on the happy path; no content was lost.

## Deferred Issues

None within the scope of Plan 20-02.

Out-of-scope discovery (logged for follow-up):

- Pre-existing CSV-env-var bug in `flyer_generator/config.py::Settings.ollama_text_model_fallbacks` and `ollama_vision_model_fallbacks`. See `.planning/phases/20-fastapi-sqlalchemy-backend/deferred-items.md` for full context and suggested fix. Not urgent: defaults work, only users explicitly setting the env var hit it.

## User Setup Required

None. `AppSettings()` works with zero configuration; defaults are local-dev-friendly (SQLite file + localhost Redis + Vite dev CORS origin).

## Next Phase Readiness

- **Wave 1 complete for this plan.** `AppSettings` is the single source of truth every Wave 2+ plan will import (`db.py`, `worker.py`, `middleware.py`, `routes/*.py`, `tasks/*.py`, `lifespan.py`). Verified importable, verified defaults, verified env overrides.
- **No blockers** for Wave 2 plans that depend on 20-02.
- **Known gotcha for 20-06 / future plans:** If a future plan adds another `list[str]` env field, apply the same `Annotated[list[str], NoDecode]` + `field_validator(mode="before")` pattern (or wait for the follow-up plan that fixes the root cause in `Settings`).

## Threat Flags

None. Plan was config-only; no new network endpoints, auth paths, file access, or schema changes introduced. T-5 (Information Disclosure for `database_url` / `redis_url`) is mitigated by defaulting to local SQLite and localhost Redis (no credentials in default values) — addressed per the plan's `<threat_model>` section.

## TDD Gate Compliance

Plan 20-02 is not a `type: tdd` plan (it is `type: execute`). No RED/GREEN/REFACTOR gate required. Verification was performed via direct Python import harness commands and the existing test suite (`pytest tests/ -q -m "not slow" -x` → 1136 passed).

## Self-Check: PASSED

**Files:**
- FOUND: `flyer_generator/api/__init__.py`
- FOUND: `flyer_generator/api/config.py`
- FOUND: `.planning/phases/20-fastapi-sqlalchemy-backend/deferred-items.md`

**Commits:**
- FOUND: `519c6bd` (Task 1: api/__init__.py)
- FOUND: `fa3100c` (Task 2: AppSettings)
- FOUND: `3587217` (docs: deferred-items.md)

**Plan must_haves truths (all verified via live Python invocation):**
- `from flyer_generator.api.config import AppSettings` — OK
- `AppSettings()` inherits all `FLYER_*` fields from `Settings` — OK (`anthropic_api_key`, `brand_kits_dir`, `comfycloud_api_key`, `output_dir` all present)
- `FLYER_DATABASE_URL=postgresql+asyncpg://u:p@h/d` env override lands on `AppSettings().database_url` — OK
- `FLYER_CORS_ORIGINS=http://a,http://b` env override parses into `['http://a','http://b']` — OK
- Defaults: `database_url='sqlite+aiosqlite:///./flyer.db'`, `redis_url='redis://localhost:6379'`, `cors_origins=['http://localhost:5173']` — OK
- `flyer_generator.api` is importable as a package — OK

**Existing test suite:** 1136 passed, 2 deselected, 1 warning (pre-existing, unrelated to 20-02).

---

*Phase: 20-fastapi-sqlalchemy-backend*
*Plan: 02*
*Completed: 2026-04-22*
