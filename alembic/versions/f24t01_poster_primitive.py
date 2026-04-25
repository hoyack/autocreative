"""poster primitive

Revision ID: f24t01
Revises: f23t01
Create Date: 2026-04-25

Adds the ``posters`` table (parallel-id, single-render artifact) + extends
the ``jobkind`` enum with ``POSTER``. Idempotent + reversible.

Phase 24 PO-01.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f24t01"
down_revision: Union[str, Sequence[str], None] = "f23t01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create posters table — single render_id (no front/back/pdf split),
    # plus a `size` column storing the locked literal (e.g. "18x24") for
    # FE display + audit.
    op.create_table(
        "posters",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("template", sa.String(length=64), nullable=False),
        sa.Column("size", sa.String(length=8), nullable=False),
        sa.Column("brand_kit_slug", sa.String(length=64), nullable=True),
        sa.Column("content_payload", sa.JSON(), nullable=False),
        sa.Column("render_id", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["brand_kit_slug"], ["brand_kits.slug"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["render_id"], ["renders.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("posters", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_posters_brand_kit_slug"),
            ["brand_kit_slug"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_posters_render_id"),
            ["render_id"],
            unique=False,
        )

    # 2. Extend jobkind enum with POSTER.
    bind = op.get_bind()
    if bind.dialect.name in ("postgresql", "postgres"):
        # ``ALTER TYPE ... ADD VALUE`` must run outside an explicit transaction
        # on older Postgres; ``autocommit_block`` handles that. ``IF NOT EXISTS``
        # makes the upgrade idempotent on re-run (T-24-10 mitigation).
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE jobkind ADD VALUE IF NOT EXISTS 'POSTER'"
            )
    # SQLite stores SAEnum as plain VARCHAR (no CHECK constraint emitted by
    # the initial f22t01 / 0001 schema), so the Python-side enum extension
    # is sufficient for ``JobRecord(kind=JobKind.POSTER, ...)`` to round-trip
    # without DDL changes here. Verified by tests/api/test_migrations_poster.py.


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop indexes + table.
    with op.batch_alter_table("posters", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_posters_render_id"))
        batch_op.drop_index(batch_op.f("ix_posters_brand_kit_slug"))
    op.drop_table("posters")
    # 2. Postgres cannot drop a single enum value cleanly without a full
    # type rebuild; we leave ``JobKind.POSTER`` in place on downgrade.
    # SQLite: no-op (no CHECK constraint to revert).
