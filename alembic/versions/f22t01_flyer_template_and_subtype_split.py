"""flyer template and subtype split

Revision ID: f22t01
Revises: 2f5971e114b3
Create Date: 2026-04-24

Adds flyers.template column + rewrites renders.kind='flyer_final' rows
to subtype-derived 'flyer_event_final' / 'flyer_info_final'. Idempotent
(WHERE kind='flyer_final' filters already-migrated rows).

Phase 22 FT-06.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f22t01"
down_revision: Union[str, Sequence[str], None] = "2f5971e114b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add template column to flyers with safe backfill default.
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
    # Subtype lookup: FlyerRecord.event_payload is the raw request body,
    # which has {"event": FlyerInput dict, ...}. The subtype lives at
    # event_payload.event.subtype — default to 'event' when absent.
    #
    # Idempotency: WHERE kind='flyer_final' guards re-runs.
    # Backend-specific JSON syntax: SQLite uses json_extract(),
    # Postgres uses ->>.
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
    """Downgrade schema — collapse both new kinds back to 'flyer_final',
    drop the template column."""
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE renders
           SET kind = 'flyer_final'
         WHERE kind IN ('flyer_event_final', 'flyer_info_final')
    """))

    with op.batch_alter_table("flyers", schema=None) as batch_op:
        batch_op.drop_column("template")
