"""Fix invoices reconciliation_request_id type mismatch.

Revision ID: 20297130_0119_fix_invoices_reconciliation_request_id_uuid
Revises: 20297125_0118_create_processing_core_enums
Create Date: 2029-07-30 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import column_exists, constraint_exists, is_postgres, table_exists
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20297130_0119_fix_invoices_reconciliation_request_id_uuid"
down_revision = "20297125_0118_create_processing_core_enums"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "invoices", schema=SCHEMA):
        return
    if not column_exists(bind, "invoices", "reconciliation_request_id", schema=SCHEMA):
        return

    if constraint_exists(bind, "invoices", "fk_invoices_reconciliation_request_id", schema=SCHEMA):
        op.drop_constraint(
            "fk_invoices_reconciliation_request_id",
            "invoices",
            type_="foreignkey",
            schema=SCHEMA,
        )

    if constraint_exists(bind, "invoices", "invoices_reconciliation_request_id_fkey", schema=SCHEMA):
        op.drop_constraint(
            "invoices_reconciliation_request_id_fkey",
            "invoices",
            type_="foreignkey",
            schema=SCHEMA,
        )

    if is_postgres(bind):
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA}".invoices '
                "ALTER COLUMN reconciliation_request_id "
                "TYPE UUID USING reconciliation_request_id::uuid"
            )
        )

    if not table_exists(bind, "reconciliation_requests", schema=SCHEMA):
        return

    if not constraint_exists(bind, "invoices", "invoices_reconciliation_request_id_fkey", schema=SCHEMA):
        op.create_foreign_key(
            "invoices_reconciliation_request_id_fkey",
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
