---
phase: 20-fastapi-sqlalchemy-backend
plan: 05
subsystem: api
tags: [pydantic-v2, fastapi, schemas, request-response, openapi]

# Dependency graph
requires:
  - phase: 20-fastapi-sqlalchemy-backend
    provides: "AppSettings (20-02), JobKind/JobStatus enums + ORM barrel (20-03)"
provides:
  - "7 new files under flyer_generator/api/schemas/ exporting 12 Pydantic v2 models"
  - "Request schemas: FlyerCreateRequest, BrochureCreateRequest, BrandKitFetchRequest, PostCreateRequest, CampaignCreateRequest"
  - "Response schemas: JobCreated, JobDetail (with ResultLink), RenderSummary, BrandKitSummary, PaginatedBrandKits, BrandKitDetail"
  - "Verbatim reuse of existing Pydantic v2 models (EventInput, BrochureContent, BrandKit, Platform/Intent Literals) via field composition — zero duplication"
  - "Consistent slug regex ^[a-z0-9][a-z0-9-]*$ across every brand-kit identifier field (matches flyer_generator.brand_kit.storage)"
  - "Hand-rolled pagination shape (items/total/limit/offset) — no new fastapi-pagination dep"
  - "72 new tests codifying barrel import, extra=forbid, model_dump(mode=json) round-trips, slug regex, accent regex, Platform/Intent Literal rejection, platforms length bounds, max_bg_attempts range"
affects:
  - "20-06 app factory (imports from schemas barrel)"
  - "20-08 flyer routes (FlyerCreateRequest, JobCreated, JobDetail)"
  - "20-09 brochure routes (BrochureCreateRequest, JobCreated, JobDetail)"
  - "20-10 brand-kit routes (BrandKitFetchRequest, BrandKitSummary, PaginatedBrandKits, BrandKitDetail, JobCreated)"
  - "20-11 social routes (PostCreateRequest, CampaignCreateRequest, JobCreated)"
  - "20-12 jobs/renders routes (JobDetail, RenderSummary)"

# Tech tracking
tech-stack:
  added: []  # No new dependencies — pydantic v2 already present
  patterns:
    - "Wrapper-schema idiom: API schemas compose existing Pydantic models verbatim (event: EventInput, content: BrochureContent, brand_kit: BrandKit)"
    - "API-boundary fields (brand_kit_slug, accent override, style_preset) live on the wrapper, not the embedded model"
    - "ConfigDict(extra='forbid') on every new schema to fail-fast on typos from clients"
    - "Slug regex duplicated across 4 files (brand_kits.py/flyers.py/brochures.py/social.py) — deliberate, avoids a shared _common.py for a 30-char regex"
    - "Hand-rolled pagination response shape (PaginatedBrandKits) per RESEARCH.md Q4"
    - "JobDetail.result_ref typed as str | list[ResultLink] | None so single-render jobs and campaigns both serialize cleanly"

key-files:
  created:
    - "flyer_generator/api/schemas/__init__.py (barrel)"
    - "flyer_generator/api/schemas/jobs.py (JobCreated, ResultLink, JobDetail)"
    - "flyer_generator/api/schemas/renders.py (RenderSummary)"
    - "flyer_generator/api/schemas/flyers.py (FlyerCreateRequest)"
    - "flyer_generator/api/schemas/brochures.py (BrochureCreateRequest)"
    - "flyer_generator/api/schemas/brand_kits.py (BrandKitFetchRequest, BrandKitSummary, PaginatedBrandKits, BrandKitDetail)"
    - "flyer_generator/api/schemas/social.py (PostCreateRequest, CampaignCreateRequest)"
    - "tests/api/test_schemas.py (72 tests locking in must_haves)"
  modified: []

key-decisions:
  - "PostCreateRequest is a thin wrapper (not PostBrief verbatim) because API clients need brand_kit_slug at the top level — PostBrief in the generator layer doesn't carry it"
  - "CampaignCreateRequest mirrors the social CLI options (platforms list, intent, topic, cta) at the API boundary, with platforms capped 1..10 by Field(min_length=1, max_length=10)"
  - "Slug regex is duplicated across schema files rather than centralized — a shared module for a 30-char regex would add import ceremony with no correctness win"
  - "Added tests/api/test_schemas.py (Rule 2) to lock in the must_have truth 'model_dump(mode=json) round-trip coverage' — without a test file, the requirement had no enforcement"

patterns-established:
  - "Wrapper schemas compose, never redefine, existing Pydantic v2 models"
  - "Every request schema enforces slug regex via @field_validator; response schemas accept arbitrary slug strings (already validated elsewhere)"
  - "JobDetail.result_ref union (str | list[ResultLink] | None) documents the single-vs-campaign-vs-pending job lifecycle directly in the schema"

requirements-completed:
  - API-05
  - API-06
  - API-07
  - API-08
  - API-09
  - API-10

# Metrics
duration: 7min
completed: 2026-04-22
---

# Phase 20 Plan 05: API Pydantic Schemas Summary

**Twelve Pydantic v2 request/response schemas wrapping existing EventInput / BrochureContent / BrandKit / PostBrief models with API-boundary fields (brand_kit_slug, accent, style_preset) and ConfigDict(extra="forbid") enforcement.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-22T22:22:57Z
- **Completed:** 2026-04-22T22:30:00Z (approx)
- **Tasks:** 2
- **Files created:** 8 (7 schema files + 1 test file)
- **Files modified:** 0

## Accomplishments

- Created 12 Pydantic v2 schemas under `flyer_generator/api/schemas/` covering every request/response shape future routes will use (flyer create, brochure create, brand-kit fetch/list/detail, social post/campaign create, job created/detail, render summary).
- Embedded existing Pydantic v2 models verbatim — `event: EventInput`, `content: BrochureContent`, `brand_kit: BrandKit` — proving the API layer does not duplicate any domain model.
- Reused `Platform` and `Intent` Literals from `flyer_generator.social.models` so the API and the generator share one source of truth for vocabulary.
- Enforced consistent slug regex (`^[a-z0-9][a-z0-9-]*$`) across every brand-kit identifier field, matching the regex already enforced in `flyer_generator.brand_kit.storage`.
- Typed `JobDetail.result_ref` as `str | list[ResultLink] | None` so single-artifact jobs can return a URL path, campaigns can return a list of platform/url entries, and queued/running jobs serialize as `null` — all in one schema.
- Added 72 tests (all passing) locking in every must_have truth: barrel wiring, `extra="forbid"`, `model_dump(mode="json")` round-trips for every model, slug/accent regex coverage, Platform/Intent Literal enforcement, `platforms` length bounds (1..10), and `max_bg_attempts` range (1..10).

## Task Commits

1. **Task 1: jobs.py + renders.py + flyers.py + brochures.py** — `0ac923a` (feat)
2. **Task 2: brand_kits.py + social.py + __init__.py + test_schemas.py** — `a06ca52` (feat)

## Files Created/Modified

- `flyer_generator/api/schemas/__init__.py` — barrel re-exporting all 12 schemas (sorted `__all__`).
- `flyer_generator/api/schemas/jobs.py` — `JobCreated` (ULID-sized `job_id`), `ResultLink` (platform+url), `JobDetail` (polymorphic `result_ref`, imports `JobKind`/`JobStatus` from the ORM module created in 20-03).
- `flyer_generator/api/schemas/renders.py` — `RenderSummary` (read-only metadata row, no bytes).
- `flyer_generator/api/schemas/flyers.py` — `FlyerCreateRequest` wrapping `EventInput`, plus `preset`, `brand_kit_slug` (regex-validated), `accent` (hex pattern), and `max_bg_attempts` (1..10).
- `flyer_generator/api/schemas/brochures.py` — `BrochureCreateRequest` wrapping `BrochureContent`, plus `template`, `brand_kit_slug`, `generate_images`, `workflow`, `style_preset`.
- `flyer_generator/api/schemas/brand_kits.py` — `BrandKitFetchRequest` (AnyHttpUrl + slug), `BrandKitSummary` (list entry), `PaginatedBrandKits` (hand-rolled pagination), `BrandKitDetail` (embeds `BrandKit`).
- `flyer_generator/api/schemas/social.py` — `PostCreateRequest` (reuses `Platform`/`Intent` Literals, adds `brand_kit_slug` + `style_preset` at the API boundary), `CampaignCreateRequest` (platforms list capped 1..10).
- `tests/api/test_schemas.py` — 72 tests: barrel import, `extra="forbid"` on every model, `model_dump(mode="json")` round-trips (with nested `EventInput` / `BrochureContent` / `BrandKit`), slug regex (valid + invalid slugs per schema), `Platform`/`Intent` Literal rejection, empty/overflowing `platforms` list rejection, hex-accent validation (good + bad), `max_bg_attempts` range.

## Decisions Made

- **PostCreateRequest is a wrapper, not PostBrief verbatim.** Plan frontmatter called for this explicitly — API clients need `brand_kit_slug` at the top level, which the generator-layer `PostBrief` deliberately does not carry. The wrapper mirrors PostBrief's fields so clients using either layer see the same vocabulary.
- **Slug regex duplicated across four files.** Centralizing into `schemas/_common.py` would introduce a new module for a 30-character regex; the duplication is local, test-enforced, and matches the pattern already in `flyer_generator/brand_kit/storage.py`.
- **`preset` / `template` / `workflow` / `style_preset` are `str`, not `Literal`.** Registries are pluggable (CLI-06 custom-preset registration). Validation happens when the worker task resolves the name; the API schema just caps length.
- **Accent uses Pydantic's `pattern=` instead of a `@field_validator`.** For compactness on a one-line constraint.
- **Added `tests/api/test_schemas.py`** (Rule 2: missing critical functionality). The plan's `must_haves.truths` explicitly require `model_dump(mode="json")` round-trip coverage, but the plan's `<tasks>` did not define a test file. Without one, the must-have was unverifiable. The 72-test file locks in every must-have truth and catches future regressions (e.g. accidental removal of `extra="forbid"` on any schema).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `tests/api/test_schemas.py`**
- **Found during:** Task 2 (acceptance checks)
- **Issue:** `must_haves.truths` require `"model_dump(mode=\"json\") round-trip coverage"` and `"Brand-kit `slug` fields are validated with the same regex \"^[a-z0-9][a-z0-9-]*$\""`, but the plan's `<tasks>` only specified inline `uv run python -c "..."` smoke checks — nothing in the repo would enforce these must-haves after the plan finished.
- **Fix:** Created `tests/api/test_schemas.py` with 72 tests covering barrel wiring, `extra="forbid"` parametrized across all 12 models, `model_dump(mode="json")` round-trips for every schema (including nested `EventInput` / `BrochureContent` / `BrandKit`), slug regex (valid + invalid) across every schema, Platform/Intent Literal enforcement, `platforms` length bounds, accent regex, and `max_bg_attempts` range.
- **Files modified:** `tests/api/test_schemas.py` (new, 356 lines).
- **Verification:** `pytest tests/api/test_schemas.py -v` → 72 passed. `pytest tests/ -q -m "not slow" -x` → 1211 passed (1139 pre-existing + 72 new), no regressions.
- **Committed in:** `a06ca52` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical).
**Impact on plan:** Adds enforcement for must_have truths that were otherwise aspirational. No scope creep — the test file only validates the schemas this plan creates.

## Issues Encountered

None.

## TDD Gate Compliance

Plan is `type: execute` (not `type: tdd`) — TDD gate sequence does not apply. The new test file was added alongside the implementation (Task 2) rather than before it (RED gate) because the plan frontmatter does not mandate TDD.

## Threat Model Compliance

- **T-2 (SSRF)** — `BrandKitFetchRequest.url` is typed `AnyHttpUrl`, which only enforces `http(s)://` syntax. Actual SSRF protection lives in `flyer_generator/brand_kit/scraper.py` lines 297-303 as planned. The schema forwards the URL verbatim to the task — no bypass added.
- **T-6 (DoS via large bodies)** — Every string field has `max_length`: event fields 120 (inherited from `EventInput`), topic 400, slug 64, cta 200, image_hint 400, style_preset 64. `platforms` list is capped `max_length=10`. `max_bg_attempts` is bounded `ge=1, le=10`.
- **T-7 (Information disclosure via slug enumeration)** — Accepted per CONTEXT.md (v1 is single-user / private-network). No mitigation required.

No new threat surface introduced beyond what the plan's threat model already documents.

## Known Stubs

None. Every schema field flows through validation and into real storage or a downstream model — no placeholder data, no hard-coded empty values wired to UI.

## Next Phase Readiness

- Plans 20-06 (app factory), 20-08 (flyer routes), 20-09 (brochure routes), 20-10 (brand-kit routes), 20-11 (social routes), 20-12 (jobs/renders routes) can now import from `flyer_generator.api.schemas` with no further schema work.
- The `result_ref: str | list[ResultLink] | None` shape documents the full job lifecycle for both single-artifact and campaign jobs, so the jobs-route plan doesn't need to re-design it.
- Barrel `__all__` is sorted and explicit — no `import *` surprises.

## Self-Check: PASSED

**Files verified:**
- FOUND: flyer_generator/api/schemas/__init__.py
- FOUND: flyer_generator/api/schemas/jobs.py
- FOUND: flyer_generator/api/schemas/renders.py
- FOUND: flyer_generator/api/schemas/flyers.py
- FOUND: flyer_generator/api/schemas/brochures.py
- FOUND: flyer_generator/api/schemas/brand_kits.py
- FOUND: flyer_generator/api/schemas/social.py
- FOUND: tests/api/test_schemas.py

**Commits verified:**
- FOUND: 0ac923a (Task 1)
- FOUND: a06ca52 (Task 2)

---
*Phase: 20-fastapi-sqlalchemy-backend*
*Plan: 05*
*Completed: 2026-04-22*
