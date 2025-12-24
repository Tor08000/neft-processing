# revision identifiers, used by Alembic.
revision = "0047_merge_heads"
down_revision = (
    "0044_documents_registry",
    "20260701_0009_client_portal",
    "20261201_0017_accounts_and_ledger",
    "20260110_0009_create_clearing_table",
    "0046_invoice_refunds",
    "20270115_0020",
    "20270201_0020",
    "0046_invoice_payments_provider_external_ref_unique",
    "0042_audit_log",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
