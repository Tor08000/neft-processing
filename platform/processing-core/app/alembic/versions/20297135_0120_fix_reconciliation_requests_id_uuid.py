"""Fix reconciliation_requests.id type mismatch.

Revision ID: 20297135_0120_fix_reconciliation_requests_id_uuid
Revises: 20297130_0119_fix_invoices_reconciliation_request_id_uuid
Create Date: 2029-07-30 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import column_exists, is_postgres, table_exists
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20297135_0120_fix_reconciliation_requests_id_uuid"
down_revision = "20297130_0119_fix_invoices_reconciliation_request_id_uuid"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema
UUID_REGEX = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "reconciliation_requests", schema=SCHEMA):
        return
    if not column_exists(bind, "reconciliation_requests", "id", schema=SCHEMA):
        return
    if not is_postgres(bind):
        return

    column_type = bind.execute(
        sa.text(
            "SELECT data_type, udt_name "
            "FROM information_schema.columns "
            "WHERE table_schema = :schema "
            "AND table_name = 'reconciliation_requests' "
            "AND column_name = 'id'"
        ),
        {"schema": SCHEMA},
    ).fetchone()
    if column_type and column_type[1] == "uuid":
        return

    bad_rows = bind.execute(
        sa.text(
            f'SELECT id FROM "{SCHEMA}".reconciliation_requests '
            "WHERE id IS NOT NULL AND (id::text) !~* :uuid_regex "
            "LIMIT 20"
        ),
        {"uuid_regex": UUID_REGEX},
    ).fetchall()
    if bad_rows:
        sample = ", ".join(str(row[0]) for row in bad_rows)
        raise RuntimeError(
            "Cannot convert reconciliation_requests.id to UUID; found non-UUID values. "
            f"Sample ids: {sample}"
        )

    op.execute(
        sa.text(
            f'ALTER TABLE "{SCHEMA}".reconciliation_requests '
            "ALTER COLUMN id TYPE UUID USING id::uuid"
        )
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
