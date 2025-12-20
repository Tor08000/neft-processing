"""Contractual limits and tariffs

Revision ID: 20261205_0018_contract_limits
Revises: 20261201_0017_accounts_and_ledger
Create Date: 2024-12-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import column_exists, ensure_pg_enum, index_exists, safe_enum
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision: str = "20261205_0018_contract_limits"
down_revision: Union[str, None] = "20261201_0017_accounts_and_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LIMIT_SCOPE_VALUES = ["CLIENT", "CARD", "TARIFF"]
LIMIT_TYPE_VALUES = ["DAILY_VOLUME", "DAILY_AMOUNT", "MONTHLY_AMOUNT", "CREDIT_LIMIT"]
LIMIT_WINDOW_VALUES = ["DAY", "MONTH"]

SCHEMA_RESOLUTION = resolve_db_schema()
SCHEMA = SCHEMA_RESOLUTION.schema


def _quote_schema(schema: str) -> str:
    escaped = schema.replace('"', '""')
    return f'"{escaped}"' if schema else schema


QUOTED_SCHEMA = _quote_schema(SCHEMA)


def _qualified(name: str, schema: str = QUOTED_SCHEMA) -> str:
    return f"{schema}.{name}" if schema else name


def table_exists(table_name: str, schema: str = SCHEMA) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT to_regclass(:name)"),
        {"name": _qualified(table_name, schema)},
    )
    return result.scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "limitscope", values=LIMIT_SCOPE_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "limittype", values=LIMIT_TYPE_VALUES, schema=SCHEMA)
    ensure_pg_enum(bind, "limitwindow", values=LIMIT_WINDOW_VALUES, schema=SCHEMA)

    limit_scope_enum = safe_enum(bind, "limitscope", LIMIT_SCOPE_VALUES, schema=SCHEMA)
    limit_type_enum = safe_enum(bind, "limittype", LIMIT_TYPE_VALUES, schema=SCHEMA)
    limit_window_enum = safe_enum(bind, "limitwindow", LIMIT_WINDOW_VALUES, schema=SCHEMA)

    if not table_exists("tariff_plans", schema=SCHEMA):
        op.create_table(
            "tariff_plans",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("params", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
    if not index_exists("ix_tariff_plans_name", schema=SCHEMA):
        op.create_index(
            "ix_tariff_plans_name", "tariff_plans", ["name"], unique=True, schema=SCHEMA
        )

    if not table_exists("limit_configs", schema=SCHEMA):
        op.create_table(
            "limit_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("scope", limit_scope_enum, nullable=False),
            sa.Column("subject_ref", sa.String(length=64), nullable=False),
            sa.Column(
                "limit_type",
                limit_type_enum,
                nullable=False,
            ),
            sa.Column("value", sa.BigInteger(), nullable=False),
            sa.Column("window", limit_window_enum, nullable=False, server_default="DAY"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("tariff_plan_id", sa.String(length=64), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["tariff_plan_id"], [f"{SCHEMA}.tariff_plans.id"], name="fk_limit_tariff"
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
    if not index_exists("ix_limit_configs_scope", schema=SCHEMA):
        op.create_index("ix_limit_configs_scope", "limit_configs", ["scope"], schema=SCHEMA)
    if not index_exists("ix_limit_configs_subject", schema=SCHEMA):
        op.create_index(
            "ix_limit_configs_subject", "limit_configs", ["subject_ref"], schema=SCHEMA
        )
    if not index_exists("ix_limit_configs_enabled", schema=SCHEMA):
        op.create_index(
            "ix_limit_configs_enabled", "limit_configs", ["enabled"], schema=SCHEMA
        )
    if not index_exists("ix_limit_configs_scope_subject_type", schema=SCHEMA):
        op.create_index(
            "ix_limit_configs_scope_subject_type",
            "limit_configs",
            ["scope", "subject_ref", "limit_type"],
            unique=False,
            schema=SCHEMA,
        )

    if not column_exists(bind, "operations", "tariff_id", schema=SCHEMA):
        op.add_column("operations", sa.Column("tariff_id", sa.String(length=64), nullable=True), schema=SCHEMA)
    if not index_exists("ix_operations_tariff_id", schema=SCHEMA):
        op.create_index(
            "ix_operations_tariff_id", "operations", ["tariff_id"], unique=False, schema=SCHEMA
        )


def downgrade() -> None:
    op.drop_index("ix_operations_tariff_id", table_name="operations", schema=SCHEMA)
    op.drop_column("operations", "tariff_id", schema=SCHEMA)

    op.drop_index("ix_limit_configs_scope_subject_type", table_name="limit_configs", schema=SCHEMA)
    op.drop_index("ix_limit_configs_enabled", table_name="limit_configs", schema=SCHEMA)
    op.drop_index("ix_limit_configs_subject", table_name="limit_configs", schema=SCHEMA)
    op.drop_index("ix_limit_configs_scope", table_name="limit_configs", schema=SCHEMA)
    op.drop_table("limit_configs", schema=SCHEMA)

    op.drop_index("ix_tariff_plans_name", table_name="tariff_plans", schema=SCHEMA)
    op.drop_table("tariff_plans", schema=SCHEMA)
