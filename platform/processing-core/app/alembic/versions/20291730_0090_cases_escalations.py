"""Cases escalation queues and SLA fields.

Revision ID: 20291730_0090_cases_escalations
Revises: 20291720_0089_cases_v1
Create Date: 2025-03-05 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import (
    column_exists,
    create_index_if_not_exists,
    ensure_pg_enum,
    index_exists,
    safe_enum,
)
from db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20291730_0090_cases_escalations"
down_revision = "20291720_0089_cases_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

CASE_QUEUE = ["FRAUD_OPS", "FINANCE_OPS", "SUPPORT", "GENERAL"]


def _create_desc_index(bind, name: str, table: str, columns: list[str]) -> None:
    if index_exists(bind, name, schema=SCHEMA):
        return
    schema_name = SCHEMA or resolve_db_schema().schema
    columns_sql = ", ".join(columns)
    bind.exec_driver_sql(f"CREATE INDEX {name} ON {schema_name}.{table} ({columns_sql})")


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "case_queue", CASE_QUEUE, schema=SCHEMA)

    queue_enum = safe_enum(bind, "case_queue", CASE_QUEUE, schema=SCHEMA)

    if not column_exists(bind, "cases", "queue", schema=SCHEMA):
        op.add_column("cases", sa.Column("queue", queue_enum, nullable=False, server_default="GENERAL"), schema=SCHEMA)
    if not column_exists(bind, "cases", "escalation_level", schema=SCHEMA):
        op.add_column("cases", sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"), schema=SCHEMA)
    if not column_exists(bind, "cases", "first_response_due_at", schema=SCHEMA):
        op.add_column("cases", sa.Column("first_response_due_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)
    if not column_exists(bind, "cases", "resolve_due_at", schema=SCHEMA):
        op.add_column("cases", sa.Column("resolve_due_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)

    _create_desc_index(
        bind,
        "ix_cases_tenant_queue_status_activity_desc",
        "cases",
        ["tenant_id", "queue", "status", "last_activity_at DESC"],
    )
    create_index_if_not_exists(bind, "ix_cases_tenant_first_response_due", "cases", ["tenant_id", "first_response_due_at"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_cases_tenant_resolve_due", "cases", ["tenant_id", "resolve_due_at"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_cases_tenant_escalation_level", "cases", ["tenant_id", "escalation_level"], schema=SCHEMA)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
