"""Ensure client approval foundation tables/columns.

Revision ID: 20299890_0192_client_approval_foundation
Revises: 20299880_0191_client_docflow_packages_notifications
Create Date: 2026-02-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists, create_unique_index_if_not_exists
from db.types import GUID

revision = "20299890_0192_client_approval_foundation"
down_revision = "20299880_0191_client_docflow_packages_notifications"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    return any(item["name"] == column for item in inspector.get_columns(table, schema=DB_SCHEMA))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    create_table_if_not_exists(
        bind,
        "client_users",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_client_users_client_id", "client_users", ["client_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_client_users_user_id", "client_users", ["user_id"], schema=DB_SCHEMA)
    create_unique_index_if_not_exists(
        bind,
        "uq_client_users_client_user",
        "client_users",
        ["client_id", "user_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "client_user_roles",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("roles", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_client_user_roles_client_id", "client_user_roles", ["client_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_client_user_roles_user_id", "client_user_roles", ["user_id"], schema=DB_SCHEMA)
    create_unique_index_if_not_exists(bind, "uq_client_user_role", "client_user_roles", ["client_id", "user_id"], schema=DB_SCHEMA)

    if _has_column(inspector, "clients", "name") and not _has_column(inspector, "clients", "legal_name"):
        op.add_column("clients", sa.Column("legal_name", sa.Text(), nullable=True), schema=DB_SCHEMA)
        op.execute(sa.text(f"UPDATE {DB_SCHEMA}.clients SET legal_name = COALESCE(legal_name, name)"))

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "clients", "org_type"):
        op.add_column("clients", sa.Column("org_type", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not _has_column(inspector, "clients", "ogrn"):
        op.add_column("clients", sa.Column("ogrn", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not _has_column(inspector, "clients", "updated_at"):
        op.add_column(
            "clients",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=DB_SCHEMA,
        )

    create_index_if_not_exists(bind, "ix_clients_status", "clients", ["status"], schema=DB_SCHEMA)
    create_unique_index_if_not_exists(bind, "uq_clients_inn", "clients", ["inn"], schema=DB_SCHEMA)

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "client_onboarding_applications", "approved_by_user_id"):
        op.add_column(
            "client_onboarding_applications",
            sa.Column("approved_by_user_id", sa.String(length=64), nullable=True),
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_column(inspector, "client_onboarding_applications", "approved_by_user_id"):
        op.drop_column("client_onboarding_applications", "approved_by_user_id", schema=DB_SCHEMA)
