"""Support requests inbox v1.

Revision ID: 20291660_0088_support_requests
Revises: 20291650_0087_bi_pricing_intelligence_v1
Create Date: 2025-02-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20291660_0088_support_requests"
down_revision = "20291650_0087_bi_pricing_intelligence_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

SCOPE_TYPES = ["CLIENT", "PARTNER"]
SUBJECT_TYPES = ["ORDER", "DOCUMENT", "PAYOUT", "SETTLEMENT", "INTEGRATION", "OTHER"]
STATUS_TYPES = ["OPEN", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"]
PRIORITY_TYPES = ["LOW", "NORMAL", "HIGH"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "support_request_scope_type", SCOPE_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "support_request_subject_type", SUBJECT_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "support_request_status", STATUS_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "support_request_priority", PRIORITY_TYPES, schema=SCHEMA)

    scope_enum = safe_enum(bind, "support_request_scope_type", SCOPE_TYPES, schema=SCHEMA)
    subject_enum = safe_enum(bind, "support_request_subject_type", SUBJECT_TYPES, schema=SCHEMA)
    status_enum = safe_enum(bind, "support_request_status", STATUS_TYPES, schema=SCHEMA)
    priority_enum = safe_enum(bind, "support_request_priority", PRIORITY_TYPES, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "support_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("partner_id", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.Text(), nullable=True),
        sa.Column("scope_type", scope_enum, nullable=False),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("event_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="OPEN"),
        sa.Column("priority", priority_enum, nullable=False, server_default="NORMAL"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    create_index_if_not_exists(bind, "ix_support_requests_scope", "support_requests", ["tenant_id", "scope_type"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_support_requests_client", "support_requests", ["client_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_support_requests_partner", "support_requests", ["partner_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_support_requests_subject", "support_requests", ["subject_type", "subject_id"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_support_requests_status", "support_requests", ["status"], schema=SCHEMA)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
