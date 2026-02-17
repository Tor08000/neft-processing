"""Add invitation resend/revoke fields and notification outbox.

Revision ID: 20299910_0194_client_invitation_resend_revoke_notifications
Revises: 20299900_0193_client_user_invitations
Create Date: 2026-02-17 00:20:01.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists
from db.types import GUID

revision = "20299910_0194_client_invitation_resend_revoke_notifications"
down_revision = "20299900_0193_client_user_invitations"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(item["name"] == column for item in inspector.get_columns(table, schema=DB_SCHEMA))


def _notification_outbox_has_aggregate_columns(inspector: sa.Inspector) -> bool:
    return _has_column(inspector, "notification_outbox", "aggregate_type") and _has_column(inspector, "notification_outbox", "aggregate_id")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("client_invitations", schema=DB_SCHEMA):
        columns = {
            "created_by_user_id": sa.String(length=64),
            "revoked_at": sa.DateTime(timezone=True),
            "revoked_by_user_id": sa.String(length=64),
            "revocation_reason": sa.Text(),
            "resent_count": sa.Integer(),
            "last_sent_at": sa.DateTime(timezone=True),
            "last_send_status": sa.String(length=32),
            "last_send_error": sa.Text(),
            "updated_at": sa.DateTime(timezone=True),
        }
        for name, col_type in columns.items():
            if not _has_column(inspector, "client_invitations", name):
                nullable = name in {"revoked_at", "revoked_by_user_id", "revocation_reason", "last_sent_at", "last_send_status", "last_send_error"}
                server_default = None
                if name == "resent_count":
                    server_default = sa.text("0")
                if name == "updated_at":
                    server_default = sa.text("now()")
                op.add_column(
                    "client_invitations",
                    sa.Column(name, col_type, nullable=nullable, server_default=server_default),
                    schema=DB_SCHEMA,
                )

        op.execute(sa.text(f"UPDATE {DB_SCHEMA}.client_invitations SET created_by_user_id = invited_by_user_id WHERE created_by_user_id IS NULL"))
        op.execute(sa.text(f"UPDATE {DB_SCHEMA}.client_invitations SET resent_count = 0 WHERE resent_count IS NULL"))
        op.execute(sa.text(f"UPDATE {DB_SCHEMA}.client_invitations SET updated_at = now() WHERE updated_at IS NULL"))
        op.alter_column("client_invitations", "created_by_user_id", nullable=False, schema=DB_SCHEMA)
        op.alter_column("client_invitations", "resent_count", nullable=False, schema=DB_SCHEMA)
        op.alter_column("client_invitations", "updated_at", nullable=False, schema=DB_SCHEMA)

    create_index_if_not_exists(bind, "ix_client_invitations_client_status", "client_invitations", ["client_id", "status"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_client_invitations_email", "client_invitations", ["email"], schema=DB_SCHEMA)
    op.execute(sa.text(f"CREATE UNIQUE INDEX IF NOT EXISTS uq_client_invitations_token_hash ON {DB_SCHEMA}.client_invitations (token_hash)"))

    create_table_if_not_exists(
        bind,
        "notification_outbox",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("aggregate_type", sa.Text(), nullable=False, server_default="client_invitation"),
        sa.Column("aggregate_id", sa.Text(), nullable=False),
        sa.Column("tenant_client_id", GUID(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="NEW"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )

    inspector = sa.inspect(bind)
    if not _notification_outbox_has_aggregate_columns(inspector):
        if not _has_column(inspector, "notification_outbox", "aggregate_type"):
            op.add_column("notification_outbox", sa.Column("aggregate_type", sa.Text(), nullable=True), schema=DB_SCHEMA)
        if not _has_column(inspector, "notification_outbox", "aggregate_id"):
            op.add_column("notification_outbox", sa.Column("aggregate_id", sa.Text(), nullable=True), schema=DB_SCHEMA)

        op.execute(
            sa.text(
                f"""
                UPDATE {DB_SCHEMA}.notification_outbox
                SET aggregate_type = COALESCE(aggregate_type, subject_type::text, 'notification')
                WHERE aggregate_type IS NULL
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {DB_SCHEMA}.notification_outbox
                SET aggregate_id = COALESCE(aggregate_id, subject_id, id::text)
                WHERE aggregate_id IS NULL
                """
            )
        )

        op.alter_column("notification_outbox", "aggregate_type", nullable=False, schema=DB_SCHEMA)
        op.alter_column("notification_outbox", "aggregate_id", nullable=False, schema=DB_SCHEMA)

    create_index_if_not_exists(bind, "ix_notification_outbox_status_retry", "notification_outbox", ["status", "next_attempt_at"], schema=DB_SCHEMA)
    inspector = sa.inspect(bind)
    if _notification_outbox_has_aggregate_columns(inspector):
        create_index_if_not_exists(bind, "ix_notification_outbox_aggregate", "notification_outbox", ["aggregate_type", "aggregate_id"], schema=DB_SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_aggregate", table_name="notification_outbox", schema=DB_SCHEMA)
    op.drop_index("ix_notification_outbox_status_retry", table_name="notification_outbox", schema=DB_SCHEMA)
    op.drop_table("notification_outbox", schema=DB_SCHEMA)
