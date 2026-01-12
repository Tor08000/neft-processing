"""tariff prices table

Revision ID: 20270201_0020
Revises: 20270101_0019_external_request_logs
Create Date: 2027-02-01 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
    table_exists,
)


# revision identifiers, used by Alembic.
revision = "20270201_0020"
down_revision = "20270101_0019_external_request_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "tariff_prices",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("tariff_id", sa.String(length=64), sa.ForeignKey("tariff_plans.id"), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("partner_id", sa.String(length=64), nullable=True),
        sa.Column("azs_id", sa.String(length=64), nullable=True),
        sa.Column("price_per_liter", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_price_per_liter", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    create_index_if_not_exists(bind, "ix_tariff_prices_tariff_id", "tariff_prices", ["tariff_id"])
    create_index_if_not_exists(bind, "ix_tariff_prices_product_id", "tariff_prices", ["product_id"])
    create_index_if_not_exists(bind, "ix_tariff_prices_partner_id", "tariff_prices", ["partner_id"])
    create_index_if_not_exists(bind, "ix_tariff_prices_azs_id", "tariff_prices", ["azs_id"])
    create_index_if_not_exists(bind, "ix_tariff_prices_valid_from", "tariff_prices", ["valid_from"])
    create_index_if_not_exists(bind, "ix_tariff_prices_valid_to", "tariff_prices", ["valid_to"])
    create_index_if_not_exists(bind, "ix_tariff_prices_priority", "tariff_prices", ["priority"])


def downgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "tariff_prices"):
        drop_index_if_exists(bind, "ix_tariff_prices_priority")
        drop_index_if_exists(bind, "ix_tariff_prices_valid_to")
        drop_index_if_exists(bind, "ix_tariff_prices_valid_from")
        drop_index_if_exists(bind, "ix_tariff_prices_azs_id")
        drop_index_if_exists(bind, "ix_tariff_prices_partner_id")
        drop_index_if_exists(bind, "ix_tariff_prices_product_id")
        drop_index_if_exists(bind, "ix_tariff_prices_tariff_id")
        drop_table_if_exists(bind, "tariff_prices")
