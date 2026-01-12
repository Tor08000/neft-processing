"""Add missing marketplace order event enum values.

Revision ID: 20297150_0122_marketplace_order_event_type_enum_update
Revises: 20297140_0121_fix_fk_type_mismatches_v1
Create Date: 2029-08-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from alembic_helpers import DB_SCHEMA, ensure_pg_enum_value, is_postgres

# revision identifiers, used by Alembic.
revision = "20297150_0122_marketplace_order_event_type_enum_update"
down_revision = "20297140_0121_fix_fk_type_mismatches_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    for value in (
        "MARKETPLACE_ORDER_CREATED",
        "MARKETPLACE_ORDER_CONFIRMED_BY_PARTNER",
        "MARKETPLACE_ORDER_STARTED",
        "MARKETPLACE_ORDER_COMPLETED",
        "MARKETPLACE_ORDER_FAILED",
    ):
        ensure_pg_enum_value(bind, "marketplace_order_event_type", value, schema=DB_SCHEMA)


def downgrade() -> None:
    # Enum additions are idempotent; no downgrade.
    pass
