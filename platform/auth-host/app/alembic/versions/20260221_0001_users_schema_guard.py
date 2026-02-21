"""Ensure auth users schema exists and has required columns.

Revision ID: 20260221_0001_users_schema_guard
Revises: 20251010_0001_user_clients, 20251027_0001_default_tenant_neft, 20251003_0002_auth_vernum
Create Date: 2026-02-21 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260221_0001_users_schema_guard"
down_revision = (
    "20251010_0001_user_clients",
    "20251027_0001_default_tenant_neft",
    "20251003_0002_auth_vernum",
)
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
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS public"))
    op.execute(sa.text("SET search_path TO public"))

    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column("email", sa.Text(), nullable=False),
            sa.Column("password_hash", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=AUTH_SCHEMA,
        )

    columns = _column_names("users")
    if "password_hash" not in columns:
        op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True), schema=AUTH_SCHEMA)
    if "is_active" not in columns:
        op.add_column(
            "users",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            schema=AUTH_SCHEMA,
        )
    if "status" not in columns:
        op.add_column(
            "users",
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
            schema=AUTH_SCHEMA,
        )
    if "created_at" not in columns:
        op.add_column(
            "users",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=AUTH_SCHEMA,
        )
    if "updated_at" not in columns:
        op.add_column(
            "users",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=AUTH_SCHEMA,
        )

    op.execute(sa.text("UPDATE public.users SET email = lower(email) WHERE email IS NOT NULL"))
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
            ON public.users (lower(email))
            """
        )
    )

    op.execute(sa.text("UPDATE public.users SET status = 'active' WHERE status IS NULL"))
    op.execute(sa.text("UPDATE public.users SET is_active = TRUE WHERE is_active IS NULL"))
    op.execute(sa.text("UPDATE public.users SET updated_at = now() WHERE updated_at IS NULL"))
    op.execute(sa.text("UPDATE public.users SET password_hash = '' WHERE password_hash IS NULL"))

    op.execute(sa.text("ALTER TABLE public.users ALTER COLUMN email SET NOT NULL"))
    op.execute(sa.text("ALTER TABLE public.users ALTER COLUMN password_hash SET NOT NULL"))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.uq_users_email_lower")
