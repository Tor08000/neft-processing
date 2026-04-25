"""Add onboarding review decision fields and client link.

Revision ID: 20299850_0188_onboarding_review_client_link
Revises: 20299840_0187_client_documents
Create Date: 2026-02-16 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from db.schema import DB_SCHEMA
from db.types import GUID

revision = "20299850_0188_onboarding_review_client_link"
down_revision = "20299840_0187_client_documents"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    return any(item["name"] == column for item in inspector.get_columns(table, schema=DB_SCHEMA))


def _has_index(inspector, table: str, name: str) -> bool:
    return any(item["name"] == name for item in inspector.get_indexes(table, schema=DB_SCHEMA))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "client_onboarding_applications", "reviewed_by_user_id"):
        op.add_column("client_onboarding_applications", sa.Column("reviewed_by_user_id", sa.String(length=64), nullable=True), schema=DB_SCHEMA)
    if not _has_column(inspector, "client_onboarding_applications", "reviewed_at"):
        op.add_column("client_onboarding_applications", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)
    if not _has_column(inspector, "client_onboarding_applications", "decision_reason"):
        op.add_column("client_onboarding_applications", sa.Column("decision_reason", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not _has_column(inspector, "client_onboarding_applications", "client_id"):
        op.add_column("client_onboarding_applications", sa.Column("client_id", GUID(), nullable=True), schema=DB_SCHEMA)
        op.create_foreign_key(
            "fk_client_onboarding_applications_client_id",
            "client_onboarding_applications",
            "clients",
            ["client_id"],
            ["id"],
            source_schema=DB_SCHEMA,
            referent_schema=DB_SCHEMA,
        )
    if not _has_column(inspector, "client_onboarding_applications", "approved_at"):
        op.add_column("client_onboarding_applications", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)
    if not _has_column(inspector, "client_onboarding_applications", "rejected_at"):
        op.add_column("client_onboarding_applications", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "client_onboarding_applications", "ix_client_onboarding_applications_created_at"):
        op.create_index("ix_client_onboarding_applications_created_at", "client_onboarding_applications", ["created_at"], schema=DB_SCHEMA)
    if not _has_index(inspector, "client_onboarding_applications", "ix_client_onboarding_applications_inn"):
        op.create_index("ix_client_onboarding_applications_inn", "client_onboarding_applications", ["inn"], schema=DB_SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_client_onboarding_applications_inn", table_name="client_onboarding_applications", schema=DB_SCHEMA)
    op.drop_index("ix_client_onboarding_applications_created_at", table_name="client_onboarding_applications", schema=DB_SCHEMA)

    op.drop_column("client_onboarding_applications", "rejected_at", schema=DB_SCHEMA)
    op.drop_column("client_onboarding_applications", "approved_at", schema=DB_SCHEMA)
    op.drop_constraint("fk_client_onboarding_applications_client_id", "client_onboarding_applications", schema=DB_SCHEMA, type_="foreignkey")
    op.drop_column("client_onboarding_applications", "client_id", schema=DB_SCHEMA)
    op.drop_column("client_onboarding_applications", "decision_reason", schema=DB_SCHEMA)
    op.drop_column("client_onboarding_applications", "reviewed_at", schema=DB_SCHEMA)
    op.drop_column("client_onboarding_applications", "reviewed_by_user_id", schema=DB_SCHEMA)
