"""BI pricing intelligence read models.

Revision ID: 20291650_0087_bi_pricing_intelligence_v1
Revises: 20291640_0086_bi_mart_v1
Create Date: 2025-02-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    is_postgres,
    table_exists,
)


# revision identifiers, used by Alembic.
revision = "20291650_0087_bi_pricing_intelligence_v1"
down_revision = "20291640_0086_bi_mart_v1"
branch_labels = None
depends_on = None


BI_SCHEMA = "bi"


def _schema_name(bind) -> str | None:
    if is_postgres(bind):
        return BI_SCHEMA
    return None


def upgrade() -> None:
    bind = op.get_bind()

    if is_postgres(bind):
        bind.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {BI_SCHEMA}")

    schema = _schema_name(bind)

    if not table_exists(bind, "bi_price_version_metrics", schema=schema):
        create_table_if_not_exists(
            bind,
            "bi_price_version_metrics",
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("partner_id", sa.String(64), primary_key=True),
            sa.Column("price_version_id", sa.String(64), primary_key=True),
            sa.Column("date", sa.Date(), primary_key=True),
            sa.Column("orders_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("completed_orders_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("revenue_total", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("avg_order_value", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("refunds_count", sa.BigInteger(), nullable=False, server_default="0"),
            schema=schema,
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_bi_price_version_metric",
            "bi_price_version_metrics",
            ["partner_id", "price_version_id", "date"],
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_price_version_partner_date",
            "bi_price_version_metrics",
            ["partner_id", "date"],
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_price_version_partner_version_date",
            "bi_price_version_metrics",
            ["partner_id", "price_version_id", "date"],
            schema=schema,
        )

    if not table_exists(bind, "bi_offer_metrics", schema=schema):
        create_table_if_not_exists(
            bind,
            "bi_offer_metrics",
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("partner_id", sa.String(64), primary_key=True),
            sa.Column("offer_id", sa.String(64), primary_key=True),
            sa.Column("date", sa.Date(), primary_key=True),
            sa.Column("views_count", sa.BigInteger(), nullable=True),
            sa.Column("orders_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("conversion_rate", sa.Numeric(10, 4), nullable=True),
            sa.Column("avg_price", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("revenue_total", sa.BigInteger(), nullable=False, server_default="0"),
            schema=schema,
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_bi_offer_metric",
            "bi_offer_metrics",
            ["partner_id", "offer_id", "date"],
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_offer_partner_date",
            "bi_offer_metrics",
            ["partner_id", "date"],
            schema=schema,
        )
        create_index_if_not_exists(
            bind,
            "ix_bi_offer_partner_offer_date",
            "bi_offer_metrics",
            ["partner_id", "offer_id", "date"],
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    schema = _schema_name(bind)
    if is_postgres(bind):
        op.drop_index("ix_bi_offer_partner_offer_date", table_name="bi_offer_metrics", schema=schema)
        op.drop_index("ix_bi_offer_partner_date", table_name="bi_offer_metrics", schema=schema)
        op.drop_index("uq_bi_offer_metric", table_name="bi_offer_metrics", schema=schema)
        op.drop_table("bi_offer_metrics", schema=schema)
        op.drop_index("ix_bi_price_version_partner_version_date", table_name="bi_price_version_metrics", schema=schema)
        op.drop_index("ix_bi_price_version_partner_date", table_name="bi_price_version_metrics", schema=schema)
        op.drop_index("uq_bi_price_version_metric", table_name="bi_price_version_metrics", schema=schema)
        op.drop_table("bi_price_version_metrics", schema=schema)
