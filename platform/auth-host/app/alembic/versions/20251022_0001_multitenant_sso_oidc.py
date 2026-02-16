"""Multi-tenant SSO OIDC tables.

Revision ID: 20251022_0001_multitenant_sso_oidc
Revises: 20251020_0001_multi_tenant_security
Create Date: 2025-10-22 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251022_0001_multitenant_sso_oidc"
down_revision = "20251020_0001_multi_tenant_security"
branch_labels = None
depends_on = None

AUTH_SCHEMA = "public"


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names(schema=AUTH_SCHEMA)


def upgrade() -> None:
    if not _table_exists("sso_idp_configs"):
        op.create_table(
            "sso_idp_configs",
            sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("provider_key", sa.Text(), nullable=False),
            sa.Column("display_name", sa.Text(), nullable=False),
            sa.Column("issuer_url", sa.Text(), nullable=False),
            sa.Column("client_id", sa.Text(), nullable=False),
            sa.Column("client_secret", sa.Text(), nullable=True),
            sa.Column("authorization_endpoint", sa.Text(), nullable=True),
            sa.Column("token_endpoint", sa.Text(), nullable=True),
            sa.Column("userinfo_endpoint", sa.Text(), nullable=True),
            sa.Column("jwks_uri", sa.Text(), nullable=True),
            sa.Column("scopes", sa.Text(), nullable=False, server_default=sa.text("'openid profile email'")),
            sa.Column("claim_email", sa.Text(), nullable=False, server_default=sa.text("'email'")),
            sa.Column("claim_sub", sa.Text(), nullable=False, server_default=sa.text("'sub'")),
            sa.Column("claim_name", sa.Text(), nullable=False, server_default=sa.text("'name'")),
            sa.Column("allowed_domains", sa.ARRAY(sa.Text()), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("tenant_id", "provider_key", name="uq_sso_idp_configs_tenant_provider"),
            schema=AUTH_SCHEMA,
        )
        op.create_index("ix_sso_idp_configs_tenant_enabled", "sso_idp_configs", ["tenant_id", "enabled"], schema=AUTH_SCHEMA)

    if not _table_exists("user_identities"):
        op.create_table(
            "user_identities",
            sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey(f"{AUTH_SCHEMA}.users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("provider_key", sa.Text(), nullable=False),
            sa.Column("external_sub", sa.Text(), nullable=False),
            sa.Column("external_email", sa.Text(), nullable=True),
            sa.Column("raw_claims", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("tenant_id", "provider_key", "external_sub", name="uq_user_identities_sub"),
            schema=AUTH_SCHEMA,
        )
        op.create_index(
            "uq_user_identities_email_not_null",
            "user_identities",
            ["tenant_id", "provider_key", "external_email"],
            unique=True,
            postgresql_where=sa.text("external_email IS NOT NULL"),
            schema=AUTH_SCHEMA,
        )

    if not _table_exists("sso_oidc_states"):
        op.create_table(
            "sso_oidc_states",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("provider_key", sa.Text(), nullable=False),
            sa.Column("portal", sa.Text(), nullable=False),
            sa.Column("redirect_uri", sa.Text(), nullable=False),
            sa.Column("nonce", sa.Text(), nullable=False),
            sa.Column("code_verifier", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=AUTH_SCHEMA,
        )

    if not _table_exists("sso_exchange_codes"):
        op.create_table(
            "sso_exchange_codes",
            sa.Column("code", sa.Text(), primary_key=True),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey(f"{AUTH_SCHEMA}.users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("portal", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=AUTH_SCHEMA,
        )


def downgrade() -> None:
    if _table_exists("sso_exchange_codes"):
        op.drop_table("sso_exchange_codes", schema=AUTH_SCHEMA)
    if _table_exists("sso_oidc_states"):
        op.drop_table("sso_oidc_states", schema=AUTH_SCHEMA)
    if _table_exists("user_identities"):
        op.drop_index("uq_user_identities_email_not_null", table_name="user_identities", schema=AUTH_SCHEMA)
        op.drop_table("user_identities", schema=AUTH_SCHEMA)
    if _table_exists("sso_idp_configs"):
        op.drop_index("ix_sso_idp_configs_tenant_enabled", table_name="sso_idp_configs", schema=AUTH_SCHEMA)
        op.drop_table("sso_idp_configs", schema=AUTH_SCHEMA)
