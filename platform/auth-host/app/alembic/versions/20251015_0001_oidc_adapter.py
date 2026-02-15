"""OIDC adapter tables.

Revision ID: 20251015_0001_oidc_adapter
Revises: 20251012_0001_users_username
Create Date: 2025-10-15 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251015_0001_oidc_adapter"
down_revision = "20251012_0001_users_username"
branch_labels = None
depends_on = None

AUTH_SCHEMA = "public"


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names(schema=AUTH_SCHEMA)


def upgrade() -> None:
    if not _table_exists("oidc_providers"):
        op.create_table(
            "oidc_providers",
            sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", sa.UUID(), nullable=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("issuer", sa.Text(), nullable=False),
            sa.Column("client_id", sa.Text(), nullable=False),
            sa.Column("client_secret", sa.Text(), nullable=False),
            sa.Column("redirect_uri", sa.Text(), nullable=False),
            sa.Column("scopes", sa.Text(), nullable=False, server_default=sa.text("'openid email profile'")),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=AUTH_SCHEMA,
        )
        op.create_unique_constraint("uq_oidc_providers_name", "oidc_providers", ["name"], schema=AUTH_SCHEMA)

    if not _table_exists("oauth_identities"):
        op.create_table(
            "oauth_identities",
            sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey(f"{AUTH_SCHEMA}.users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider_id", sa.UUID(), sa.ForeignKey(f"{AUTH_SCHEMA}.oidc_providers.id", ondelete="SET NULL"), nullable=True),
            sa.Column("provider_name", sa.Text(), nullable=False),
            sa.Column("provider_user_id", sa.Text(), nullable=False),
            sa.Column("email", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("provider_id", "provider_user_id", name="uq_oauth_identities_providerid_uid"),
            sa.UniqueConstraint("provider_name", "provider_user_id", name="uq_oauth_identities_provider_uid"),
            schema=AUTH_SCHEMA,
        )

    if not _table_exists("oidc_role_mappings"):
        op.create_table(
            "oidc_role_mappings",
            sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("provider_id", sa.UUID(), sa.ForeignKey(f"{AUTH_SCHEMA}.oidc_providers.id", ondelete="CASCADE"), nullable=True),
            sa.Column("external_role", sa.Text(), nullable=False),
            sa.Column("internal_role", sa.Text(), nullable=False),
            sa.UniqueConstraint("provider_id", "external_role", name="uq_oidc_role_mappings_provider_external"),
            schema=AUTH_SCHEMA,
        )

    if not _table_exists("oauth_states"):
        op.create_table(
            "oauth_states",
            sa.Column("state_id", sa.Text(), primary_key=True),
            sa.Column("provider_name", sa.Text(), nullable=False),
            sa.Column("portal", sa.Text(), nullable=False),
            sa.Column("nonce", sa.Text(), nullable=False),
            sa.Column("redirect_url", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=AUTH_SCHEMA,
        )


def downgrade() -> None:
    if _table_exists("oauth_states"):
        op.drop_table("oauth_states", schema=AUTH_SCHEMA)
    if _table_exists("oidc_role_mappings"):
        op.drop_table("oidc_role_mappings", schema=AUTH_SCHEMA)
    if _table_exists("oauth_identities"):
        op.drop_table("oauth_identities", schema=AUTH_SCHEMA)
    if _table_exists("oidc_providers"):
        op.drop_table("oidc_providers", schema=AUTH_SCHEMA)
