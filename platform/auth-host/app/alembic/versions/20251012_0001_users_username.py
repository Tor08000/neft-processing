"""Add username to users.

Revision ID: 20251012_0001_users_username
Revises: 20251010_0002_merge_auth_vernum_user_clients
Create Date: 2025-10-12 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251012_0001_users_username"
down_revision = "20251010_0002_merge_auth_vernum_user_clients"
branch_labels = None
depends_on = None

AUTH_SCHEMA = "public"


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name, schema=AUTH_SCHEMA)}


def upgrade() -> None:
    columns = _column_names("users")
    if "username" not in columns:
        op.add_column("users", sa.Column("username", sa.Text(), nullable=True), schema=AUTH_SCHEMA)

    op.execute(
        sa.text(
            f'CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower ON "{AUTH_SCHEMA}".users (lower(username)) WHERE username IS NOT NULL'
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f'DROP INDEX IF EXISTS "{AUTH_SCHEMA}".idx_users_username_lower'))
    columns = _column_names("users")
    if "username" in columns:
        op.drop_column("users", "username", schema=AUTH_SCHEMA)
