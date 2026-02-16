"""Client documents outbound drafts fields.

Revision ID: 20299950_0198_client_documents_outbound_drafts
Revises: 20299940_0197_client_documents_module_skeleton
Create Date: 2029-09-95 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import column_exists, create_index_if_not_exists, create_unique_index_if_not_exists
from db.schema import resolve_db_schema

revision = "20299950_0198_client_documents_outbound_drafts"
down_revision = "20299940_0197_client_documents_module_skeleton"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if not column_exists(bind, table_name, column_name, schema=SCHEMA):
        op.add_column(table_name, column, schema=SCHEMA)


def upgrade() -> None:
    bind = op.get_bind()

    _add_column_if_missing("documents", "description", sa.Column("description", sa.Text(), nullable=True))
    _add_column_if_missing("document_files", "sha256", sa.Column("sha256", sa.Text(), nullable=True))

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
