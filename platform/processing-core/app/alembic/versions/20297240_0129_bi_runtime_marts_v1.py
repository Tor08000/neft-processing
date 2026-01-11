"""BI runtime marts and sync tables.

Revision ID: 20297240_0129_bi_runtime_marts_v1
Revises: 20297230_0128_edo_v2
Create Date: 2029-09-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    is_postgres,
    safe_enum,
    table_exists,
)


revision = "20297240_0129_bi_runtime_marts_v1"
down_revision = "20297230_0128_edo_v2"
branch_labels = None
depends_on = None

BI_SCHEMA = "bi"


def _json_type() -> sa.JSON:
    if is_postgres(op.get_bind()):
        return postgresql.JSONB()
    return sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    if is_postgres(bind):
        bind.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {BI_SCHEMA}")

    schema = BI_SCHEMA if is_postgres(bind) else None
    ensure_pg_enum(bind, "bi_sync_run_type", ["INIT", "INCREMENTAL"], schema=schema)
    ensure_pg_enum(bind, "bi_sync_run_status", ["RUNNING", "COMPLETED", "FAILED"], schema=schema)

    if not table_exists(bind, "bi_watermarks", schema=schema):
        create_table_if_not_exists(
            bind,
            "bi_watermarks",
            sa.Column("name", sa.String(128), primary_key=True),
            sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            schema=schema,
        )

    if not table_exists(bind, "bi_sync_runs", schema=schema):
        run_type = safe_enum(bind, "bi_sync_run_type", ["INIT", "INCREMENTAL"], schema=schema)
        run_status = safe_enum(bind, "bi_sync_run_status", ["RUNNING", "COMPLETED", "FAILED"], schema=schema)
        create_table_if_not_exists(
            bind,
            "bi_sync_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("type", run_type, nullable=False),
            sa.Column("status", run_status, nullable=False),
            sa.Column("rows_written", sa.BigInteger(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            schema=schema,
        )

    if not table_exists(bind, "bi_mart_versions", schema=schema):
        create_table_if_not_exists(
            bind,
            "bi_mart_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("mart_name", sa.String(128), nullable=False),
            sa.Column("version", sa.String(32), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            schema=schema,
        )
        create_index_if_not_exists(bind, "ix_bi_mart_versions_name", "bi_mart_versions", ["mart_name"], schema=schema)

    if not table_exists(bind, "mart_finance_daily", schema=schema):
        create_table_if_not_exists(
            bind,
            "mart_finance_daily",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("gross_revenue", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("net_revenue", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("commission_income", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("vat", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("refunds", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("penalties", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("margin", sa.BigInteger(), nullable=False, server_default="0"),
            schema=schema,
        )
        create_index_if_not_exists(
            bind, "ix_mart_finance_daily_tenant_date", "mart_finance_daily", ["tenant_id", "date"], schema=schema
        )

    if not table_exists(bind, "mart_cashflow", schema=schema):
        create_table_if_not_exists(
            bind,
            "mart_cashflow",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("inflow", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("outflow", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("net_cashflow", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("balance_estimated", sa.BigInteger(), nullable=False, server_default="0"),
            schema=schema,
        )
        create_index_if_not_exists(
            bind, "ix_mart_cashflow_tenant_date", "mart_cashflow", ["tenant_id", "date"], schema=schema
        )

    if not table_exists(bind, "mart_ops_sla", schema=schema):
        create_table_if_not_exists(
            bind,
            "mart_ops_sla",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("total_orders", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("sla_breaches", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("avg_resolution_time", sa.Numeric(12, 4), nullable=True),
            sa.Column("p95_resolution_time", sa.Numeric(12, 4), nullable=True),
            sa.Column("top_partners_by_breaches", _json_type(), nullable=True),
            schema=schema,
        )
        create_index_if_not_exists(
            bind, "ix_mart_ops_sla_tenant_date", "mart_ops_sla", ["tenant_id", "date"], schema=schema
        )

    if not table_exists(bind, "mart_partner_performance", schema=schema):
        create_table_if_not_exists(
            bind,
            "mart_partner_performance",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("partner_id", sa.String(64), nullable=False),
            sa.Column("period", sa.Date(), nullable=False),
            sa.Column("orders_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("revenue", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("penalties", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("payout_amount", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("sla_score", sa.Numeric(6, 4), nullable=True),
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_mart_partner_performance_tenant_partner_period",
            "mart_partner_performance",
            ["tenant_id", "partner_id", "period"],
            schema=schema,
        )

    if not table_exists(bind, "mart_client_spend", schema=schema):
        create_table_if_not_exists(
            bind,
            "mart_client_spend",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("period", sa.Date(), nullable=False),
            sa.Column("spend_total", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("spend_by_product", _json_type(), nullable=True),
            sa.Column("fuel_spend", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("marketplace_spend", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("avg_ticket", sa.BigInteger(), nullable=False, server_default="0"),
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_mart_client_spend_tenant_client_period",
            "mart_client_spend",
            ["tenant_id", "client_id", "period"],
            schema=schema,
        )

    if not table_exists(bind, "bi_exports", schema=schema):
        create_table_if_not_exists(
            bind,
            "bi_exports",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("mart_name", sa.String(128), nullable=False),
            sa.Column("period", sa.String(64), nullable=False),
            sa.Column("format", sa.String(16), nullable=False),
            sa.Column("file_ref", sa.String(512), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            schema=schema,
        )
        create_index_if_not_exists(bind, "ix_bi_exports_tenant", "bi_exports", ["tenant_id"], schema=schema)


def downgrade() -> None:
    schema = BI_SCHEMA if is_postgres(op.get_bind()) else None
    op.drop_table("bi_exports", schema=schema)
    op.drop_table("mart_client_spend", schema=schema)
    op.drop_table("mart_partner_performance", schema=schema)
    op.drop_table("mart_ops_sla", schema=schema)
    op.drop_table("mart_cashflow", schema=schema)
    op.drop_table("mart_finance_daily", schema=schema)
    op.drop_table("bi_mart_versions", schema=schema)
    op.drop_table("bi_sync_runs", schema=schema)
    op.drop_table("bi_watermarks", schema=schema)
