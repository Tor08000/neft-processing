"""BI mart tables and exports.

Revision ID: 20291640_0086_bi_mart_v1
Revises: 20291630_0085_erp_accounting_exports
Create Date: 2025-02-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    is_postgres,
    safe_enum,
    table_exists,
)


# revision identifiers, used by Alembic.
revision = "20291640_0086_bi_mart_v1"
down_revision = "20291630_0085_erp_accounting_exports"
branch_labels = None
depends_on = None


BI_SCHEMA = "bi"

BI_SCOPE_TYPES = ["TENANT", "CLIENT", "PARTNER", "STATION"]
BI_EXPORT_KINDS = ["ORDERS", "PAYOUTS", "DECLINES", "DAILY_METRICS"]
BI_EXPORT_FORMATS = ["CSV"]
BI_EXPORT_STATUSES = ["CREATED", "GENERATED", "DELIVERED", "CONFIRMED", "FAILED"]

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _schema_name(bind) -> str | None:
    if is_postgres(bind):
        return BI_SCHEMA
    return None


def upgrade() -> None:
    bind = op.get_bind()

    if is_postgres(bind):
        bind.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {BI_SCHEMA}")

    schema = _schema_name(bind)
    ensure_pg_enum(bind, "bi_scope_type", BI_SCOPE_TYPES, schema=schema)
    ensure_pg_enum(bind, "bi_export_kind", BI_EXPORT_KINDS, schema=schema)
    ensure_pg_enum(bind, "bi_export_format", BI_EXPORT_FORMATS, schema=schema)
    ensure_pg_enum(bind, "bi_export_status", BI_EXPORT_STATUSES, schema=schema)

    if not table_exists(bind, "bi_cursors", schema=schema):
        create_table_if_not_exists(
            bind,
            "bi_cursors",
            sa.Column("name", sa.String(64), primary_key=True),
            sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            schema=schema,
        )

    if not table_exists(bind, "bi_order_events", schema=schema):
        create_table_if_not_exists(
            bind,
            "bi_order_events",
            sa.Column("event_id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("client_id", sa.String(64), nullable=True),
            sa.Column("partner_id", sa.String(64), nullable=True),
            sa.Column("order_id", sa.String(64), nullable=True),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("amount", sa.BigInteger(), nullable=True),
            sa.Column("currency", sa.String(8), nullable=True),
            sa.Column("service_id", sa.String(64), nullable=True),
            sa.Column("offer_id", sa.String(64), nullable=True),
            sa.Column("status_after", sa.String(64), nullable=True),
            sa.Column("correlation_id", sa.String(128), nullable=True),
            sa.Column("payload", JSON_TYPE, nullable=True),
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_order_events_tenant_occurred",
            "bi_order_events",
            ["tenant_id", "occurred_at"],
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_order_events_partner_occurred",
            "bi_order_events",
            ["partner_id", "occurred_at"],
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_order_events_client_occurred",
            "bi_order_events",
            ["client_id", "occurred_at"],
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_order_events_order",
            "bi_order_events",
            ["order_id"],
            schema=schema,
        )

    if not table_exists(bind, "bi_payout_events", schema=schema):
        create_table_if_not_exists(
            bind,
            "bi_payout_events",
            sa.Column("event_id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("partner_id", sa.String(64), nullable=True),
            sa.Column("settlement_id", sa.String(64), nullable=True),
            sa.Column("payout_batch_id", sa.String(64), nullable=True),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("amount_gross", sa.BigInteger(), nullable=True),
            sa.Column("amount_net", sa.BigInteger(), nullable=True),
            sa.Column("amount_commission", sa.BigInteger(), nullable=True),
            sa.Column("currency", sa.String(8), nullable=True),
            sa.Column("correlation_id", sa.String(128), nullable=True),
            sa.Column("payload", JSON_TYPE, nullable=True),
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_payout_events_tenant_occurred",
            "bi_payout_events",
            ["tenant_id", "occurred_at"],
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_payout_events_partner_occurred",
            "bi_payout_events",
            ["partner_id", "occurred_at"],
            schema=schema,
        )

    if not table_exists(bind, "bi_decline_events", schema=schema):
        create_table_if_not_exists(
            bind,
            "bi_decline_events",
            sa.Column("operation_id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("client_id", sa.String(64), nullable=True),
            sa.Column("partner_id", sa.String(64), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("primary_reason", sa.String(255), nullable=True),
            sa.Column("secondary_reasons", JSON_TYPE, nullable=True),
            sa.Column("amount", sa.BigInteger(), nullable=True),
            sa.Column("product_type", sa.String(32), nullable=True),
            sa.Column("station_id", sa.String(64), nullable=True),
            sa.Column("correlation_id", sa.String(128), nullable=True),
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_decline_events_tenant_occurred",
            "bi_decline_events",
            ["tenant_id", "occurred_at"],
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_decline_events_reason",
            "bi_decline_events",
            ["primary_reason"],
            schema=schema,
        )

    if not table_exists(bind, "bi_daily_metrics", schema=schema):
        scope_type = safe_enum(bind, "bi_scope_type", BI_SCOPE_TYPES, schema=schema)
        create_table_if_not_exists(
            bind,
            "bi_daily_metrics",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("scope_type", scope_type, nullable=False),
            sa.Column("scope_id", sa.String(64), nullable=False),
            sa.Column("spend_total", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("orders_total", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("orders_completed", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("refunds_total", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("payouts_total", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("declines_total", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("top_primary_reason", sa.String(255), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "tenant_id",
                "date",
                "scope_type",
                "scope_id",
                name="uq_bi_daily_scope",
            ),
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_daily_metrics_tenant_date",
            "bi_daily_metrics",
            ["tenant_id", "date"],
            schema=schema,
        )

    if not table_exists(bind, "bi_export_batches", schema=schema):
        export_kind = safe_enum(bind, "bi_export_kind", BI_EXPORT_KINDS, schema=schema)
        export_format = safe_enum(bind, "bi_export_format", BI_EXPORT_FORMATS, schema=schema)
        export_status = safe_enum(bind, "bi_export_status", BI_EXPORT_STATUSES, schema=schema)
        scope_type = safe_enum(bind, "bi_scope_type", BI_SCOPE_TYPES, schema=schema)
        create_table_if_not_exists(
            bind,
            "bi_export_batches",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("kind", export_kind, nullable=False),
            sa.Column("scope_type", scope_type, nullable=True),
            sa.Column("scope_id", sa.String(64), nullable=True),
            sa.Column("date_from", sa.Date(), nullable=False),
            sa.Column("date_to", sa.Date(), nullable=False),
            sa.Column("format", export_format, nullable=False),
            sa.Column("status", export_status, nullable=False),
            sa.Column("object_key", sa.String(512), nullable=True),
            sa.Column("bucket", sa.String(128), nullable=True),
            sa.Column("sha256", sa.String(64), nullable=True),
            sa.Column("row_count", sa.BigInteger(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_export_batches_tenant",
            "bi_export_batches",
            ["tenant_id"],
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    schema = _schema_name(bind)

    op.drop_table("bi_export_batches", schema=schema)
    op.drop_table("bi_daily_metrics", schema=schema)
    op.drop_table("bi_decline_events", schema=schema)
    op.drop_table("bi_payout_events", schema=schema)
    op.drop_table("bi_order_events", schema=schema)
    op.drop_table("bi_cursors", schema=schema)

