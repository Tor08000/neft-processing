"""crm_v1_core_tables

Revision ID: 20260216_01
Revises:
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision = "20260216_01"
down_revision = None
branch_labels = None
depends_on = None

CRM_CORE_TABLES = (
    "crm_contacts",
    "crm_pipelines",
    "crm_pipeline_stages",
    "crm_deals",
    "crm_tasks",
    "crm_comments",
    "crm_audit_events",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if all(inspector.has_table(table_name) for table_name in CRM_CORE_TABLES):
        return

    op.create_table(
        "crm_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_crm_contacts_tenant_id", "crm_contacts", ["tenant_id"])
    op.create_index("ix_crm_contacts_client_id", "crm_contacts", ["client_id"])
    op.create_index("ix_crm_contacts_partner_id", "crm_contacts", ["partner_id"])
    op.execute("CREATE UNIQUE INDEX uq_crm_contacts_tenant_email ON crm_contacts (tenant_id, email) WHERE email IS NOT NULL")

    op.create_table(
        "crm_pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_crm_pipelines_tenant_name"),
    )

    op.create_table(
        "crm_pipeline_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_won", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_lost", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pipeline_id", "position", name="uq_crm_pipeline_stages_position"),
    )
    op.create_index("ix_crm_pipeline_stages_tenant_pipeline", "crm_pipeline_stages", ["tenant_id", "pipeline_id"])

    op.create_table(
        "crm_deals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_pipelines.id"), nullable=False),
        sa.Column("stage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_pipeline_stages.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.Text(), server_default="RUB", nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_contacts.id"), nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_crm_deals_tenant_status", "crm_deals", ["tenant_id", "status"])
    op.create_index("ix_crm_deals_tenant_stage", "crm_deals", ["tenant_id", "stage_id"])
    op.create_index("ix_crm_deals_tenant_owner", "crm_deals", ["tenant_id", "owner_user_id"])

    op.create_table(
        "crm_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_deals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "crm_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_crm_comments_tenant_entity", "crm_comments", ["tenant_id", "entity_type", "entity_id"])

    op.create_table(
        "crm_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_email", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_crm_audit_tenant_entity", "crm_audit_events", ["tenant_id", "entity_type", "entity_id"])
    op.create_index("ix_crm_audit_tenant_created", "crm_audit_events", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("crm_audit_events")
    op.drop_table("crm_comments")
    op.drop_table("crm_tasks")
    op.drop_table("crm_deals")
    op.drop_table("crm_pipeline_stages")
    op.drop_table("crm_pipelines")
    op.drop_table("crm_contacts")
