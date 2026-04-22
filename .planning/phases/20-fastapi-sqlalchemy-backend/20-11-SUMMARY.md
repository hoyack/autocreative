---
phase: 20-fastapi-sqlalchemy-backend
plan: 11
subsystem: api
tags: [fastapi, sqlalchemy, path-traversal, security, job-polling, file-streaming]

# Dependency graph
requires:
  - phase: 20-fastapi-sqlalchemy-backend
    provides: JobRecord + RenderRecord + CampaignRecord/PostRecord ORM models (Plan 20-03), JobDetail/ResultLink schemas (Plan 20-05), empty route stubs + app wiring (Plan 20-06), campaign task writes CampaignRecord.id=JobRecord.id (Plan 20-07)
provides:
  - "GET /api/v1/jobs/{id} polling endpoint returning JobDetail with campaign result fusion"
  - "GET /api/v1/renders/{id}/image artifact streaming with T-1 (HIGH) path-traversal mitigation"
  - "7 job-polling tests covering queued/succeeded/failed/campaign-fuse/running-campaign paths"
  - "8 render-streaming tests including explicit T-1 traversal rejection test"
  - "Stable polling contract consumable by Phase 21 frontend"
affects: [21-frontend, future-auth-phase, future-websocket-streaming]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Campaign result fusion via selectinload(CampaignRecord.posts).selectinload(PostRecord.render) — single query, no N+1"
    - "T-1 path containment: Path.resolve(strict=True) + is_relative_to over allow-listed roots; every failure returns opaque 404 'render not found'"
    - "Extension whitelist as defense-in-depth (.png/.pdf/.jpg/.jpeg) — unknown suffix -> 404, never octet-stream"
    - "FastAPI PathParam(min_length=26, max_length=26) enforces ULID shape at the URL layer -> 422 on malformed id"

key-files:
  created:
    - tests/api/test_jobs_routes.py
    - tests/api/test_renders_routes.py
  modified:
    - flyer_generator/api/routes/jobs.py
    - flyer_generator/api/routes/renders.py

key-decisions:
  - "Campaign fusion keyed on JobRecord.id == CampaignRecord.id (per Plan 20-07 task_generate_campaign contract), avoiding a FK or lookup table"
  - "All renders.py failure modes collapse to opaque 404 'render not found' to prevent filesystem-shape disclosure (T-1 mitigation)"
  - "Content-Disposition: inline (not attachment) because API consumers embed these in an <img>/<object> tag, not download them"
  - "resolve(strict=True) chosen over naive startswith/normpath because it follows symlinks and forces existence — a single check catches both symlink escape and missing-file"
  - "Running campaigns return result_ref=None (not a partial list) so clients continue polling until terminal status"

patterns-established:
  - "Read-side endpoint test template: seed via sessionmaker_fx, assert via AsyncClient(ASGITransport)"
  - "Security test template: point all four allowed roots inside tmp_path, plant malicious file_path, assert 404 + opaque body"

requirements-completed: [API-10, API-11]

# Metrics
duration: 35min
completed: 2026-04-22
---

# Phase 20 Plan 11: Jobs + Renders Routes Summary

**Read-side HTTP surface complete — job polling fuses campaign posts into ResultLink lists, and render streaming ships T-1 (HIGH) path-traversal mitigation verified by an explicit grep-named test.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-04-22 (agent startup)
- **Completed:** 2026-04-22
- **Tasks:** 4 (all auto)
- **Files modified:** 2 route files populated (stubs replaced) + 2 new test files

## Accomplishments

- `GET /api/v1/jobs/{id}` returns stable `JobDetail` shape: single-render jobs get `result_ref` as a URL path; campaigns get a list of `ResultLink(platform, url)` fused via `selectinload` (no N+1); queued/running/failed jobs get `result_ref=None`.
- `GET /api/v1/renders/{id}/image` mitigates T-1 (HIGH) via three concentric defenses — DB-keyed lookup (no filename input), resolved-path containment against four allowed roots, and extension whitelist. Every failure returns an opaque 404 so the filesystem shape never leaks.
- `test_get_render_rejects_path_traversal_outside_all_roots` is a grep-verifiable T-1 test that plants a `RenderRecord` with `file_path="/etc/hostname"` and asserts 404 + an opaque body. Catches any future regression if someone reintroduces `StreamingResponse(open(record.file_path))` on a sibling route.
- 15 new tests, 135 passing in `tests/api/`, 1138 passing in the rest of the suite — no regression.

## Task Commits

1. **Task 1: Implement routes/jobs.py with campaign-fusing result_ref** — `f64ffd5` (feat)
2. **Task 2: Implement routes/renders.py — path-traversal-safe artifact streaming (T-1)** — `e8fba45` (feat)
3. **Task 3: tests/api/test_jobs_routes.py — polling + campaign fusing** — `8e6fd1b` (test)
4. **Task 4: tests/api/test_renders_routes.py — T-1 path-traversal rejection** — `0379640` (test)

## Files Created/Modified

- `flyer_generator/api/routes/jobs.py` — `GET /api/v1/jobs/{job_id}` returning `JobDetail`; campaign branch fuses `CampaignRecord.posts` + `PostRecord.render` via single `selectinload` query
- `flyer_generator/api/routes/renders.py` — `GET /api/v1/renders/{render_id}/image` + `_is_within()` helper + `_ALLOWED_EXT_MIME` whitelist; every guard failure -> opaque 404
- `tests/api/test_jobs_routes.py` — 7 async tests: 404, 422, queued, succeeded-single, failed, campaign-fuse, running-campaign
- `tests/api/test_renders_routes.py` — 8 async tests: 404, 422, PNG happy path, PDF happy path, T-1 /etc/hostname traversal, dotdot traversal, missing file inside root, bad extension

## Decisions Made

- **Campaign fusion keyed on JobRecord.id == CampaignRecord.id** (Plan 20-07 contract). No FK needed on JobRecord — keeps the `result_ref` column as a nullable single-render pointer and lets campaigns use ORM relationships.
- **Opaque 404 on every renders failure** (missing id, missing file, outside roots, bad extension). Deliberate — a 403 "outside allowed roots" would leak filesystem shape and help an attacker map the trusted roots.
- **`Path.resolve(strict=True)` + `is_relative_to`** over `os.path.commonpath` or string prefix checks — resolves symlinks, forces existence, and is the canonical py3.9+ idiom.
- **`Content-Disposition: inline; filename="<name>"`** so the frontend can `<img src>` the endpoint directly; a download flow would switch to `attachment`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's hand-crafted test ULIDs had wrong length (27-29 chars)**
- **Found during:** Task 3 (tests/api/test_jobs_routes.py authoring)
- **Issue:** The plan's `<action>` body supplied ULID fixtures such as `01HJOBQUEUED0000000000000001` (28 chars) and `01HRENDER000000000000000001` (27 chars). These would fail the route's `PathParam(min_length=26, max_length=26)` with 422 instead of hitting the route body, so the queued/succeeded/failed/campaign/404-by-missing tests would all assert the wrong status code and the T-1 test would never reach the containment guard.
- **Fix:** Regenerated all test ULIDs as valid 26-char strings (`01HABC…`-prefixed) so each id flows through the PathParam guard and exercises the intended code path.
- **Files modified:** tests/api/test_jobs_routes.py, tests/api/test_renders_routes.py
- **Verification:** `python -c "assert all(len(s) == 26 for s in [...])"`; all 15 tests pass.
- **Committed in:** 8e6fd1b (Task 3) and 0379640 (Task 4).

**2. [Rule 1 - Bug] Plan's dotdot traversal test used too few '..' segments to escape pytest's tmp_path**
- **Found during:** Task 4 (first run of `test_get_render_rejects_dotdot_in_filepath`)
- **Issue:** The plan constructed `flyer_root / ".." / ".." / ".." / "etc" / "hostname"`. pytest's `tmp_path` is typically `/tmp/pytest-of-<user>/pytest-N/<test>/flyers`, so three `..` segments resolve to `/tmp/pytest-of-<user>/etc/hostname` (non-existent), causing the test to SKIP instead of exercising the traversal guard.
- **Fix:** Used a loop that prepends 10 `..` segments — enough to reach filesystem root even under nested tmp_path trees (`Path.resolve` clamps at `/`).
- **Files modified:** tests/api/test_renders_routes.py
- **Verification:** `pytest tests/api/test_renders_routes.py::test_get_render_rejects_dotdot_in_filepath -v` → PASSED (no longer SKIPPED).
- **Committed in:** 0379640 (Task 4 commit, fix applied before commit).

**3. [Rule 2 - Missing Critical] Added `Annotated` branch-free return in `_is_within` for robustness**
- **Found during:** Task 2 authoring
- **Issue:** The plan's `_is_within` sketch wrapped both the candidate `resolve(strict=True)` AND the root resolve in the same try, and included a dead py<3.9 `relative_to`+ValueError fallback branch. On py3.11+ (the project target) the fallback is unreachable, and a single `try` block conflated two different failure modes (candidate missing vs. root I/O error) that should return `False` silently.
- **Fix:** Split candidate and root resolution into two `try` blocks; dropped the unreachable py<3.9 fallback (project pins `python>=3.11`); kept the existence-not-required semantics on root (root may legitimately be empty during tests).
- **Files modified:** flyer_generator/api/routes/renders.py
- **Verification:** All 8 renders tests pass; `_is_within` correctly returns `False` for missing file, non-existent directory, symlink-outside-root, and IO errors.
- **Committed in:** e8fba45 (Task 2 commit).

---

**Total deviations:** 3 auto-fixed (2 × Rule 1 bug, 1 × Rule 2 hardening)
**Impact on plan:** All three fixes essential for the test suite to actually exercise the code paths they claim to test. No scope creep — the endpoint shape and guard semantics match the plan exactly.

## Issues Encountered

None beyond the deviations above.

## Threat Flags

None. No new network endpoints, auth paths, or schema changes introduced beyond what the plan and phase-level threat register already covered.

## Test Results

- `tests/api/test_jobs_routes.py` — 7 passed (0 skipped, 0 failed)
- `tests/api/test_renders_routes.py` — 8 passed (0 skipped, 0 failed)
- `tests/api/` aggregate — 135 passed
- Remaining suite — 1138 passed, 1 pre-existing warning (`Post.copy` shadow — not introduced by this plan)

## User Setup Required

None — no external service configuration or env-var changes for this plan.

## Next Phase Readiness

- Read-side HTTP surface is complete and stable for Phase 21 (frontend polling loop).
- `GET /api/v1/jobs/{id}` response shape is the consumed contract: `{id, kind, status, started_at, completed_at, error_detail, result_ref, created_at}`.
- `result_ref` polymorphism handled client-side via `typeof result_ref === 'string'` vs array check.
- T-1 regression guard is in place — any future route that streams files should use `_is_within` from `routes/renders.py` (or a shared helper if/when a second streaming endpoint emerges).

## Self-Check: PASSED

Verified claims before finalizing:

- `flyer_generator/api/routes/jobs.py` — present, implements `GET /jobs/{job_id}`
- `flyer_generator/api/routes/renders.py` — present, implements `GET /renders/{render_id}/image` with `_is_within` + `_ALLOWED_EXT_MIME`
- `tests/api/test_jobs_routes.py` — present, 7 async tests
- `tests/api/test_renders_routes.py` — present, 8 async tests including `test_get_render_rejects_path_traversal_outside_all_roots`
- Commits `f64ffd5`, `e8fba45`, `8e6fd1b`, `0379640` — all present in `git log --oneline`
- All 15 new tests pass; 1138 baseline suite tests still green; no regressions

---
*Phase: 20-fastapi-sqlalchemy-backend*
*Completed: 2026-04-22*
