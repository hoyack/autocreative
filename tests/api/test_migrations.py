"""Alembic migration tests — Phase 22 FT-06 template + subtype-split migration.

Covers:
- Upgrade adds flyers.template column with server_default backfill
- Upgrade rewrites renders.kind='flyer_final' to subtype-derived kinds
- Migration is idempotent (re-running has no effect)
- Downgrade reverses cleanly

NOTE: alembic/env.py:31 always overrides ``sqlalchemy.url`` with
``AppSettings().database_url`` at runtime. The ONLY reliable way to point
alembic at a tmp_path SQLite DB is to set ``FLYER_DATABASE_URL`` in the
environment (consumed by AppSettings). We do that via monkeypatch in each
fixture/test that needs an isolated DB.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parents[2] / "alembic"),
    )
    return cfg


@pytest.fixture()
def migrated_engine(tmp_path, monkeypatch):
    """Build a sqlite DB at down_revision with seed flyer_final rows,
    then apply f22t01 and yield the engine."""
    db = tmp_path / "test.db"
    # Async URL for alembic env.py (uses aiosqlite). Sync URL for the
    # synchronous create_engine() we use to seed + assert.
    async_url = f"sqlite+aiosqlite:///{db}"
    sync_url = f"sqlite:///{db}"
    # alembic/env.py reads AppSettings().database_url on every invocation —
    # override it via env var (FLYER_ prefix per pydantic-settings config).
    monkeypatch.setenv("FLYER_DATABASE_URL", async_url)
    cfg = _alembic_cfg(async_url)
    # Upgrade to just BEFORE this migration (run up to down_revision).
    command.upgrade(cfg, "2f5971e114b3")
    engine = create_engine(sync_url)

    # Seed legacy flyer_final rows that should get rewritten.
    with engine.begin() as conn:
        # Two render rows pre-Phase-22 (kind='flyer_final')
        conn.execute(text(
            "INSERT INTO renders (id, kind, file_path, created_at) "
            "VALUES ('R_EVENT00000000000000000', 'flyer_final', '/tmp/e.png', '2026-04-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO renders (id, kind, file_path, created_at) "
            "VALUES ('R_INFO0000000000000000000', 'flyer_final', '/tmp/i.png', '2026-04-01T00:00:00')"
        ))
        # Seed two flyer rows pointing at those renders.
        # event_payload nests {"event": {... "subtype": "event"|"info"}}
        conn.execute(text(
            "INSERT INTO flyers (id, title, preset, event_payload, render_id, created_at) "
            "VALUES ('F_EVENT0000000000000000000', 'Gala', 'photorealistic', "
            "'{\"event\": {\"title\":\"Gala\",\"subtype\":\"event\"}}', "
            "'R_EVENT00000000000000000', '2026-04-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO flyers (id, title, preset, event_payload, render_id, created_at) "
            "VALUES ('F_INFO00000000000000000000', 'Notice', 'photorealistic', "
            "'{\"event\": {\"title\":\"Notice\",\"subtype\":\"info\"}}', "
            "'R_INFO0000000000000000000', '2026-04-01T00:00:00')"
        ))

    # Now apply the Phase-22 migration.
    command.upgrade(cfg, "f22t01")
    yield engine
    engine.dispose()


def test_template_column_added(migrated_engine):
    """flyers.template exists and existing rows backfill to 'editorial_classic'."""
    with migrated_engine.begin() as conn:
        row = conn.execute(text(
            "SELECT template FROM flyers WHERE id='F_EVENT0000000000000000000'"
        )).fetchone()
        assert row is not None
        assert row[0] == "editorial_classic"  # server_default backfill


def test_render_kind_rewritten_event(migrated_engine):
    """Rows whose flyer.event_payload.event.subtype='event' become flyer_event_final."""
    with migrated_engine.begin() as conn:
        row = conn.execute(text(
            "SELECT kind FROM renders WHERE id='R_EVENT00000000000000000'"
        )).fetchone()
        assert row[0] == "flyer_event_final"


def test_render_kind_rewritten_info(migrated_engine):
    """Rows whose flyer.event_payload.event.subtype='info' become flyer_info_final."""
    with migrated_engine.begin() as conn:
        row = conn.execute(text(
            "SELECT kind FROM renders WHERE id='R_INFO0000000000000000000'"
        )).fetchone()
        assert row[0] == "flyer_info_final"


def test_migration_idempotent(migrated_engine):
    """Re-running the UPDATE finds no flyer_final rows; no kind changes."""
    with migrated_engine.begin() as conn:
        before = conn.execute(text(
            "SELECT id, kind FROM renders ORDER BY id"
        )).fetchall()
    # Simulate re-running the migration's UPDATE; WHERE kind='flyer_final'
    # filters out already-migrated rows, so this is a no-op.
    with migrated_engine.begin() as conn:
        conn.execute(text(
            "UPDATE renders SET kind = 'flyer_event_final' WHERE kind = 'flyer_final'"
        ))
    with migrated_engine.begin() as conn:
        after = conn.execute(text(
            "SELECT id, kind FROM renders ORDER BY id"
        )).fetchall()
    assert before == after


def test_default_event_subtype_when_subtype_missing(tmp_path, monkeypatch):
    """COALESCE handles rows with missing subtype → defaults to event kind."""
    db = tmp_path / "noxtype.db"
    async_url = f"sqlite+aiosqlite:///{db}"
    sync_url = f"sqlite:///{db}"
    monkeypatch.setenv("FLYER_DATABASE_URL", async_url)
    cfg = _alembic_cfg(async_url)
    command.upgrade(cfg, "2f5971e114b3")
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        # No subtype in event_payload — pre-Phase-22 row shape
        conn.execute(text(
            "INSERT INTO renders (id, kind, file_path, created_at) "
            "VALUES ('R_NOSUB0000000000000000000', 'flyer_final', '/tmp/n.png', '2026-04-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO flyers (id, title, preset, event_payload, render_id, created_at) "
            "VALUES ('F_NOSUB0000000000000000000', 'Old', 'photorealistic', "
            "'{\"event\": {\"title\":\"Old\"}}', "
            "'R_NOSUB0000000000000000000', '2026-04-01T00:00:00')"
        ))
    command.upgrade(cfg, "f22t01")
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT kind FROM renders WHERE id='R_NOSUB0000000000000000000'"
        )).fetchone()
        assert row[0] == "flyer_event_final"  # COALESCE → 'event'
    engine.dispose()


def test_downgrade_reverses(tmp_path, monkeypatch):
    """Downgrade collapses both new kinds back to flyer_final + drops template col."""
    db = tmp_path / "dg.db"
    async_url = f"sqlite+aiosqlite:///{db}"
    sync_url = f"sqlite:///{db}"
    monkeypatch.setenv("FLYER_DATABASE_URL", async_url)
    cfg = _alembic_cfg(async_url)
    command.upgrade(cfg, "f22t01")
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO renders (id, kind, file_path, created_at) "
            "VALUES ('R_NEW0000000000000000000', 'flyer_event_final', '/tmp/n.png', '2026-04-24T00:00:00')"
        ))
    command.downgrade(cfg, "2f5971e114b3")
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT kind FROM renders WHERE id='R_NEW0000000000000000000'"
        )).fetchone()
        assert row[0] == "flyer_final"
        # template column dropped
        with pytest.raises(Exception):  # OperationalError: no such column
            conn.execute(text("SELECT template FROM flyers")).fetchone()
    engine.dispose()
