"""geo tiles daily overlays cache

Revision ID: 20299690_0178_geo_tiles_daily_overlays
Revises: 20299680_0177_geo_tiles_daily
Create Date: 2026-02-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, constraint_exists, index_exists, table_exists

revision = "20299690_0178_geo_tiles_daily_overlays"
down_revision = "20299680_0177_geo_tiles_daily"
branch_labels = None
depends_on = None

_UNIQUE = "uq_geo_tiles_daily_overlays_day_zoom_tile_kind"


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "geo_tiles_daily_overlays", schema=DB_SCHEMA):
        op.create_table(
            "geo_tiles_daily_overlays",
            sa.Column("day", sa.Date(), nullable=False),
            sa.Column("zoom", sa.SmallInteger(), nullable=False),
            sa.Column("tile_x", sa.Integer(), nullable=False),
            sa.Column("tile_y", sa.Integer(), nullable=False),
            sa.Column("overlay_kind", sa.String(length=32), nullable=False),
            sa.Column("value", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP") if bind.dialect.name == "sqlite" else sa.text("now()"),
            ),
            sa.PrimaryKeyConstraint("day", "zoom", "tile_x", "tile_y", "overlay_kind", name="pk_geo_tiles_daily_overlays"),
            schema=DB_SCHEMA,
        )

    if bind.dialect.name != "sqlite" and not constraint_exists(bind, "geo_tiles_daily_overlays", _UNIQUE, schema=DB_SCHEMA):
        op.create_unique_constraint(
            _UNIQUE,
            "geo_tiles_daily_overlays",
            ["day", "zoom", "tile_x", "tile_y", "overlay_kind"],
            schema=DB_SCHEMA,
        )

    if not index_exists(bind, "ix_geo_tiles_daily_overlays_day_zoom_kind_tile", schema=DB_SCHEMA):
        op.create_index(
            "ix_geo_tiles_daily_overlays_day_zoom_kind_tile",
            "geo_tiles_daily_overlays",
            ["day", "zoom", "overlay_kind", "tile_x", "tile_y"],
            unique=False,
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if index_exists(bind, "ix_geo_tiles_daily_overlays_day_zoom_kind_tile", schema=DB_SCHEMA):
        op.drop_index("ix_geo_tiles_daily_overlays_day_zoom_kind_tile", table_name="geo_tiles_daily_overlays", schema=DB_SCHEMA)

    if bind.dialect.name != "sqlite" and constraint_exists(bind, "geo_tiles_daily_overlays", _UNIQUE, schema=DB_SCHEMA):
        op.drop_constraint(_UNIQUE, "geo_tiles_daily_overlays", type_="unique", schema=DB_SCHEMA)

    if table_exists(bind, "geo_tiles_daily_overlays", schema=DB_SCHEMA):
        op.drop_table("geo_tiles_daily_overlays", schema=DB_SCHEMA)
