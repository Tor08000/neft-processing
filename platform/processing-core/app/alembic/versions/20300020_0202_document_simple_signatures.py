"""Document simple signatures for client inbound docs.

Revision ID: 20300020_0202_document_simple_signatures
Revises: 20300010_0201_document_edostate
Create Date: 2030-00-20 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import (
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    index_exists,
)
from db.schema import resolve_db_schema

revision = "20300020_0202_document_simple_signatures"
down_revision = "20300010_0201_document_edostate"
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
        "document_signatures",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("document_id", document_id_type, sa.ForeignKey(documents_fk, ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("signer_user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signer_type", sa.Text(), nullable=False, server_default=sa.text("'CLIENT_USER'")),
        sa.Column("signature_method", sa.String(length=16), nullable=False, server_default=sa.text("'SIMPLE'")),
        sa.Column("consent_text_version", sa.Text(), nullable=False),
        sa.Column("document_hash_sha256", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("document_id", "signer_user_id", "signature_method", name="uq_doc_signature_per_user_method"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_document_signatures_client_id", "document_signatures", ["client_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_document_signatures_document_id", "document_signatures", ["document_id"], schema=SCHEMA)

    if not column_exists(bind, "documents", "signed_by_client_at", schema=SCHEMA):
        op.add_column("documents", sa.Column("signed_by_client_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "documents", "signed_by_client_user_id", schema=SCHEMA):
        op.add_column("documents", sa.Column("signed_by_client_user_id", postgresql.UUID(as_uuid=False), nullable=True), schema=SCHEMA)
    if not index_exists(bind, "ix_documents_signed_by_client_at", schema=SCHEMA):
        op.create_index("ix_documents_signed_by_client_at", "documents", ["signed_by_client_at"], schema=SCHEMA)


def downgrade() -> None:
    pass
