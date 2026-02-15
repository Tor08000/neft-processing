"""station risk stability streak metadata

Revision ID: 20299710_0180_station_risk_streaks
Revises: 20299700_0179_station_health_risk_automation
Create Date: 2026-02-16 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists

revision = "20299710_0180_station_risk_streaks"
down_revision = "20299700_0179_station_health_risk_automation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists(bind, "fuel_stations", "risk_red_clear_streak_days", schema=DB_SCHEMA):
        op.add_column(
            "fuel_stations",
            sa.Column("risk_red_clear_streak_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
            schema=DB_SCHEMA,
        )

    if not column_exists(bind, "fuel_stations", "risk_yellow_clear_streak_days", schema=DB_SCHEMA):
        op.add_column(
            "fuel_stations",
            sa.Column("risk_yellow_clear_streak_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
            schema=DB_SCHEMA,
        )

    if not column_exists(bind, "fuel_stations", "risk_last_eval_day", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("risk_last_eval_day", sa.Date(), nullable=True), schema=DB_SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()

    for name in ("risk_last_eval_day", "risk_yellow_clear_streak_days", "risk_red_clear_streak_days"):
        if column_exists(bind, "fuel_stations", name, schema=DB_SCHEMA):
            op.drop_column("fuel_stations", name, schema=DB_SCHEMA)
