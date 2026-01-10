"""Fix FK type mismatches.

Revision ID: 20297140_0121_fix_fk_type_mismatches_v1
Revises: 20297140_0121_fix_vehicle_recommendations_partner_id_type
Create Date: 2029-07-30 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.helpers import column_exists, constraint_exists, is_postgres, table_exists
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20297140_0121_fix_fk_type_mismatches_v1"
down_revision = "20297140_0121_fix_vehicle_recommendations_partner_id_type"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema
UUID_REGEX = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


FIXES = [
    {
        "table": "marketplace_order_events",
        "column": "audit_event_id",
        "from_type": "varchar(64)",
        "to_type": "uuid",
        "ref_table": "case_events",
        "ref_column": "id",
        "constraint": "marketplace_order_events_audit_event_id_fkey",
    },
    {
        "table": "service_booking_events",
        "column": "audit_event_id",
        "from_type": "varchar(64)",
        "to_type": "uuid",
        "ref_table": "case_events",
        "ref_column": "id",
        "constraint": "service_booking_events_audit_event_id_fkey",
    },
    {
        "table": "fuel_risk_profiles",
        "column": "policy_id",
        "from_type": "uuid",
        "to_type": "varchar(64)",
        "ref_table": "risk_policies",
        "ref_column": "id",
        "constraint": "fuel_risk_profiles_policy_id_fkey",
    },
    {
        "table": "vehicle_service_records",
        "column": "partner_id",
        "from_type": "uuid",
        "to_type": "varchar(64)",
        "ref_table": "partners",
        "ref_column": "id",
        "constraint": "vehicle_service_records_partner_id_fkey",
    },
]


def _column_info(bind, table: str, column: str):
    return bind.execute(
        sa.text(
            """
            SELECT data_type, udt_name, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table_name
              AND column_name = :column_name
            """
        ),
        {"schema": SCHEMA, "table_name": table, "column_name": column},
    ).fetchone()


def _is_uuid_column(column_info) -> bool:
    return bool(column_info and column_info[1] == "uuid")


def _is_string_column(column_info) -> bool:
    return bool(column_info and column_info[0] in {"character varying", "text", "character"})


def _fetch_fk_constraint(bind, table: str, column: str):
    return bind.execute(
        sa.text(
            """
            SELECT tc.constraint_name, rc.delete_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints rc
              ON tc.constraint_name = rc.constraint_name
             AND tc.table_schema = rc.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = :schema
              AND tc.table_name = :table_name
              AND kcu.column_name = :column_name
            """
        ),
        {"schema": SCHEMA, "table_name": table, "column_name": column},
    ).fetchone()


def _drop_fk_if_exists(bind, table: str, fk_name: str) -> None:
    if not table_exists(bind, table, schema=SCHEMA):
        return
    if not constraint_exists(bind, table, fk_name, schema=SCHEMA):
        return
    op.execute(
        sa.text(
            f'ALTER TABLE "{SCHEMA}"."{table}" '
            f'DROP CONSTRAINT IF EXISTS "{fk_name}"'
        )
    )


def _preflight_uuid_cast(bind, table: str, column: str) -> None:
    bad_rows = bind.execute(
        sa.text(
            f'SELECT "{column}" FROM "{SCHEMA}"."{table}" '
            f'WHERE "{column}" IS NOT NULL AND ("{column}"::text) !~* :uuid_regex '
            "LIMIT 20"
        ),
        {"uuid_regex": UUID_REGEX},
    ).fetchall()
    if bad_rows:
        sample = ", ".join(str(row[0]) for row in bad_rows)
        raise RuntimeError(
            f"Cannot convert {table}.{column} to UUID; found non-UUID values. "
            f"Sample ids: {sample}"
        )


def _ensure_case_events_id_uuid(bind) -> None:
    if not table_exists(bind, "case_events", schema=SCHEMA):
        return
    if not column_exists(bind, "case_events", "id", schema=SCHEMA):
        return

    column_info = _column_info(bind, "case_events", "id")
    if _is_uuid_column(column_info):
        return

    _preflight_uuid_cast(bind, "case_events", "id")

    op.execute(
        sa.text(
            f'ALTER TABLE "{SCHEMA}"."case_events" '
            'ALTER COLUMN "id" TYPE UUID USING "id"::uuid'
        )
    )


def _ensure_decision_memory_audit_event_id_uuid(bind) -> None:
    if not table_exists(bind, "decision_memory", schema=SCHEMA):
        return
    if not column_exists(bind, "decision_memory", "audit_event_id", schema=SCHEMA):
        return

    case_events_info = _column_info(bind, "case_events", "id")
    if not _is_uuid_column(case_events_info):
        _ensure_case_events_id_uuid(bind)
        case_events_info = _column_info(bind, "case_events", "id")
    if not _is_uuid_column(case_events_info):
        return

    column_info = _column_info(bind, "decision_memory", "audit_event_id")
    if _is_uuid_column(column_info):
        return

    _preflight_uuid_cast(bind, "decision_memory", "audit_event_id")
    op.execute(
        sa.text(
            f'ALTER TABLE "{SCHEMA}"."decision_memory" '
            'ALTER COLUMN "audit_event_id" TYPE UUID USING "audit_event_id"::uuid'
        )
    )


def _ensure_decision_memory_fk(bind) -> None:
    if not table_exists(bind, "decision_memory", schema=SCHEMA):
        return
    if not column_exists(bind, "decision_memory", "audit_event_id", schema=SCHEMA):
        return
    if not table_exists(bind, "case_events", schema=SCHEMA):
        return
    if not column_exists(bind, "case_events", "id", schema=SCHEMA):
        return
    if constraint_exists(
        bind, "decision_memory", "decision_memory_audit_event_id_fkey", schema=SCHEMA
    ):
        return

    op.create_foreign_key(
        "decision_memory_audit_event_id_fkey",
        "decision_memory",
        "case_events",
        ["audit_event_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )


def _apply_fix(bind, fix: dict) -> None:
    if not table_exists(bind, fix["table"], schema=SCHEMA):
        return
    if not column_exists(bind, fix["table"], fix["column"], schema=SCHEMA):
        return

    column_info = _column_info(bind, fix["table"], fix["column"])
    if fix["to_type"] == "uuid" and _is_uuid_column(column_info):
        return
    if fix["to_type"].startswith("varchar") and _is_string_column(column_info):
        return

    fk_info = _fetch_fk_constraint(bind, fix["table"], fix["column"])
    constraint_name = fk_info[0] if fk_info else None
    delete_rule = fk_info[1] if fk_info else None

    constraint_name = fix["constraint"] or constraint_name
    if constraint_name and constraint_exists(bind, fix["table"], constraint_name, schema=SCHEMA):
        op.drop_constraint(constraint_name, fix["table"], schema=SCHEMA, type_="foreignkey")

    if fix["to_type"] == "uuid":
        _preflight_uuid_cast(bind, fix["table"], fix["column"])
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA}"."{fix["table"]}" '
                f'ALTER COLUMN "{fix["column"]}" TYPE UUID USING "{fix["column"]}"::uuid'
            )
        )
    else:
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA}"."{fix["table"]}" '
                f'ALTER COLUMN "{fix["column"]}" TYPE {fix["to_type"]} USING "{fix["column"]}"::text'
            )
        )

    constraint_name = constraint_name or f'fk_{fix["table"]}_{fix["column"]}_{fix["ref_table"]}'
    if not table_exists(bind, fix["ref_table"], schema=SCHEMA):
        return
    if not column_exists(bind, fix["ref_table"], fix["ref_column"], schema=SCHEMA):
        return
    if not constraint_exists(bind, fix["table"], constraint_name, schema=SCHEMA):
        ondelete = None if delete_rule in {None, "NO ACTION"} else delete_rule
        op.create_foreign_key(
            constraint_name,
            fix["table"],
            fix["ref_table"],
            [fix["column"]],
            [fix["ref_column"]],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete=ondelete,
        )


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    _drop_fk_if_exists(bind, "decision_memory", "decision_memory_audit_event_id_fkey")
    _ensure_case_events_id_uuid(bind)
    _ensure_decision_memory_audit_event_id_uuid(bind)
    _ensure_decision_memory_fk(bind)

    for fix in FIXES:
        _apply_fix(bind, fix)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
