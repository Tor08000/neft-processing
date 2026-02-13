"""fuel station prices mvp

Revision ID: 20299660_0175_fuel_station_prices
Revises: 20299650_0174_fuel_station_health_and_rules
Create Date: 2026-02-13 00:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, constraint_exists, index_exists, table_exists

revision = "20299660_0175_fuel_station_prices"
down_revision = "20299650_0174_fuel_station_health_and_rules"
branch_labels = None
depends_on = None

_PRICE_STATUS_CHECK = "ck_fuel_station_prices_status"
_PRICE_SOURCE_CHECK = "ck_fuel_station_prices_source"
_PRICE_POSITIVE_CHECK = "ck_fuel_station_prices_price_positive"
_PRICE_CURRENCY_CHECK = "ck_fuel_station_prices_currency"


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "fuel_station_prices", schema=DB_SCHEMA):
        op.create_table(
            "fuel_station_prices",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("station_id", sa.String(length=36), nullable=False),
            sa.Column("product_code", sa.String(length=32), nullable=False),
            sa.Column("price", sa.Numeric(12, 3), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source", sa.String(length=16), nullable=False, server_default="MANUAL"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_by", sa.String(length=256), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["station_id"], [f"{DB_SCHEMA}.fuel_stations.id"], name="fk_fuel_station_prices_station"),
            schema=DB_SCHEMA,
        )

    if not constraint_exists(bind, "fuel_station_prices", _PRICE_STATUS_CHECK, schema=DB_SCHEMA):
        op.create_check_constraint(
            _PRICE_STATUS_CHECK,
            "fuel_station_prices",
            "status IN ('ACTIVE', 'INACTIVE')",
            schema=DB_SCHEMA,
        )
    if not constraint_exists(bind, "fuel_station_prices", _PRICE_SOURCE_CHECK, schema=DB_SCHEMA):
        op.create_check_constraint(
            _PRICE_SOURCE_CHECK,
            "fuel_station_prices",
            "source IN ('MANUAL', 'IMPORT', 'API')",
            schema=DB_SCHEMA,
        )
    if not constraint_exists(bind, "fuel_station_prices", _PRICE_POSITIVE_CHECK, schema=DB_SCHEMA):
        op.create_check_constraint(
            _PRICE_POSITIVE_CHECK,
            "fuel_station_prices",
            "price > 0",
            schema=DB_SCHEMA,
        )
    if not constraint_exists(bind, "fuel_station_prices", _PRICE_CURRENCY_CHECK, schema=DB_SCHEMA):
        op.create_check_constraint(
            _PRICE_CURRENCY_CHECK,
            "fuel_station_prices",
            "currency = 'RUB'",
            schema=DB_SCHEMA,
        )

    if not index_exists(bind, "ix_fuel_station_prices_station_product_status", schema=DB_SCHEMA):
        op.create_index(
            "ix_fuel_station_prices_station_product_status",
            "fuel_station_prices",
            ["station_id", "product_code", "status"],
            unique=False,
            schema=DB_SCHEMA,
        )
    if not index_exists(bind, "ix_fuel_station_prices_station_status_valid_from", schema=DB_SCHEMA):
        op.create_index(
            "ix_fuel_station_prices_station_status_valid_from",
            "fuel_station_prices",
            ["station_id", "status", "valid_from"],
            unique=False,
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if index_exists(bind, "ix_fuel_station_prices_station_status_valid_from", schema=DB_SCHEMA):
        op.drop_index("ix_fuel_station_prices_station_status_valid_from", table_name="fuel_station_prices", schema=DB_SCHEMA)
    if index_exists(bind, "ix_fuel_station_prices_station_product_status", schema=DB_SCHEMA):
        op.drop_index("ix_fuel_station_prices_station_product_status", table_name="fuel_station_prices", schema=DB_SCHEMA)
    if constraint_exists(bind, "fuel_station_prices", _PRICE_CURRENCY_CHECK, schema=DB_SCHEMA):
        op.drop_constraint(_PRICE_CURRENCY_CHECK, "fuel_station_prices", type_="check", schema=DB_SCHEMA)
    if constraint_exists(bind, "fuel_station_prices", _PRICE_POSITIVE_CHECK, schema=DB_SCHEMA):
        op.drop_constraint(_PRICE_POSITIVE_CHECK, "fuel_station_prices", type_="check", schema=DB_SCHEMA)
    if constraint_exists(bind, "fuel_station_prices", _PRICE_SOURCE_CHECK, schema=DB_SCHEMA):
        op.drop_constraint(_PRICE_SOURCE_CHECK, "fuel_station_prices", type_="check", schema=DB_SCHEMA)
    if constraint_exists(bind, "fuel_station_prices", _PRICE_STATUS_CHECK, schema=DB_SCHEMA):
        op.drop_constraint(_PRICE_STATUS_CHECK, "fuel_station_prices", type_="check", schema=DB_SCHEMA)
    if table_exists(bind, "fuel_station_prices", schema=DB_SCHEMA):
        op.drop_table("fuel_station_prices", schema=DB_SCHEMA)
