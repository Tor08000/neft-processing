"""operations limits alignment

Revision ID: 20261020_0013
Revises: 20261010_0012_client_ids_uuid
Create Date: 2026-10-20 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import column_exists, constraint_exists, ensure_pg_enum, table_exists
from db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema


def _add_column_if_missing(bind, table_name: str, column: sa.Column) -> None:
    if not column_exists(bind, table_name, column.name, schema=SCHEMA):
        op.add_column(table_name, column, schema=SCHEMA)


def _drop_column_if_exists(bind, table_name: str, column_name: str) -> None:
    if column_exists(bind, table_name, column_name, schema=SCHEMA):
        op.drop_column(table_name, column_name, schema=SCHEMA)

# revision identifiers, used by Alembic.
revision = "20261020_0013"
down_revision = "20261010_0012_client_ids_uuid"
branch_labels = None
depends_on = None

# Migration 20261020_0013a_operations_limits_alignment_alias updates
# `alembic_version_core` automatically for databases that already recorded
# version `20261020_0013`.

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

PRODUCT_TYPE_VALUES = ["DIESEL", "AI92", "AI95", "AI98", "GAS", "OTHER"]

RISK_RESULT_VALUES = ["LOW", "MEDIUM", "HIGH", "BLOCK", "MANUAL_REVIEW"]

LIMIT_ENTITY_VALUES = ["CLIENT", "CARD", "TERMINAL", "MERCHANT"]

LIMIT_SCOPE_VALUES = ["PER_TX", "DAILY", "MONTHLY"]

FUEL_PRODUCT_VALUES = ["ANY", "DIESEL", "AI92", "AI95", "AI98", "GAS", "OTHER"]


operation_type_enum = postgresql.ENUM(
    *OPERATION_TYPE_VALUES, name="operationtype", create_type=False, schema=SCHEMA
)
operation_status_enum = postgresql.ENUM(
    *OPERATION_STATUS_VALUES, name="operationstatus", create_type=False, schema=SCHEMA
)
product_type_enum = postgresql.ENUM(
    *PRODUCT_TYPE_VALUES, name="producttype", create_type=False, schema=SCHEMA
)
risk_result_enum = postgresql.ENUM(
    *RISK_RESULT_VALUES, name="riskresult", create_type=False, schema=SCHEMA
)
limit_entity_enum = postgresql.ENUM(
    *LIMIT_ENTITY_VALUES, name="limitentitytype", create_type=False, schema=SCHEMA
)
limit_scope_enum = postgresql.ENUM(
    *LIMIT_SCOPE_VALUES, name="limitscope", create_type=False, schema=SCHEMA
)
fuel_product_enum = postgresql.ENUM(
    *FUEL_PRODUCT_VALUES, name="fuelproducttype", create_type=False, schema=SCHEMA
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


def _get_inspector(bind):
    return sa.inspect(bind)


def _get_operation_fks(bind, *, referred_columns: list[str]) -> list[tuple[str, dict]]:
    inspector = _get_inspector(bind)
    fks: list[tuple[str, dict]] = []
    for table_name in ("clearing_batch_operation", "ledger_entries"):
        fk_defs = inspector.get_foreign_keys(table_name, schema=SCHEMA)

        for fk in fk_defs:
            if fk.get("referred_table") != "operations":
                continue
            referred = fk.get("referred_columns") or []
            if referred != referred_columns:
                continue

            fks.append((table_name, fk))

    return fks


def _drop_fk_constraints(bind, fk_constraints: list[tuple[str, dict]]) -> None:
    for table_name, fk in fk_constraints:
        fk_name = fk.get("name") or f"{table_name}_operation_id_fkey"
        if constraint_exists(bind, table_name, fk_name, schema=SCHEMA):
            op.drop_constraint(
                fk_name,
                table_name=table_name,
                type_="foreignkey",
                schema=SCHEMA,
            )


def _recreate_fk_constraints(
    bind,
    fk_constraints: list[tuple[str, dict]],
    *,
    prefer_uuid_references: bool = True,
) -> None:
    def _get_child_column_data_type(table_name: str, column_name: str) -> str | None:
        return bind.execute(
            sa.text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = :table_name
                  AND column_name = :column_name
                LIMIT 1
                """
            ),
            {
                "schema": SCHEMA,
                "table_name": table_name,
                "column_name": column_name,
            },
        ).scalar_one_or_none()

    def _resolve_referent_column(table_name: str, column_name: str) -> str:
        if not prefer_uuid_references:
            return "operation_id"

        data_type = (_get_child_column_data_type(table_name, column_name) or "").lower()
        if data_type == "uuid":
            return "id"

        return "operation_id"

    for table_name, fk in fk_constraints:
        fk_name = fk.get("name") or f"{table_name}_operation_id_fkey"
        ondelete = (fk.get("options") or {}).get("ondelete")
        constrained_columns = fk.get("constrained_columns") or ["operation_id"]
        referent_columns = [
            _resolve_referent_column(table_name, constrained_columns[0])
        ]

        op.create_foreign_key(
            fk_name,
            source_table=table_name,
            referent_table="operations",
            local_cols=constrained_columns,
            remote_cols=referent_columns,
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete=ondelete,
        )


def drop_partial_and_expression_indexes(table_name: str) -> list[str]:
    bind = op.get_bind()
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return []

    preparer = getattr(getattr(bind, "dialect", None), "identifier_preparer", None)
    quote = getattr(preparer, "quote", None) or (lambda ident: f'"{ident}"')

    result = bind.execute(
        sa.text(
            """
            SELECT
              idx.relname AS index_name,
              pg_get_expr(i.indpred, i.indrelid) AS predicate,
              pg_get_expr(i.indexprs, i.indrelid) AS expr
            FROM pg_index i
            JOIN pg_class tbl ON tbl.oid = i.indrelid
            JOIN pg_class idx ON idx.oid = i.indexrelid
            JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
            WHERE ns.nspname = :schema
              AND tbl.relname = :table_name
              AND (i.indpred IS NOT NULL OR i.indexprs IS NOT NULL);
            """
        ),
        {"table_name": table_name, "schema": SCHEMA},
    )

    dropped_indexes: list[str] = []
    for index_name, predicate, expr in result.fetchall():  # noqa: B007 - explicit unpacking
        if not index_name:
            continue

        op.execute(sa.text(f"DROP INDEX IF EXISTS {quote(index_name)}"))
        dropped_indexes.append(index_name)

    return dropped_indexes


def _create_operations_active_status_index() -> None:
    _create_index_if_not_exists(
        "idx_operations_active_status",
        "operations",
        ["status", "created_at"],
        where="status IN ('PENDING', 'AUTHORIZED', 'OPEN', 'HELD')",
    )


def _column_is_operationtype_enum(column: dict) -> bool:
    column_type = column.get("type")
    return bool(
        isinstance(column_type, sa.Enum)
        and getattr(column_type, "name", None) == "operationtype"
    )


def _ensure_operation_type_enum(bind) -> None:
    ensure_pg_enum(bind, operation_type_enum.name, values=OPERATION_TYPE_VALUES)
    inspector = _get_inspector(bind)

    table_names = set(inspector.get_table_names()) if inspector is not None else set()

    if "operations" not in table_names:
        return

    columns = {column["name"]: column for column in inspector.get_columns("operations")}
    if "operation_type" not in columns:
        return

    column = columns["operation_type"]
    if _column_is_operationtype_enum(column):
        return

    op.execute(
        sa.text(
            """
            UPDATE operations
            SET operation_type = UPPER(TRIM(operation_type))
            WHERE operation_type IS NOT NULL
            """
        )
    )

    invalid_values = bind.execute(
        sa.text(
            """
            SELECT operation_type, count(*)
            FROM operations
            WHERE operation_type IS NOT NULL
              AND operation_type::text NOT IN :enum_values
            GROUP BY operation_type
            """
        ).bindparams(
            sa.bindparam(
                "enum_values", value=tuple(OPERATION_TYPE_VALUES), expanding=True
            )
        )
    ).fetchall()

    if invalid_values:
        values_list = ", ".join(
            f"{value} ({count})" for value, count in invalid_values[:10]
        )
        raise RuntimeError(
            "operations.operation_type contains values outside enum: "
            f"{values_list}. Please clean the data before rerunning the migration."
        )

    op.alter_column(
        "operations",
        "operation_type",
        type_=operation_type_enum,
        existing_nullable=False,
        postgresql_using="operation_type::operationtype",
    )


def _column_is_operationstatus_enum(column: dict) -> bool:
    column_type = column.get("type")
    return bool(
        isinstance(column_type, sa.Enum)
        and getattr(column_type, "name", None) == "operationstatus"
    )


def _ensure_operation_status_enum(bind) -> None:
    ensure_pg_enum(bind, operation_status_enum.name, values=OPERATION_STATUS_VALUES)
    inspector = _get_inspector(bind)

    table_names = set(inspector.get_table_names()) if inspector is not None else set()

    if "operations" not in table_names:
        return

    columns = {column["name"]: column for column in inspector.get_columns("operations")}
    if "status" not in columns:
        return

    column = columns["status"]
    if _column_is_operationstatus_enum(column):
        return

    op.execute(
        sa.text(
            """
            UPDATE operations
            SET status = UPPER(TRIM(status))
            WHERE status IS NOT NULL
            """
        )
    )

    invalid_values = bind.execute(
        sa.text(
            """
            SELECT status, count(*)
            FROM operations
            WHERE status IS NOT NULL
              AND status::text NOT IN :enum_values
            GROUP BY status
            """
        ).bindparams(
            sa.bindparam("enum_values", value=tuple(OPERATION_STATUS_VALUES), expanding=True)
        )
    ).fetchall()

    if invalid_values:
        values_list = ", ".join(
            f"{value} ({count})" for value, count in invalid_values[:10]
        )
        raise RuntimeError(
            "operations.status contains values outside enum: "
            f"{values_list}. Please clean the data before rerunning the migration."
        )

    drop_partial_and_expression_indexes("operations")

    op.alter_column(
        "operations",
        "status",
        type_=operation_status_enum,
        existing_nullable=False,
        postgresql_using="status::operationstatus",
    )

    _create_operations_active_status_index()


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, operation_type_enum.name, values=OPERATION_TYPE_VALUES)
    ensure_pg_enum(bind, operation_status_enum.name, values=OPERATION_STATUS_VALUES)
    ensure_pg_enum(bind, product_type_enum.name, values=PRODUCT_TYPE_VALUES)
    ensure_pg_enum(bind, risk_result_enum.name, values=RISK_RESULT_VALUES)
    ensure_pg_enum(bind, limit_entity_enum.name, values=LIMIT_ENTITY_VALUES)
    ensure_pg_enum(bind, limit_scope_enum.name, values=LIMIT_SCOPE_VALUES)
    ensure_pg_enum(bind, fuel_product_enum.name, values=FUEL_PRODUCT_VALUES)

    if table_exists(bind, "operations", schema=SCHEMA):
        _add_column_if_missing(
            bind,
            "operations",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
        )
        _add_column_if_missing(
            bind, "operations", sa.Column("product_id", sa.String(length=64), nullable=True)
        )
        _add_column_if_missing(
            bind,
            "operations",
            sa.Column("amount_settled", sa.BigInteger(), nullable=True, server_default="0"),
        )
        _add_column_if_missing(
            bind, "operations", sa.Column("product_type", product_type_enum, nullable=True)
        )
        _add_column_if_missing(
            bind, "operations", sa.Column("quantity", sa.Numeric(18, 3), nullable=True)
        )
        _add_column_if_missing(
            bind, "operations", sa.Column("unit_price", sa.Numeric(18, 3), nullable=True)
        )
        _add_column_if_missing(
            bind, "operations", sa.Column("limit_profile_id", sa.String(length=64), nullable=True)
        )
        _add_column_if_missing(
            bind, "operations", sa.Column("limit_check_result", sa.JSON(), nullable=True)
        )
        _add_column_if_missing(bind, "operations", sa.Column("risk_score", sa.Float(), nullable=True))
        _add_column_if_missing(
            bind, "operations", sa.Column("risk_result", risk_result_enum, nullable=True)
        )
        _add_column_if_missing(bind, "operations", sa.Column("risk_payload", sa.JSON(), nullable=True))
        _add_column_if_missing(
            bind, "operations", sa.Column("auth_code", sa.String(length=32), nullable=True)
        )
        _add_column_if_missing(
            bind,
            "operations",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
        )

        operation_fks = _get_operation_fks(bind, referred_columns=["operation_id"])
        _drop_fk_constraints(bind, operation_fks)

        inspector = _get_inspector(bind)
        if inspector is not None:
            pk = inspector.get_pk_constraint("operations", schema=SCHEMA) or {}
            pk_columns = pk.get("constrained_columns") or []
            pk_name = pk.get("name")
            if pk_name and pk_columns != ["id"]:
                op.drop_constraint(
                    pk_name, table_name="operations", type_="primary", schema=SCHEMA
                )
            if pk_columns != ["id"]:
                op.create_primary_key(
                    "operations_pkey", "operations", ["id"], schema=SCHEMA
                )

        if not constraint_exists(
            bind, "operations", "uq_operations_operation_id", schema=SCHEMA
        ):
            op.create_unique_constraint(
                "uq_operations_operation_id",
                "operations",
                ["operation_id"],
                schema=SCHEMA,
            )

        _recreate_fk_constraints(bind, operation_fks)

    _create_index_if_not_exists("ix_operations_status", "operations", ["status"])
    _create_index_if_not_exists(
        "ix_operations_operation_type", "operations", ["operation_type"]
    )

    _ensure_operation_type_enum(bind)
    _ensure_operation_status_enum(bind)

    if table_exists(bind, "limits_rules", schema=SCHEMA):
        _add_column_if_missing(
            bind,
            "limits_rules",
            sa.Column(
                "entity_type",
                limit_entity_enum,
                nullable=False,
                server_default="CLIENT",
            ),
        )
        _add_column_if_missing(
            bind,
            "limits_rules",
            sa.Column("scope", limit_scope_enum, nullable=False, server_default="PER_TX"),
        )
        _add_column_if_missing(
            bind, "limits_rules", sa.Column("product_type", fuel_product_enum, nullable=True)
        )
        _add_column_if_missing(
            bind, "limits_rules", sa.Column("max_amount", sa.BigInteger(), nullable=True)
        )
        _add_column_if_missing(
            bind, "limits_rules", sa.Column("max_quantity", sa.Numeric(18, 3), nullable=True)
        )

    _create_index_if_not_exists("ix_limits_rules_entity_type", "limits_rules", ["entity_type"])
    _create_index_if_not_exists("ix_limits_rules_scope", "limits_rules", ["scope"])
    _create_index_if_not_exists(
        "ix_limits_rules_product_type", "limits_rules", ["product_type"]
    )


def downgrade() -> None:
    _drop_index_if_exists("ix_limits_rules_product_type", table_name="limits_rules")
    _drop_index_if_exists("ix_limits_rules_scope", table_name="limits_rules")
    _drop_index_if_exists("ix_limits_rules_entity_type", table_name="limits_rules")

    bind = op.get_bind()

    if table_exists(bind, "limits_rules", schema=SCHEMA):
        _drop_column_if_exists(bind, "limits_rules", "max_quantity")
        _drop_column_if_exists(bind, "limits_rules", "max_amount")
        _drop_column_if_exists(bind, "limits_rules", "product_type")
        _drop_column_if_exists(bind, "limits_rules", "scope")
        _drop_column_if_exists(bind, "limits_rules", "entity_type")

    _drop_index_if_exists("ix_operations_operation_type", table_name="operations")
    _drop_index_if_exists("ix_operations_status", table_name="operations")
    if table_exists(bind, "operations", schema=SCHEMA):
        operation_fks = _get_operation_fks(bind, referred_columns=["id"])
        _drop_fk_constraints(bind, operation_fks)

        inspector = _get_inspector(bind)
        pk_name = None
        pk_columns: list[str] = []
        if inspector is not None:
            pk = inspector.get_pk_constraint("operations", schema=SCHEMA) or {}
            pk_columns = pk.get("constrained_columns") or []
            pk_name = pk.get("name")

        if pk_name and pk_columns == ["id"]:
            op.drop_constraint(
                pk_name, table_name="operations", type_="primary", schema=SCHEMA
            )
            op.create_primary_key(
                "operations_pkey", "operations", ["operation_id"], schema=SCHEMA
            )

        if constraint_exists(
            bind, "operations", "uq_operations_operation_id", schema=SCHEMA
        ):
            op.drop_constraint(
                "uq_operations_operation_id",
                table_name="operations",
                type_="unique",
                schema=SCHEMA,
            )

        _recreate_fk_constraints(bind, operation_fks, prefer_uuid_references=False)

        _drop_column_if_exists(bind, "operations", "id")
        _drop_column_if_exists(bind, "operations", "product_id")
        _drop_column_if_exists(bind, "operations", "amount_settled")
        _drop_column_if_exists(bind, "operations", "product_type")
        _drop_column_if_exists(bind, "operations", "quantity")
        _drop_column_if_exists(bind, "operations", "unit_price")
        _drop_column_if_exists(bind, "operations", "limit_profile_id")
        _drop_column_if_exists(bind, "operations", "limit_check_result")
        _drop_column_if_exists(bind, "operations", "risk_score")
        _drop_column_if_exists(bind, "operations", "risk_result")
        _drop_column_if_exists(bind, "operations", "risk_payload")
        _drop_column_if_exists(bind, "operations", "auth_code")
        _drop_column_if_exists(bind, "operations", "updated_at")
