"""align operation and limits models"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20261020_0013_operations_limits_alignment"
down_revision = "20261010_0012_client_ids_uuid"
branch_labels = None
depends_on = None


operation_type_enum = sa.Enum(
    "AUTH",
    "HOLD",
    "COMMIT",
    "REVERSE",
    "REFUND",
    "DECLINE",
    "CAPTURE",
    "REVERSAL",
    name="operationtype",
)

operation_status_enum = sa.Enum(
    "PENDING",
    "AUTHORIZED",
    "HELD",
    "COMPLETED",
    "REVERSED",
    "REFUNDED",
    "DECLINED",
    "CANCELLED",
    "CAPTURED",
    "OPEN",
    name="operationstatus",
)

product_type_enum = sa.Enum(
    "DIESEL",
    "AI92",
    "AI95",
    "AI98",
    "GAS",
    "OTHER",
    name="producttype",
)

risk_result_enum = sa.Enum(
    "LOW",
    "MEDIUM",
    "HIGH",
    "BLOCK",
    "MANUAL_REVIEW",
    name="riskresult",
)

limit_entity_enum = sa.Enum(
    "CLIENT",
    "CARD",
    "TERMINAL",
    "MERCHANT",
    name="limitentitytype",
)

limit_scope_enum = sa.Enum("PER_TX", "DAILY", "MONTHLY", name="limitscope")

fuel_product_enum = sa.Enum(
    "ANY",
    "DIESEL",
    "AI92",
    "AI95",
    "AI98",
    "GAS",
    "OTHER",
    name="fuelproducttype",
)


def _create_index_if_not_exists(
    name: str,
    table_name: str,
    columns: list[str] | tuple[str, ...],
    *,
    unique: bool = False,
    where: str | None = None,
) -> None:
    bind = op.get_bind()
    if getattr(getattr(bind, "dialect", None), "name", None) == "postgresql":
        columns_sql = ", ".join(columns)
        unique_sql = "UNIQUE " if unique else ""
        where_sql = f" WHERE {where}" if where else ""
        op.execute(
            sa.text(
                f"CREATE {unique_sql}INDEX IF NOT EXISTS {name} "
                f"ON {table_name} ({columns_sql}){where_sql}"
            )
        )
        return

    op.create_index(name, table_name, columns, unique=unique)


def _drop_index_if_exists(name: str, table_name: str) -> None:
    bind = op.get_bind()
    if getattr(getattr(bind, "dialect", None), "name", None) == "postgresql":
        op.execute(sa.text(f"DROP INDEX IF EXISTS {name}"))
        return

    op.drop_index(name, table_name=table_name)


def upgrade() -> None:
    # Create enums if they don't exist
    operation_type_enum.create(op.get_bind(), checkfirst=True)
    operation_status_enum.create(op.get_bind(), checkfirst=True)
    product_type_enum.create(op.get_bind(), checkfirst=True)
    risk_result_enum.create(op.get_bind(), checkfirst=True)
    limit_entity_enum.create(op.get_bind(), checkfirst=True)
    limit_scope_enum.create(op.get_bind(), checkfirst=True)
    fuel_product_enum.create(op.get_bind(), checkfirst=True)

    with op.batch_alter_table("operations") as batch:
        batch.add_column(
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            )
        )
        batch.add_column(sa.Column("product_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("amount_settled", sa.BigInteger(), nullable=True, server_default="0"))
        batch.add_column(sa.Column("product_type", product_type_enum, nullable=True))
        batch.add_column(sa.Column("quantity", sa.Numeric(18, 3), nullable=True))
        batch.add_column(sa.Column("unit_price", sa.Numeric(18, 3), nullable=True))
        batch.add_column(sa.Column("limit_profile_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("limit_check_result", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("risk_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("risk_result", risk_result_enum, nullable=True))
        batch.add_column(sa.Column("risk_payload", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("auth_code", sa.String(length=32), nullable=True))
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            )
        )
        batch.drop_constraint("operations_pkey", type_="primary")
        batch.create_primary_key("operations_pkey", ["id"])

    _create_index_if_not_exists("ix_operations_status", "operations", ["status"])
    _create_index_if_not_exists(
        "ix_operations_operation_type", "operations", ["operation_type"]
    )

    # Adjust types for enums
    op.alter_column("operations", "operation_type", type_=operation_type_enum, existing_nullable=False)
    op.alter_column("operations", "status", type_=operation_status_enum, existing_nullable=False)

    with op.batch_alter_table("limits_rules") as batch:
        batch.add_column(sa.Column("entity_type", limit_entity_enum, nullable=False, server_default="CLIENT"))
        batch.add_column(sa.Column("scope", limit_scope_enum, nullable=False, server_default="PER_TX"))
        batch.add_column(sa.Column("product_type", fuel_product_enum, nullable=True))
        batch.add_column(sa.Column("max_amount", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("max_quantity", sa.Numeric(18, 3), nullable=True))

    _create_index_if_not_exists("ix_limits_rules_entity_type", "limits_rules", ["entity_type"])
    _create_index_if_not_exists("ix_limits_rules_scope", "limits_rules", ["scope"])
    _create_index_if_not_exists(
        "ix_limits_rules_product_type", "limits_rules", ["product_type"]
    )


def downgrade() -> None:
    _drop_index_if_exists("ix_limits_rules_product_type", table_name="limits_rules")
    _drop_index_if_exists("ix_limits_rules_scope", table_name="limits_rules")
    _drop_index_if_exists("ix_limits_rules_entity_type", table_name="limits_rules")

    with op.batch_alter_table("limits_rules") as batch:
        batch.drop_column("max_quantity")
        batch.drop_column("max_amount")
        batch.drop_column("product_type")
        batch.drop_column("scope")
        batch.drop_column("entity_type")

    _drop_index_if_exists("ix_operations_operation_type", table_name="operations")
    _drop_index_if_exists("ix_operations_status", table_name="operations")
    with op.batch_alter_table("operations") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("auth_code")
        batch.drop_column("risk_payload")
        batch.drop_column("risk_result")
        batch.drop_column("risk_score")
        batch.drop_column("limit_check_result")
        batch.drop_column("limit_profile_id")
        batch.drop_column("unit_price")
        batch.drop_column("quantity")
        batch.drop_column("product_type")
        batch.drop_column("amount_settled")
        batch.drop_column("product_id")
        batch.drop_constraint("operations_pkey", type_="primary")
        batch.create_primary_key("operations_pkey", ["operation_id"])
        batch.drop_column("id")

    risk_result_enum.drop(op.get_bind(), checkfirst=True)
    product_type_enum.drop(op.get_bind(), checkfirst=True)
    operation_status_enum.drop(op.get_bind(), checkfirst=True)
    operation_type_enum.drop(op.get_bind(), checkfirst=True)
    limit_entity_enum.drop(op.get_bind(), checkfirst=True)
    limit_scope_enum.drop(op.get_bind(), checkfirst=True)
    fuel_product_enum.drop(op.get_bind(), checkfirst=True)
