"""Align billing_summary schema with required fields

Revision ID: 20261101_0014_billing_summary_alignment
Revises: 20261020_0013_operations_limits_alignment
Create Date: 2026-11-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

from app.models.operation import ProductType


# revision identifiers, used by Alembic.
revision = "20261101_0014_billing_summary_alignment"
down_revision = "20261020_0013_operations_limits_alignment"
branch_labels = None
depends_on = None


product_type_values = [value.value for value in ProductType]
product_type_enum = sa.Enum(*product_type_values, name="product_type")
status_enum = sa.Enum("PENDING", "FINALIZED", name="billing_summary_status")


def ensure_enum_type_exists(bind, type_name: str, values: list[str], schema: str = "public") -> None:
    if bind.dialect.name != "postgresql":  # pragma: no cover - alembic migrations run on PG
        return

    res = bind.exec_driver_sql(
        "SELECT 1 FROM pg_type t "
        "JOIN pg_namespace n ON n.oid = t.typnamespace "
        "WHERE n.nspname = %s AND t.typname = %s",
        (schema, type_name),
    ).first()
    exists = res is not None

    if exists:
        return

    values_sql = ", ".join(f"'{value}'" for value in values)
    bind.exec_driver_sql(
        f"CREATE TYPE {schema}.{type_name} AS ENUM ({values_sql})"
    )


def _column_exists(bind, table_name: str, column_name: str, schema: str = "public") -> bool:
    return bool(
        bind.exec_driver_sql(
            "SELECT 1 "
            "FROM information_schema.columns "
            "WHERE table_schema = %s "
            "  AND table_name = %s "
            "  AND column_name = %s",
            (schema, table_name, column_name),
        ).scalar()
    )


def upgrade() -> None:
    bind = op.get_bind()
    ensure_enum_type_exists(bind, "product_type", values=product_type_values, schema="public")

    op.drop_index("ix_billing_summary_generated_at", table_name="billing_summary")
    op.drop_index("ix_billing_summary_status", table_name="billing_summary")
    op.drop_index("ix_billing_summary_date", table_name="billing_summary")
    op.drop_index("ix_billing_summary_merchant_id", table_name="billing_summary")

    op.drop_constraint(
        "uq_billing_summary_date_merchant",
        "billing_summary",
        type_="unique",
    )

    op.alter_column("billing_summary", "date", new_column_name="billing_date")
    op.alter_column(
        "billing_summary",
        "total_captured_amount",
        new_column_name="total_amount",
    )

    op.drop_column("billing_summary", "status")
    op.drop_column("billing_summary", "generated_at")
    op.drop_column("billing_summary", "finalized_at")
    op.drop_column("billing_summary", "hash")

    op.add_column(
        "billing_summary",
        sa.Column("client_id", sa.String(length=64), nullable=False),
    )
    if not _column_exists(bind, "billing_summary", "product_type", schema="public"):
        op.add_column(
            "billing_summary",
            sa.Column("product_type", product_type_enum, nullable=True),
        )
    op.add_column(
        "billing_summary",
        sa.Column("currency", sa.String(length=3), nullable=False),
    )
    op.add_column(
        "billing_summary",
        sa.Column("total_quantity", sa.Numeric(18, 3), nullable=True),
    )
    op.add_column(
        "billing_summary",
        sa.Column(
            "commission_amount",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "billing_summary",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_billing_summary_billing_date", "billing_summary", ["billing_date"], False
    )
    op.create_index(
        "ix_billing_summary_merchant_id", "billing_summary", ["merchant_id"], False
    )
    op.create_index(
        "ix_billing_summary_client_id", "billing_summary", ["client_id"], False
    )
    op.create_index(
        "ix_billing_summary_product_type",
        "billing_summary",
        ["product_type"],
        False,
    )
    op.create_index(
        "ix_billing_summary_currency", "billing_summary", ["currency"], False
    )

    op.create_unique_constraint(
        "uq_billing_summary_unique_scope",
        "billing_summary",
        ["billing_date", "merchant_id", "client_id", "product_type", "currency"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_billing_summary_unique_scope",
        "billing_summary",
        type_="unique",
    )

    op.drop_index("ix_billing_summary_currency", table_name="billing_summary")
    op.drop_index("ix_billing_summary_product_type", table_name="billing_summary")
    op.drop_index("ix_billing_summary_client_id", table_name="billing_summary")
    op.drop_index("ix_billing_summary_merchant_id", table_name="billing_summary")
    op.drop_index("ix_billing_summary_billing_date", table_name="billing_summary")

    op.drop_column("billing_summary", "updated_at")
    op.drop_column("billing_summary", "commission_amount")
    op.drop_column("billing_summary", "total_quantity")
    op.drop_column("billing_summary", "currency")
    op.drop_column("billing_summary", "product_type")
    op.drop_column("billing_summary", "client_id")

    op.add_column(
        "billing_summary",
        sa.Column("hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "billing_summary",
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "billing_summary",
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "billing_summary",
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default="PENDING",
        ),
    )

    op.alter_column(
        "billing_summary",
        "total_amount",
        new_column_name="total_captured_amount",
    )
    op.alter_column("billing_summary", "billing_date", new_column_name="date")

    op.create_unique_constraint(
        "uq_billing_summary_date_merchant", "billing_summary", ["date", "merchant_id"]
    )
    op.create_index("ix_billing_summary_merchant_id", "billing_summary", ["merchant_id"], False)
    op.create_index("ix_billing_summary_date", "billing_summary", ["date"], False)
    op.create_index("ix_billing_summary_status", "billing_summary", ["status"], False)
    op.create_index(
        "ix_billing_summary_generated_at", "billing_summary", ["generated_at"], False
    )
