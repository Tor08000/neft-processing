# revision identifiers, used by Alembic.
revision = "0047_merge_heads"
down_revision = (
    "0046_invoice_refunds",
    "0046_invoice_payments_provider_external_ref_unique",
    "0042_audit_log",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
