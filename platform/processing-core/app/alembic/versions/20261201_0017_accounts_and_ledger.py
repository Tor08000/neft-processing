"""Add accounts and ledger tables

Revision ID: 20261201_0017_accounts_and_ledger
Revises: 20261125_0016_risk_rule_audit
Create Date: 2026-12-01 00:17:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261201_0017_accounts_and_ledger"
down_revision = "20261125_0016_risk_rule_audit"
branch_labels = None
depends_on = None

account_type_enum = sa.Enum(
    "CLIENT_MAIN",
    "CLIENT_CREDIT",
    "CARD_LIMIT",
    "TECHNICAL",
    name="accounttype",
)

account_status_enum = sa.Enum("ACTIVE", "FROZEN", "CLOSED", name="accountstatus")

ledger_direction_enum = sa.Enum("DEBIT", "CREDIT", name="ledgerdirection")


def upgrade() -> None:
    account_type_enum.create(op.get_bind(), checkfirst=True)
    account_status_enum.create(op.get_bind(), checkfirst=True)
    ledger_direction_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "accounts",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("client_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("card_id", sa.String(length=64), sa.ForeignKey("cards.id"), nullable=True),
        sa.Column("tariff_id", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("type", account_type_enum, nullable=False),
        sa.Column("status", account_status_enum, nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_accounts_client_id", "accounts", ["client_id"], unique=False)
    op.create_index("ix_accounts_card_id", "accounts", ["card_id"], unique=False)
    op.create_index("ix_accounts_type", "accounts", ["type"], unique=False)
    op.create_index("ix_accounts_status", "accounts", ["status"], unique=False)

    op.create_table(
        "account_balances",
        sa.Column(
            "account_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("current_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("available_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "ledger_entries",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "account_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "operation_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("operations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("direction", ledger_direction_enum, nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "posted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("value_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_ledger_entries_account_id", "ledger_entries", ["account_id"], unique=False)
    op.create_index(
        "ix_ledger_entries_operation_id", "ledger_entries", ["operation_id"], unique=False
    )
    op.create_index("ix_ledger_entries_posted_at", "ledger_entries", ["posted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ledger_entries_posted_at", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_operation_id", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_account_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")

    op.drop_table("account_balances")

    op.drop_index("ix_accounts_status", table_name="accounts")
    op.drop_index("ix_accounts_type", table_name="accounts")
    op.drop_index("ix_accounts_card_id", table_name="accounts")
    op.drop_index("ix_accounts_client_id", table_name="accounts")
    op.drop_table("accounts")

    ledger_direction_enum.drop(op.get_bind(), checkfirst=True)
    account_status_enum.drop(op.get_bind(), checkfirst=True)
    account_type_enum.drop(op.get_bind(), checkfirst=True)
