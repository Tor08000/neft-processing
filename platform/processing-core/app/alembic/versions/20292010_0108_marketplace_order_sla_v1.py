"""Marketplace order SLA coupling v1.

Revision ID: 20292010_0108_marketplace_order_sla_v1
Revises: 20292000_0107_marketplace_catalog_v1
Create Date: 2026-02-08 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from app.alembic.helpers import (
    DB_SCHEMA,
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    safe_enum,
    table_exists,
)
from app.db.types import GUID


revision = "20292010_0108_marketplace_order_sla_v1"
down_revision = "20292000_0107_marketplace_catalog_v1"
branch_labels = None
depends_on = None


ORDER_SLA_STATUS = ["OK", "VIOLATION"]
ORDER_SLA_SEVERITY = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ORDER_SLA_CONSEQUENCE_TYPE = ["PENALTY_FEE", "CREDIT_NOTE", "REFUND"]
ORDER_SLA_CONSEQUENCE_STATUS = ["APPLIED", "FAILED"]
MARKETPLACE_SLA_NOTIFICATION_STATUS = ["PENDING", "SENT", "FAILED"]


def _schema_prefix() -> str:
    return f"{DB_SCHEMA}." if DB_SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "order_sla_status", ORDER_SLA_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "order_sla_severity", ORDER_SLA_SEVERITY, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "order_sla_consequence_type", ORDER_SLA_CONSEQUENCE_TYPE, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "order_sla_consequence_status", ORDER_SLA_CONSEQUENCE_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(
        bind,
        "marketplace_sla_notification_status",
        MARKETPLACE_SLA_NOTIFICATION_STATUS,
        schema=DB_SCHEMA,
    )
    ensure_pg_enum_value(bind, "case_event_type", "SLA_ESCALATION_CASE_CREATED", schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "marketplace_order_contract_links",
        sa.Column("order_id", sa.String(length=64), primary_key=True),
        sa.Column("contract_id", GUID(), nullable=False),
        sa.Column("sla_policy_version", sa.Integer(), nullable=True),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("audit_event_id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            [f"{_schema_prefix()}contracts.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_order_contract_links_contract",
        "marketplace_order_contract_links",
        ["contract_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_order_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("partner_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("audit_event_id", GUID(), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_order_events_order",
        "marketplace_order_events",
        ["order_id", "occurred_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_marketplace_order_events_order_type",
        "marketplace_order_events",
        ["order_id", "event_type"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "order_sla_evaluations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("contract_id", GUID(), nullable=False),
        sa.Column("obligation_id", GUID(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("measured_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", safe_enum(bind, "order_sla_status", ORDER_SLA_STATUS), nullable=False),
        sa.Column("breach_reason", sa.Text(), nullable=True),
        sa.Column(
            "breach_severity",
            safe_enum(bind, "order_sla_severity", ORDER_SLA_SEVERITY),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("audit_event_id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            [f"{_schema_prefix()}contracts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["obligation_id"],
            [f"{_schema_prefix()}contract_obligations.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_order_sla_evaluations_order_created",
        "order_sla_evaluations",
        ["order_id", "created_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_order_sla_evaluations_order_obligation",
        "order_sla_evaluations",
        ["order_id", "obligation_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "order_sla_consequences",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("evaluation_id", GUID(), nullable=False),
        sa.Column(
            "consequence_type",
            safe_enum(bind, "order_sla_consequence_type", ORDER_SLA_CONSEQUENCE_TYPE),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("billing_invoice_id", GUID(), nullable=True),
        sa.Column("billing_refund_id", GUID(), nullable=True),
        sa.Column("ledger_tx_id", GUID(), nullable=True),
        sa.Column(
            "status",
            safe_enum(bind, "order_sla_consequence_status", ORDER_SLA_CONSEQUENCE_STATUS),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("audit_event_id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            [f"{_schema_prefix()}order_sla_evaluations.id"],
            ondelete="CASCADE",
        ),
        schema=DB_SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_order_sla_consequences_dedupe",
        "order_sla_consequences",
        ["dedupe_key"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "marketplace_sla_notification_outbox",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("partner_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("payload_redacted", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "marketplace_sla_notification_status",
                MARKETPLACE_SLA_NOTIFICATION_STATUS,
            ),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("audit_event_id", GUID(), nullable=True),
        schema=DB_SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_marketplace_sla_notification_outbox_dedupe",
        "marketplace_sla_notification_outbox",
        ["dedupe_key"],
        schema=DB_SCHEMA,
    )

    if table_exists(bind, "marketplace_orders", schema=DB_SCHEMA):
        if not column_exists(bind, "marketplace_orders", "contract_id", schema=DB_SCHEMA):
            op.add_column(
                "marketplace_orders",
                sa.Column("contract_id", GUID(), nullable=True),
                schema=DB_SCHEMA,
            )
        if not column_exists(bind, "marketplace_orders", "sla_policy_version", schema=DB_SCHEMA):
            op.add_column(
                "marketplace_orders",
                sa.Column("sla_policy_version", sa.Integer(), nullable=True),
                schema=DB_SCHEMA,
            )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("marketplace_sla_notification_outbox", schema=DB_SCHEMA)
    op.drop_table("order_sla_consequences", schema=DB_SCHEMA)
    op.drop_table("order_sla_evaluations", schema=DB_SCHEMA)
    op.drop_table("marketplace_order_events", schema=DB_SCHEMA)
    op.drop_table("marketplace_order_contract_links", schema=DB_SCHEMA)

    if table_exists(bind, "marketplace_orders", schema=DB_SCHEMA):
        if column_exists(bind, "marketplace_orders", "sla_policy_version", schema=DB_SCHEMA):
            op.drop_column("marketplace_orders", "sla_policy_version", schema=DB_SCHEMA)
        if column_exists(bind, "marketplace_orders", "contract_id", schema=DB_SCHEMA):
            op.drop_column("marketplace_orders", "contract_id", schema=DB_SCHEMA)
