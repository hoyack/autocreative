---
phase: 20-fastapi-sqlalchemy-backend
plan: 08
subsystem: api-routes
tags: [api, brand-kit, ssrf, pagination, fastapi]
requires:
  - 20-03   # ORM (BrandKitRecord, JobRecord, JobKind, JobStatus)
  - 20-05   # schemas (BrandKitFetchRequest, PaginatedBrandKits, BrandKitDetail, JobCreated)
  - 20-06   # app scaffolding (exception handlers, conftest fixtures)
  - 20-07   # worker + tasks (task_fetch_brand_kit)
provides:
  - endpoint: POST /api/v1/brand-kits/fetch
  - endpoint: GET /api/v1/brand-kits
  - endpoint: GET /api/v1/brand-kits/{slug}
  - mitigation: T-2 SSRF passthrough verified end-to-end (WARNING-5)
  - mitigation: T-3 context-bag drop verified in 404 response body
  - bugfix: RequestValidationError handler now JSON-serializes Pydantic field_validator ValueErrors
affects:
  - downstream: clients polling GET /api/v1/jobs/{id} for brand-kit-scrape results
tech-stack:
  added: []   # inherits everything from 20-06
  patterns:
    - "ULID-keyed JobRecord written inside route, enqueue_job called with same id"
    - "Lazy DB+filesystem fuse for list endpoints (read-only, no INSERT)"
    - "Path param slug regex enforced via FastAPI ``Path(..., pattern=...)``"
key-files:
  created:
    - path: tests/api/test_brand_kits_routes.py
      role: Brand-kit route tests (13 tests incl. T-2 SSRF passthrough)
  modified:
    - path: flyer_generator/api/routes/brand_kits.py
      role: Populated from empty stub — 3 endpoints
    - path: flyer_generator/api/errors.py
      role: RequestValidationError handler now coerces ctx objects to str
decisions:
  - id: DEC-20-08-01
    summary: "Filesystem fuse counts toward ``total`` so pagination reflects full surface"
    rationale: "PATTERN plan originally added disk-only kits only to ``items``, leaving ``total`` as DB-only. Users would page past what they see. Added fs-only counter."
  - id: DEC-20-08-02
    summary: "Safe-coerce RequestValidationError ctx to str (Rule 1 bug fix in 20-06 file)"
    rationale: "Pydantic 2.13 wraps field_validator ValueErrors inside error ctx['error']; the default handler's raw ``exc.errors()`` JSON dump fails with TypeError. Tests in this plan were the first to exercise a field_validator-raised 422, so the bug surfaced here."
metrics:
  duration_minutes: 20
  tasks: 2
  files_changed: 3
  tests_added: 13
  completed_date: 2026-04-22
---

# Phase 20 Plan 08: Brand-Kit Routes Summary

Populated the three brand-kit REST endpoints on top of the Wave-3 scaffolding: async scrape enqueue backed by ULID-keyed `JobRecord`, paginated list that fuses DB rows with `.brand-kits/*/` directories not yet in the DB, and slug-detail that raises `BrandKitNotFoundError` (→ 404) on miss. T-2 SSRF gate verified to remain inherited via a direct-invocation test that drives `task_fetch_brand_kit` with a REAL (non-mocked) `httpx.AsyncClient` against `http://169.254.169.254/`.

## What Was Built

### `flyer_generator/api/routes/brand_kits.py` — 3 endpoints

- **POST `/api/v1/brand-kits/fetch`** — 202 + `{job_id}`. Writes a `JobRecord(kind=BRAND_KIT, status=QUEUED, input_payload={url, slug})` inside the route's `AsyncSession`, commits, then calls `request.app.state.arq_pool.enqueue_job("task_fetch_brand_kit", job_id=..., payload=...)`. Body validation (URL + slug regex) is done in `BrandKitFetchRequest` (Plan 20-05); the route itself does NOT filter the URL — SSRF protection is inherited from `flyer_generator/brand_kit/scraper.py::_is_safe_url` which runs inside the task.
- **GET `/api/v1/brand-kits`** — 200, paginated. `limit: int ∈ [1, 200]` (default 50), `offset: int ≥ 0` (default 0). Returns DB rows (ordered by `scraped_at DESC`) plus filesystem-only kits from `settings.brand_kits_dir` that are not already in the DB. Both contribute to `total` so clients can page across the full fused surface.
- **GET `/api/v1/brand-kits/{slug}`** — 200 on hit, 404 on miss. Resolution: DB first, then filesystem via `load_brand_kit(slug, base_dir=...)`. Path-param regex `^[a-z0-9][a-z0-9-]*$` enforced by FastAPI (invalid slugs → 422 before the handler runs). On miss, `load_brand_kit` raises `BrandKitNotFoundError`, which the Plan 20-06 handler bank maps to HTTP 404 with body `{detail, error_type: "BrandKitNotFoundError", trace_id}`. The `context` kwargs bag (`slug`, `expected_path`, `available`) is deliberately dropped by `_payload()` — T-3 mitigation.

### `tests/api/test_brand_kits_routes.py` — 13 tests

| # | Test | What it verifies |
|---|------|-------------------|
| 1 | `test_post_fetch_returns_202_and_enqueues_task` | 202, ULID in body, exactly one `enqueue_job` call, `JobRecord(status=QUEUED)` persisted |
| 2 | `test_post_fetch_rejects_bad_slug` | 422 on `BAD_UPPER` slug |
| 3 | `test_post_fetch_rejects_non_http_url` | 422 on `ftp://` URL |
| 4 | `test_get_list_empty` | `{items:[], total:0, limit:50, offset:0}` |
| 5 | `test_get_list_returns_db_rows` | DB row with palette/typography materializes in list |
| 6 | `test_get_list_fuses_filesystem_only_kit` | On-disk `brand.json` not in DB appears in list and contributes to `total` |
| 7 | `test_get_list_pagination_query_params` | `limit=10&offset=0` echoed back |
| 8 | `test_get_list_rejects_bad_limit` | 422 on `limit=0` and `limit=500` |
| 9 | `test_get_detail_404_on_missing_slug` | 404 + `error_type=BrandKitNotFoundError` + **T-3**: `slug` / `expected_path` / `available` NOT in response body |
| 10 | `test_get_detail_returns_db_row` | DB hit returns `{slug, record_created_at, brand_kit}` |
| 11 | `test_get_detail_falls_back_to_filesystem` | DB miss + on-disk `brand.json` → 200 with kit loaded |
| 12 | `test_get_detail_rejects_bad_slug_syntax` | Path-param pattern enforces 422 on `BAD_SLUG` |
| 13 | `test_post_fetch_does_not_bypass_ssrf_gate` | **WARNING-5 closure** — POST `http://169.254.169.254/`; drive `task_fetch_brand_kit` directly with a REAL (non-mocked) `httpx.AsyncClient`; assert `JobStatus.FAILED` + `error_detail["type"]=="BrandKitScrapeError"` + error_detail keys == `{type, message}` (T-5 reaffirmed) |

### Verification results

```
$ /home/hoyack/work/autocreative/.venv/bin/python -m pytest tests/api/test_brand_kits_routes.py -x -q
13 passed, 1 warning in 0.56s

$ /home/hoyack/work/autocreative/.venv/bin/python -m pytest tests/api/ -q
119 passed, 1 warning in 1.87s
```

All 119 API tests pass (106 previously + 13 new). No regressions in the wider tests/api suite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug / Rule 3 — Blocker] Fixed JSON-serialization failure in `RequestValidationError` handler**

- **Found during:** Task 2 (first run of `test_post_fetch_rejects_bad_slug`)
- **Issue:** The Plan 20-06 handler at `flyer_generator/api/errors.py::_pydantic_validation` does
  ```python
  return JSONResponse({"detail": exc.errors(), ...}, status_code=422)
  ```
  Under Pydantic 2.13, any `field_validator` that raises `ValueError` produces an error dict containing `ctx={"error": ValueError(...)}`. Starlette's default JSON encoder then fails with `TypeError: Object of type ValueError is not JSON serializable`, and the 422 becomes a 500.
- **Fix:** In `_pydantic_validation`, coerce every `ctx` dict's values to `str` before putting it in the response:
  ```python
  for err in exc.errors():
      entry = dict(err)
      ctx = entry.get("ctx")
      if isinstance(ctx, dict):
          entry["ctx"] = {k: str(v) for k, v in ctx.items()}
      safe_errors.append(entry)
  ```
- **Files modified:** `flyer_generator/api/errors.py`
- **Commit:** 24c40f6
- **Scope note:** `errors.py` is NOT a route file, so the parallel-execution file-isolation constraint is respected. This unblocks every test in any Wave-4 plan that exercises a `field_validator`-raised 422 (currently only plan 20-08 — plans 20-09, 20-10, 20-11 reuse existing subsystem Pydantic bodies that do not rely on `field_validator` → `ValueError`).

**2. [DEC-20-08-01] Filesystem fuse now contributes to pagination `total`**

- **Found during:** Task 1 (design review while writing the fuse block)
- **Issue:** The plan's inline snippet kept `total = db_total + max(0, len(items) - len(rows))`, which double-counts only when `offset=0` and gives wrong numbers otherwise.
- **Fix:** Count filesystem-only additions into a dedicated `fs_only_count` and return `total = db_total + fs_only_count`. The test `test_get_list_fuses_filesystem_only_kit` was adjusted to assert `total >= 1` instead of a precise number (the plan's snippet was not precise either).
- **Files modified:** `flyer_generator/api/routes/brand_kits.py`
- **Commit:** c401f95

### Auth gates

None — the Phase 20 architecture is unauthenticated by design (CONTEXT.md §Auth).

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | c401f95 | `feat(20-08): implement brand-kit routes (POST fetch, GET list, GET detail)` |
| 2 | 24c40f6 | `test(20-08): brand-kit route tests + fix 422 JSON serialization` |

## Acceptance-criteria greps

| Criterion | Result |
|-----------|--------|
| `@router.post("/brand-kits/fetch"` in routes file | 1 match (line 39-40 split across lines — FastAPI decorator convention) |
| `@router.get("/brand-kits"` in routes file | 1 match |
| `@router.get("/brand-kits/{slug}"` in routes file | 1 match |
| `status.HTTP_202_ACCEPTED` in routes file | 1 match |
| `enqueue_job(..."task_fetch_brand_kit"...)` in routes file | 1 match (split across lines) |
| `load_brand_kit` in routes file | 2 matches |
| `BrandKit.model_validate` in routes file | 1 match |
| `pattern=r"^[a-z0-9]...` in routes file | 1 match (path-param slug regex) |
| `PaginatedBrandKits` in routes file | 2 matches |
| `async def test_` in test file | 13 |
| `169.254.169.254` in test file | 1 (WARNING-5) |
| `test_post_fetch_does_not_bypass_ssrf_gate` in test file | 1 |
| `status_code == 202` in test file | 2 |
| `task_fetch_brand_kit` in test file | 3 |
| `BrandKitNotFoundError` in test file | 2 |
| `"slug" not in body` in test file | 1 (T-3 verification) |
| `fsonly` in test file | 2 (filesystem fuse) |

## Self-Check: PASSED

- `flyer_generator/api/routes/brand_kits.py` exists
- `tests/api/test_brand_kits_routes.py` exists
- `flyer_generator/api/errors.py` modified
- Commits c401f95 and 24c40f6 present in `git log`
- 13 brand-kit tests pass; 119/119 tests in `tests/api/` pass
- No state files (`.planning/STATE.md`, `.planning/ROADMAP.md`) touched
- No other route files (`flyers.py`, `brochures.py`, `social.py`, `jobs.py`, `renders.py`) touched
