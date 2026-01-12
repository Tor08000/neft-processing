"""Fix invoices reconciliation_request_id type mismatch.

Revision ID: 20297130_0119_fix_invoices_reconciliation_request_id_uuid
Revises: 20297125_0118_create_processing_core_enums
Create Date: 2029-07-30 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import column_exists, constraint_exists, is_postgres, table_exists
from db.schema import resolve_db_schema

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

    if is_postgres(bind) and column_exists(bind, "reconciliation_requests", "id", schema=SCHEMA):
        id_type = bind.execute(
            sa.text(
                """
                SELECT data_type, udt_name
                FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = :table_name AND column_name = :column_name
                """
            ),
            {"schema": SCHEMA, "table_name": "reconciliation_requests", "column_name": "id"},
        ).first()
        is_uuid = bool(id_type) and (id_type[0] == "uuid" or id_type[1] == "uuid")

        if not is_uuid:
            invalid_ids = bind.execute(
                sa.text(
                    f"""
                    SELECT id
                    FROM "{SCHEMA}".reconciliation_requests
                    WHERE id IS NOT NULL
                      AND id !~* '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$'
                    LIMIT 5
                    """
                )
            ).fetchall()
            if invalid_ids:
                invalid_values = ", ".join(str(row[0]) for row in invalid_ids)
                raise RuntimeError(
                    "reconciliation_requests.id contains non-UUID values; "
                    f"example values: {invalid_values}"
                )

            op.execute(
                sa.text(
                    f'ALTER TABLE "{SCHEMA}".reconciliation_requests '
                    "ALTER COLUMN id "
                    "TYPE UUID USING id::uuid"
                )
            )

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
