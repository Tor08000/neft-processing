"""marketplace_moderation_audit

Revision ID: 20299360_0164_marketplace_moderation_audit
Revises: 20299350_0163_marketplace_offers_v1
Create Date: 2025-02-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20299360_0164_marketplace_moderation_audit"
down_revision = "20299350_0163_marketplace_offers_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    entity_type_enum = sa.Enum(
        "PRODUCT",
        "SERVICE",
        "OFFER",
        name="marketplace_moderation_entity_type",
        create_type=False,
    )
    action_enum = sa.Enum(
        "APPROVE",
        "REJECT",
        "SUSPEND",
        name="marketplace_moderation_action",
        create_type=False,
    )
    entity_type_enum.create(op.get_bind(), checkfirst=True)
    action_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "marketplace_moderation_audit",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("entity_type", entity_type_enum, nullable=False),
        sa.Column("entity_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("actor_user_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("actor_role", sa.Text(), nullable=True),
        sa.Column("action", action_enum, nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("before_status", sa.Text(), nullable=True),
        sa.Column("after_status", sa.Text(), nullable=True),
        sa.Column("meta", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_marketplace_moderation_audit_entity",
        "marketplace_moderation_audit",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_marketplace_moderation_audit_entity", table_name="marketplace_moderation_audit")
    op.drop_table("marketplace_moderation_audit")
    op.execute("DROP TYPE IF EXISTS marketplace_moderation_action")
    op.execute("DROP TYPE IF EXISTS marketplace_moderation_entity_type")
