"""Marketplace gamification v1.

Revision ID: 20295000_0111_marketplace_gamification_v1
Revises: 20294000_0110_marketplace_promotions_v1
Create Date: 2026-02-11 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from app.alembic.helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    is_postgres,
)
from app.db.types import GUID


revision = "20295000_0111_marketplace_gamification_v1"
down_revision = "20294000_0110_marketplace_promotions_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def _schema_prefix() -> str:
    return f"{DB_SCHEMA}." if DB_SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    create_table_if_not_exists(
        bind,
        "partner_tiers",
        sa.Column("tier_code", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("thresholds", JSON_TYPE, nullable=False),
        sa.Column("benefits", JSON_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_tier_state",
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("tier_code", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=False),
        sa.Column("metrics_snapshot", JSON_TYPE, nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("partner_id"),
        sa.ForeignKeyConstraint(
            ["tier_code"],
            [f"{_schema_prefix()}partner_tiers.tier_code"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_tier_state_tenant_partner",
        "partner_tier_state",
        ["tenant_id", "partner_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_missions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rule", JSON_TYPE, nullable=False),
        sa.Column("reward", JSON_TYPE, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_missions_tenant_active",
        "partner_missions",
        ["tenant_id", "active"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_mission_progress",
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("mission_id", GUID(), nullable=False),
        sa.Column("progress", sa.Numeric(), nullable=False),
        sa.Column("target", sa.Numeric(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("last_event_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("partner_id", "mission_id"),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            [f"{_schema_prefix()}partner_missions.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_mission_progress_tenant_status",
        "partner_mission_progress",
        ["tenant_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_badges",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("rule", JSON_TYPE, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("code", name="uq_partner_badges_code"),
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_badge_awards",
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("badge_id", GUID(), nullable=False),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("meta", JSON_TYPE, nullable=True),
        sa.PrimaryKeyConstraint("partner_id", "badge_id"),
        sa.ForeignKeyConstraint(
            ["badge_id"],
            [f"{_schema_prefix()}partner_badges.id"],
            ondelete="RESTRICT",
        ),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_badge_awards_tenant_partner",
        "partner_badge_awards",
        ["tenant_id", "partner_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_metrics_daily",
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("orders_created", sa.Integer(), nullable=False),
        sa.Column("orders_paid", sa.Integer(), nullable=False),
        sa.Column("orders_completed", sa.Integer(), nullable=False),
        sa.Column("orders_canceled", sa.Integer(), nullable=False),
        sa.Column("orders_refunded", sa.Integer(), nullable=False),
        sa.Column("revenue", sa.Numeric(), nullable=False),
        sa.Column("avg_check", sa.Numeric(), nullable=False),
        sa.Column("cancel_rate", sa.Numeric(), nullable=False),
        sa.Column("refund_rate", sa.Numeric(), nullable=False),
        sa.Column("unique_clients", sa.Integer(), nullable=False),
        sa.Column("repeat_clients", sa.Integer(), nullable=False),
        sa.Column("repeat_rate", sa.Numeric(), nullable=False),
        sa.Column("avg_rating", sa.Numeric(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("partner_id", "day"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_metrics_daily_tenant_day",
        "partner_metrics_daily",
        ["tenant_id", "day"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_metrics_rolling",
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("metrics_json", JSON_TYPE, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("partner_id", "window_days", "as_of"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_metrics_rolling_tenant_window",
        "partner_metrics_rolling",
        ["tenant_id", "window_days", "as_of"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "partner_boosts",
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("partner_id", GUID(), nullable=False),
        sa.Column("boost_type", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("meta", JSON_TYPE, nullable=True),
        sa.PrimaryKeyConstraint("partner_id", "boost_type", "starts_at"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_partner_boosts_tenant_partner",
        "partner_boosts",
        ["tenant_id", "partner_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    pass
