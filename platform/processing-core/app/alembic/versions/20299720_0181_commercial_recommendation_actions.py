"""commercial recommendation workflow actions

Revision ID: 20299720_0181_commercial_recommendation_actions
Revises: 20299710_0180_station_risk_streaks
Create Date: 2026-02-16 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, index_exists, table_exists

revision = "20299720_0181_commercial_recommendation_actions"
down_revision = "20299710_0180_station_risk_streaks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "commercial_recommendation_actions", schema=DB_SCHEMA):
        op.create_table(
            "commercial_recommendation_actions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("rec_id", sa.String(length=128), nullable=False),
            sa.Column("action_type", sa.String(length=16), nullable=False),
            sa.Column("actor", sa.String(length=256), nullable=True),
            sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("meta", sa.JSON(), nullable=True),
            schema=DB_SCHEMA,
        )

    if not index_exists(bind, "ix_commercial_recommendation_actions_rec_ts", schema=DB_SCHEMA):
        op.create_index(
            "ix_commercial_recommendation_actions_rec_ts",
            "commercial_recommendation_actions",
            ["rec_id", "ts"],
            unique=False,
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if index_exists(bind, "ix_commercial_recommendation_actions_rec_ts", schema=DB_SCHEMA):
        op.drop_index(
            "ix_commercial_recommendation_actions_rec_ts",
            table_name="commercial_recommendation_actions",
            schema=DB_SCHEMA,
        )

    if table_exists(bind, "commercial_recommendation_actions", schema=DB_SCHEMA):
        op.drop_table("commercial_recommendation_actions", schema=DB_SCHEMA)
