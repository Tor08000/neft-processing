"""Fix invoices reconciliation_request_id type.

Revision ID: 20290625_0050_fix_invoices_reconciliation_request_id_type
Revises: 20290620_0049_fix_settlement_period_id_type
Create Date: 2029-06-25 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import column_exists, constraint_exists, create_index_if_not_exists, is_postgres, table_exists
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20290625_0050_fix_invoices_reconciliation_request_id_type"
down_revision = "20290620_0049_fix_settlement_period_id_type"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _is_uuid_column(bind, table_name: str, column_name: str, schema: str) -> bool:
    if not is_postgres(bind):
        return False

    result = bind.execute(
        sa.text(
            """
            SELECT data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table_name AND column_name = :column_name
            """
        ),
        {"schema": schema, "table_name": table_name, "column_name": column_name},
    ).first()
    return bool(result and result.udt_name == "uuid")


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "invoices", schema=SCHEMA):
        return
    if not column_exists(bind, "invoices", "reconciliation_request_id", schema=SCHEMA):
        return

    if _is_uuid_column(bind, "invoices", "reconciliation_request_id", schema=SCHEMA):
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA}".invoices '
                "ALTER COLUMN reconciliation_request_id "
                "TYPE VARCHAR(36) USING reconciliation_request_id::text"
            )
        )

    create_index_if_not_exists(
        bind,
        "ix_invoices_reconciliation_request_id",
        "invoices",
        ["reconciliation_request_id"],
        schema=SCHEMA,
    )

    if not table_exists(bind, "reconciliation_requests", schema=SCHEMA):
        return
    if not constraint_exists(bind, "invoices", "fk_invoices_reconciliation_request_id", schema=SCHEMA):
        op.create_foreign_key(
            "fk_invoices_reconciliation_request_id",
            "invoices",
            "reconciliation_requests",
            ["reconciliation_request_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
        )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
