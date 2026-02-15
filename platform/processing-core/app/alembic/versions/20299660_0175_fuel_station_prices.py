"""fuel station prices and audit

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
_PRICE_VALID_WINDOW_CHECK = "ck_fuel_station_prices_valid_window"


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "fuel_station_prices", schema=DB_SCHEMA):
        op.create_table(
            "fuel_station_prices",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("station_id", sa.String(length=36), nullable=False),
            sa.Column("product_code", sa.String(length=32), nullable=False),
            sa.Column("price", sa.Numeric(14, 3), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source", sa.String(length=16), nullable=False, server_default="MANUAL"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["station_id"], [f"{DB_SCHEMA}.fuel_stations.id"], name="fk_fuel_station_prices_station"),
            sa.UniqueConstraint("station_id", "product_code", "valid_from", "valid_to", name="uq_fuel_station_prices_station_product_validity"),
            schema=DB_SCHEMA,
        )

    if not table_exists(bind, "fuel_station_price_audit", schema=DB_SCHEMA):
        op.create_table(
            "fuel_station_price_audit",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("station_id", sa.String(length=36), nullable=False),
            sa.Column("product_code", sa.String(length=32), nullable=False),
            sa.Column("action", sa.String(length=16), nullable=False),
            sa.Column("actor", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=16), nullable=False),
            sa.Column("before", sa.JSON(), nullable=True),
            sa.Column("after", sa.JSON(), nullable=True),
            sa.Column("request_id", sa.Text(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["station_id"], [f"{DB_SCHEMA}.fuel_stations.id"], name="fk_fuel_station_price_audit_station"),
            schema=DB_SCHEMA,
        )

    if not constraint_exists(bind, "fuel_station_prices", _PRICE_STATUS_CHECK, schema=DB_SCHEMA):
        op.create_check_constraint(_PRICE_STATUS_CHECK, "fuel_station_prices", "status IN ('ACTIVE', 'INACTIVE')", schema=DB_SCHEMA)
    if not constraint_exists(bind, "fuel_station_prices", _PRICE_SOURCE_CHECK, schema=DB_SCHEMA):
        op.create_check_constraint(_PRICE_SOURCE_CHECK, "fuel_station_prices", "source IN ('MANUAL', 'IMPORT', 'API')", schema=DB_SCHEMA)
    if not constraint_exists(bind, "fuel_station_prices", _PRICE_POSITIVE_CHECK, schema=DB_SCHEMA):
        op.create_check_constraint(_PRICE_POSITIVE_CHECK, "fuel_station_prices", "price > 0", schema=DB_SCHEMA)
    if not constraint_exists(bind, "fuel_station_prices", _PRICE_CURRENCY_CHECK, schema=DB_SCHEMA):
        op.create_check_constraint(_PRICE_CURRENCY_CHECK, "fuel_station_prices", "currency IN ('RUB')", schema=DB_SCHEMA)
    if not constraint_exists(bind, "fuel_station_prices", _PRICE_VALID_WINDOW_CHECK, schema=DB_SCHEMA):
        op.create_check_constraint(
            _PRICE_VALID_WINDOW_CHECK,
            "fuel_station_prices",
            "valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from",
            schema=DB_SCHEMA,
        )

    if not index_exists(bind, "idx_prices_station_product_active", schema=DB_SCHEMA):
        op.create_index("idx_prices_station_product_active", "fuel_station_prices", ["station_id", "product_code", "status"], unique=False, schema=DB_SCHEMA)
    if not index_exists(bind, "idx_prices_station_active", schema=DB_SCHEMA):
        op.create_index("idx_prices_station_active", "fuel_station_prices", ["station_id", "status"], unique=False, schema=DB_SCHEMA)
    if not index_exists(bind, "idx_prices_valid_from", schema=DB_SCHEMA):
        op.create_index("idx_prices_valid_from", "fuel_station_prices", ["valid_from"], unique=False, schema=DB_SCHEMA)

    if not index_exists(bind, "ix_fuel_station_price_audit_station_ts", schema=DB_SCHEMA):
        op.create_index("ix_fuel_station_price_audit_station_ts", "fuel_station_price_audit", ["station_id", "ts"], unique=False, schema=DB_SCHEMA)
    if not index_exists(bind, "ix_fuel_station_price_audit_product_ts", schema=DB_SCHEMA):
        op.create_index("ix_fuel_station_price_audit_product_ts", "fuel_station_price_audit", ["product_code", "ts"], unique=False, schema=DB_SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    for idx, table in [
        ("ix_fuel_station_price_audit_product_ts", "fuel_station_price_audit"),
        ("ix_fuel_station_price_audit_station_ts", "fuel_station_price_audit"),
        ("idx_prices_valid_from", "fuel_station_prices"),
        ("idx_prices_station_active", "fuel_station_prices"),
        ("idx_prices_station_product_active", "fuel_station_prices"),
    ]:
        if index_exists(bind, idx, schema=DB_SCHEMA):
            op.drop_index(idx, table_name=table, schema=DB_SCHEMA)

    for ck in [_PRICE_VALID_WINDOW_CHECK, _PRICE_CURRENCY_CHECK, _PRICE_POSITIVE_CHECK, _PRICE_SOURCE_CHECK, _PRICE_STATUS_CHECK]:
        if constraint_exists(bind, "fuel_station_prices", ck, schema=DB_SCHEMA):
            op.drop_constraint(ck, "fuel_station_prices", type_="check", schema=DB_SCHEMA)

    if table_exists(bind, "fuel_station_price_audit", schema=DB_SCHEMA):
        op.drop_table("fuel_station_price_audit", schema=DB_SCHEMA)
    if table_exists(bind, "fuel_station_prices", schema=DB_SCHEMA):
        op.drop_table("fuel_station_prices", schema=DB_SCHEMA)
