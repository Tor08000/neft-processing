"""Client cards & limits v1 hardening.

Revision ID: 20299920_0195_client_cards_limits_v1
Revises: 20299910_0194_client_invitation_resend_revoke_notifications
Create Date: 2026-02-17 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    column_exists,
    constraint_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
)
from db.types import GUID


revision = "20299920_0195_client_cards_limits_v1"
down_revision = "20299910_0194_client_invitation_resend_revoke_notifications"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    query = sa.text(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema=:schema AND table_name=:table
        """
    )
    return bind.execute(query, {"schema": DB_SCHEMA, "table": table_name}).first() is not None


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "cards",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("client_id", GUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("pan_masked", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_cards_client_id", "cards", ["client_id"], schema=DB_SCHEMA)

    if _table_exists(bind, "cards"):
        if not column_exists(bind, "cards", "external_id", schema=DB_SCHEMA):
            op.add_column("cards", sa.Column("external_id", sa.Text(), nullable=True), schema=DB_SCHEMA)
        if not column_exists(bind, "cards", "issued_at", schema=DB_SCHEMA):
            op.add_column("cards", sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)
        if not column_exists(bind, "cards", "updated_at", schema=DB_SCHEMA):
            op.add_column(
                "cards",
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
                schema=DB_SCHEMA,
            )

    create_table_if_not_exists(
        bind,
        "card_limits",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("card_id", sa.String(), sa.ForeignKey("cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("limit_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    if not column_exists(bind, "card_limits", "active", schema=DB_SCHEMA):
        op.add_column(
            "card_limits",
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            schema=DB_SCHEMA,
        )
    create_index_if_not_exists(bind, "ix_card_limits_client_id", "card_limits", ["client_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_card_limits_card_id", "card_limits", ["card_id"], schema=DB_SCHEMA)
    create_unique_index_if_not_exists(bind, "uq_card_limits_card_type", "card_limits", ["card_id", "limit_type"], schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "limit_templates",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("limits", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    if not column_exists(bind, "limit_templates", "is_default", schema=DB_SCHEMA):
        op.add_column(
            "limit_templates",
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "limit_templates", "updated_at", schema=DB_SCHEMA):
        op.add_column(
            "limit_templates",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=DB_SCHEMA,
        )
    create_unique_index_if_not_exists(
        bind,
        "uq_limit_templates_client_name",
        "limit_templates",
        ["client_id", "name"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if constraint_exists(bind, "limit_templates", "uq_limit_templates_client_name", schema=DB_SCHEMA):
        op.drop_index("uq_limit_templates_client_name", table_name="limit_templates", schema=DB_SCHEMA)
    if column_exists(bind, "limit_templates", "is_default", schema=DB_SCHEMA):
        op.drop_column("limit_templates", "is_default", schema=DB_SCHEMA)
    if column_exists(bind, "limit_templates", "updated_at", schema=DB_SCHEMA):
        op.drop_column("limit_templates", "updated_at", schema=DB_SCHEMA)
    if column_exists(bind, "card_limits", "active", schema=DB_SCHEMA):
        op.drop_column("card_limits", "active", schema=DB_SCHEMA)
    if column_exists(bind, "cards", "external_id", schema=DB_SCHEMA):
        op.drop_column("cards", "external_id", schema=DB_SCHEMA)
    if column_exists(bind, "cards", "issued_at", schema=DB_SCHEMA):
        op.drop_column("cards", "issued_at", schema=DB_SCHEMA)
    if column_exists(bind, "cards", "updated_at", schema=DB_SCHEMA):
        op.drop_column("cards", "updated_at", schema=DB_SCHEMA)
