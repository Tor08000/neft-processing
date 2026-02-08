"""marketplace_moderation_audit

Revision ID: 20299360_0164_marketplace_moderation_audit
Revises: 20299350_0163_marketplace_offers_v1
Create Date: 2025-02-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision = "20299360_0164_marketplace_moderation_audit"
down_revision = "20299350_0163_marketplace_offers_v1"
branch_labels = None
depends_on = None

def upgrade() -> None:
    entity_type_create = pg.ENUM(
        "PRODUCT",
        "SERVICE",
        "OFFER",
        name="marketplace_moderation_entity_type",
    )
    action_create = pg.ENUM(
        "APPROVE",
        "REJECT",
        "SUSPEND",
        name="marketplace_moderation_action",
    )

    bind = op.get_bind()
    entity_type_create.create(bind, checkfirst=True)
    action_create.create(bind, checkfirst=True)

    entity_type_enum = pg.ENUM(
        "PRODUCT",
        "SERVICE",
        "OFFER",
        name="marketplace_moderation_entity_type",
        create_type=False,
    )
    action_enum = pg.ENUM(
        "APPROVE",
        "REJECT",
        "SUSPEND",
        name="marketplace_moderation_action",
        create_type=False,
    )

    op.create_table(
        "marketplace_moderation_audit",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("entity_type", entity_type_enum, nullable=False),
        sa.Column("entity_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("actor_user_id", pg.UUID(as_uuid=False), nullable=True),
        sa.Column("actor_role", sa.Text(), nullable=True),
        sa.Column("action", action_enum, nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("before_status", sa.Text(), nullable=True),
        sa.Column("after_status", sa.Text(), nullable=True),
        sa.Column("meta", pg.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="processing_core",
    )
    op.create_index(
        "ix_marketplace_moderation_audit_entity",
        "marketplace_moderation_audit",
        ["entity_type", "entity_id"],
        schema="processing_core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_marketplace_moderation_audit_entity",
        table_name="marketplace_moderation_audit",
        schema="processing_core",
    )
    op.drop_table("marketplace_moderation_audit", schema="processing_core")
    op.execute("DROP TYPE IF EXISTS processing_core.marketplace_moderation_action")
    op.execute("DROP TYPE IF EXISTS processing_core.marketplace_moderation_entity_type")
