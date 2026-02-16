"""Documents inbound sender fields.

Revision ID: 20299970_0200_documents_inbound_sender_fields
Revises: 20299960_0199_client_documents_timeline_events
Create Date: 2029-09-97 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import column_exists, create_index_if_not_exists
from db.schema import resolve_db_schema

revision = "20299970_0200_documents_inbound_sender_fields"
down_revision = "20299960_0199_client_documents_timeline_events"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if not column_exists(bind, table_name, column_name, schema=SCHEMA):
        op.add_column(table_name, column, schema=SCHEMA)


def upgrade() -> None:
    bind = op.get_bind()
    _add_column_if_missing(
        "documents",
        "category",
        sa.Column("category", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "documents",
        "sender_type",
        sa.Column("sender_type", sa.Text(), nullable=False, server_default="NEFT"),
    )
    _add_column_if_missing(
        "documents",
        "sender_name",
        sa.Column("sender_name", sa.Text(), nullable=True),
    )

    create_index_if_not_exists(
        bind,
        "idx_documents_client_id_direction_created_at",
        "documents",
        ["client_id", "direction", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
