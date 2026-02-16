"""Client documents timeline events.

Revision ID: 20299960_0199_client_documents_timeline_events
Revises: 20299950_0198_client_documents_outbound_drafts
Create Date: 2029-09-96 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists
from db.schema import resolve_db_schema

revision = "20299960_0199_client_documents_timeline_events"
down_revision = "20299950_0198_client_documents_outbound_drafts"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "document_timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "idx_doc_timeline_doc_id_created_at",
        "document_timeline_events",
        ["document_id", "created_at"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "idx_doc_timeline_client_id_created_at",
        "document_timeline_events",
        ["client_id", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
