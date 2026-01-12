"""fleet intelligence trends v2

Revision ID: 20291580_0080_fleet_intelligence_trends_v2
Revises: 20291570_0079_fleet_intelligence_v1
Create Date: 2029-05-80 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_table_if_not_exists, ensure_pg_enum, table_exists
from db.schema import resolve_db_schema


SCHEMA = resolve_db_schema().schema

revision = "20291580_0080_fleet_intelligence_trends_v2"
down_revision = "20291570_0079_fleet_intelligence_v1"
branch_labels = None
depends_on = None

TREND_ENTITY_TYPE = ["DRIVER", "VEHICLE", "STATION"]
TREND_METRIC = ["DRIVER_BEHAVIOR_SCORE", "STATION_TRUST_SCORE", "VEHICLE_EFFICIENCY_DELTA_PCT"]
TREND_WINDOW = ["D7", "D30", "ROLLING"]
TREND_LABEL = ["IMPROVING", "STABLE", "DEGRADING", "UNKNOWN"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "fi_trend_entity_type", TREND_ENTITY_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_trend_metric", TREND_METRIC, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_trend_window", TREND_WINDOW, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_trend_label", TREND_LABEL, schema=SCHEMA)

    if not table_exists(bind, "fi_trend_snapshots", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_trend_snapshots",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("client_id", sa.String(64), nullable=True),
                sa.Column(
                    "entity_type",
                    postgresql.ENUM(
                        *TREND_ENTITY_TYPE,
                        name="fi_trend_entity_type",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("entity_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column(
                    "metric",
                    postgresql.ENUM(
                        *TREND_METRIC,
                        name="fi_trend_metric",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column(
                    "window",
                    postgresql.ENUM(
                        *TREND_WINDOW,
                        name="fi_trend_window",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("baseline_value", sa.Float, nullable=True),
                sa.Column("current_value", sa.Float, nullable=True),
                sa.Column("delta", sa.Float, nullable=True),
                sa.Column("delta_pct", sa.Float, nullable=True),
                sa.Column(
                    "label",
                    postgresql.ENUM(
                        *TREND_LABEL,
                        name="fi_trend_label",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("computed_day", sa.Date, nullable=False),
                sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("explain", sa.JSON, nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint(
                    "tenant_id",
                    "entity_type",
                    "entity_id",
                    "metric",
                    "window",
                    "computed_day",
                    name="uq_fi_trend_snapshot_tenant_entity_metric_window_day",
                ),
            ),
        )
        op.create_index(
            "ix_fi_trend_client_entity_ts",
            "fi_trend_snapshots",
            ["client_id", "entity_type", "computed_at"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_fi_trend_entity_ts",
            "fi_trend_snapshots",
            ["entity_type", "entity_id", "computed_at"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_fi_trend_label",
            "fi_trend_snapshots",
            ["label"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    pass
