"""Add client invitations table and ensure JSON roles for client user roles.

Revision ID: 20299900_0193_client_user_invitations
Revises: 20299890_0192_client_approval_foundation
Create Date: 2026-02-17 00:00:01.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists
from db.types import GUID

revision = "20299900_0193_client_user_invitations"
down_revision = "20299890_0192_client_approval_foundation"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(item["name"] == column for item in inspector.get_columns(table, schema=DB_SCHEMA))


def _column_type(inspector: sa.Inspector, table: str, column: str) -> str | None:
    for item in inspector.get_columns(table, schema=DB_SCHEMA):
        if item["name"] == column:
            return str(item.get("type") or "").lower()
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("client_user_roles", schema=DB_SCHEMA):
        col_type = _column_type(inspector, "client_user_roles", "roles") or ""
        if "json" not in col_type:
            op.execute(
                sa.text(
                    f"""
                    ALTER TABLE {DB_SCHEMA}.client_user_roles
                    ALTER COLUMN roles TYPE jsonb
                    USING CASE
                        WHEN roles IS NULL OR roles = '' THEN '[]'::jsonb
                        WHEN left(trim(roles), 1) = '[' THEN roles::jsonb
                        ELSE to_jsonb(string_to_array(roles, ','))
                    END
                    """
                )
            )
            op.execute(
                sa.text(
                    f"UPDATE {DB_SCHEMA}.client_user_roles SET roles='[]'::jsonb WHERE roles IS NULL"
                )
            )
            op.alter_column("client_user_roles", "roles", nullable=False, schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "client_invitations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("invited_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_user_id", sa.String(length=64), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_client_invitations_client_id", "client_invitations", ["client_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_client_invitations_email", "client_invitations", ["email"], schema=DB_SCHEMA)
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_client_invitations_pending_email
            ON {DB_SCHEMA}.client_invitations (client_id, email)
            WHERE status = 'PENDING'
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {DB_SCHEMA}.uq_client_invitations_pending_email"))
    op.drop_index("ix_client_invitations_email", table_name="client_invitations", schema=DB_SCHEMA)
    op.drop_index("ix_client_invitations_client_id", table_name="client_invitations", schema=DB_SCHEMA)
    op.drop_table("client_invitations", schema=DB_SCHEMA)
