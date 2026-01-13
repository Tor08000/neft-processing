"""Create auth tables.

Revision ID: 20251002_0001_create_auth_tables
Revises: 20251001_0001_auth_bootstrap
Create Date: 2025-10-02 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251002_0001_create_auth_tables"
down_revision = "20251001_0001_auth_bootstrap"
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


def _has_unique_constraint(columns: set[str]) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    pk_constraint = inspector.get_pk_constraint("user_roles", schema=AUTH_SCHEMA)
    pk_columns = set(pk_constraint.get("constrained_columns") or [])
    if pk_columns == columns:
        return True
    for constraint in inspector.get_unique_constraints("user_roles", schema=AUTH_SCHEMA):
        if set(constraint.get("column_names") or []) == columns:
            return True
    return False


def upgrade() -> None:
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS public"))
    op.execute(sa.text("SET search_path TO public"))

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
            sa.Column("role_code", sa.Text(), nullable=False),
            sa.UniqueConstraint("user_id", "role_code", name="uq_user_roles_user_id_role_code"),
            schema=AUTH_SCHEMA,
        )
    else:
        columns = _column_names("user_roles")
        if "role" in columns and "role_code" not in columns:
            op.alter_column("user_roles", "role", new_column_name="role_code", schema=AUTH_SCHEMA)
        if not _has_unique_constraint({"user_id", "role_code"}):
            op.create_unique_constraint(
                "uq_user_roles_user_id_role_code",
                "user_roles",
                ["user_id", "role_code"],
                schema=AUTH_SCHEMA,
            )


def downgrade() -> None:
    if _table_exists("user_roles"):
        op.drop_table("user_roles", schema=AUTH_SCHEMA)
    if _table_exists("users"):
        op.drop_table("users", schema=AUTH_SCHEMA)
