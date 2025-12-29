"""Bootstrap auth-host schema.

Revision ID: 20251001_0001_auth_bootstrap
Revises:
Create Date: 2025-10-01 00:01:00.000000
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251001_0001_auth_bootstrap"
down_revision = None
branch_labels = None
depends_on = None


AUTH_SCHEMA = os.getenv("AUTH_DB_SCHEMA", "public")


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names(schema=AUTH_SCHEMA)


def upgrade() -> None:
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("email", sa.Text(), nullable=False, unique=True),
            sa.Column("full_name", sa.Text(), nullable=True),
            sa.Column("password_hash", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=AUTH_SCHEMA,
        )

    op.execute(
        sa.text(f'CREATE INDEX IF NOT EXISTS idx_users_email_lower ON "{AUTH_SCHEMA}".users (lower(email))')
    )

    if not _table_exists("user_roles"):
        op.create_table(
            "user_roles",
            sa.Column(
                "user_id",
                sa.UUID(),
                sa.ForeignKey(f"{AUTH_SCHEMA}.users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("user_id", "role"),
            schema=AUTH_SCHEMA,
        )


def downgrade() -> None:
    if _table_exists("user_roles"):
        op.drop_table("user_roles", schema=AUTH_SCHEMA)
    if _table_exists("users"):
        op.drop_table("users", schema=AUTH_SCHEMA)
