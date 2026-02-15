"""station margin daily aggregates

Revision ID: 20299680_0177_station_margin_day
Revises: 20299670_0176_geo_station_metrics_daily
Create Date: 2026-02-15 08:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, constraint_exists, index_exists, table_exists

revision = "20299680_0177_station_margin_day"
down_revision = "20299670_0176_geo_station_metrics_daily"
branch_labels = None
depends_on = None

_UNIQUE = "uq_station_margin_day_day_station"


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "station_margin_day", schema=DB_SCHEMA):
        op.create_table(
            "station_margin_day",
            sa.Column("day", sa.Date(), nullable=False),
            sa.Column("station_id", sa.String(length=36), nullable=False),
            sa.Column("revenue_sum", sa.Float(), nullable=False, server_default="0"),
            sa.Column("cost_sum", sa.Float(), nullable=False, server_default="0"),
            sa.Column("gross_margin", sa.Float(), nullable=False, server_default="0"),
            sa.Column("tx_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP") if bind.dialect.name == "sqlite" else sa.text("now()"),
            ),
            sa.PrimaryKeyConstraint("day", "station_id", name="pk_station_margin_day"),
            schema=DB_SCHEMA,
        )

    if bind.dialect.name != "sqlite" and not constraint_exists(bind, "station_margin_day", _UNIQUE, schema=DB_SCHEMA):
        op.create_unique_constraint(_UNIQUE, "station_margin_day", ["day", "station_id"], schema=DB_SCHEMA)

    if not index_exists(bind, "ix_station_margin_day_day", schema=DB_SCHEMA):
        op.create_index("ix_station_margin_day_day", "station_margin_day", ["day"], unique=False, schema=DB_SCHEMA)
    if not index_exists(bind, "ix_station_margin_day_station_day", schema=DB_SCHEMA):
        op.create_index(
            "ix_station_margin_day_station_day", "station_margin_day", ["station_id", "day"], unique=False, schema=DB_SCHEMA
        )


def downgrade() -> None:
    bind = op.get_bind()

    if index_exists(bind, "ix_station_margin_day_station_day", schema=DB_SCHEMA):
        op.drop_index("ix_station_margin_day_station_day", table_name="station_margin_day", schema=DB_SCHEMA)
    if index_exists(bind, "ix_station_margin_day_day", schema=DB_SCHEMA):
        op.drop_index("ix_station_margin_day_day", table_name="station_margin_day", schema=DB_SCHEMA)

    if bind.dialect.name != "sqlite" and constraint_exists(bind, "station_margin_day", _UNIQUE, schema=DB_SCHEMA):
        op.drop_constraint(_UNIQUE, "station_margin_day", type_="unique", schema=DB_SCHEMA)

    if table_exists(bind, "station_margin_day", schema=DB_SCHEMA):
        op.drop_table("station_margin_day", schema=DB_SCHEMA)
