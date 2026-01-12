"""Extend document signatures for audit chain.

Revision ID: 20291610_0083_document_signature_chain
Revises: 20291600_0082_scheduler_job_runs
Create Date: 2029-16-10 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    column_exists,
    create_index_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20291610_0083_document_signature_chain"
down_revision = "20291600_0082_scheduler_job_runs"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

DOCUMENT_SIGNATURE_STATUS = ["REQUESTED", "SIGNING", "SIGNED", "FAILED", "VERIFIED", "REJECTED"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "document_signature_status", DOCUMENT_SIGNATURE_STATUS, schema=SCHEMA)
    status_enum = safe_enum(bind, "document_signature_status", DOCUMENT_SIGNATURE_STATUS, schema=SCHEMA)

    table_name = "document_signatures"

    _add_column_if_missing(table_name, "version", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    _add_column_if_missing(table_name, "request_id", sa.Column("request_id", sa.String(length=128), nullable=True))
    _add_column_if_missing(
        table_name,
        "status",
        sa.Column("status", status_enum, nullable=False, server_default=sa.text("'SIGNED'")),
    )
    _add_column_if_missing(table_name, "input_object_key", sa.Column("input_object_key", sa.Text(), nullable=True))
    _add_column_if_missing(table_name, "input_sha256", sa.Column("input_sha256", sa.String(length=64), nullable=True))
    _add_column_if_missing(table_name, "signed_object_key", sa.Column("signed_object_key", sa.Text(), nullable=True))
    _add_column_if_missing(table_name, "signed_sha256", sa.Column("signed_sha256", sa.String(length=64), nullable=True))
    _add_column_if_missing(table_name, "signature_object_key", sa.Column("signature_object_key", sa.Text(), nullable=True))
    _add_column_if_missing(table_name, "signature_sha256", sa.Column("signature_sha256", sa.String(length=64), nullable=True))
    _add_column_if_missing(table_name, "attempt", sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
    _add_column_if_missing(table_name, "error_code", sa.Column("error_code", sa.String(length=128), nullable=True))
    _add_column_if_missing(table_name, "error_message", sa.Column("error_message", sa.Text(), nullable=True))
    _add_column_if_missing(table_name, "started_at", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing(table_name, "finished_at", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing(table_name, "meta", sa.Column("meta", sa.JSON(), nullable=True))

    create_unique_index_if_not_exists(
        bind,
        "uq_document_signatures_document_version",
        table_name,
        ["document_id", "version"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_document_signatures_status_finished",
        table_name,
        ["status", "finished_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if column_exists(bind, table_name, column_name, schema=SCHEMA):
        return
    op.add_column(table_name, column, schema=SCHEMA)
