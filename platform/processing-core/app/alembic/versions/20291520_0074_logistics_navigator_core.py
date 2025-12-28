"""logistics navigator core tables

Revision ID: 20291520_0074_logistics_navigator_core
Revises: 20291510_0070_money_flow_v2
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import create_table_if_not_exists, ensure_pg_enum, table_exists
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20291520_0074_logistics_navigator_core"
down_revision = "20291510_0070_money_flow_v2"
branch_labels = None
depends_on = None

LOGISTICS_NAVIGATOR_EXPLAIN_TYPE = ["ETA", "DEVIATION"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "logistics_navigator_explain_type", LOGISTICS_NAVIGATOR_EXPLAIN_TYPE, schema=SCHEMA)

    if not table_exists(bind, "logistics_route_snapshots", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "logistics_route_snapshots",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(36), primary_key=True),
                sa.Column("order_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_orders.id"), nullable=False),
                sa.Column("route_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_routes.id"), nullable=False),
                sa.Column("provider", sa.String(32), nullable=False),
                sa.Column("geometry", sa.JSON(), nullable=False),
                sa.Column("distance_km", sa.Float, nullable=False),
                sa.Column("eta_minutes", sa.Integer, nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
            ),
        )
        op.create_index(
            "ix_logistics_route_snapshots_route",
            "logistics_route_snapshots",
            ["route_id", "created_at"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_logistics_route_snapshots_order",
            "logistics_route_snapshots",
            ["order_id"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "logistics_navigator_explains", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "logistics_navigator_explains",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(36), primary_key=True),
                sa.Column(
                    "route_snapshot_id",
                    sa.String(36),
                    sa.ForeignKey(f"{SCHEMA}.logistics_route_snapshots.id"),
                    nullable=False,
                ),
                sa.Column(
                    "type",
                    postgresql.ENUM(
                        *LOGISTICS_NAVIGATOR_EXPLAIN_TYPE,
                        name="logistics_navigator_explain_type",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("payload", sa.JSON(), nullable=False),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
            ),
        )
        op.create_index(
            "ix_logistics_navigator_explains_snapshot",
            "logistics_navigator_explains",
            ["route_snapshot_id", "created_at"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    pass
