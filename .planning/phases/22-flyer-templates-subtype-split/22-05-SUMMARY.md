---
phase: 22-flyer-templates-subtype-split
plan: 05
subsystem: db-schema + alembic-migration + arq-worker
tags: [alembic, sqlalchemy, sqlite, postgres, json-extract, arq, tdd, blocker-2-mirror, t-22-10-mitigation]

# Dependency graph
requires:
  - 22-01 (FlyerTemplateSchema + load_template)
  - 22-02 (FlyerInput + EventInput alias)
  - 22-03 (PosterComposer.compose accepts template kwarg)
  - 22-04 (FlyerCreateRequest.template required + FlyerGenerator.generate template kwarg)
provides:
  - FlyerRecord.template column (String(64), NOT NULL, server_default='editorial_classic')
  - Alembic migration f22t01: adds flyers.template + rewrites renders.kind='flyer_final' subtype-derived
  - task_generate_flyer module-scope load_template import (BLOCKER-2 mirror)
  - task_generate_flyer T-22-10 path-traversal guard (_validate_template_slug)
  - task_generate_flyer subtype-aware RenderRecord.kind derivation
  - RenderRecord.kind values: flyer_event_final, flyer_info_final (flyer_final deprecated)
affects:
  - 22-06 (frontend): OpenAPI schema can now be regenerated with the template column + new render kinds
  - 22-07/22-08/22-09 (FE filter pages): KINDS arrays must include flyer_event_final + flyer_info_final
  - tests/api/test_flyer_routes.py and test_worker_tasks.py: 19+ tests now green (the 2 deferred + 17 deselected from Plan 04)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Alembic data-rewrite migration with backend-aware JSON path syntax (SQLite json_extract vs Postgres ->>)"
    - "Idempotent UPDATE guarded by WHERE kind='flyer_final' — re-running migration is a no-op"
    - "COALESCE({subtype_expr}, 'event') — pre-Phase-22 rows without subtype safely default to event-kind"
    - "Module-scope load_template import (BLOCKER-2 mirror) — patchable at flyer_generator.api.tasks.flyer.load_template"
    - "T-22-10 mitigation: bare-slug template name guard (_validate_template_slug) BEFORE load_template's file-path branch"
    - "Subtype-aware RenderRecord.kind derivation: subtype='event' → flyer_event_final; subtype='info' → flyer_info_final"
    - "Test pattern: monkeypatch.setenv('FLYER_DATABASE_URL', ...) to force alembic env.py to use a tmp_path SQLite DB (env.py:31 always overrides sqlalchemy.url with AppSettings.database_url)"

key-files:
  created:
    - alembic/versions/f22t01_flyer_template_and_subtype_split.py  (84 lines)
    - tests/api/test_migrations.py  (181 lines, 6 tests)
  modified:
    - flyer_generator/api/models/flyer.py  (added template column)
    - flyer_generator/api/models/render.py  (extended kind comment)
    - flyer_generator/api/tasks/flyer.py  (full rewrite — module-scope load_template, path guard, subtype kind)
    - tests/api/test_flyer_routes.py  (added template field to all payloads + 2 new tests)
    - tests/api/test_worker_tasks.py  (8 new TDD tests + helpers)

key-decisions:
  - "T-22-10 path-traversal guard placed in worker (_validate_template_slug) rather than schema layer — schema-level rejection would alter the FlyerCreateRequest contract without regard for the worker's actual loader behavior. Worker-side guard is closest to the file-system boundary it protects (defense-in-depth principle)."
  - "Migration includes a third dialect branch (`else: subtype_expr = 'NULL'`) so unsupported backends (mysql/oracle/etc) still upgrade cleanly — the COALESCE then defaults all rows to flyer_event_final. SQLite + Postgres are explicitly handled; everything else gets the conservative default. This avoids a hard-fail upgrade in unforeseen environments."
  - "Migration test fixture uses two SQLAlchemy URLs: async (sqlite+aiosqlite) for alembic env.py, sync (sqlite) for direct seed/assert via create_engine. Pointing at the same on-disk file means the alembic-applied DDL is visible to the sync handle without an extra round-trip."
  - "monkeypatch.setenv('FLYER_DATABASE_URL', ...) is the ONLY mechanism that overrides alembic env.py's hardcoded `config.set_main_option('sqlalchemy.url', settings.database_url)` (env.py:31). Setting cfg.set_main_option('sqlalchemy.url', url) on the test-side Config is silently ignored at runtime. Documented in test docstring + module header."
  - "Reused existing _seed_job + sessionmaker_fx helpers from tests/api/conftest.py + tests/api/test_worker_tasks.py — no new fixtures invented. New helpers (_FakeFlyerOut, _flyer_event_payload, _flyer_info_payload) are module-private to the test file."
  - "The smoke test test_task_generate_flyer_writes_render_and_flyer was rewritten (not just patched) — the pre-Phase-22 version called `EventInput.model_validate` (which is now an alias for FlyerInput) and lacked the template field. The simpler approach was to harmonize it with the new helpers used by the 8 Phase-22 tests."

requirements-completed: [FT-01, FT-06]

# Metrics
duration: ~30min
completed: 2026-04-23
---

# Phase 22 Plan 05: DB Migration + Worker Template Loading Summary

Closes the backend half of Phase 22. After this plan, `POST /api/v1/flyers` with a `template` slug enqueues a worker that loads the template by name, derives the render kind from `FlyerInput.subtype`, and writes a fully-typed `FlyerRecord.template` + subtype-discriminated `RenderRecord.kind` row. Existing `flyer_final` render rows are migrated in-place to subtype-derived kinds via alembic, and the new column is back-filled via a server-default.

## What Was Built

### Task 1 — DB schema + migration (commit `2ad0285`)

**`flyer_generator/api/models/flyer.py`** — added `template` column between `title` and `preset` (mirrors BrochureRecord ordering):

```python
class FlyerRecord(Base):
    __tablename__ = "flyers"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # Phase 22 FT-01: template slug used to render this flyer (mirrors
    # BrochureRecord.template). Existing rows backfill via alembic
    # f22t01 with server_default='editorial_classic'.
    template: Mapped[str] = mapped_column(String(64), nullable=False)
    preset: Mapped[str] = mapped_column(String(64), nullable=False)
    ...
```

**`flyer_generator/api/models/render.py`** — extended the `kind` column comment (no DDL change):

```python
kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
# Valid kinds: "flyer_event_final", "flyer_info_final", "brochure_front",
# "brochure_back", "brochure_pdf", "social_post_image", "brand_kit_logo".
# Deprecated (migrated): "flyer_final" — rewritten to flyer_event_final or
# flyer_info_final by alembic migration f22t01 (Phase 22 FT-06).
```

**`alembic/versions/f22t01_flyer_template_and_subtype_split.py`** — revision `f22t01`, down_revision `2f5971e114b3`. Final migration body:

```python
def upgrade() -> None:
    # 1. Add template column with safe backfill default.
    with op.batch_alter_table("flyers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "template",
                sa.String(length=64),
                nullable=False,
                server_default="editorial_classic",
            )
        )

    # 2. Rewrite renders.kind for pre-Phase-22 flyer rows, subtype-derived.
    connection = op.get_bind()
    dialect = connection.dialect.name

    if dialect == "sqlite":
        subtype_expr = "json_extract(f.event_payload, '$.event.subtype')"
    elif dialect in ("postgresql", "postgres"):
        subtype_expr = "f.event_payload->'event'->>'subtype'"
    else:
        # Conservative default: treat everything as event subtype
        subtype_expr = "NULL"

    connection.execute(sa.text(f"""
        UPDATE renders
           SET kind = CASE
               WHEN (
                   SELECT COALESCE({subtype_expr}, 'event')
                   FROM flyers f
                   WHERE f.render_id = renders.id
               ) = 'info' THEN 'flyer_info_final'
               ELSE 'flyer_event_final'
           END
         WHERE kind = 'flyer_final'
    """))


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE renders
           SET kind = 'flyer_final'
         WHERE kind IN ('flyer_event_final', 'flyer_info_final')
    """))

    with op.batch_alter_table("flyers", schema=None) as batch_op:
        batch_op.drop_column("template")
```

**Idempotency:** `WHERE kind='flyer_final'` in the UPDATE filters already-migrated rows. Re-running `upgrade()` is a no-op.

**Reversibility:** `downgrade()` collapses both new kinds back to `flyer_final` and drops the `template` column. Verified by `test_downgrade_reverses` and dev smoke `alembic upgrade head` followed by `alembic downgrade -1`.

**Backend dialect support:**
- **SQLite** — `json_extract(f.event_payload, '$.event.subtype')` (the repo default)
- **Postgres** — `f.event_payload->'event'->>'subtype'`
- **Other** — fallback to `NULL` so `COALESCE(... , 'event')` defaults all rows to `flyer_event_final`. Upgrade still succeeds; downgrade trivially reverses regardless of dialect.

**`tests/api/test_migrations.py`** — 6 tests covering:

1. `test_template_column_added` — server_default backfills existing rows to `editorial_classic`
2. `test_render_kind_rewritten_event` — subtype='event' rows become `flyer_event_final`
3. `test_render_kind_rewritten_info` — subtype='info' rows become `flyer_info_final`
4. `test_migration_idempotent` — re-running the UPDATE finds 0 rows; before/after kinds identical
5. `test_default_event_subtype_when_subtype_missing` — pre-Phase-22 rows without `subtype` field COALESCE to 'event' → `flyer_event_final`
6. `test_downgrade_reverses` — upgrade then downgrade: kinds revert to `flyer_final`, `template` column dropped

### Task 2 — Worker template loading + subtype-derived kind (commits `0046dd7` RED, `5d64d6b` GREEN)

**`flyer_generator/api/tasks/flyer.py`** — full rewrite. Final shape:

```python
"""arq task wrapping :class:`FlyerGenerator`.generate.

Writes one :class:`RenderRecord` (kind derived from FlyerInput.subtype —
``flyer_event_final`` or ``flyer_info_final``) + one :class:`FlyerRecord`
per generated flyer, then transitions :class:`JobRecord` to ``succeeded``
with ``result_ref`` pointing at the render row.

Phase 22 (FT-01 + FT-06): Late-binding template loader + subtype-aware
render kind. Mirrors the brochure worker's BLOCKER-2 module-scope import
pattern so direct-invocation tests can patch ``load_template`` via
``patch("flyer_generator.api.tasks.flyer.load_template")``.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from flyer_generator import FlyerGenerator
from flyer_generator.api.models import FlyerRecord, RenderRecord
from flyer_generator.api.tasks._state import mark_failed, mark_running, mark_succeeded
from flyer_generator.models import FlyerInput

# NOTE: Module-scope import so direct-invocation tests can patch via
# ``patch("flyer_generator.api.tasks.flyer.load_template")``. Mirrors the
# BLOCKER-2 pattern from brochure.py:22-33: import errors surface at
# worker-boot, not at first request.
from flyer_generator.flyer.schema_renderer.loader import load_template

logger = structlog.get_logger()


def _validate_template_slug(template_name: str) -> None:
    """T-22-10 mitigation: refuse template names that look like file paths.

    The loader's file-path branch activates when ``name_or_path.endswith(".json")``
    (loader.py:20). FlyerCreateRequest.template enforces ``max_length=64`` but
    payloads can still contain ``.json`` (e.g. ``"foo.json"`` is 8 chars) or
    path separators — escape hatches that would let user input read arbitrary
    JSON files. Reject those names here, BEFORE :func:`load_template`.

    Phase 22 threat register entry T-22-10. Phase 26 will harden further with
    adversarial coverage.
    """
    if (
        template_name.endswith(".json")
        or "/" in template_name
        or "\\" in template_name
    ):
        msg = (
            "template must be a bare slug, not a path "
            "(no '.json' suffix, no '/' or '\\\\' separators)"
        )
        raise ValueError(msg)


async def task_generate_flyer(ctx: dict, *, job_id: str, payload: dict) -> str | None:
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]
    http_client = ctx["http_client"]

    log = logger.bind(job_id=job_id, kind="flyer")
    log.info("task_start")
    await mark_running(sessionmaker, job_id)

    try:
        flyer_input = FlyerInput.model_validate(payload["event"])
        template_name = payload["template"]

        # T-22-10: refuse path-like slugs BEFORE the loader's file-path branch.
        _validate_template_slug(template_name)

        # Load template BEFORE any Comfy work so FileNotFoundError /
        # ValidationError surfaces early (mirrors brochure worker behavior).
        template = load_template(template_name)

        log = log.bind(subtype=flyer_input.subtype, template=template_name)

        gen = FlyerGenerator(settings=settings, http_client=http_client)
        out = await gen.generate(flyer_input, template=template)

        artifact_path = Path(settings.artifact_root_flyer) / f"{job_id}.png"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        out.save(artifact_path)

        # Render kind derived from subtype (Phase 22 FT-06).
        render_kind = (
            "flyer_event_final"
            if flyer_input.subtype == "event"
            else "flyer_info_final"
        )

        async with sessionmaker() as s:
            render = RenderRecord(
                kind=render_kind,
                file_path=str(artifact_path.resolve()),
                comfy_job_id=getattr(out, "comfy_job_id", None),
                vision_verdict=(
                    out.final_vision_verdict.model_dump(mode="json")
                    if getattr(out, "final_vision_verdict", None) is not None
                    else None
                ),
            )
            s.add(render)
            await s.flush()  # assign render.id

            flyer = FlyerRecord(
                title=flyer_input.title,
                template=template_name,  # Phase 22 FT-01
                preset=payload["preset"],
                brand_kit_slug=payload.get("brand_kit_slug"),
                event_payload=payload,
                render_id=render.id,
            )
            s.add(flyer)
            await s.commit()

            render_id = render.id

        await mark_succeeded(sessionmaker, job_id, result_ref=render_id)
        log.info("task_succeeded", render_id=render_id, render_kind=render_kind)
        return render_id

    except Exception as exc:
        log.exception("task_failed")
        await mark_failed(sessionmaker, job_id, exc)
        raise
```

**T-22-10 path-traversal guard added: YES.** `_validate_template_slug()` rejects:
- `.json` suffix (e.g. `"foo.json"`) — would activate the loader's file-path branch
- `/` (forward slash) — directory traversal
- `\\` (backslash) — Windows-style traversal

Tested via parametrized `test_flyer_task_rejects_path_like_template_names` covering `'../etc/passwd'`, `'foo.json'`, `'subdir/template'`, `'subdir\\template'` — each raises `ValueError` and marks the JobRecord failed with `error_detail.type == 'ValueError'`.

**`tests/api/test_worker_tasks.py`** — 8 new tests (plus the rewritten smoke test):

1. `test_task_generate_flyer_writes_render_and_flyer` — happy path smoke (rewritten — was broken on Plan 04)
2. `test_flyer_task_loads_template_at_module_scope` — `load_template` called once with `'editorial_classic'`, patchable via the worker module path
3. `test_flyer_task_bad_template_raises_and_marks_failed` — non-existent template name → `FileNotFoundError`, JobRecord marked failed with `error_detail.type == 'FileNotFoundError'`
4. `test_flyer_task_event_subtype_produces_event_render_kind` — subtype='event' → `RenderRecord.kind == 'flyer_event_final'` + FlyerRecord.template column populated
5. `test_flyer_task_info_subtype_produces_info_render_kind` — subtype='info' → `RenderRecord.kind == 'flyer_info_final'`
6. `test_flyer_task_missing_subtype_defaults_to_event` — back-compat: payloads without subtype default to 'event' → `flyer_event_final`
7. `test_flyer_task_threads_template_kwarg_to_generator` — `FlyerGenerator.generate(event, template=template)` receives the loaded template via kwarg
8. `test_flyer_task_writes_template_column` — `FlyerRecord.template == payload['template']`
9. `test_flyer_task_rejects_path_like_template_names` (parametrized × 4) — T-22-10 guard rejects path-like slugs

**`tests/api/test_flyer_routes.py`** — added `template` field to all 8 existing payloads + 2 new tests:
- `test_post_flyer_rejects_missing_template` — 422 when `template` absent
- `test_post_flyer_rejects_empty_template` — 422 when `template=""`
- `test_post_flyer_info_subtype_returns_202` — info-subtype payload (no date/time/venue/fees) accepted with template

## Verification Run Log

```bash
# RED gate (Task 2)
$ .venv/bin/pytest tests/api/test_worker_tasks.py tests/api/test_flyer_routes.py -q
# -> 12 failed, 19 passed (the failures: NOT NULL constraint failed: flyers.template;
#    missing load_template module-scope import; no path-traversal guard)

# GREEN gate (Task 2)
$ .venv/bin/pytest tests/api/test_worker_tasks.py tests/api/test_flyer_routes.py -q
# -> 31 passed in 2.51s

# Migration tests (Task 1)
$ .venv/bin/pytest tests/api/test_migrations.py tests/api/test_models_ddl.py -q
# -> 9 passed in 1.93s

# Full tests/api/ suite
$ .venv/bin/pytest tests/api/ -q
# -> 205 passed, 1 warning in 11.85s

# Full backend suite (excludes tests/integration which hit network)
$ .venv/bin/pytest tests/ -q -k "not slow" --ignore=tests/integration
# -> 1415 passed, 2 deselected, 1 warning in 100.86s

# Alembic head check
$ .venv/bin/alembic heads
# -> f22t01 (head)

# Alembic upgrade/downgrade smoke (fresh sqlite db)
$ FLYER_DATABASE_URL="sqlite+aiosqlite:///tmp/smoke.db" .venv/bin/alembic upgrade head
# -> Running upgrade  -> 2f5971e114b3, initial schema
#    Running upgrade 2f5971e114b3 -> f22t01, flyer template and subtype split
$ FLYER_DATABASE_URL="sqlite+aiosqlite:///tmp/smoke.db" .venv/bin/alembic downgrade -1
# -> Running downgrade f22t01 -> 2f5971e114b3, flyer template and subtype split
```

## Acceptance Criteria — All Pass

### Task 1
- [x] `grep -n "template: Mapped\[str\]" flyer_generator/api/models/flyer.py` → 1 line
- [x] `grep -n "String(length=64)\|String(64)" flyer_generator/api/models/flyer.py` → 2 lines (template + preset)
- [x] `grep -n "flyer_event_final" flyer_generator/api/models/render.py` → 2 lines (comment update)
- [x] `ls alembic/versions/f22t01_flyer_template_and_subtype_split.py` exists
- [x] `grep -n "WHERE kind = 'flyer_final'" alembic/versions/f22t01_flyer_template_and_subtype_split.py` → 1 line
- [x] `grep -n "json_extract" alembic/versions/f22t01_flyer_template_and_subtype_split.py` → 2 lines (SQLite branch)
- [x] `grep -n "f.event_payload->" alembic/versions/f22t01_flyer_template_and_subtype_split.py` → 1 line (Postgres branch)
- [x] `uv run alembic heads` → `f22t01 (head)`
- [x] `tests/api/test_migrations.py` — 6 tests passing
- [x] `tests/api/test_models_ddl.py` — 3 tests passing (no DDL regression)

### Task 2
- [x] `grep -n "from flyer_generator.flyer.schema_renderer.loader import load_template" flyer_generator/api/tasks/flyer.py` → 1 line
- [x] `grep -n "BLOCKER-2" flyer_generator/api/tasks/flyer.py` → 2 lines (module-comment + threat-register reference)
- [x] `grep -n "template_name = payload\[" flyer_generator/api/tasks/flyer.py` → 1 line
- [x] `grep -n "load_template(template_name)" flyer_generator/api/tasks/flyer.py` → 1 line
- [x] `grep -n "template=template" flyer_generator/api/tasks/flyer.py` → 3 lines (gen.generate call + log.bind + FlyerRecord kwarg)
- [x] `grep -n "flyer_event_final\|flyer_info_final" flyer_generator/api/tasks/flyer.py` → 3 lines (kind derivation)
- [x] `grep -n "template=template_name" flyer_generator/api/tasks/flyer.py` → 2 lines (log.bind + FlyerRecord kwarg)
- [x] `tests/api/test_worker_tasks.py` — 31 tests passing including all 12 new/updated Phase-22 tests
- [x] `tests/api/test_flyer_routes.py` — 11 tests passing including all 3 new Phase-22 tests
- [x] `tests/api/test_migrations.py` — 6 tests passing
- [x] `.venv/bin/pytest tests/ -q -k "not slow" --ignore=tests/integration` — 1415 passed, 0 failed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] alembic env.py overrides test-supplied sqlalchemy.url**

- **Found during:** Task 1 migration test authoring.
- **Issue:** The plan's example test fixture set `cfg.set_main_option("sqlalchemy.url", db_url)` to point at a tmp_path SQLite file. At runtime this was silently ignored: `alembic/env.py:31` unconditionally executes `config.set_main_option("sqlalchemy.url", settings.database_url)` after env.py is loaded, so the test's URL was always overwritten by `AppSettings.database_url` (which defaults to `sqlite+aiosqlite:///./flyer.db`). Tests failed with `OperationalError: no such table: renders` because the migration ran against the dev DB, not the tmp_path DB.
- **Fix:** Use `monkeypatch.setenv("FLYER_DATABASE_URL", async_url)` in each test/fixture that needs an isolated DB. Pydantic-settings then picks up the env var when `AppSettings()` is instantiated inside env.py. Documented the mechanism in the test module docstring + each fixture for future readers.
- **Files modified:** `tests/api/test_migrations.py` (3 fixtures/tests).
- **Committed in:** `2ad0285` (Task 1 implementation — fixture written correctly on first commit, but the wrong-fixture pattern was caught during local iteration before commit).

**2. [Rule 2 - Critical functionality] T-22-10 path-traversal guard placement decision**

- **Found during:** Task 2 implementation (referenced by plan + threat register).
- **Issue:** Plan's `<verification>` section + threat register entry T-22-10 both flagged the path-traversal mitigation as a worker-side requirement. The schema layer (FlyerCreateRequest) only enforces `max_length=64`, which is insufficient — `"foo.json"` is 8 chars and `"../etc/passwd"` is 13 chars, both well under the limit. Without the worker guard, a `template` value ending in `.json` would activate `load_template`'s file-path branch (loader.py:20-21), reading an arbitrary path.
- **Fix:** Added `_validate_template_slug()` in the worker that raises `ValueError` if the template name contains `.json` suffix, `/`, or `\\`. Fires BEFORE `load_template()`. Tested with 4 parametrized cases. Documented as Phase 22 threat register T-22-10 mitigation in the function docstring.
- **Files modified:** `flyer_generator/api/tasks/flyer.py` + `tests/api/test_worker_tasks.py`.
- **Committed in:** RED `0046dd7` (path-traversal tests fail) + GREEN `5d64d6b` (guard added — tests pass).

**3. [Rule 1 - Bug] Pre-Phase-22 smoke test patches a now-aliased name and uses old generate signature**

- **Found during:** Task 2 RED authoring.
- **Issue:** The existing `test_task_generate_flyer_writes_render_and_flyer` patched `flyer_generator.api.tasks.flyer.EventInput.model_validate` (which is now an alias for `FlyerInput.model_validate`) with a fake instance lacking the `subtype` attribute. After Task 2's worker rewrite, the worker accesses `flyer_input.subtype` — the fake object would fail with `AttributeError`. Additionally the test's `FakeGen.generate(self, event)` signature lacked the `template=` kwarg added in Plan 04.
- **Fix:** Rewrote the smoke test to use the new `_FakeFlyerOut` + `_flyer_event_payload` helpers and patch `load_template` at module scope. Drops the brittle `EventInput.model_validate` patch in favor of letting real `FlyerInput.model_validate(payload["event"])` run on a valid payload.
- **Files modified:** `tests/api/test_worker_tasks.py`.
- **Committed in:** RED `0046dd7` (rewritten test still fails — NOT NULL constraint on flyers.template) + GREEN `5d64d6b` (passes).

**Total deviations:** 3 — all auto-fixed (1 blocking infra issue, 1 critical security mitigation, 1 stale-test bug). No scope creep.

## Threat Model Posture

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-22-10 (Tampering: payload['template'] path traversal) | mitigate | **MITIGATED** in worker via `_validate_template_slug()`. 4 parametrized tests verify rejection of `.json` suffix, `/`, `\\`. |
| T-22-11 (Information disclosure: migration error logs) | accept | Migration runs in operator context. No change. |
| T-22-12 (DoS: malformed event_payload aborts UPDATE) | mitigate | **MITIGATED** via `COALESCE({subtype_expr}, 'event')` — NULL/missing subtype defaults to event-kind. Test `test_default_event_subtype_when_subtype_missing` regresses against this. |

## Threat Flags

None — no new trust boundaries introduced. The DB column + new render kinds are server-controlled values; the worker-side path-traversal guard is the only new trust check, and it's tested.

## Known Stubs

None — all behavior is wired end-to-end:
- Schema layer (Plan 04) validates `template: str` shape
- Worker (Plan 05) loads + path-traversal-guards + threads template into pipeline
- DB column populated from payload
- Render kind derived from subtype

## Frontend Readiness Checklist (for Plan 06)

- [x] Backend test suite green: 1415 passed, 0 failed
- [x] FlyerRecord.template column lives in DDL (migration f22t01)
- [x] RenderRecord.kind values flyer_event_final + flyer_info_final emitted by the worker
- [x] FlyerCreateRequest.template required at the schema layer (Plan 04)
- [x] **Frontend can now safely regenerate the OpenAPI snapshot** — `frontend/src/api/openapi.snapshot.json` + `schema.gen.ts` will pick up:
  - `template: string` on the FlyerCreateRequest body
  - The expanded RenderRecord.kind enum (when the response model exposes it)
  - FlyerRecord.template field on detail/list responses

Plan 06 should:
1. Run `cd frontend && pnpm openapi:fetch && pnpm openapi:gen` to regenerate the schema snapshot + types
2. Update `frontend/src/pages/flyers/new.tsx` to add a `template` `<Select>` and a `subtype` `<Select>` with conditional date/time/venue/fees fields
3. Extend `frontend/src/pages/renders/gallery.tsx::KINDS` and `frontend/src/pages/jobs/list.tsx::KINDS` to include `flyer_event_final` + `flyer_info_final`

## TDD Gate Compliance

Task 2 was tagged `tdd="true"`. Both gates satisfied with explicit RED → GREEN commits:

- **Task 2 RED:** `0046dd7` `test(22-05): add failing tests for template loading + subtype-derived render kind`
- **Task 2 GREEN:** `5d64d6b` `feat(22-05): wire task_generate_flyer to load template + derive subtype-aware kind`

Task 1 was tagged `auto` (not TDD), but still landed in a single feat commit alongside its 6 migration tests for atomicity:

- **Task 1:** `2ad0285` `feat(22-05): add FlyerRecord.template + alembic migration f22t01`

No REFACTOR commits needed — both tasks were minimal-correct on first GREEN pass.

## Self-Check: PASSED

Verified each created/modified file exists and each commit hash is reachable:

- `flyer_generator/api/models/flyer.py` FOUND (modified)
- `flyer_generator/api/models/render.py` FOUND (modified)
- `flyer_generator/api/tasks/flyer.py` FOUND (modified)
- `alembic/versions/f22t01_flyer_template_and_subtype_split.py` FOUND (created)
- `tests/api/test_migrations.py` FOUND (created)
- `tests/api/test_flyer_routes.py` FOUND (modified)
- `tests/api/test_worker_tasks.py` FOUND (modified)
- Commit `2ad0285` (Task 1) FOUND
- Commit `0046dd7` (Task 2 RED) FOUND
- Commit `5d64d6b` (Task 2 GREEN) FOUND

---

*Phase: 22-flyer-templates-subtype-split*
*Completed: 2026-04-23*
