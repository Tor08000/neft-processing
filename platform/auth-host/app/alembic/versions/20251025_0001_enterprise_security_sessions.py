"""Enterprise security sessions, refresh rotation and revocation.

Revision ID: 20251025_0001_enterprise_security_sessions
Revises: 20251022_0001_multitenant_sso_oidc
Create Date: 2025-10-25 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20251025_0001_enterprise_security_sessions"
down_revision = "20251022_0001_multitenant_sso_oidc"
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


def _index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {idx["name"] for idx in inspector.get_indexes(table_name, schema=AUTH_SCHEMA)}


def upgrade() -> None:
    if not _table_exists("auth_sessions"):
        op.create_table(
            "auth_sessions",
            sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey(f"{AUTH_SCHEMA}.users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", sa.UUID(), sa.ForeignKey(f"{AUTH_SCHEMA}.tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("portal", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revocation_reason", sa.Text(), nullable=True),
            sa.Column("ip", sa.Text(), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            schema=AUTH_SCHEMA,
        )

    indexes = _index_names("auth_sessions")
    if "ix_auth_sessions_user_id" not in indexes:
        op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], schema=AUTH_SCHEMA)
    if "ix_auth_sessions_tenant_id" not in indexes:
        op.create_index("ix_auth_sessions_tenant_id", "auth_sessions", ["tenant_id"], schema=AUTH_SCHEMA)
    if "ix_auth_sessions_revoked_at" not in indexes:
        op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"], schema=AUTH_SCHEMA)

    if _table_exists("refresh_tokens"):
        cols = _column_names("refresh_tokens")
        if "session_id" not in cols:
            op.add_column("refresh_tokens", sa.Column("session_id", sa.UUID(), nullable=True), schema=AUTH_SCHEMA)
        if "rotated_from_id" not in cols:
            op.add_column("refresh_tokens", sa.Column("rotated_from_id", sa.UUID(), nullable=True), schema=AUTH_SCHEMA)
        if "revoked_at" not in cols:
            op.add_column("refresh_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True), schema=AUTH_SCHEMA)

        op.execute(sa.text(
            """
            UPDATE public.refresh_tokens rt
            SET rotated_from_id = rt.rotated_from
            WHERE rt.rotated_from IS NOT NULL AND rt.rotated_from_id IS NULL
            """
        ))

        op.execute(sa.text(
            """
            UPDATE public.refresh_tokens rt
            SET revoked_at = now()
            WHERE rt.revoked = TRUE AND rt.revoked_at IS NULL
            """
        ))

        op.execute(sa.text(
            """
            WITH seeded AS (
                INSERT INTO public.auth_sessions (id, user_id, tenant_id, portal, created_at, last_seen_at)
                SELECT gen_random_uuid(), rt.user_id, rt.tenant_id, 'client', min(rt.created_at), max(rt.created_at)
                FROM public.refresh_tokens rt
                WHERE rt.session_id IS NULL
                GROUP BY rt.user_id, rt.tenant_id
                RETURNING id, user_id, tenant_id
            )
            UPDATE public.refresh_tokens rt
            SET session_id = seeded.id
            FROM seeded
            WHERE rt.user_id = seeded.user_id AND rt.tenant_id = seeded.tenant_id AND rt.session_id IS NULL
            """
        ))

        op.alter_column("refresh_tokens", "session_id", nullable=False, schema=AUTH_SCHEMA)
        op.create_foreign_key(
            "fk_refresh_tokens_session_id",
            "refresh_tokens",
            "auth_sessions",
            ["session_id"],
            ["id"],
            source_schema=AUTH_SCHEMA,
            referent_schema=AUTH_SCHEMA,
            ondelete="CASCADE",
        )
        op.create_foreign_key(
            "fk_refresh_tokens_rotated_from_id",
            "refresh_tokens",
            "refresh_tokens",
            ["rotated_from_id"],
            ["id"],
            source_schema=AUTH_SCHEMA,
            referent_schema=AUTH_SCHEMA,
            ondelete="SET NULL",
        )

        refresh_indexes = _index_names("refresh_tokens")
        if "ix_refresh_tokens_session_id" not in refresh_indexes:
            op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"], schema=AUTH_SCHEMA)
        if "ix_refresh_tokens_expires_at" not in refresh_indexes:
            op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], schema=AUTH_SCHEMA)


def downgrade() -> None:
    if _table_exists("refresh_tokens"):
        for name in ("ix_refresh_tokens_expires_at", "ix_refresh_tokens_session_id"):
            try:
                op.drop_index(name, table_name="refresh_tokens", schema=AUTH_SCHEMA)
            except Exception:
                pass
    if _table_exists("auth_sessions"):
        for name in ("ix_auth_sessions_revoked_at", "ix_auth_sessions_tenant_id", "ix_auth_sessions_user_id"):
            try:
                op.drop_index(name, table_name="auth_sessions", schema=AUTH_SCHEMA)
            except Exception:
                pass
        op.drop_table("auth_sessions", schema=AUTH_SCHEMA)
