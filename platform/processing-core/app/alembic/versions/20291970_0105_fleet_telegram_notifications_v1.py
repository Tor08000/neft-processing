"""fleet telegram notifications v1.

Revision ID: 20291970_0105_fleet_telegram_notifications_v1
Revises: 20291960_0104_fleet_notifications_v2
Create Date: 2026-01-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum_value,
    safe_enum,
)


# revision identifiers, used by Alembic.
revision = "20291970_0105_fleet_telegram_notifications_v1"
down_revision = "20291960_0104_fleet_notifications_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum_value(bind, "fleet_notification_channel_type", "TELEGRAM", schema=DB_SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "FLEET_TELEGRAM_LINK_TOKEN_ISSUED", schema=DB_SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "FLEET_TELEGRAM_BOUND", schema=DB_SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "FLEET_TELEGRAM_UNBOUND", schema=DB_SCHEMA)
    ensure_pg_enum_value(bind, "case_event_type", "FLEET_TELEGRAM_SEND_FAILED", schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "fleet_telegram_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column(
            "scope_type",
            safe_enum(bind, "fleet_telegram_scope_type", ["client", "group"], schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("scope_id", sa.String(36), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_title", sa.Text(), nullable=True),
        sa.Column(
            "chat_type",
            safe_enum(
                bind,
                "fleet_telegram_chat_type",
                ["private", "group", "supergroup", "channel"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "fleet_telegram_binding_status",
                ["ACTIVE", "DISABLED", "PENDING"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_event_id", sa.String(36), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "uq_fleet_telegram_bindings_client_chat_scope",
        "fleet_telegram_bindings",
        ["client_id", "chat_id", "scope_type", "scope_id"],
        unique=True,
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fleet_telegram_bindings_client_status",
        "fleet_telegram_bindings",
        ["client_id", "status"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "fleet_telegram_link_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column(
            "scope_type",
            safe_enum(bind, "fleet_telegram_scope_type", ["client", "group"], schema=DB_SCHEMA),
            nullable=False,
        ),
        sa.Column("scope_id", sa.String(36), nullable=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "fleet_telegram_link_token_status",
                ["ISSUED", "USED", "EXPIRED", "REVOKED"],
                schema=DB_SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("issued_by_user_id", sa.String(36), nullable=True),
        sa.Column("used_by_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("audit_event_id", sa.String(36), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_fleet_telegram_link_tokens_client_status",
        "fleet_telegram_link_tokens",
        ["client_id", "status"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    # No downgrade operations for additive changes.
    pass
