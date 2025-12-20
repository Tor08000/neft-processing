"""Add client tariffs and commission rules tables

Revision ID: 20270901_0031_tariff_commission_rules
Revises: 20270831_0030_billing_state_machine
Create Date: 2027-09-01 00:31:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
)
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20270901_0031_tariff_commission_rules"
down_revision = "20270831_0030_billing_state_machine"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "client_tariffs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("tariff_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.tariff_plans.id"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_client_tariffs_client_id": ["client_id"],
        "ix_client_tariffs_tariff_id": ["tariff_id"],
        "ix_client_tariffs_valid_from": ["valid_from"],
        "ix_client_tariffs_valid_to": ["valid_to"],
        "ix_client_tariffs_priority": ["priority"],
    }.items():
        create_index_if_not_exists(bind, index_name, "client_tariffs", columns, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "commission_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tariff_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.tariff_plans.id"), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=True),
        sa.Column("partner_id", sa.String(length=64), nullable=True),
        sa.Column("azs_id", sa.String(length=64), nullable=True),
        sa.Column("platform_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("partner_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("promo_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    for index_name, columns in {
        "ix_commission_rules_tariff_id": ["tariff_id"],
        "ix_commission_rules_product_id": ["product_id"],
        "ix_commission_rules_partner_id": ["partner_id"],
        "ix_commission_rules_azs_id": ["azs_id"],
        "ix_commission_rules_valid_from": ["valid_from"],
        "ix_commission_rules_valid_to": ["valid_to"],
        "ix_commission_rules_priority": ["priority"],
    }.items():
        create_index_if_not_exists(bind, index_name, "commission_rules", columns, schema=SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()

    for index_name in (
        "ix_commission_rules_priority",
        "ix_commission_rules_valid_to",
        "ix_commission_rules_valid_from",
        "ix_commission_rules_azs_id",
        "ix_commission_rules_partner_id",
        "ix_commission_rules_product_id",
        "ix_commission_rules_tariff_id",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)
    drop_table_if_exists(bind, "commission_rules", schema=SCHEMA)

    for index_name in (
        "ix_client_tariffs_priority",
        "ix_client_tariffs_valid_to",
        "ix_client_tariffs_valid_from",
        "ix_client_tariffs_tariff_id",
        "ix_client_tariffs_client_id",
    ):
        drop_index_if_exists(bind, index_name, schema=SCHEMA)
    drop_table_if_exists(bind, "client_tariffs", schema=SCHEMA)
