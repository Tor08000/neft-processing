"""Cases snapshotting v1.

Revision ID: 20291720_0089_cases_v1
Revises: 76e4bcb5869e
Create Date: 2025-02-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    index_exists,
    safe_enum,
)
from app.db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20291720_0089_cases_v1"
down_revision = "76e4bcb5869e"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

CASE_KIND = ["operation", "invoice", "order", "kpi"]
CASE_STATUS = ["TRIAGE", "IN_PROGRESS", "RESOLVED", "CLOSED"]
CASE_PRIORITY = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
CASE_COMMENT_TYPE = ["user", "system"]


def _create_desc_index(bind, name: str, table: str, columns: list[str]) -> None:
    if index_exists(bind, name, schema=SCHEMA):
        return
    schema_name = SCHEMA or resolve_db_schema().schema
    columns_sql = ", ".join(columns)
    bind.exec_driver_sql(f"CREATE INDEX {name} ON {schema_name}.{table} ({columns_sql})")


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "case_kind", CASE_KIND, schema=SCHEMA)
    ensure_pg_enum(bind, "case_status", CASE_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "case_priority", CASE_PRIORITY, schema=SCHEMA)
    ensure_pg_enum(bind, "case_comment_type", CASE_COMMENT_TYPE, schema=SCHEMA)
    ensure_pg_enum_value(bind, "crm_feature_flag", "CASES_ENABLED", schema=SCHEMA)

    kind_enum = safe_enum(bind, "case_kind", CASE_KIND, schema=SCHEMA)
    status_enum = safe_enum(bind, "case_status", CASE_STATUS, schema=SCHEMA)
    priority_enum = safe_enum(bind, "case_priority", CASE_PRIORITY, schema=SCHEMA)
    comment_type_enum = safe_enum(bind, "case_comment_type", CASE_COMMENT_TYPE, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "cases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("kind", kind_enum, nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("kpi_key", sa.String(length=64), nullable=True),
        sa.Column("window_days", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="TRIAGE"),
        sa.Column("priority", priority_enum, nullable=False, server_default="MEDIUM"),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("assigned_to", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "case_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("explain_snapshot", sa.JSON(), nullable=False),
        sa.Column("diff_snapshot", sa.JSON(), nullable=True),
        sa.Column("selected_actions", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "case_comments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("author", sa.String(length=128), nullable=True),
        sa.Column("type", comment_type_enum, nullable=False, server_default="user"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    create_index_if_not_exists(bind, "ix_cases_tenant_status", "cases", ["tenant_id", "status"], schema=SCHEMA)
    _create_desc_index(bind, "ix_cases_tenant_status_updated", "cases", ["tenant_id", "status", "updated_at DESC"])
    create_index_if_not_exists(bind, "ix_cases_tenant_kind_entity", "cases", ["tenant_id", "kind", "entity_id"], schema=SCHEMA)
    _create_desc_index(bind, "ix_case_snapshots_case_created", "case_snapshots", ["case_id", "created_at DESC"])
    create_index_if_not_exists(bind, "ix_case_comments_case_created", "case_comments", ["case_id", "created_at"], schema=SCHEMA)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
