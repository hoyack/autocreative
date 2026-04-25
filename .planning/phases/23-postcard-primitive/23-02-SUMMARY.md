---
phase: 23-postcard-primitive
plan: 02
subsystem: api-schemas + db-models + alembic-migration
tags: [pydantic-v2, sqlalchemy, alembic, parallel-id, jobkind-enum, tdd, pc-01, pc-02, pc-03, pc-06]

# Dependency graph
requires: []
provides:
  - flyer_generator.api.schemas.postcards.PostcardCreateRequest (PC-01)
  - flyer_generator.api.schemas.postcards.AddressBlock (PC-03)
  - flyer_generator.api.schemas.postcards.PostcardDetail (3-artifact response)
  - flyer_generator.api.models.postcard.PostcardRecord (PC-02 parallel-id, NO default factory on id)
  - flyer_generator.api.models.JobKind.POSTCARD = "postcard" (PC-06)
  - alembic revision f23t01 (down_revision f22t01) — postcards table + jobkind enum extension
affects:
  - 23-03 (renderer + templates) — content_payload shape now locked
  - 23-04 (worker task_generate_postcard) — JobKind.POSTCARD + PostcardRecord(id=job_id) ready for the worker
  - 23-05 (routes POST/GET /api/v1/postcards) — schemas can now be imported into the route module
  - 23-06 (frontend) — OpenAPI snapshot can be regenerated once routes land in 23-05

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pydantic v2 Field(min_length, max_length) + ConfigDict(extra='forbid') validators (mirrors brochure schema)"
    - "Slug regex validator ^[a-z0-9][a-z0-9-]*$ (verbatim from brochure schema)"
    - "Parallel-id ORM contract: id: Mapped[str] = mapped_column(String(26), primary_key=True) with NO default — enforces explicit id == job_id assignment"
    - "Backend-aware idempotent enum extension: postgres ALTER TYPE jobkind ADD VALUE IF NOT EXISTS 'POSTCARD' inside op.get_context().autocommit_block(); SQLite no-op (the initial schema does not emit a CHECK constraint, verified empirically)"
    - "Alembic batch_alter_table for index create/drop (SQLite-safe; mirrors brochures index pattern in 0001_initial_schema)"

key-files:
  created:
    - flyer_generator/api/schemas/postcards.py  (74 lines — 3 Pydantic models)
    - flyer_generator/api/models/postcard.py  (56 lines — PostcardRecord ORM)
    - alembic/versions/f23t01_postcard_primitive.py  (95 lines — migration)
    - tests/api/test_postcard_schemas.py  (219 lines — 16 tests)
    - tests/api/test_postcard_models_ddl.py  (84 lines — 7 tests)
    - tests/api/test_migrations_postcard.py  (127 lines — 6 tests)
  modified:
    - flyer_generator/api/schemas/__init__.py  (added 3 schema imports + sorted __all__)
    - flyer_generator/api/models/__init__.py  (added PostcardRecord import + sorted __all__)
    - flyer_generator/api/models/job.py  (added JobKind.POSTCARD = "postcard")

key-decisions:
  - "PostcardRecord.id has NO default factory (no `default=new_ulid`). The parallel-id pattern (PC-02) requires that id == JobRecord.id be set explicitly by the route handler from the JobRecord enqueue path. An auto-default would silently mint a fresh ULID and break the FE's GET /postcards/{job_id} navigation; a DDL test (test_postcard_record_id_has_no_default_factory) regresses against this rule."
  - "AddressBlock is a separate Pydantic model (not a TypedDict) so the validators (min_length=1 / max_length=120 + extra='forbid') run on dict payloads passed through PostcardCreateRequest.address_block."
  - "PostcardCreateRequest flattens its body — no `content` sub-model wrapper like BrochureCreateRequest. Postcards have only 6 top-level fields (headline + body + image_hint + brand_kit_slug + template + address_block); a wrapper would add ceremony without value. PC-01 spec confirms the flat shape."
  - "Migration is dialect-aware. Postgres uses `ALTER TYPE jobkind ADD VALUE IF NOT EXISTS 'POSTCARD'` inside `autocommit_block()` (older Postgres rejects ALTER TYPE inside an open txn). SQLite gets a no-op for the enum extension because the existing schema (verified empirically) does NOT emit a CHECK constraint on jobs.kind, so JobRecord(kind=JobKind.POSTCARD, ...) inserts cleanly without DDL changes."
  - "Downgrade leaves JobKind.POSTCARD in the postgres enum on rollback. Postgres cannot drop a single enum value cleanly without a full type rebuild that would block on dependent jobs.kind values; same disposition as Phase 22 T-22-11."
  - "13 failing tests committed BEFORE implementation (RED gates: schemas + ORM/migration). GREEN commits delivered minimal code that makes them all pass plus 16 additional schema tests (29 total). No REFACTOR needed."
  - "Used `monkeypatch.setenv('FLYER_DATABASE_URL', ...)` for migration tests — alembic/env.py:31 unconditionally overrides cfg.set_main_option('sqlalchemy.url', ...) with AppSettings.database_url, so env-var override is the only mechanism that works (mirrors Phase 22-05 SUMMARY decision)."

requirements-completed: [PC-01, PC-02, PC-03, PC-06]

# Metrics
duration: ~5min
completed: 2026-04-23
---

# Phase 23 Plan 02: Postcard API Schemas + ORM Model + Alembic Migration Summary

Lands the API/DB layer for the postcard primitive: 3 Pydantic schemas (`PostcardCreateRequest`, `AddressBlock`, `PostcardDetail`), the `PostcardRecord` SQLAlchemy ORM model with the parallel-id contract, the `JobKind.POSTCARD` enum value, and alembic migration `f23t01` that creates the `postcards` table and extends the `jobkind` enum on Postgres. After this plan: `from flyer_generator.api.schemas import PostcardCreateRequest, PostcardDetail, AddressBlock` succeeds; `from flyer_generator.api.models import PostcardRecord` succeeds; `JobKind.POSTCARD == "postcard"`; `alembic upgrade head` creates the `postcards` table; `alembic downgrade -1` drops it.

## What Was Built

### Task 1 — Pydantic schemas + barrel update (RED `11a58fe`, GREEN `e5322fc`)

**`flyer_generator/api/schemas/postcards.py`** — 3 new Pydantic v2 models:

```python
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class AddressBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_name: str = Field(min_length=1, max_length=120)
    street: str = Field(min_length=1, max_length=120)
    city_state_zip: str = Field(min_length=1, max_length=120)


class PostcardCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    headline: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    image_hint: str | None = Field(default=None, max_length=500)
    brand_kit_slug: str | None = Field(default=None, max_length=64)
    template: str = Field(min_length=1, max_length=64)
    address_block: AddressBlock | None = None

    @field_validator("brand_kit_slug")
    @classmethod
    def _validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SLUG_RE.match(v):
            raise ValueError("brand_kit_slug must match ^[a-z0-9][a-z0-9-]*$")
        return v


class PostcardDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    template: str
    brand_kit_slug: str | None = None
    front_render_url: str | None = None
    back_render_url: str | None = None
    pdf_render_url: str | None = None
    created_at: datetime
```

Barrel `flyer_generator/api/schemas/__init__.py` now exports `AddressBlock`, `PostcardCreateRequest`, `PostcardDetail` in alphabetical `__all__`.

**`tests/api/test_postcard_schemas.py`** — 16 tests:

1–3. `PostcardCreateRequest` minimal payload + empty/oversize template (4 cases)
4–5. headline/body length boundaries (200 / 2000)
6–7. brand_kit_slug regex (rejects `not_a_valid_slug!`, `UpperSlug`; accepts `acme-co`)
8. `extra="forbid"` rejects unknown keys
9–10. `address_block` accepts dict payload + `None` round-trip
11–12. `AddressBlock` empty + length-121 rejection (each of 3 fields)
13. `AddressBlock` `extra="forbid"`
14–15. `PostcardDetail` accepts URLs + accepts None
16. Barrel re-export round-trip (`from flyer_generator.api.schemas import AddressBlock, PostcardCreateRequest, PostcardDetail`)

### Task 2 — PostcardRecord ORM + JobKind.POSTCARD + alembic f23t01 (RED `0ea7633`, GREEN `a37c71a`)

**`flyer_generator/api/models/postcard.py`** — mirrors `BrochureRecord` but drops `title` (postcards embed the headline in `content_payload`) and removes the auto-default on `id`:

```python
class PostcardRecord(Base):
    __tablename__ = "postcards"

    # Parallel-id (PC-02): NO default=new_ulid; route handler MUST set id from JobRecord.id.
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    template: Mapped[str] = mapped_column(String(64), nullable=False)
    brand_kit_slug: Mapped[str | None] = mapped_column(
        ForeignKey("brand_kits.slug", ondelete="SET NULL"), nullable=True, index=True
    )
    content_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    render_front_id: Mapped[str | None] = mapped_column(
        ForeignKey("renders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    render_back_id: Mapped[str | None] = mapped_column(
        ForeignKey("renders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    render_pdf_id: Mapped[str | None] = mapped_column(
        ForeignKey("renders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    render_front: Mapped[RenderRecord | None] = relationship(
        "RenderRecord", foreign_keys=[render_front_id], lazy="joined"
    )
    render_back: Mapped[RenderRecord | None] = relationship(
        "RenderRecord", foreign_keys=[render_back_id], lazy="joined"
    )
    render_pdf: Mapped[RenderRecord | None] = relationship(
        "RenderRecord", foreign_keys=[render_pdf_id], lazy="joined"
    )
```

**`flyer_generator/api/models/job.py`** — `JobKind` gains `POSTCARD = "postcard"` between BROCHURE and SOCIAL_POST.

**`flyer_generator/api/models/__init__.py`** — adds `from flyer_generator.api.models.postcard import PostcardRecord` + `"PostcardRecord"` in sorted `__all__`.

**`alembic/versions/f23t01_postcard_primitive.py`** — `down_revision="f22t01"`. Final body:

```python
def upgrade() -> None:
    op.create_table(
        "postcards",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("template", sa.String(length=64), nullable=False),
        sa.Column("brand_kit_slug", sa.String(length=64), nullable=True),
        sa.Column("content_payload", sa.JSON(), nullable=False),
        sa.Column("render_front_id", sa.String(length=26), nullable=True),
        sa.Column("render_back_id", sa.String(length=26), nullable=True),
        sa.Column("render_pdf_id", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["brand_kit_slug"], ["brand_kits.slug"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["render_front_id"], ["renders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["render_back_id"], ["renders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["render_pdf_id"], ["renders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("postcards", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_postcards_brand_kit_slug"), ["brand_kit_slug"], unique=False)
        batch_op.create_index(batch_op.f("ix_postcards_render_front_id"), ["render_front_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_postcards_render_back_id"), ["render_back_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_postcards_render_pdf_id"), ["render_pdf_id"], unique=False)

    bind = op.get_bind()
    if bind.dialect.name in ("postgresql", "postgres"):
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE jobkind ADD VALUE IF NOT EXISTS 'POSTCARD'")
    # SQLite: no-op (initial schema emits no CHECK constraint on jobs.kind)


def downgrade() -> None:
    with op.batch_alter_table("postcards", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_postcards_render_pdf_id"))
        batch_op.drop_index(batch_op.f("ix_postcards_render_back_id"))
        batch_op.drop_index(batch_op.f("ix_postcards_render_front_id"))
        batch_op.drop_index(batch_op.f("ix_postcards_brand_kit_slug"))
    op.drop_table("postcards")
    # Postgres: leave JobKind.POSTCARD in the enum (cannot drop a single value cleanly).
```

**`tests/api/test_postcard_models_ddl.py`** — 7 tests:

1. `test_postcard_record_subclasses_base` — Base subclass + tablename
2. `test_postcard_record_columns_match_spec` — exact column set match (8 names)
3. `test_postcard_record_primary_key_is_id_str26` — PK == id, length 26
4. `test_postcard_record_id_has_no_default_factory` — explicit guard against `default=new_ulid` regression
5. `test_postcard_record_creates_in_sqlite` — DDL smoke
6. `test_jobkind_postcard_value` — `JobKind.POSTCARD == "postcard"`
7. `test_postcard_record_can_be_inserted_with_explicit_id` — parallel-id round-trip

**`tests/api/test_migrations_postcard.py`** — 6 tests:

1. `test_postcards_table_created` — table exists post-upgrade
2. `test_postcards_columns_present` — all 8 columns present
3. `test_postcards_indexes_present` — 4 indexes (brand_kit_slug + 3 render FKs)
4. `test_jobkind_postcard_round_trips` — `JobRecord(kind=JobKind.POSTCARD, ...)` inserts + reads back
5. `test_downgrade_drops_postcards` — `alembic downgrade -1` removes the table
6. `test_alembic_head_is_f23t01` — `alembic_version` row pinned

## Verification Run Log

```bash
$ .venv/bin/pytest tests/api/test_postcard_schemas.py -v
# -> 16 passed in 0.04s

$ .venv/bin/pytest tests/api/test_postcard_models_ddl.py tests/api/test_migrations_postcard.py -v
# -> 13 passed in 2.11s

$ .venv/bin/pytest tests/api/ -q
# -> 255 passed, 1 warning in 11.61s (no regressions vs. f22t01 baseline)

$ .venv/bin/alembic heads
# -> f23t01 (head)

$ .venv/bin/python -c "
from flyer_generator.api.schemas import PostcardCreateRequest, PostcardDetail, AddressBlock
from flyer_generator.api.models import PostcardRecord, JobKind
assert JobKind.POSTCARD.value == 'postcard'
print('OK')
"
# -> OK
```

## Acceptance Criteria — All Pass

### Task 1
- [x] `flyer_generator/api/schemas/postcards.py` exists
- [x] `class PostcardCreateRequest` defined (1 occurrence)
- [x] `class AddressBlock` defined (1 occurrence)
- [x] `class PostcardDetail` defined (1 occurrence)
- [x] `address_block: AddressBlock | None` field present
- [x] `extra="forbid"` count >= 3 (one per BaseModel)
- [x] Barrel `__init__.py` references `AddressBlock` >= 2 times (import + __all__)
- [x] All 16 schema tests pass

### Task 2
- [x] `flyer_generator/api/models/postcard.py` exists with `class PostcardRecord(Base)`
- [x] `POSTCARD = "postcard"` in `flyer_generator/api/models/job.py`
- [x] PK line matches `id: Mapped[str] = mapped_column(String(26), primary_key=True)` exactly (NO `default=new_ulid` — verified by DDL test)
- [x] 3 render FK columns + 3 relationships (6 references)
- [x] Barrel `__init__.py` references `PostcardRecord` >= 2 times
- [x] `alembic/versions/f23t01_postcard_primitive.py` exists with `down_revision="f22t01"`
- [x] Postgres enum extension `ALTER TYPE jobkind ADD VALUE IF NOT EXISTS 'POSTCARD'` present
- [x] `.venv/bin/alembic heads` reports `f23t01 (head)`
- [x] All 13 model/migration tests pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Decision verification] SQLite jobkind CHECK-constraint reality check**

- **Found during:** Task 2 implementation (before writing the migration body).
- **Issue:** Plan comments suggested SQLite "stores SAEnum as plain VARCHAR with a CHECK constraint that SQLAlchemy regenerates on subsequent migrations". I verified this empirically against the actual on-disk schema produced by `alembic upgrade head` after f22t01:
  ```sql
  CREATE TABLE jobs (
      id VARCHAR(26) NOT NULL,
      kind VARCHAR(15) NOT NULL,  -- no CHECK constraint
      ...
      PRIMARY KEY (id)
  )
  ```
  No CHECK constraint exists on `jobs.kind`. The current `JobRecord.kind` definition uses `SAEnum(JobKind, name="jobkind")` without `create_constraint=True`, and the initial migration (0001_initial_schema.py:35) uses `sa.Enum(... name='jobkind')` — neither emits a CHECK on SQLite.
- **Fix:** Migration leaves SQLite alone (no DDL needed); the Python-side `JobKind.POSTCARD` extension is sufficient. Test `test_jobkind_postcard_round_trips` regresses against this conclusion (inserts a `JobRecord(kind=JobKind.POSTCARD, ...)` against a fresh post-f23t01 SQLite DB and reads back). No code change vs. plan; only the comment in the migration was clarified ("no CHECK constraint emitted by the initial f22t01 / 0001 schema").
- **Files affected:** `alembic/versions/f23t01_postcard_primitive.py` (clarifying comment).
- **Committed in:** `a37c71a` (Task 2 GREEN).

**2. [Rule 2 - Critical correctness] Added regression test for "no default factory on PostcardRecord.id"**

- **Found during:** Task 2 RED authoring.
- **Issue:** The parallel-id contract (PC-02) is a non-obvious invariant. Without an explicit DDL-level guard, a future refactor could silently re-add `default=new_ulid` (mirroring `BrochureRecord.id` which DOES have the default), breaking the FE's `GET /postcards/{job_id}` navigation. The plan's `<acceptance_criteria>` mentioned the rule but did not test it.
- **Fix:** Added `test_postcard_record_id_has_no_default_factory` in `tests/api/test_postcard_models_ddl.py` that asserts both `id_col.default is None` and `id_col.server_default is None`. This locks the parallel-id rule into the test suite at the DDL level.
- **Files affected:** `tests/api/test_postcard_models_ddl.py`.
- **Committed in:** `0ea7633` (Task 2 RED).

**Total deviations:** 2 — one verification-driven decision tightening (SQLite CHECK-constraint reality), one critical regression-test addition (parallel-id DDL guard). No scope creep.

## Threat Model Posture

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-23-04 (Tampering: PostcardCreateRequest unbounded fields) | mitigate | **MITIGATED** — every str field has `max_length` (200/2000/500/64/120). `extra="forbid"` rejects extra keys. 16 schema tests cover boundaries. |
| T-23-05 (Tampering: brand_kit_slug regex bypass) | mitigate | **MITIGATED** — `_SLUG_RE = ^[a-z0-9][a-z0-9-]*$` validator. Tests reject `not_a_valid_slug!` and `UpperSlug`; accept `acme-co`. |
| T-23-06 (Tampering: template path-traversal) | accept (deferred to Plan 23-04 worker) | Worker-side `_validate_template_slug` is owed by 23-04, mirroring Phase 22 T-22-10 placement. Schema-level only enforces `max_length=64` here. |
| T-23-07 (DoS: ALTER TYPE blocks) | mitigate | **MITIGATED** — postgres enum extension wrapped in `op.get_context().autocommit_block()` with `IF NOT EXISTS` for idempotency. |
| T-23-08 (Information disclosure: migration error logs) | accept | Operator-context only, same disposition as Phase 22 T-22-11. |

## Threat Flags

None — no new trust boundaries introduced. The 3 schemas live behind the existing FastAPI routing (which lands in 23-05), and the migration's only new surface is a postgres-side `ALTER TYPE` that was already implicitly part of Phase 20's `JobKind` enum.

## Known Stubs

None — every artifact this plan claims to provide is wired and tested:
- 3 Pydantic schemas: validated, barrel-exported, regression-tested
- PostcardRecord ORM: DDL-correct, parallel-id-locked, can be inserted + queried
- JobKind.POSTCARD: round-trips through SQLite (postgres parity covered by the explicit `ALTER TYPE` in the migration)
- Alembic f23t01: upgrade creates the table + indexes + extends the enum; downgrade reverses cleanly

The next plan (23-03) builds on `content_payload` shape and PC-04 templates; the plan after (23-04) wires the worker that finally writes `PostcardRecord(id=job_id, ...)`. Both have unblocked deps from this plan.

## TDD Gate Compliance

Both Task 1 and Task 2 were tagged `tdd="true"`. RED → GREEN gates satisfied with explicit commits:

- **Task 1 RED:** `11a58fe` `test(23-02): add failing tests for postcard schemas (PostcardCreateRequest + AddressBlock + PostcardDetail)`
- **Task 1 GREEN:** `e5322fc` `feat(23-02): add PostcardCreateRequest + AddressBlock + PostcardDetail schemas (PC-01, PC-03)`
- **Task 2 RED:** `0ea7633` `test(23-02): add failing tests for PostcardRecord ORM + alembic f23t01`
- **Task 2 GREEN:** `a37c71a` `feat(23-02): add PostcardRecord ORM + JobKind.POSTCARD + alembic f23t01 (PC-02, PC-06)`

No REFACTOR commits needed — both GREEN passes were minimal-correct on first try.

## Self-Check: PASSED

Verified each created/modified file exists and each commit hash is reachable:

- `flyer_generator/api/schemas/postcards.py` FOUND (created)
- `flyer_generator/api/schemas/__init__.py` FOUND (modified)
- `flyer_generator/api/models/postcard.py` FOUND (created)
- `flyer_generator/api/models/__init__.py` FOUND (modified)
- `flyer_generator/api/models/job.py` FOUND (modified — POSTCARD enum value)
- `alembic/versions/f23t01_postcard_primitive.py` FOUND (created)
- `tests/api/test_postcard_schemas.py` FOUND (created — 16 tests)
- `tests/api/test_postcard_models_ddl.py` FOUND (created — 7 tests)
- `tests/api/test_migrations_postcard.py` FOUND (created — 6 tests)
- Commit `11a58fe` (Task 1 RED) FOUND
- Commit `e5322fc` (Task 1 GREEN) FOUND
- Commit `0ea7633` (Task 2 RED) FOUND
- Commit `a37c71a` (Task 2 GREEN) FOUND

29 tests across the 3 new test files green; 255 tests/api tests green (no regressions vs. f22t01 baseline). `alembic heads` reports `f23t01 (head)`. Plan-level holistic import smoke `from flyer_generator.api.schemas import PostcardCreateRequest, PostcardDetail, AddressBlock; from flyer_generator.api.models import PostcardRecord, JobKind; assert JobKind.POSTCARD.value == 'postcard'` returns OK.

---

*Phase: 23-postcard-primitive*
*Completed: 2026-04-23*
