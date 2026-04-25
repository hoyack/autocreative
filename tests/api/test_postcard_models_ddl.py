"""Phase 23-02 Task 2: PostcardRecord DDL smoke + parallel-id contract.

Verifies the ORM shape (columns, primary key, parallel-id rule: NO default
factory on `id`).
"""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from flyer_generator.api.models import Base, JobKind, PostcardRecord


def test_postcard_record_subclasses_base() -> None:
    assert issubclass(PostcardRecord, Base)
    assert PostcardRecord.__tablename__ == "postcards"


def test_postcard_record_columns_match_spec() -> None:
    expected = {
        "id",
        "template",
        "brand_kit_slug",
        "content_payload",
        "render_front_id",
        "render_back_id",
        "render_pdf_id",
        "created_at",
    }
    assert set(PostcardRecord.__table__.columns.keys()) == expected


def test_postcard_record_primary_key_is_id_str26() -> None:
    pk_cols = list(PostcardRecord.__table__.primary_key.columns.keys())
    assert pk_cols == ["id"]
    id_col = PostcardRecord.__table__.columns["id"]
    assert id_col.type.length == 26


def test_postcard_record_id_has_no_default_factory() -> None:
    """Parallel-id (PC-02): id MUST be supplied by the route handler from
    JobRecord.id at enqueue time. No `default=new_ulid` is allowed because
    that would silently mint a fresh id and break the id == job_id invariant.
    """
    id_col = PostcardRecord.__table__.columns["id"]
    assert id_col.default is None, (
        "PostcardRecord.id must NOT have a default factory — parallel-id pattern "
        "requires explicit assignment from JobRecord.id"
    )
    assert id_col.server_default is None


def test_postcard_record_creates_in_sqlite() -> None:
    """DDL smoke — table builds cleanly on a fresh in-memory SQLite engine."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    assert "postcards" in set(insp.get_table_names())


def test_jobkind_postcard_value() -> None:
    """PC-06: JobKind gains POSTCARD = 'postcard'."""
    assert JobKind.POSTCARD == "postcard"
    assert JobKind.POSTCARD.value == "postcard"


def test_postcard_record_can_be_inserted_with_explicit_id() -> None:
    """Parallel-id round-trip: insert with id set explicitly (no auto-default)."""
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    job_id = "01H" + "Y" * 23  # 26 chars
    with Session(engine) as s:
        rec = PostcardRecord(id=job_id, template="classic_portrait", content_payload={})
        s.add(rec)
        s.commit()
        fetched = s.get(PostcardRecord, job_id)
        assert fetched is not None
        assert fetched.id == job_id
        assert fetched.template == "classic_portrait"
