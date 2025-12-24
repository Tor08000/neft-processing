"""Ensure invoice payments unique by provider and external reference.

Revision ID: 0046_invoice_payments_provider_external_ref_unique
Revises: 0045_invoice_payments_provider
Create Date: 2025-02-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from app.alembic.utils import (
    SCHEMA,
    create_index_if_not_exists,
    drop_index_if_exists,
    index_exists,
    is_postgres,
)

# revision identifiers, used by Alembic.
revision = "0046_invoice_payments_provider_external_ref_unique"
down_revision = "0045_invoice_payments_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    drop_index_if_exists(bind, "uq_invoice_payments_external_ref", schema=SCHEMA)

    create_index_if_not_exists(
        bind,
        "ix_invoice_payments_external_ref",
        "invoice_payments",
        ["external_ref"],
        schema=SCHEMA,
    )

    if index_exists(bind, "uq_invoice_payments_provider_external_ref", schema=SCHEMA):
        return

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_payments_provider_external_ref
        ON public.invoice_payments (COALESCE(provider, ''), external_ref)
        """
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
