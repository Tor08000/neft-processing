"""Add document hash and reconciliation request link.

Revision ID: 20290601_0047_document_chain_reconciliation
Revises: 20290520_0046_risk_scores
Create Date: 2029-06-01 00:00:00
"""

from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    column_exists,
    constraint_exists,
    create_index_if_not_exists,
    is_postgres,
    table_exists,
)
from db.schema import resolve_db_schema


revision = "20290601_0047_document_chain_reconciliation"
down_revision = "20290601_0046a_documents_bootstrap"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema
LOGGER = logging.getLogger(__name__)


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
    if not table_exists(bind, "documents", schema=SCHEMA):
        raise RuntimeError("documents table missing; run documents bootstrap migration")

    if not column_exists(bind, "documents", "document_hash", schema=SCHEMA):
        op.add_column(
            "documents",
            sa.Column("document_hash", sa.String(length=64), nullable=True),
            schema=SCHEMA,
        )

    if table_exists(bind, "invoices", schema=SCHEMA):
        if not column_exists(bind, "invoices", "reconciliation_request_id", schema=SCHEMA):
            op.add_column(
                "invoices",
                sa.Column("reconciliation_request_id", sa.String(length=36), nullable=True),
                schema=SCHEMA,
            )
        create_index_if_not_exists(
            bind,
            "ix_invoices_reconciliation_request_id",
            "invoices",
            ["reconciliation_request_id"],
            schema=SCHEMA,
        )
        if _is_uuid_column(bind, "invoices", "reconciliation_request_id", schema=SCHEMA):
            LOGGER.warning(
                "Skipping foreign key creation for invoices.reconciliation_request_id "
                "because column type is UUID; follow-up migration will fix the type."
            )
        elif not constraint_exists(
            bind, "invoices", "fk_invoices_reconciliation_request_id", schema=SCHEMA
        ):
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
