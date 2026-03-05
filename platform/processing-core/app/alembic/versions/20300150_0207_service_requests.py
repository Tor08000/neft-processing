"""service requests table

Revision ID: 20300150_0207
Revises: 28d39dce919f
Create Date: 2026-03-05 14:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20300150_0207"
down_revision = "28d39dce919f"
branch_labels = None
depends_on = None


service_request_status = sa.Enum(
    "new",
    "accepted",
    "in_progress",
    "done",
    "rejected",
    name="service_request_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        service_request_status.create(bind, checkfirst=True)

    op.create_table(
        "service_requests",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", service_request_status, nullable=False, server_default="new"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        schema="processing_core",
    )

    op.create_index(
        "ix_service_requests_tenant_partner_status",
        "service_requests",
        ["tenant_id", "partner_id", "status"],
        unique=False,
        schema="processing_core",
    )
    op.create_index(
        "ix_service_requests_tenant_client_created",
        "service_requests",
        ["tenant_id", "client_id", "created_at"],
        unique=False,
        schema="processing_core",
    )


def downgrade() -> None:
    op.drop_index("ix_service_requests_tenant_client_created", table_name="service_requests", schema="processing_core")
    op.drop_index("ix_service_requests_tenant_partner_status", table_name="service_requests", schema="processing_core")
    op.drop_table("service_requests", schema="processing_core")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        service_request_status.drop(bind, checkfirst=True)
