"""tariff prices table

Revision ID: 20270201_0020
Revises: 20270101_0019_external_request_logs
Create Date: 2027-02-01 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20270201_0020"
down_revision = "20270101_0019_external_request_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
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
    op.create_index("ix_tariff_prices_tariff_id", "tariff_prices", ["tariff_id"])
    op.create_index("ix_tariff_prices_product_id", "tariff_prices", ["product_id"])
    op.create_index("ix_tariff_prices_partner_id", "tariff_prices", ["partner_id"])
    op.create_index("ix_tariff_prices_azs_id", "tariff_prices", ["azs_id"])
    op.create_index("ix_tariff_prices_valid_from", "tariff_prices", ["valid_from"])
    op.create_index("ix_tariff_prices_valid_to", "tariff_prices", ["valid_to"])
    op.create_index("ix_tariff_prices_priority", "tariff_prices", ["priority"])


def downgrade() -> None:
    op.drop_index("ix_tariff_prices_priority", table_name="tariff_prices")
    op.drop_index("ix_tariff_prices_valid_to", table_name="tariff_prices")
    op.drop_index("ix_tariff_prices_valid_from", table_name="tariff_prices")
    op.drop_index("ix_tariff_prices_azs_id", table_name="tariff_prices")
    op.drop_index("ix_tariff_prices_partner_id", table_name="tariff_prices")
    op.drop_index("ix_tariff_prices_product_id", table_name="tariff_prices")
    op.drop_index("ix_tariff_prices_tariff_id", table_name="tariff_prices")
    op.drop_table("tariff_prices")
