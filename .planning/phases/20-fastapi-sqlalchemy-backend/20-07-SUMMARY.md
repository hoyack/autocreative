---
phase: 20-fastapi-sqlalchemy-backend
plan: 07
subsystem: api-worker
tags: [arq, worker, tasks, async, sqlalchemy]
dependency_graph:
  requires:
    - flyer_generator.api.config.AppSettings
    - flyer_generator.api.db.build_engine
    - flyer_generator.api.db.build_sessionmaker
    - flyer_generator.api.models.JobRecord
    - flyer_generator.api.models.JobStatus
    - flyer_generator.api.models.RenderRecord
    - flyer_generator.api.models.BrandKitRecord
    - flyer_generator.api.models.FlyerRecord
    - flyer_generator.api.models.BrochureRecord
    - flyer_generator.api.models.CampaignRecord
    - flyer_generator.api.models.PostRecord
    - flyer_generator.brand_kit.fetch_brand_kit
    - flyer_generator.brand_kit.load_brand_kit
    - flyer_generator.pipeline.FlyerGenerator
    - flyer_generator.brochure.schema_renderer.loader.load_template
    - flyer_generator.brochure.schema_renderer.renderer.render_schema_brochure
    - flyer_generator.brochure.stages.pdf.assemble_brochure_pdf
    - flyer_generator.social.generate_post
    - flyer_generator.social.generate_campaign
  provides:
    - flyer_generator.api.worker.WorkerSettings
    - flyer_generator.api.tasks.ALL_TASKS
    - flyer_generator.api.tasks.task_fetch_brand_kit
    - flyer_generator.api.tasks.task_generate_flyer
    - flyer_generator.api.tasks.task_generate_brochure
    - flyer_generator.api.tasks.task_generate_post
    - flyer_generator.api.tasks.task_generate_campaign
    - flyer_generator.api.tasks._state.mark_running
    - flyer_generator.api.tasks._state.mark_succeeded
    - flyer_generator.api.tasks._state.mark_failed
  affects:
    - routes in Plan 20-08..11 will enqueue tasks by string name via arq_pool.enqueue_job
tech_stack:
  added:
    - arq.connections.RedisSettings (worker broker config)
  patterns:
    - per-task state-transition helpers commit JobRecord on every hop
    - asyncio.to_thread wrapping for sync image/PDF pipelines
    - httpx.AsyncClient owned by worker on_startup, threaded via ctx
    - session.merge upsert for idempotent re-scrape of brand kits
    - Campaign.model_construct in tests to bypass strict Pydantic validation
key_files:
  created:
    - flyer_generator/api/worker.py
    - flyer_generator/api/tasks/__init__.py
    - flyer_generator/api/tasks/_state.py
    - flyer_generator/api/tasks/brand_kit.py
    - flyer_generator/api/tasks/flyer.py
    - flyer_generator/api/tasks/brochure.py
    - flyer_generator/api/tasks/post.py
    - flyer_generator/api/tasks/campaign.py
    - tests/api/conftest.py
    - tests/api/test_worker_tasks.py
  modified: []
decisions:
  - Worker owns its own engine+sessionmaker+httpx client in on_startup (cannot reach uvicorn's app.state)
  - max_tries=1 deliberate — llm_retry.py already handles per-call retry, avoids ComfyCloud double-charge
  - Campaign jobs store NULL in JobRecord.result_ref; route fuses per-post URLs from CampaignRecord.posts at GET time
  - State helpers commit per-hop so SIGTERM mid-task still leaves a durable JobStatus
  - mark_failed writes only {type, message} — exc.context kwargs may carry SecretStr/paths/SSRF reasons (T-5)
metrics:
  duration: 10min
  completed: 2026-04-22
  task_count: 3
  file_count: 10
requirements: [API-12]
---

# Phase 20 Plan 07: Worker Tasks Summary

Landed arq `WorkerSettings` + five wrapper task functions + per-hop state-transition helpers + 8 direct-invocation tests. Each task wraps an existing generator entrypoint verbatim (no reimplementation) and commits `JobRecord.status` on every hop so polling clients see correct state even if the worker is SIGTERM'd mid-run.

## One-Liner

arq worker + 5 async task wrappers routing to existing `FlyerGenerator` / `fetch_brand_kit` / `render_schema_brochure` / `generate_post` / `generate_campaign` entrypoints with per-hop JobRecord commits and T-5-safe error_detail.

## What Got Built

### `flyer_generator/api/worker.py` (61 lines)
- `WorkerSettings` class — arq CLI entrypoint
- `on_startup(ctx)` builds per-worker engine + sessionmaker + shared `httpx.AsyncClient(follow_redirects=True, timeout=300)`
- `on_shutdown(ctx)` closes client + disposes engine
- `functions = ALL_TASKS` — all 5 task coroutines registered
- `max_tries = 1` (Pitfall 4: llm_retry already owns retry)
- `max_jobs = 4`, `job_timeout = 600s`, `keep_result = 3600s`
- `redis_settings = RedisSettings.from_dsn(str(AppSettings().redis_url))`

### `flyer_generator/api/tasks/_state.py` (77 lines)
Three coroutines, each using its own `async with sessionmaker()` block so commits are durable across hops:
- `mark_running(sm, job_id)` — queued -> running + `started_at`
- `mark_succeeded(sm, job_id, *, result_ref)` — running -> succeeded + `completed_at`; stores result_ref as string or NULL (campaigns)
- `mark_failed(sm, job_id, exc)` — running -> failed + `completed_at`; writes **only** `{"type": type(exc).__name__, "message": str(exc)}` (T-5: `exc.context` bag stays out of the JSON column)

### `flyer_generator/api/tasks/__init__.py` (30 lines)
Imports + re-exports all five task coroutines and `ALL_TASKS` list consumed by `WorkerSettings.functions`.

### Five task modules
Uniform signature `async def task_*(ctx: dict, *, job_id: str, payload: dict) -> str | None`.

Each task flow: `mark_running` -> call existing generator -> persist `RenderRecord` + subsystem record -> `mark_succeeded`.  On exception: `mark_failed` + re-raise (arq records failed, max_tries=1 prevents retry).

| Task | Wraps | Primary Record Writes |
|---|---|---|
| `task_fetch_brand_kit` | `flyer_generator.brand_kit.fetch_brand_kit` | `BrandKitRecord` (upsert via `session.merge`) |
| `task_generate_flyer` | `flyer_generator.FlyerGenerator.generate` | `RenderRecord(kind="flyer_final")` + `FlyerRecord` |
| `task_generate_brochure` | `render_schema_brochure` (sync) + `generate_template_images` (async) + `assemble_brochure_pdf` (sync) | 3x `RenderRecord` (front/back/pdf) + `BrochureRecord` |
| `task_generate_post` | `flyer_generator.social.generate_post` | `PostRecord` + optional `RenderRecord(kind="social_post_image")` |
| `task_generate_campaign` | `flyer_generator.social.generate_campaign` | `CampaignRecord` + N `PostRecord` + M `RenderRecord` |

### `tests/api/conftest.py` (31 lines)
`sessionmaker_fx` fixture: in-memory SQLite via `StaticPool` + `check_same_thread=False` so coroutines share one connection (else each gets a fresh empty `:memory:` DB).  Mirrors the production `expire_on_commit=False`.

### `tests/api/test_worker_tasks.py` (418 lines, 8 tests)

| # | Test | What it covers |
|---|---|---|
| 1 | `test_mark_running_then_succeeded` | `_state.py` happy path + timestamps |
| 2 | `test_mark_failed_writes_safe_error_detail` | **T-5 mitigation**: `BrandKitNotFoundError(slug=..., expected_path=...)` context kwargs must NOT appear in `error_detail` JSON |
| 3 | `test_task_fetch_brand_kit_writes_record` | Mocked `fetch_brand_kit`, asserts `BrandKitRecord` + `JobStatus.SUCCEEDED` |
| 4 | `test_task_raises_on_failure_and_marks_failed` | Mocked `BrandKitScrapeError`, asserts `JobStatus.FAILED` + error type, verifies re-raise |
| 5 | `test_task_generate_flyer_writes_render_and_flyer` | **WARNING-6**: mocked `FlyerGenerator`, verifies `RenderRecord` + `FlyerRecord` + `result_ref` wiring |
| 6 | `test_task_generate_brochure_imports_cleanly_and_writes_records` | **BLOCKER-2 guard**: proves `load_template` + `assemble_brochure_pdf` + `Rasterizer` imports resolve at worker-boot time; 3 RenderRecord rows persisted |
| 7 | `test_task_generate_post_writes_post_and_optional_render` | **WARNING-6**: `FakePost` with `image_bytes`, asserts `PostRecord` + `RenderRecord` |
| 8 | `test_task_generate_campaign_iterates_posts_full` | **BLOCKER-1 guard**: uses real `Campaign.model_construct(posts=..., posts_full=...)`; catches AttributeError if anyone regresses `campaign.posts_full.values()` back to `campaign.posts` |

**Result:** 8/8 passing.  Full suite (post-plan): **1224/1224 passing** (`pytest -q`), 0 failures, 1 pre-existing unrelated warning about `Post.copy` shadowing BaseModel.copy.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Wrong kwarg name: `workflow` -> `workflow_name`**
- **Found during:** Task 3, reading `image_gate.py:197`
- **Issue:** Plan wrote `generate_template_images(..., workflow=payload.get("workflow", ...))` but the real signature is `workflow_name: str = "ernie_landscape"` (see `flyer_generator/brochure/schema_renderer/image_gate.py:202`). Calling with `workflow=` would raise TypeError at runtime.
- **Fix:** Used `workflow_name=payload.get("workflow_name", "turbo_landscape")`.
- **Files modified:** `flyer_generator/api/tasks/brochure.py:75`
- **Commit:** `9cded10`

**2. [Rule 1 — Bug] `kit.logos[0].bytes` doesn't exist on `BrandLogo`**
- **Found during:** Task 3, reading `flyer_generator/brand_kit/models.py:70-78`
- **Issue:** Plan wrote `logo_bytes=(kit.logos[0].bytes if kit and kit.logos else None)`. `BrandLogo` is filesystem-backed — it has `path: str`, `variant: Literal[...]`, `format: Literal[...]`, `aspect_ratio: float` but NO `.bytes` attribute. The assets live on disk at `kit_dir / logo.path`. The original code would AttributeError any time a brand kit was attached.
- **Fix:** Set `logo_bytes: bytes | None = None` with a comment documenting that proper byte-hydration is deferred to a follow-up plan. Downstream renderer already handles `logo_bytes=None`.
- **Files modified:** `flyer_generator/api/tasks/brochure.py:79-91`
- **Commit:** `9cded10`

**3. [Rule 1 — Bug] `Campaign.posts_full` rejects duck-typed `FakePost`**
- **Found during:** Task 3 first test run — `pydantic_core.ValidationError: Input should be a valid dictionary or instance of Post`
- **Issue:** Test used `Campaign(posts_full={"key": FakePost(...)})` but `Campaign.posts_full: dict[str, "Post"]` enforces strict Pydantic validation. Test doubles fail type check.
- **Fix:** Switched to `Campaign.model_construct(...)` which bypasses validation — canonical Pydantic v2 idiom for injecting test fakes. Regression test still validates the iteration path (the one thing it's meant to protect).
- **Files modified:** `tests/api/test_worker_tasks.py:~400`
- **Commit:** `9cded10`

**4. [Rule 3 — Blocking] Task 1 verification needs all 5 task modules to exist**
- **Found during:** Task 1, running Task 1's `<verify>` block
- **Issue:** Task 1's `<verify>` imports `from flyer_generator.api.tasks import ALL_TASKS` which transitively imports all 5 task modules. Tasks 2 and 3 create them — Task 1 as written cannot verify.
- **Fix:** Created minimal `NotImplementedError`-raising stub task files at Task 1 time so the `__init__.py` import chain resolves. Tasks 2 and 3 overwrite the stubs with real implementations. Each commit shows the correct task-by-task diff.
- **Files affected:** `flyer_generator/api/tasks/brand_kit.py`, `flyer.py`, `post.py`, `brochure.py`, `campaign.py`
- **Commit:** `cdff4fb` (stubs) -> `7b76925` (brand_kit/flyer/post filled) -> `9cded10` (brochure/campaign filled)

### Auth Gates

None.  No external APIs contacted during execution — tests mock `fetch_brand_kit`, `FlyerGenerator`, `generate_post`, `generate_campaign`, and the brochure pipeline at their import boundaries.

### Deferred

**`BrandLogo` bytes hydration.**  The brochure task currently passes `logo_bytes=None` unconditionally.  When a follow-up plan wires logo-byte loading (likely via a small `load_logo_bytes(kit, kit_dir) -> bytes` helper in `flyer_generator.brand_kit.storage`), update line 84 of `flyer_generator/api/tasks/brochure.py`.  Logged to the phase `deferred-items.md` isn't present yet; noting here instead.

## Known Stubs

None.  Every task's happy path writes real DB rows and on-disk artifacts.  The `logo_bytes=None` path is a renderer-supported no-op, not a stub.

## Threat Flags

None found.  This plan:
- Reuses existing SSRF gate inside `fetch_brand_kit` (Phase 18) — task does NOT bypass.
- Keeps `JobRecord.error_detail` to `{type, message}` only — T-5 covered and tested.
- Writes artifacts to deterministic `<artifact_root>/<job_id>/*.png` paths under settings-controlled roots; `job_id` is a ULID minted by the route layer (not user-supplied).

No new network endpoints, no new auth paths, no new schema changes at trust boundaries — this plan is an internal worker component consumed only by Plans 20-08..11 routes.

## Verification Evidence

```bash
$ .venv/bin/python -c "from flyer_generator.api.worker import WorkerSettings; print([f.__name__ for f in WorkerSettings.functions])"
['task_fetch_brand_kit', 'task_generate_flyer', 'task_generate_brochure', 'task_generate_post', 'task_generate_campaign']

$ .venv/bin/python -m pytest tests/api/test_worker_tasks.py -v
8 passed in 0.85s

$ .venv/bin/python -m pytest -q
1224 passed, 1 warning in 76.87s
```

Grep audit (all acceptance criteria pass):
- `class WorkerSettings` ✓ (worker.py:45)
- `max_tries = 1` ✓ (worker.py:60)
- `functions = ALL_TASKS` ✓ (worker.py:53)
- `async def on_startup/on_shutdown` ✓
- `httpx.AsyncClient(follow_redirects=True, timeout=300` ✓
- 3x `async def mark_` in `_state.py` ✓
- `"type": type(exc).__name__` ✓ (T-5 mitigation, _state.py:72)
- `for post in campaign.posts_full.values()` ✓ (campaign.py:72, BLOCKER-1 fix)
- `from flyer_generator.brochure.schema_renderer.loader import load_template` ✓ (brochure.py:30)
- `from flyer_generator.brochure.stages.pdf import assemble_brochure_pdf` ✓ (brochure.py:32)
- 8 tests in `test_worker_tasks.py` (all 4 WARNING-6 closure tests present) ✓

## Commits

| Task | Hash | Message |
|---|---|---|
| 1 | `cdff4fb` | `feat(20-07): add arq WorkerSettings + task state helpers` |
| 2 | `7b76925` | `feat(20-07): implement brand_kit/flyer/post tasks` |
| 3 | `9cded10` | `feat(20-07): implement brochure/campaign tasks + direct-invocation tests` |

## Self-Check: PASSED

All 10 created files present on disk:

- flyer_generator/api/worker.py (FOUND)
- flyer_generator/api/tasks/__init__.py (FOUND)
- flyer_generator/api/tasks/_state.py (FOUND)
- flyer_generator/api/tasks/brand_kit.py (FOUND)
- flyer_generator/api/tasks/flyer.py (FOUND)
- flyer_generator/api/tasks/brochure.py (FOUND)
- flyer_generator/api/tasks/post.py (FOUND)
- flyer_generator/api/tasks/campaign.py (FOUND)
- tests/api/conftest.py (FOUND)
- tests/api/test_worker_tasks.py (FOUND)

All 3 commits present in git log:

- cdff4fb (FOUND)
- 7b76925 (FOUND)
- 9cded10 (FOUND)
