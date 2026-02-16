"""Client documents module skeleton.

Revision ID: 20299940_0197_client_documents_module_skeleton
Revises: b1f4572ed8d3
Create Date: 2029-09-94 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.schema import resolve_db_schema

revision = "20299940_0197_client_documents_module_skeleton"
down_revision = "b1f4572ed8d3"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

DIRECTION_VALUES = ["INBOUND", "OUTBOUND"]
STATUS_VALUES = ["DRAFT", "SENT", "RECEIVED", "SIGNED", "REJECTED", "CANCELLED"]


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if not column_exists(bind, table_name, column_name, schema=SCHEMA):
        op.add_column(table_name, column, schema=SCHEMA)


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "documents_direction", DIRECTION_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "documents_status", STATUS_VALUES, schema=SCHEMA)

    direction_enum = safe_enum(bind, "documents_direction", DIRECTION_VALUES, schema=SCHEMA)
    status_enum = safe_enum(bind, "documents_status", STATUS_VALUES, schema=SCHEMA)

    documents_fk = f"{SCHEMA}.documents.id" if SCHEMA else "documents.id"

    create_table_if_not_exists(
        bind,
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("direction", direction_enum, nullable=False, server_default="INBOUND"),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("doc_type", sa.Text(), nullable=True),
        sa.Column("status", status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("counterparty_name", sa.Text(), nullable=True),
        sa.Column("counterparty_inn", sa.Text(), nullable=True),
        sa.Column("number", sa.Text(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )

    _add_column_if_missing("documents", "direction", sa.Column("direction", direction_enum, nullable=False, server_default="INBOUND"))
    _add_column_if_missing("documents", "title", sa.Column("title", sa.Text(), nullable=False, server_default=""))
    _add_column_if_missing("documents", "doc_type", sa.Column("doc_type", sa.Text(), nullable=True))
    _add_column_if_missing("documents", "counterparty_name", sa.Column("counterparty_name", sa.Text(), nullable=True))
    _add_column_if_missing("documents", "counterparty_inn", sa.Column("counterparty_inn", sa.Text(), nullable=True))
    _add_column_if_missing("documents", "date", sa.Column("date", sa.Date(), nullable=True))
    _add_column_if_missing("documents", "amount", sa.Column("amount", sa.Numeric(18, 2), nullable=True))
    _add_column_if_missing("documents", "currency", sa.Column("currency", sa.Text(), nullable=True))

    create_index_if_not_exists(
        bind,
        "ix_documents_client_direction_status",
        "documents",
        ["client_id", "direction", "status"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_documents_client_created_desc",
        "documents",
        ["client_id", "created_at"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "document_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey(documents_fk, ondelete="CASCADE"), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("filename", sa.Text(), nullable=False, server_default=""),
        sa.Column("mime", sa.Text(), nullable=False, server_default="application/octet-stream"),
        sa.Column("size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )

    _add_column_if_missing("document_files", "storage_key", sa.Column("storage_key", sa.Text(), nullable=False, server_default=""))
    _add_column_if_missing("document_files", "filename", sa.Column("filename", sa.Text(), nullable=False, server_default=""))
    _add_column_if_missing("document_files", "mime", sa.Column("mime", sa.Text(), nullable=False, server_default="application/octet-stream"))
    _add_column_if_missing("document_files", "size", sa.Column("size", sa.BigInteger(), nullable=False, server_default="0"))

    create_index_if_not_exists(bind, "ix_document_files_document_id", "document_files", ["document_id"], schema=SCHEMA)
    create_unique_index_if_not_exists(
        bind,
        "uq_document_files_document_storage_key",
        "document_files",
        ["document_id", "storage_key"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
