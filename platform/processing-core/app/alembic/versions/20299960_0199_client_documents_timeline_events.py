"""Client documents timeline events.

Revision ID: 20299960_0199_client_documents_timeline_events
Revises: 20299950_0198_client_documents_outbound_drafts
Create Date: 2029-09-96 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists, table_exists
from db.schema import resolve_db_schema

revision = "20299960_0199_client_documents_timeline_events"
down_revision = "20299950_0198_client_documents_outbound_drafts"
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


def _type_signature(column_type: sa.types.TypeEngine) -> tuple[str, int | None]:
    if isinstance(column_type, sa.Text):
        return ("text", None)
    if isinstance(column_type, sa.String):
        return ("varchar", column_type.length)
    return (column_type.__class__.__name__.lower(), getattr(column_type, "length", None))


def _validate_existing_document_timeline_events(bind, expected_document_id_type: sa.types.TypeEngine) -> None:
    if not table_exists(bind, "document_timeline_events", schema=SCHEMA):
        return

    inspector = sa.inspect(bind)
    columns = inspector.get_columns("document_timeline_events", schema=SCHEMA)
    document_id_column = next((column for column in columns if column.get("name") == "document_id"), None)
    if document_id_column is None:
        raise RuntimeError("document_timeline_events.document_id column is missing")

    actual_type = document_id_column.get("type")
    if _type_signature(actual_type) != _type_signature(expected_document_id_type):
        raise RuntimeError("document_timeline_events.document_id type mismatch with documents.id")


def upgrade() -> None:
    bind = op.get_bind()
    documents_fk = f"{SCHEMA}.documents.id" if SCHEMA else "documents.id"
    document_id_type = _documents_id_column_type(bind)

    _validate_existing_document_timeline_events(bind, document_id_type)

    create_table_if_not_exists(
        bind,
        "document_timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            document_id_type,
            sa.ForeignKey(documents_fk, ondelete="CASCADE"),
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
        "ix_document_timeline_events_document_id",
        "document_timeline_events",
        ["document_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_document_timeline_events_client_id",
        "document_timeline_events",
        ["client_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_document_timeline_events_created_at",
        "document_timeline_events",
        ["created_at"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_document_timeline_events_document_id_created_at",
        "document_timeline_events",
        ["document_id", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    pass
