"""audit signing keys registry and export object lock fields.

Revision ID: 20250320_0106_audit_signing_keys_object_lock
Revises: 20291970_0105_fleet_telegram_notifications_v1
Create Date: 2025-03-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists


revision = "20250320_0106_audit_signing_keys_object_lock"
down_revision = "20291970_0105_fleet_telegram_notifications_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "audit_signing_keys",
        sa.Column("key_id", sa.String(256), primary_key=True),
        sa.Column("alg", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("public_key_pem", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "audit_signing_keys_status",
        "audit_signing_keys",
        ["status"],
        schema=DB_SCHEMA,
    )
    op.add_column(
        "case_exports",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_case_exports_locked_until",
        "case_exports",
        ["locked_until"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_case_exports_locked_until", table_name="case_exports", schema=DB_SCHEMA)
    op.drop_column("case_exports", "locked_until", schema=DB_SCHEMA)
    op.drop_index("audit_signing_keys_status", table_name="audit_signing_keys", schema=DB_SCHEMA)
    op.drop_table("audit_signing_keys", schema=DB_SCHEMA)
