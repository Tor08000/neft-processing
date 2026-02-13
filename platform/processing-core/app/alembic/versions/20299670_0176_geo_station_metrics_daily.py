"""geo station metrics daily aggregates

Revision ID: 20299670_0176_geo_station_metrics_daily
Revises: 20299660_0175_fuel_station_prices
Create Date: 2026-02-13 02:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, constraint_exists, index_exists, table_exists

revision = "20299670_0176_geo_station_metrics_daily"
down_revision = "20299660_0175_fuel_station_prices"
branch_labels = None
depends_on = None

_UNIQUE = "uq_geo_station_metrics_daily_day_station"


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "geo_station_metrics_daily", schema=DB_SCHEMA):
        op.create_table(
            "geo_station_metrics_daily",
            sa.Column("day", sa.Date(), nullable=False),
            sa.Column("station_id", sa.String(length=36), nullable=False),
            sa.Column("tx_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("captured_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("declined_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("amount_sum", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("liters_sum", sa.Numeric(14, 3), nullable=False, server_default="0"),
            sa.Column("risk_red_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("risk_yellow_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP") if bind.dialect.name == "sqlite" else sa.text("now()"),
            ),
            sa.PrimaryKeyConstraint("day", "station_id", name="pk_geo_station_metrics_daily"),
            schema=DB_SCHEMA,
        )

    if bind.dialect.name != "sqlite" and not constraint_exists(bind, "geo_station_metrics_daily", _UNIQUE, schema=DB_SCHEMA):
        op.create_unique_constraint(
            _UNIQUE,
            "geo_station_metrics_daily",
            ["day", "station_id"],
            schema=DB_SCHEMA,
        )

    if not index_exists(bind, "ix_geo_station_metrics_daily_day", schema=DB_SCHEMA):
        op.create_index("ix_geo_station_metrics_daily_day", "geo_station_metrics_daily", ["day"], unique=False, schema=DB_SCHEMA)
    if not index_exists(bind, "ix_geo_station_metrics_daily_station_day", schema=DB_SCHEMA):
        op.create_index(
            "ix_geo_station_metrics_daily_station_day",
            "geo_station_metrics_daily",
            ["station_id", "day"],
            unique=False,
            schema=DB_SCHEMA,
        )
    if not index_exists(bind, "ix_geo_station_metrics_daily_day_amount_sum", schema=DB_SCHEMA):
        op.create_index(
            "ix_geo_station_metrics_daily_day_amount_sum",
            "geo_station_metrics_daily",
            ["day", "amount_sum"],
            unique=False,
            schema=DB_SCHEMA,
        )
    if not index_exists(bind, "ix_geo_station_metrics_daily_day_tx_count", schema=DB_SCHEMA):
        op.create_index(
            "ix_geo_station_metrics_daily_day_tx_count",
            "geo_station_metrics_daily",
            ["day", "tx_count"],
            unique=False,
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if index_exists(bind, "ix_geo_station_metrics_daily_day_tx_count", schema=DB_SCHEMA):
        op.drop_index("ix_geo_station_metrics_daily_day_tx_count", table_name="geo_station_metrics_daily", schema=DB_SCHEMA)
    if index_exists(bind, "ix_geo_station_metrics_daily_day_amount_sum", schema=DB_SCHEMA):
        op.drop_index("ix_geo_station_metrics_daily_day_amount_sum", table_name="geo_station_metrics_daily", schema=DB_SCHEMA)
    if index_exists(bind, "ix_geo_station_metrics_daily_station_day", schema=DB_SCHEMA):
        op.drop_index("ix_geo_station_metrics_daily_station_day", table_name="geo_station_metrics_daily", schema=DB_SCHEMA)
    if index_exists(bind, "ix_geo_station_metrics_daily_day", schema=DB_SCHEMA):
        op.drop_index("ix_geo_station_metrics_daily_day", table_name="geo_station_metrics_daily", schema=DB_SCHEMA)

    if bind.dialect.name != "sqlite" and constraint_exists(bind, "geo_station_metrics_daily", _UNIQUE, schema=DB_SCHEMA):
        op.drop_constraint(_UNIQUE, "geo_station_metrics_daily", type_="unique", schema=DB_SCHEMA)

    if table_exists(bind, "geo_station_metrics_daily", schema=DB_SCHEMA):
        op.drop_table("geo_station_metrics_daily", schema=DB_SCHEMA)
