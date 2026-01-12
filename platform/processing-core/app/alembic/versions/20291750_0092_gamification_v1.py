"""Gamification v1 tables.

Revision ID: 20291750_0092_gamification_v1
Revises: 20291740_0091_subscription_system_v1
Create Date: 2025-03-06 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists
from db.schema import resolve_db_schema


# revision identifiers, used by Alembic.
revision = "20291750_0092_gamification_v1"
down_revision = "20291740_0091_subscription_system_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("module_code", sa.String(length=64), nullable=True),
        sa.Column("plan_codes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_achievements_code", "achievements", ["code"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "achievement_conditions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("achievement_id", sa.Integer(), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["achievement_id"], [f"{SCHEMA}.achievements.id" if SCHEMA else "achievements.id"]),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_achievement_conditions_achievement", "achievement_conditions", ["achievement_id"], schema=SCHEMA
    )

    create_table_if_not_exists(
        bind,
        "streaks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("module_code", sa.String(length=64), nullable=True),
        sa.Column("plan_codes", sa.JSON(), nullable=True),
        sa.Column("condition", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_streaks_code", "streaks", ["code"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "bonuses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reward", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("plan_codes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_bonuses_code", "bonuses", ["code"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "client_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("achievements", sa.JSON(), nullable=True),
        sa.Column("streaks", sa.JSON(), nullable=True),
        sa.Column("bonuses", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_client_progress_tenant_client", "client_progress", ["tenant_id", "client_id"], schema=SCHEMA)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
