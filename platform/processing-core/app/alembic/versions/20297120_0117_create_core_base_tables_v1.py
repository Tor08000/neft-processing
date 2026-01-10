"""Bootstrap core base tables v1.

Revision ID: 20297120_0117_create_core_base_tables_v1
Revises: 20297115_0116_create_money_flow_link_type_enum
Create Date: 2029-07-20 00:00:00.000000
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import SCHEMA, create_index_if_not_exists, ensure_pg_enum, safe_enum, table_exists
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20297120_0117_create_core_base_tables_v1"
down_revision = "20297115_0116_create_money_flow_link_type_enum"  # keep chain after 0116
branch_labels = None
depends_on = None

OPERATION_TYPE_VALUES = [
    "AUTH",
    "HOLD",
    "COMMIT",
    "REVERSE",
    "REFUND",
    "DECLINE",
    "CAPTURE",
    "REVERSAL",
]

OPERATION_STATUS_VALUES = [
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
]

PRODUCT_TYPE_VALUES = [
    "DIESEL",
    "AI92",
    "AI95",
    "AI98",
    "GAS",
    "OTHER",
]

RISK_RESULT_VALUES = [
    "LOW",
    "MEDIUM",
    "HIGH",
    "BLOCK",
    "MANUAL_REVIEW",
]

SCHEMA_RESOLUTION = resolve_db_schema()


def _ensure_schema(bind: sa.engine.Connection) -> None:
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))


def _uuid_type(bind: sa.engine.Connection) -> sa.types.TypeEngine:
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _jsonb_type(bind: sa.engine.Connection) -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_schema(bind)

    print(f"[{revision}] {SCHEMA_RESOLUTION.line()}")

    ensure_pg_enum(bind, "operationtype", OPERATION_TYPE_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "operationstatus", OPERATION_STATUS_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "producttype", PRODUCT_TYPE_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "riskresult", RISK_RESULT_VALUES, schema=SCHEMA)

    operation_type_enum = safe_enum(bind, "operationtype", OPERATION_TYPE_VALUES, schema=SCHEMA)
    operation_status_enum = safe_enum(bind, "operationstatus", OPERATION_STATUS_VALUES, schema=SCHEMA)
    product_type_enum = safe_enum(bind, "producttype", PRODUCT_TYPE_VALUES, schema=SCHEMA)
    risk_result_enum = safe_enum(bind, "riskresult", RISK_RESULT_VALUES, schema=SCHEMA)

    uuid_type = _uuid_type(bind)
    jsonb_type = _jsonb_type(bind)

    operations_exists = table_exists(bind, "operations", schema=SCHEMA)
    if not operations_exists:
        op.create_table(
            "operations",
            sa.Column("id", uuid_type, primary_key=True, nullable=False, default=uuid.uuid4),
            sa.Column("operation_id", sa.String(length=64), nullable=False),
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
            sa.Column("operation_type", operation_type_enum, nullable=False),
            sa.Column("status", operation_status_enum, nullable=False),
            sa.Column("merchant_id", sa.String(length=64), nullable=False),
            sa.Column("terminal_id", sa.String(length=64), nullable=False),
            sa.Column("client_id", sa.String(length=64), nullable=False),
            sa.Column("card_id", sa.String(length=64), nullable=False),
            sa.Column("tariff_id", sa.String(length=64), nullable=True),
            sa.Column("product_id", sa.String(length=64), nullable=True),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("amount_settled", sa.BigInteger(), nullable=True, default=0),
            sa.Column("currency", sa.String(length=3), nullable=False, default="RUB"),
            sa.Column("product_type", product_type_enum, nullable=True),
            sa.Column("quantity", sa.Numeric(18, 3), nullable=True),
            sa.Column("unit_price", sa.Numeric(18, 3), nullable=True),
            sa.Column("captured_amount", sa.BigInteger(), nullable=False, default=0),
            sa.Column("refunded_amount", sa.BigInteger(), nullable=False, default=0),
            sa.Column("daily_limit", sa.BigInteger(), nullable=True),
            sa.Column("limit_per_tx", sa.BigInteger(), nullable=True),
            sa.Column("used_today", sa.BigInteger(), nullable=True),
            sa.Column("new_used_today", sa.BigInteger(), nullable=True),
            sa.Column("limit_profile_id", sa.String(length=64), nullable=True),
            sa.Column("limit_check_result", sa.JSON(), nullable=True),
            sa.Column("authorized", sa.Boolean(), nullable=False, default=False),
            sa.Column("response_code", sa.String(length=8), nullable=False, default="00"),
            sa.Column("response_message", sa.String(length=255), nullable=False, default="OK"),
            sa.Column("auth_code", sa.String(length=32), nullable=True),
            sa.Column("parent_operation_id", sa.String(length=64), nullable=True),
            sa.Column("reason", sa.String(length=255), nullable=True),
            sa.Column("mcc", sa.String(length=8), nullable=True),
            sa.Column("product_code", sa.String(length=32), nullable=True),
            sa.Column("product_category", sa.String(length=32), nullable=True),
            sa.Column("tx_type", sa.String(length=16), nullable=True),
            sa.Column("accounts", jsonb_type, nullable=True),
            sa.Column("posting_result", jsonb_type, nullable=True),
            sa.Column("risk_score", sa.Float(), nullable=True),
            sa.Column("risk_result", risk_result_enum, nullable=True),
            sa.Column("risk_payload", sa.JSON(), nullable=True),
            sa.UniqueConstraint("operation_id", name="uq_operations_operation_id"),
            schema=SCHEMA,
        )
        operations_exists = True

    if operations_exists:
        for index_name, columns in {
            "ix_operations_card_id": ["card_id"],
            "ix_operations_client_id": ["client_id"],
            "ix_operations_merchant_id": ["merchant_id"],
            "ix_operations_terminal_id": ["terminal_id"],
            "ix_operations_created_at": ["created_at"],
            "ix_operations_mcc": ["mcc"],
            "ix_operations_product_category": ["product_category"],
            "ix_operations_tx_type": ["tx_type"],
            "ix_operations_operation_id": ["operation_id"],
            "ix_operations_operation_type": ["operation_type"],
            "ix_operations_status": ["status"],
            "ix_operations_parent_operation_id": ["parent_operation_id"],
            "ix_operations_tariff_id": ["tariff_id"],
        }.items():
            create_index_if_not_exists(bind, index_name, "operations", columns, schema=SCHEMA)

def downgrade() -> None:
    raise RuntimeError("bootstrap core base tables migration cannot be safely downgraded")
