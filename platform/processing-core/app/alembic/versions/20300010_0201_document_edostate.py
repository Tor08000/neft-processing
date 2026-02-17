"""Document EDO state table.

Revision ID: 20300010_0201_document_edostate
Revises: 20299970_0200_documents_inbound_sender_fields
Create Date: 2030-00-10 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists
from db.schema import resolve_db_schema

revision = "20300010_0201_document_edostate"
down_revision = "20299970_0200_documents_inbound_sender_fields"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _documents_id_column_type(bind) -> sa.types.TypeEngine:
    inspector = sa.inspect(bind)
    columns = inspector.get_columns("documents", schema=SCHEMA)
    document_id_column = next((column for column in columns if column.get("name") == "id"), None)
    if document_id_column is None:
        raise RuntimeError("documents.id column was not found")

    column_type = document_id_column.get("type")
    if isinstance(column_type, sa.Text):
        return sa.Text()
    if isinstance(column_type, sa.String):
        return sa.String(length=column_type.length)

    raise RuntimeError(f"Unsupported documents.id type: {column_type}")


def upgrade() -> None:
    bind = op.get_bind()
    documents_fk = f"{SCHEMA}.documents.id" if SCHEMA else "documents.id"
    document_id_type = _documents_id_column_type(bind)

    create_table_if_not_exists(
        bind,
        "document_edostate",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("document_id", document_id_type, sa.ForeignKey(documents_fk, ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("provider_mode", sa.String(length=16), nullable=False, server_default=sa.text("'real'")),
        sa.Column("edo_status", sa.String(length=32), nullable=False, server_default=sa.text("'NEW'")),
        sa.Column("edo_message_id", sa.Text(), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("attempts_send", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("attempts_poll", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("document_id", name="uq_document_edostate_document_id"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_document_edostate_document_id", "document_edostate", ["document_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_document_edostate_client_id", "document_edostate", ["client_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_document_edostate_updated_at", "document_edostate", ["updated_at"], schema=SCHEMA)
    create_index_if_not_exists(bind, "idx_document_edostate_next_poll_at", "document_edostate", ["next_poll_at"], schema=SCHEMA)
    create_index_if_not_exists(bind, "idx_document_edostate_client_id_status", "document_edostate", ["client_id", "edo_status"], schema=SCHEMA)


def downgrade() -> None:
    pass
