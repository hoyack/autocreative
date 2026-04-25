"""Alembic migration tests — Phase 24-03 f24t01 poster primitive.

Covers:
- Upgrade creates `posters` table with all 7 columns
- 2 indexes (brand_kit_slug + render_id) present
- JobKind.POSTER round-trips through SQLite (job row insert + read-back)
- Downgrade drops the `posters` table cleanly
- alembic head pointer is f24t01 after upgrade

NOTE: alembic/env.py:31 always overrides `sqlalchemy.url` with
`AppSettings().database_url` at runtime. Use
`monkeypatch.setenv("FLYER_DATABASE_URL", ...)` to point alembic at a
tmp_path SQLite DB (mirrors test_migrations_postcard.py pattern from f23t01).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parents[2] / "alembic"),
    )
    return cfg


@pytest.fixture()
def upgraded_engine(tmp_path, monkeypatch):
    """Apply migrations through f24t01 against a fresh tmp_path sqlite DB."""
    db = tmp_path / "test.db"
    async_url = f"sqlite+aiosqlite:///{db}"
    sync_url = f"sqlite:///{db}"
    monkeypatch.setenv("FLYER_DATABASE_URL", async_url)
    cfg = _alembic_cfg(async_url)
    command.upgrade(cfg, "f24t01")
    engine = create_engine(sync_url)
    yield engine, cfg, async_url
    engine.dispose()


def test_posters_table_created(upgraded_engine):
    engine, _cfg, _url = upgraded_engine
    insp = inspect(engine)
    assert "posters" in set(insp.get_table_names())


def test_posters_columns_present(upgraded_engine):
    engine, _cfg, _url = upgraded_engine
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("posters")}
    expected = {
        "id",
        "template",
        "size",
        "brand_kit_slug",
        "content_payload",
        "render_id",
        "created_at",
    }
    assert cols == expected


def test_posters_indexes_present(upgraded_engine):
    """2 indexes covering brand_kit_slug + render_id."""
    engine, _cfg, _url = upgraded_engine
    insp = inspect(engine)
    idx_names = {i["name"] for i in insp.get_indexes("posters")}
    assert "ix_posters_brand_kit_slug" in idx_names
    assert "ix_posters_render_id" in idx_names


def test_jobkind_poster_round_trips(upgraded_engine):
    """JobRecord with kind=JobKind.POSTER inserts + reads back via SQLAlchemy."""
    from sqlalchemy.orm import Session

    from flyer_generator.api.models import JobKind, JobRecord, JobStatus

    engine, _cfg, _url = upgraded_engine
    job_id = "01H" + "P" * 23
    with Session(engine) as s:
        s.add(
            JobRecord(
                id=job_id,
                kind=JobKind.POSTER,
                status=JobStatus.QUEUED,
                input_payload={},
            )
        )
        s.commit()
        fetched = s.get(JobRecord, job_id)
        assert fetched is not None
        assert fetched.kind == JobKind.POSTER


def test_downgrade_drops_posters(tmp_path, monkeypatch):
    """alembic downgrade -1 from f24t01 → f23t01 drops `posters` table."""
    db = tmp_path / "dg.db"
    async_url = f"sqlite+aiosqlite:///{db}"
    sync_url = f"sqlite:///{db}"
    monkeypatch.setenv("FLYER_DATABASE_URL", async_url)
    cfg = _alembic_cfg(async_url)
    command.upgrade(cfg, "f24t01")
    engine = create_engine(sync_url)
    insp = inspect(engine)
    assert "posters" in set(insp.get_table_names())
    engine.dispose()
    command.downgrade(cfg, "-1")
    engine2 = create_engine(sync_url)
    insp2 = inspect(engine2)
    assert "posters" not in set(insp2.get_table_names())
    engine2.dispose()


def test_alembic_head_is_f24t01(upgraded_engine):
    """After upgrade, alembic_version row is f24t01."""
    engine, _cfg, _url = upgraded_engine
    with engine.begin() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        assert row is not None
        assert row[0] == "f24t01"
