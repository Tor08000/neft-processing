"""Security baseline: service identities and ABAC policies.

Revision ID: 20298010_0129_security_service_identities_abac
Revises: 20297230_0128_edo_v2
Create Date: 2029-10-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import (
    SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
)


revision = "20298010_0129_security_service_identities_abac"
down_revision = "20297230_0128_edo_v2"
branch_labels = None
depends_on = None


SERVICE_IDENTITY_STATUS = ["ACTIVE", "DISABLED"]
SERVICE_TOKEN_STATUS = ["ACTIVE", "REVOKED", "EXPIRED"]
SERVICE_TOKEN_AUDIT_ACTION = ["ISSUED", "ROTATED", "REVOKED", "USED", "DENIED"]
SERVICE_TOKEN_ACTOR_TYPE = ["ADMIN", "SYSTEM"]
ABAC_POLICY_VERSION_STATUS = ["DRAFT", "PUBLISHED", "ACTIVE", "ARCHIVED"]
ABAC_POLICY_EFFECT = ["ALLOW", "DENY"]

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "service_identity_status", SERVICE_IDENTITY_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "service_token_status", SERVICE_TOKEN_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "service_token_audit_action", SERVICE_TOKEN_AUDIT_ACTION, schema=SCHEMA)
    ensure_pg_enum(bind, "service_token_actor_type", SERVICE_TOKEN_ACTOR_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "abac_policy_version_status", ABAC_POLICY_VERSION_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "abac_policy_effect", ABAC_POLICY_EFFECT, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "service_identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("service_name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(*SERVICE_IDENTITY_STATUS, name="service_identity_status", schema=SCHEMA, create_type=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("service_name", name="uq_service_identities_service_name"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_identities_service_name",
        "service_identities",
        ["service_name"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "service_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("service_identity_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.service_identities.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("prefix", sa.String(32), nullable=False),
        sa.Column("scopes", JSON_TYPE, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_from_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.service_tokens.id"), nullable=True),
        sa.Column("rotation_grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(*SERVICE_TOKEN_STATUS, name="service_token_status", schema=SCHEMA, create_type=False),
            nullable=False,
        ),
        sa.UniqueConstraint("token_hash", name="uq_service_tokens_hash"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_tokens_prefix",
        "service_tokens",
        ["prefix"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_tokens_identity_status",
        "service_tokens",
        ["service_identity_id", "status"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "service_token_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("service_token_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.service_tokens.id"), nullable=True),
        sa.Column(
            "action",
            postgresql.ENUM(
                *SERVICE_TOKEN_AUDIT_ACTION,
                name="service_token_audit_action",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "actor_type",
            postgresql.ENUM(
                *SERVICE_TOKEN_ACTOR_TYPE,
                name="service_token_actor_type",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("ip", postgresql.INET().with_variant(sa.String(64), "sqlite"), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta", JSON_TYPE, nullable=True),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_service_token_audit_action",
        "service_token_audit",
        ["action"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "abac_policy_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                *ABAC_POLICY_VERSION_STATUS,
                name="abac_policy_version_status",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "abac_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.abac_policy_versions.id"), nullable=False),
        sa.Column("code", sa.String(128), nullable=False),
        sa.Column(
            "effect",
            postgresql.ENUM(*ABAC_POLICY_EFFECT, name="abac_policy_effect", schema=SCHEMA, create_type=False),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("actions", JSON_TYPE, nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("condition", JSON_TYPE, nullable=True),
        sa.Column("reason_code", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("version_id", "code", name="uq_abac_policy_version_code"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_abac_policy_version",
        "abac_policies",
        ["version_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_abac_policy_resource",
        "abac_policies",
        ["resource_type"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("abac_policies", schema=SCHEMA)
    op.drop_table("abac_policy_versions", schema=SCHEMA)
    op.drop_table("service_token_audit", schema=SCHEMA)
    op.drop_table("service_tokens", schema=SCHEMA)
    op.drop_table("service_identities", schema=SCHEMA)

    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.abac_policy_effect")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.abac_policy_version_status")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.service_token_actor_type")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.service_token_audit_action")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.service_token_status")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.service_identity_status")
