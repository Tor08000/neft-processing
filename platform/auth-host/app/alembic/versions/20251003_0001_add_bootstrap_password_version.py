"""Add bootstrap password version to users.

Revision ID: 20251003_0001_add_bootstrap_password_version
Revises: 20251002_0001_create_auth_tables
Create Date: 2025-10-03 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251003_0001_add_bootstrap_password_version"
down_revision = "20251002_0001_create_auth_tables"
branch_labels = None
depends_on = None


AUTH_SCHEMA = "public"


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names(schema=AUTH_SCHEMA)


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name, schema=AUTH_SCHEMA)}


def upgrade() -> None:
    if not _table_exists("users"):
        return

    columns = _column_names("users")
    if "bootstrap_password_version" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "bootstrap_password_version",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            schema=AUTH_SCHEMA,
        )


def downgrade() -> None:
    if not _table_exists("users"):
        return

    columns = _column_names("users")
    if "bootstrap_password_version" in columns:
        op.drop_column("users", "bootstrap_password_version", schema=AUTH_SCHEMA)
