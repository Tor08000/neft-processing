"""Align document status lifecycle with legal finalization.

Revision ID: 20290501_0045_document_status_lifecycle
Revises: 20280415_0044_accounting_export_batches
Create Date: 2029-05-01 00:00:00
"""

from __future__ import annotations

from alembic import op

from app.alembic.helpers import is_postgres
from app.db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20290501_0045_document_status_lifecycle"
down_revision = "20280415_0044_accounting_export_batches"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

DOCUMENT_STATUSES = ["DRAFT", "ISSUED", "ACKNOWLEDGED", "FINALIZED", "VOID"]
CLOSING_PACKAGE_STATUSES = ["DRAFT", "ISSUED", "ACKNOWLEDGED", "FINALIZED", "VOID"]


def _qualify(name: str) -> str:
    if SCHEMA:
        return f'"{SCHEMA}"."{name}"'
    return name


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    document_status_type = _qualify("document_status")
    closing_status_type = _qualify("closing_package_status")
    document_status_old = _qualify("document_status_old")
    closing_status_old = _qualify("closing_package_status_old")

    op.execute(f"ALTER TYPE {document_status_type} RENAME TO document_status_old")
    op.execute(
        "CREATE TYPE {name} AS ENUM ({values})".format(
            name=document_status_type,
            values=", ".join(f"'{value}'" for value in DOCUMENT_STATUSES),
        )
    )
    op.execute(
        "ALTER TABLE {schema}documents "
        "ALTER COLUMN status TYPE {enum} "
        "USING (CASE status::text "
        "WHEN 'GENERATED' THEN 'ISSUED' "
        "WHEN 'SENT' THEN 'ISSUED' "
        "WHEN 'CANCELLED' THEN 'VOID' "
        "ELSE status::text END)::text::{enum}".format(
            schema=f'"{SCHEMA}".' if SCHEMA else "",
            enum=document_status_type,
        )
    )
    op.execute(
        "ALTER TABLE {schema}documents ALTER COLUMN status SET DEFAULT 'DRAFT'".format(
            schema=f'"{SCHEMA}".' if SCHEMA else ""
        )
    )
    op.execute(f"DROP TYPE {document_status_old}")

    op.execute(f"ALTER TYPE {closing_status_type} RENAME TO closing_package_status_old")
    op.execute(
        "CREATE TYPE {name} AS ENUM ({values})".format(
            name=closing_status_type,
            values=", ".join(f"'{value}'" for value in CLOSING_PACKAGE_STATUSES),
        )
    )
    op.execute(
        "ALTER TABLE {schema}closing_packages "
        "ALTER COLUMN status TYPE {enum} "
        "USING (CASE status::text "
        "WHEN 'GENERATED' THEN 'ISSUED' "
        "WHEN 'SENT' THEN 'ISSUED' "
        "WHEN 'CANCELLED' THEN 'VOID' "
        "ELSE status::text END)::text::{enum}".format(
            schema=f'"{SCHEMA}".' if SCHEMA else "",
            enum=closing_status_type,
        )
    )
    op.execute(
        "ALTER TABLE {schema}closing_packages ALTER COLUMN status SET DEFAULT 'DRAFT'".format(
            schema=f'"{SCHEMA}".' if SCHEMA else ""
        )
    )
    op.execute(f"DROP TYPE {closing_status_old}")


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
