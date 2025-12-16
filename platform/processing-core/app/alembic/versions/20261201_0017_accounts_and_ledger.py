"""Add accounts and ledger tables

Revision ID: 20261201_0017_accounts_and_ledger
Revises: 20261125_0016_risk_rule_audit
Create Date: 2026-12-01 00:17:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    create_index_if_not_exists,
    drop_index_if_exists,
    pg_ensure_enum,
    table_exists,
)

# revision identifiers, used by Alembic.
revision = "20261201_0017_accounts_and_ledger"
down_revision = "20261125_0016_risk_rule_audit"
branch_labels = None
depends_on = None

ACCOUNT_TYPE_VALUES = ["CLIENT_MAIN", "CLIENT_CREDIT", "CARD_LIMIT", "TECHNICAL"]
ACCOUNT_STATUS_VALUES = ["ACTIVE", "FROZEN", "CLOSED"]
LEDGER_DIRECTION_VALUES = ["DEBIT", "CREDIT"]


def _account_type_enum(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            *ACCOUNT_TYPE_VALUES, name="accounttype", create_type=False
        )

    return sa.Enum(
        *ACCOUNT_TYPE_VALUES,
        name="accounttype",
        native_enum=False,
    )


def _account_status_enum(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            *ACCOUNT_STATUS_VALUES, name="accountstatus", create_type=False
        )

    return sa.Enum(
        *ACCOUNT_STATUS_VALUES,
        name="accountstatus",
        native_enum=False,
    )


def _ledger_direction_enum(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            *LEDGER_DIRECTION_VALUES, name="ledgerdirection", create_type=False
        )

    return sa.Enum(
        *LEDGER_DIRECTION_VALUES,
        name="ledgerdirection",
        native_enum=False,
    )


def _uuid_type(bind):
    if bind.dialect.name == "postgresql":
        return sa.dialects.postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        pg_ensure_enum(bind, "accounttype", ACCOUNT_TYPE_VALUES)
        pg_ensure_enum(bind, "accountstatus", ACCOUNT_STATUS_VALUES)
        pg_ensure_enum(bind, "ledgerdirection", LEDGER_DIRECTION_VALUES)

    account_type_enum = _account_type_enum(bind)
    account_status_enum = _account_status_enum(bind)
    ledger_direction_enum = _ledger_direction_enum(bind)

    if not table_exists(bind, "accounts"):
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
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
        )
    create_index_if_not_exists(bind, "ix_accounts_client_id", "accounts", ["client_id"])
    create_index_if_not_exists(bind, "ix_accounts_card_id", "accounts", ["card_id"])
    create_index_if_not_exists(bind, "ix_accounts_type", "accounts", ["type"])
    create_index_if_not_exists(bind, "ix_accounts_status", "accounts", ["status"])

    if not table_exists(bind, "account_balances"):
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

    if not table_exists(bind, "ledger_entries"):
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
                _uuid_type(bind),
                sa.ForeignKey("operations.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("direction", ledger_direction_enum, nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("balance_after", sa.Numeric(18, 4), nullable=True),
            sa.Column(
                "posted_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("value_date", sa.Date(), nullable=True),
        )
    create_index_if_not_exists(bind, "ix_ledger_entries_account_id", "ledger_entries", ["account_id"])
    create_index_if_not_exists(
        bind, "ix_ledger_entries_operation_id", "ledger_entries", ["operation_id"]
    )
    create_index_if_not_exists(bind, "ix_ledger_entries_posted_at", "ledger_entries", ["posted_at"])


def downgrade() -> None:
    bind = op.get_bind()

    drop_index_if_exists(
        bind, "ix_ledger_entries_posted_at", table_name="ledger_entries"
    )
    drop_index_if_exists(
        bind, "ix_ledger_entries_operation_id", table_name="ledger_entries"
    )
    drop_index_if_exists(
        bind, "ix_ledger_entries_account_id", table_name="ledger_entries"
    )
    if table_exists(bind, "ledger_entries"):
        op.drop_table("ledger_entries")

    if table_exists(bind, "account_balances"):
        op.drop_table("account_balances")

    drop_index_if_exists(bind, "ix_accounts_status", table_name="accounts")
    drop_index_if_exists(bind, "ix_accounts_type", table_name="accounts")
    drop_index_if_exists(bind, "ix_accounts_card_id", table_name="accounts")
    drop_index_if_exists(bind, "ix_accounts_client_id", table_name="accounts")
    if table_exists(bind, "accounts"):
        op.drop_table("accounts")

    if bind.dialect.name == "postgresql":
        for enum_name in ("ledgerdirection", "accountstatus", "accounttype"):
            bind.exec_driver_sql(f"DROP TYPE IF EXISTS public.{enum_name}")
