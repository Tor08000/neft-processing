"""Create missing client portal tables: client_user_roles and card_limits.

Revision ID: 20299800_0183_client_portal_role_and_card_limits
Revises: 20299730_0182_merge_heads_station_margin_day_and_commercial_recommendation_actions
Create Date: 2026-02-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
)
from db.types import GUID


revision = "20299800_0183_client_portal_role_and_card_limits"
down_revision = "20299730_0182_merge_heads_station_margin_day_and_commercial_recommendation_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "client_user_roles",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("roles", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_client_user_roles_client_id",
        "client_user_roles",
        ["client_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_client_user_roles_user_id",
        "client_user_roles",
        ["user_id"],
        schema=DB_SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_client_user_role",
        "client_user_roles",
        ["client_id", "user_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "card_limits",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("card_id", sa.String(), nullable=False),
        sa.Column("limit_type", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_card_limits_client_id",
        "card_limits",
        ["client_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_card_limits_card_id",
        "card_limits",
        ["card_id"],
        schema=DB_SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_card_limits_client_card_type",
        "card_limits",
        ["client_id", "card_id", "limit_type"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("uq_card_limits_client_card_type", table_name="card_limits", schema=DB_SCHEMA)
    op.drop_index("ix_card_limits_card_id", table_name="card_limits", schema=DB_SCHEMA)
    op.drop_index("ix_card_limits_client_id", table_name="card_limits", schema=DB_SCHEMA)
    op.drop_table("card_limits", schema=DB_SCHEMA)

    op.drop_index("uq_client_user_role", table_name="client_user_roles", schema=DB_SCHEMA)
    op.drop_index("ix_client_user_roles_user_id", table_name="client_user_roles", schema=DB_SCHEMA)
    op.drop_index("ix_client_user_roles_client_id", table_name="client_user_roles", schema=DB_SCHEMA)
    op.drop_table("client_user_roles", schema=DB_SCHEMA)
