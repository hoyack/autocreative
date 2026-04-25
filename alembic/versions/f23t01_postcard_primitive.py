"""postcard primitive

Revision ID: f23t01
Revises: f22t01
Create Date: 2026-04-23

Adds the ``postcards`` table (mirrors ``brochures`` shape) + extends the
``jobkind`` enum with ``POSTCARD``. Idempotent + reversible.

Phase 23 PC-01 / PC-02 / PC-06.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f23t01"
down_revision: Union[str, Sequence[str], None] = "f22t01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create postcards table (mirrors brochures table shape, no `title`
    # column — postcards embed the headline in content_payload).
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
        sa.ForeignKeyConstraint(
            ["brand_kit_slug"], ["brand_kits.slug"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["render_front_id"], ["renders.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["render_back_id"], ["renders.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["render_pdf_id"], ["renders.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("postcards", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_postcards_brand_kit_slug"),
            ["brand_kit_slug"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_postcards_render_front_id"),
            ["render_front_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_postcards_render_back_id"),
            ["render_back_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_postcards_render_pdf_id"),
            ["render_pdf_id"],
            unique=False,
        )

    # 2. Extend jobkind enum with POSTCARD.
    bind = op.get_bind()
    if bind.dialect.name in ("postgresql", "postgres"):
        # ``ALTER TYPE ... ADD VALUE`` must run outside an explicit transaction
        # on older Postgres; ``autocommit_block`` handles that. ``IF NOT EXISTS``
        # makes the upgrade idempotent on re-run.
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE jobkind ADD VALUE IF NOT EXISTS 'POSTCARD'"
            )
    # SQLite stores SAEnum as plain VARCHAR (no CHECK constraint emitted by
    # the initial f22t01 / 0001 schema), so the Python-side enum extension
    # is sufficient for ``JobRecord(kind=JobKind.POSTCARD, ...)`` to round-trip
    # without DDL changes here. Verified by tests/api/test_migrations_postcard.py.


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop indexes + table.
    with op.batch_alter_table("postcards", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_postcards_render_pdf_id"))
        batch_op.drop_index(batch_op.f("ix_postcards_render_back_id"))
        batch_op.drop_index(batch_op.f("ix_postcards_render_front_id"))
        batch_op.drop_index(batch_op.f("ix_postcards_brand_kit_slug"))
    op.drop_table("postcards")
    # 2. Postgres cannot drop a single enum value cleanly without a full
    # type rebuild; we leave ``JobKind.POSTCARD`` in place on downgrade.
    # SQLite: no-op (no CHECK constraint to revert).
