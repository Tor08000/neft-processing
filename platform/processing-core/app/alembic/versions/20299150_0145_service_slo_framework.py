"""Service SLO framework tables.

Revision ID: 20299150_0145_service_slo_framework
Revises: 20299140_0144_export_job_eta_fields
Create Date: 2026-02-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.types import GUID


revision = "20299150_0145_service_slo_framework"
down_revision = "20299140_0144_export_job_eta_fields"
branch_labels = None
depends_on = None


SERVICE_SLO_SERVICE = ["exports", "email", "support", "schedules"]
SERVICE_SLO_METRIC = ["latency", "success_rate"]
SERVICE_SLO_WINDOW = ["7d", "30d"]
SERVICE_SLO_BREACH_STATUS = ["OPEN", "ACKED", "RESOLVED"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "service_slo_service", SERVICE_SLO_SERVICE, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "service_slo_metric", SERVICE_SLO_METRIC, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "service_slo_window", SERVICE_SLO_WINDOW, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "service_slo_breach_status", SERVICE_SLO_BREACH_STATUS, schema=DB_SCHEMA)

    service_enum = safe_enum(bind, "service_slo_service", SERVICE_SLO_SERVICE, schema=DB_SCHEMA)
    metric_enum = safe_enum(bind, "service_slo_metric", SERVICE_SLO_METRIC, schema=DB_SCHEMA)
    window_enum = safe_enum(bind, "service_slo_window", SERVICE_SLO_WINDOW, schema=DB_SCHEMA)
    breach_status_enum = safe_enum(bind, "service_slo_breach_status", SERVICE_SLO_BREACH_STATUS, schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "service_slo",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("service", service_enum, nullable=False),
        sa.Column("metric", metric_enum, nullable=False),
        sa.Column("objective_json", sa.JSON(), nullable=False),
        sa.Column("window", window_enum, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "service_slo_breaches",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("slo_id", GUID(), nullable=False),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("service", service_enum, nullable=False),
        sa.Column("metric", metric_enum, nullable=False),
        sa.Column("window", window_enum, nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_value_json", sa.JSON(), nullable=True),
        sa.Column("breached_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", breach_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("slo_id", "window_start", "window_end", name="uq_service_slo_window"),
        sa.ForeignKeyConstraint(["slo_id"], ["service_slo.id"], ondelete="CASCADE"),
        schema=DB_SCHEMA,
    )

    create_index_if_not_exists(bind, "ix_service_slo_org_enabled", "service_slo", ["org_id", "enabled"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_service_slo_service", "service_slo", ["service", "metric"], schema=DB_SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_service_slo_breaches_org_status",
        "service_slo_breaches",
        ["org_id", "status"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_slo_breaches_slo_id",
        "service_slo_breaches",
        ["slo_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_slo_breaches_window",
        "service_slo_breaches",
        ["window", "window_end"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("service_slo_breaches", schema=DB_SCHEMA)
    op.drop_table("service_slo", schema=DB_SCHEMA)
