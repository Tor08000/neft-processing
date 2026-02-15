"""Multi-tenant SSO and enterprise token security.

Revision ID: 20251020_0001_multi_tenant_security
Revises: 20251015_0001_oidc_adapter
Create Date: 2025-10-20 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20251020_0001_multi_tenant_security"
down_revision = "20251015_0001_oidc_adapter"
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


def _constraint_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    names: set[str] = set()
    for constraint in inspector.get_unique_constraints(table_name, schema=AUTH_SCHEMA):
        if constraint.get("name"):
            names.add(str(constraint["name"]))
    fk_constraints = inspector.get_foreign_keys(table_name, schema=AUTH_SCHEMA)
    for constraint in fk_constraints:
        if constraint.get("name"):
            names.add(str(constraint["name"]))
    return names


def upgrade() -> None:
    if not _table_exists("tenants"):
        op.create_table(
            "tenants",
            sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("code", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("sso_enforced", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
            sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("code", name="uq_tenants_code"),
            schema=AUTH_SCHEMA,
        )

    op.execute(sa.text("""
        INSERT INTO public.tenants (code, name)
        SELECT 'default', 'Default Tenant'
        WHERE NOT EXISTS (SELECT 1 FROM public.tenants WHERE code='default')
    """))

    if _table_exists("users"):
        cols = _column_names("users")
        if "tenant_id" not in cols:
            op.add_column("users", sa.Column("tenant_id", sa.UUID(), nullable=True), schema=AUTH_SCHEMA)
        if "status" not in cols:
            op.add_column(
                "users",
                sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
                schema=AUTH_SCHEMA,
            )
        if "token_version" not in cols:
            op.add_column(
                "users",
                sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
                schema=AUTH_SCHEMA,
            )

        op.execute(sa.text("""
            UPDATE public.users u
            SET tenant_id=t.id
            FROM public.tenants t
            WHERE u.tenant_id IS NULL AND t.code='default'
        """))
        op.alter_column("users", "tenant_id", nullable=False, schema=AUTH_SCHEMA)

        constraints = _constraint_names("users")
        if "fk_users_tenant" not in constraints:
            op.create_foreign_key(
                "fk_users_tenant",
                "users",
                "tenants",
                ["tenant_id"],
                ["id"],
                source_schema=AUTH_SCHEMA,
                referent_schema=AUTH_SCHEMA,
            )
        if "users_email_key" in constraints:
            op.drop_constraint("users_email_key", "users", schema=AUTH_SCHEMA, type_="unique")
        if "uq_users_tenant_email" not in constraints:
            op.create_unique_constraint("uq_users_tenant_email", "users", ["tenant_id", "email"], schema=AUTH_SCHEMA)

    if _table_exists("oidc_providers"):
        cols = _column_names("oidc_providers")
        if "tenant_id" in cols:
            op.execute(sa.text("""
                UPDATE public.oidc_providers p
                SET tenant_id=t.id
                FROM public.tenants t
                WHERE p.tenant_id IS NULL AND t.code='default'
            """))
            op.alter_column("oidc_providers", "tenant_id", nullable=False, schema=AUTH_SCHEMA)
        constraints = _constraint_names("oidc_providers")
        if "uq_oidc_providers_name" in constraints:
            op.drop_constraint("uq_oidc_providers_name", "oidc_providers", schema=AUTH_SCHEMA, type_="unique")
        if "uq_oidc_providers_tenant_name" not in constraints:
            op.create_unique_constraint(
                "uq_oidc_providers_tenant_name", "oidc_providers", ["tenant_id", "name"], schema=AUTH_SCHEMA
            )

    if _table_exists("oauth_states"):
        cols = _column_names("oauth_states")
        if "tenant_id" not in cols:
            op.add_column("oauth_states", sa.Column("tenant_id", sa.UUID(), nullable=True), schema=AUTH_SCHEMA)
        if "provider_id" not in cols:
            op.add_column("oauth_states", sa.Column("provider_id", sa.UUID(), nullable=True), schema=AUTH_SCHEMA)

    if not _table_exists("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey(f"{AUTH_SCHEMA}.users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", sa.UUID(), sa.ForeignKey(f"{AUTH_SCHEMA}.tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("rotated_from", sa.UUID(), sa.ForeignKey(f"{AUTH_SCHEMA}.refresh_tokens.id", ondelete="SET NULL"), nullable=True),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("device_key", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
            schema=AUTH_SCHEMA,
        )


def downgrade() -> None:
    if _table_exists("refresh_tokens"):
        op.drop_table("refresh_tokens", schema=AUTH_SCHEMA)
