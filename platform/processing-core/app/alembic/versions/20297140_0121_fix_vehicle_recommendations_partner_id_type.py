"""Fix vehicle_recommendations.partner_id type.

Revision ID: 20297140_0121_fix_vehicle_recommendations_partner_id_type
Revises: 20297135_0120_fix_reconciliation_requests_id_uuid
Create Date: 2029-07-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import column_exists, is_postgres, table_exists
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20297140_0121_fix_vehicle_recommendations_partner_id_type"
down_revision = "20297135_0120_fix_reconciliation_requests_id_uuid"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    if not table_exists(bind, "vehicle_recommendations", schema=SCHEMA):
        return
    if not column_exists(bind, "vehicle_recommendations", "partner_id", schema=SCHEMA):
        return

    column_type = bind.execute(
        sa.text(
            "SELECT data_type, character_maximum_length "
            "FROM information_schema.columns "
            "WHERE table_schema = :schema "
            "AND table_name = 'vehicle_recommendations' "
            "AND column_name = 'partner_id'"
        ),
        {"schema": SCHEMA},
    ).fetchone()
    if column_type and column_type[0] in {"character varying", "varchar"} and column_type[1] == 64:
        return

    op.execute(
        sa.text(
            f'ALTER TABLE "{SCHEMA}".vehicle_recommendations '
            "ALTER COLUMN partner_id TYPE VARCHAR(64) USING partner_id::text"
        )
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
