"""Add billing payment intakes.

Revision ID: 20297305_0129_billing_payment_intakes
Revises: 20297230_0128_integrations_hub_v1
Create Date: 2025-03-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import (
    SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)


revision = "20297305_0129_billing_payment_intakes"
down_revision = "20297230_0128_integrations_hub_v1"
branch_labels = None
depends_on = None


BILLING_PAYMENT_INTAKE_STATUS = [
    "SUBMITTED",
    "UNDER_REVIEW",
    "APPROVED",
    "REJECTED",
]


def _schema_prefix() -> str:
    if not SCHEMA:
        return ""
    return f"{SCHEMA}."


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "billing_payment_intake_status", BILLING_PAYMENT_INTAKE_STATUS, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "billing_payment_intakes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            safe_enum(
                bind,
                "billing_payment_intake_status",
                BILLING_PAYMENT_INTAKE_STATUS,
                schema=SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("payer_name", sa.String(length=255), nullable=True),
        sa.Column("payer_inn", sa.String(length=32), nullable=True),
        sa.Column("bank_reference", sa.String(length=128), nullable=True),
        sa.Column("paid_at_claimed", sa.Date(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("proof_object_key", sa.Text(), nullable=True),
        sa.Column("proof_file_name", sa.String(length=255), nullable=True),
        sa.Column("proof_content_type", sa.String(length=128), nullable=True),
        sa.Column("proof_size", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=False),
        sa.Column("reviewed_by_admin", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["invoice_id"], [f"{_schema_prefix()}billing_invoices.id"], ondelete="CASCADE"),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_billing_payment_intakes_invoice_status",
        "billing_payment_intakes",
        ["invoice_id", "status"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_billing_payment_intakes_org_created",
        "billing_payment_intakes",
        ["org_id", "created_at"],
        schema=SCHEMA,
        postgresql_using="btree",
    )


def downgrade() -> None:
    bind = op.get_bind()

    if bind is None:
        return

    op.drop_table("billing_payment_intakes", schema=SCHEMA)
