---
phase: 18-brand-kit-system
plan: 01
subsystem: foundation
tags: [brand-kit, storage, config, dependencies, pydantic-settings, errors, gitignore]

# Dependency graph
requires:
  - phase: prior
    provides: FlyerGeneratorError base class, Settings (pydantic-settings), schema_renderer loader pattern
provides:
  - BrandKitError hierarchy (BrandKitError, BrandKitScrapeError, BrandKitContrastError, BrandKitAuditError)
  - Settings.brand_kits_dir field honoring FLYER_BRAND_KITS_DIR env var
  - flyer_generator.brand_kit package stub (docstring-only, per B1)
  - storage.py with resolve_kit_dir / save_brand_kit / load_brand_kit / list_brand_kits
  - Slug regex + path-containment safety rails (T-18-CONFIG-01, T-18-PATH-01 mitigations)
  - .brand-kit-template.json tracked schema-reference
  - Five new deps declared: beautifulsoup4, tinycss2, wcag-contrast-ratio, coloraide, playwright
  - .brand-kits/ gitignored
affects: [18-02-models, 18-03-contrast, 18-04-scraper, 18-05-applier, 18-06-audit, 18-07-init-consolidation, 18-08-cli]

# Tech tracking
tech-stack:
  added: [beautifulsoup4>=4.14, tinycss2>=1.5, wcag-contrast-ratio>=0.9, coloraide>=8,<9, playwright>=1.58]
  patterns:
    - "Lazy-import pattern for same-wave module load cycles (storage.py ↔ models.py)"
    - "Explicit base_dir= bypasses containment check; env-driven path enforces CWD/HOME"
    - "Docstring-only __init__.py stub during parallel execution; consolidated re-exports deferred to Plan 07"
    - "TDD RED/GREEN commit separation per task (test commit precedes feat commit)"

key-files:
  created:
    - flyer_generator/brand_kit/__init__.py
    - flyer_generator/brand_kit/storage.py
    - .brand-kit-template.json
    - tests/brand_kit/__init__.py
    - tests/brand_kit/test_errors.py
    - tests/brand_kit/test_storage.py
  modified:
    - flyer_generator/errors.py
    - flyer_generator/config.py
    - pyproject.toml
    - .gitignore

key-decisions:
  - "Containment check applies only when base_dir is resolved from Settings (env/default), not when caller passes explicit base_dir= (matches threat model T-18-CONFIG-01 scope and allows pytest tmp_path to work)."
  - "__init__.py is docstring-only during Plans 01-06/08; Plan 07 owns the consolidated re-export block (per checker iteration 1, B1)."
  - "All tests use direct-module imports (from flyer_generator.brand_kit.storage import ...); never from package root."
  - "BrandKit imported lazily inside save/load functions to avoid load-cycle with models.py (same wave)."
  - "FLYER_BRAND_KITS_ALLOW_SYSTEM=1 escape hatch lets operators opt into system paths explicitly."

patterns-established:
  - "Lazy-import for same-wave cycle avoidance: TYPE_CHECKING import at module top; concrete import inside function body with # noqa: PLC0415"
  - "Slug safety: regex ^[a-z0-9][a-z0-9-]*$ enforced at _validate_slug before any Path join; list_brand_kits filters same regex on discovered dirs"
  - "Error subclass with typed context: __init__(message, *, cycles=0, remaining_issues=None, **kwargs) calls super() with **kwargs so trace_id + ad-hoc context continue to flow"

requirements-completed: [HANDOFF-BK-STORAGE]

# Metrics
duration: ~12min
completed: 2026-04-21
---

# Phase 18 Plan 01: Brand Kit Foundation Summary

**Laid the foundation for the brand-kit subsystem: 4-class exception hierarchy, Settings.brand_kits_dir field, flyer_generator.brand_kit package (docstring-only stub), storage module with slug + containment safety rails, tracked .brand-kit-template.json, and 5 new deps declared.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-20T23:59Z (approx)
- **Completed:** 2026-04-21T00:14Z
- **Tasks:** 3
- **Files created:** 6
- **Files modified:** 4

## Accomplishments
- BrandKit exception hierarchy (base + 3 subclasses) appended to `flyer_generator/errors.py` following the existing `ComfyJobTimeoutError` extended-init pattern; `BrandKitAuditError` carries `cycles` and `remaining_issues` typed fields.
- `Settings.brand_kits_dir: Path = Path(".brand-kits")` added, reachable via `FLYER_BRAND_KITS_DIR` env var through the existing `FLYER_` pydantic-settings prefix.
- `flyer_generator/brand_kit/` package initialized with a MINIMAL DOCSTRING-ONLY `__init__.py` per checker iteration 1 (B1) so Plans 02-06 and 08 can write in parallel without conflict.
- `flyer_generator/brand_kit/storage.py` implemented with `resolve_kit_dir`, `save_brand_kit`, `load_brand_kit`, `list_brand_kits`; lazy-imports `BrandKit` inside functions so it compiles before Plan 02 lands.
- Slug regex `^[a-z0-9][a-z0-9-]*$` rejects uppercase, slashes, path traversal, and leading hyphens. `list_brand_kits` filters discovered directories by the same regex (ignores `Bad Name/` on disk).
- Path-containment check enforces CWD-or-HOME for env-driven paths; explicit `base_dir=` kwarg trusts the caller (tests, library users). `FLYER_BRAND_KITS_ALLOW_SYSTEM=1` escape hatch for operator-controlled system paths.
- `.brand-kit-template.json` committed at repo root with every BrandKit field populated — realistic placeholder values across palette (primary + 4 named neutrals + extras dict), typography (with `size_scale` + `font_sources`), logos (primary + mark_only), voice, photography, source_artifacts, and `size_multiplier=1.0`.
- Five new deps declared in `pyproject.toml`: `beautifulsoup4>=4.14`, `tinycss2>=1.5`, `wcag-contrast-ratio>=0.9`, `coloraide>=8,<9`, `playwright>=1.58`. `colorthief` deliberately NOT added (abandoned, Python-2 only — RESEARCH.md).
- `.brand-kits/` added to `.gitignore`.
- 13 new tests (4 errors + 9 storage), 2 skipped pending Plan 02's `models.py` (per design). 665 existing tests continue to pass.

## Task Commits

Each task was committed atomically with TDD RED/GREEN separation:

1. **Task 1 RED — test(18-01): add failing tests for BrandKit exception hierarchy** — `781d266` (test)
2. **Task 1 GREEN — feat(18-01): add BrandKit exception hierarchy + deps + gitignore** — `81883bc` (feat)
3. **Task 2 RED — test(18-01): add failing storage tests (direct-module imports)** — `3c7b0c9` (test)
4. **Task 2 GREEN — feat(18-01): add brand_kits_dir Settings + brand_kit package stub + storage** — `8d97dde` (feat)
5. **Task 3 — docs(18-01): add .brand-kit-template.json schema-reference at repo root** — `158276c` (docs)

## Files Created/Modified

- `flyer_generator/errors.py` — Appended `BrandKitError`, `BrandKitScrapeError`, `BrandKitContrastError`, `BrandKitAuditError` (with `cycles` + `remaining_issues` typed fields on the audit subclass).
- `flyer_generator/config.py` — Added `brand_kits_dir: Path = Path(".brand-kits")` field to `Settings` (env: `FLYER_BRAND_KITS_DIR`).
- `flyer_generator/brand_kit/__init__.py` — Docstring-only stub declaring package; explicitly documents Plan 07's consolidated re-export responsibility.
- `flyer_generator/brand_kit/storage.py` — Storage primitives: slug validation, containment check, resolve_kit_dir, save_brand_kit (writes brand.json + logos/ + source/ dirs), load_brand_kit (lazy-imports BrandKit), list_brand_kits.
- `.brand-kit-template.json` — Tracked schema-reference at repo root; every BrandKit field populated with realistic placeholder values.
- `pyproject.toml` — Added 5 brand-kit deps to `[project] dependencies`.
- `.gitignore` — Added `.brand-kits/`.
- `tests/brand_kit/__init__.py` — Package marker for test discovery.
- `tests/brand_kit/test_errors.py` — 4 tests covering hierarchy, scrape-error context round-trip, audit-error typed fields, catch-as-base.
- `tests/brand_kit/test_storage.py` — 9 tests covering Settings default + env override, slug regex rejection (uppercase/traversal/slash), list enumeration + bad-slug filtering, round-trip (skips pending Plan 02), missing-kit FileNotFoundError.

## Decisions Made

- **Containment check scope narrowed to env-driven paths only.** The plan's `test_resolve_kit_dir_valid_slug(tmp_path)` cannot pass under pytest's default `/tmp/pytest-of-*/` tmp_path, which is outside both CWD (`/home/hoyack/work/autocreative/...`) and HOME. The threat model (T-18-CONFIG-01) is scoped explicitly to `Settings.brand_kits_dir read from env`; explicit `base_dir=` kwargs are a trust assertion by the caller. So containment enforcement happens only when `base_dir is None` (Settings path). All plan acceptance criteria still pass (traversal/uppercase/slash still rejected via slug regex, which runs unconditionally). Documented in storage.py docstring.
- **Lazy `BrandKit` import inside `save_brand_kit` and `load_brand_kit`** so this module compiles even when `flyer_generator.brand_kit.models` does not exist yet (Plan 02 lands in the same wave). `TYPE_CHECKING` block preserves static-type-checker visibility without a runtime import. Tests guard round-trip assertions with `pytest.importorskip("flyer_generator.brand_kit.models")`.
- **`__init__.py` docstring-only stub** per checker iteration 1 (B1). No imports, no `__all__`. Plan 07 overwrites with the consolidated re-export block after Plans 02-06/08 have landed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Containment check refused pytest tmp_path, breaking a plan-mandated test**
- **Found during:** Task 2 (storage.py GREEN phase)
- **Issue:** `test_resolve_kit_dir_valid_slug(tmp_path)` passes `base_dir=tmp_path` (e.g. `/tmp/pytest-of-hoyack/pytest-7/test_0`), which is neither under CWD (`/home/hoyack/work/autocreative/.claude/worktrees/agent-a2dc5529`) nor under HOME (`/home/hoyack`). The containment check as written in the plan raised `BrandKitError` and failed the test. Either the plan's test or the plan's containment behavior had to bend.
- **Fix:** Narrowed `_validate_containment` enforcement to the code path where `base_dir is None` (i.e. resolved from Settings/env). When the caller passes `base_dir=` explicitly, containment is skipped because the caller has asserted trust in that path. This matches the threat model's scope (T-18-CONFIG-01 targets `Settings.brand_kits_dir read from env` specifically) and preserves every acceptance criterion — slug regex still blocks `"WithCaps"`, `"../evil"`, `"a/b"` unconditionally.
- **Files modified:** `flyer_generator/brand_kit/storage.py` (inside `resolve_kit_dir`).
- **Verification:** `pytest tests/brand_kit/ -q` → 13 passed, 2 skipped. Both the rejection tests (uppercase, traversal, slash) and the valid-slug test now pass.
- **Committed in:** `8d97dde` (Task 2 GREEN commit).

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** Zero scope creep. The plan's acceptance criteria, behavior contracts, and threat mitigations are all preserved. A docstring in `storage.py` explains the scope narrowing.

## Issues Encountered
- None beyond the deviation above.

## User Setup Required

None in this plan. Developer/CI will need to `uv sync` before Plan 04 (scraper) because Playwright also requires `playwright install chromium` for the headless browser. That's Plan 04's concern.

## Next Phase Readiness

- **Plan 02 (models.py):** Can proceed immediately. Storage module is ready to round-trip `BrandKit` through `model_dump_json()` and `model_validate()`. Two skipped tests in `tests/brand_kit/test_storage.py` auto-activate as soon as `flyer_generator/brand_kit/models.py` is importable.
- **Plan 03 (contrast), Plan 04 (scraper), Plan 05 (applier), Plan 06 (audit):** All can proceed in parallel on top of this foundation without touching `__init__.py`. Each writes its own submodule and tests with direct-module imports.
- **Plan 07 (init consolidation):** Will overwrite `__init__.py` with the consolidated re-export block once Plans 02-06 and 08 have landed.
- **No blockers.**

## Self-Check: PASSED

All created files exist on disk:
- FOUND: flyer_generator/errors.py (modified)
- FOUND: flyer_generator/config.py (modified)
- FOUND: flyer_generator/brand_kit/__init__.py
- FOUND: flyer_generator/brand_kit/storage.py
- FOUND: .brand-kit-template.json
- FOUND: tests/brand_kit/__init__.py
- FOUND: tests/brand_kit/test_errors.py
- FOUND: tests/brand_kit/test_storage.py
- FOUND: pyproject.toml (modified)
- FOUND: .gitignore (modified)

All task commits present in `git log`:
- FOUND: 781d266 (Task 1 RED)
- FOUND: 81883bc (Task 1 GREEN)
- FOUND: 3c7b0c9 (Task 2 RED)
- FOUND: 8d97dde (Task 2 GREEN)
- FOUND: 158276c (Task 3)

Verification run: `pytest tests/ -q` → 678 passed, 2 skipped (round-trip tests skip pending Plan 02).

---
*Phase: 18-brand-kit-system*
*Completed: 2026-04-21*
