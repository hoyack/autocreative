"""Phase 24-03 Task 2: PosterRecord DDL smoke + parallel-id contract.

Verifies the ORM shape (columns, primary key, parallel-id rule: NO default
factory on `id` per T-24-11), JobKind.POSTER enum value, and round-trip
insertion via in-memory SQLite.
"""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from flyer_generator.api.models import Base, JobKind, PosterRecord


def test_poster_record_subclasses_base_and_tablename() -> None:
    assert issubclass(PosterRecord, Base)
    assert PosterRecord.__tablename__ == "posters"


def test_poster_record_columns_match_spec() -> None:
    """Exact 7-column set per <interfaces>: id, template, size,
    brand_kit_slug, content_payload, render_id, created_at."""
    expected = {
        "id",
        "template",
        "size",
        "brand_kit_slug",
        "content_payload",
        "render_id",
        "created_at",
    }
    assert set(PosterRecord.__table__.columns.keys()) == expected


def test_poster_record_primary_key_is_id_str26() -> None:
    pk_cols = list(PosterRecord.__table__.primary_key.columns.keys())
    assert pk_cols == ["id"]
    id_col = PosterRecord.__table__.columns["id"]
    assert id_col.type.length == 26


def test_poster_record_id_has_no_default_factory() -> None:
    """Parallel-id (PO-XX): id MUST be supplied by the route handler from
    JobRecord.id at enqueue time. No `default=new_ulid` is allowed because
    that would silently mint a fresh id and break the id == job_id invariant.

    Regression guard for T-24-11.
    """
    id_col = PosterRecord.__table__.columns["id"]
    assert id_col.default is None, (
        "PosterRecord.id must NOT have a default factory — parallel-id pattern "
        "requires explicit assignment from JobRecord.id"
    )
    assert id_col.server_default is None


def test_poster_record_size_column_is_string_8() -> None:
    """size column stores the literal (e.g. '18x24'); String(8) is wide
    enough for all 3 locked values."""
    size_col = PosterRecord.__table__.columns["size"]
    assert size_col.type.length == 8
    assert size_col.nullable is False


def test_poster_record_template_not_null() -> None:
    template_col = PosterRecord.__table__.columns["template"]
    assert template_col.type.length == 64
    assert template_col.nullable is False


def test_poster_record_content_payload_not_null() -> None:
    content_col = PosterRecord.__table__.columns["content_payload"]
    assert content_col.nullable is False


def test_poster_record_creates_in_sqlite() -> None:
    """DDL smoke — table builds cleanly on a fresh in-memory SQLite engine."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    assert "posters" in set(insp.get_table_names())


def test_jobkind_poster_value() -> None:
    """PO-01: JobKind gains POSTER = 'poster'."""
    assert JobKind.POSTER == "poster"
    assert JobKind.POSTER.value == "poster"


def test_poster_record_can_be_inserted_with_explicit_id() -> None:
    """Parallel-id round-trip: insert with id set explicitly (no auto-default)."""
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    job_id = "01H" + "Z" * 23  # 26 chars
    with Session(engine) as s:
        rec = PosterRecord(
            id=job_id,
            template="editorial_grand",
            size="18x24",
            content_payload={},
        )
        s.add(rec)
        s.commit()
        fetched = s.get(PosterRecord, job_id)
        assert fetched is not None
        assert fetched.id == job_id
        assert fetched.template == "editorial_grand"
        assert fetched.size == "18x24"


def test_poster_record_render_relationship_present() -> None:
    """Single render_id FK + relationship — no front/back/pdf split."""
    # Confirm the render relationship is configured on the mapper.
    rel_keys = {r.key for r in PosterRecord.__mapper__.relationships}
    assert "render" in rel_keys
    # And not the postcard-style triple.
    assert "render_front" not in rel_keys
    assert "render_back" not in rel_keys
    assert "render_pdf" not in rel_keys
