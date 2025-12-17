"""Fix limit config scope enum and add window period

Revision ID: 20270710_0028_limit_config_scope_enum_fix
Revises: 20270626_0027_add_posting_result_to_operations
Create Date: 2027-07-10 00:00:00
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import column_exists, is_postgres, safe_enum, table_exists

# revision identifiers, used by Alembic.
revision = "20270710_0028_limit_config_scope_enum_fix"
down_revision = "20270626_0027_add_posting_result_to_operations"
branch_labels = None
depends_on: Sequence[str] | None = None


LIMIT_CONFIG_SCOPE_VALUES = ["GLOBAL", "CLIENT", "CARD", "TARIFF"]
LIMIT_WINDOW_VALUES = ["PER_TX", "DAILY", "MONTHLY"]
LIMIT_WINDOW_ENUM_NAME = "limitwindow"
LIMIT_CONFIG_SCOPE_ENUM_NAME = "limitconfigscope"


def _ensure_enum_exists(enum_name: str, values: Sequence[str]) -> None:
    bind = op.get_bind()
    if not is_postgres(bind):  # pragma: no cover - defensive for sqlite
        return

    exists = bind.exec_driver_sql(
        "SELECT 1 FROM pg_type WHERE typname = %s",
        (enum_name,),
    ).first()
    if exists:
        return

    values_sql = ", ".join(f"'{value}'" for value in values)
    op.execute(sa.text(f"CREATE TYPE {enum_name} AS ENUM ({values_sql})"))


def _ensure_enum_labels(enum_name: str, values: Sequence[str]) -> None:
    """Ensure a Postgres enum has at least the provided values."""

    bind = op.get_bind()
    if not is_postgres(bind):  # pragma: no cover - defensive for sqlite
        return

    _ensure_enum_exists(enum_name, values)
    existing_labels = _get_enum_labels(enum_name)

    for value in values:
        if value in existing_labels:
            continue
        op.execute(sa.text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def _get_column_udt_name(table: str, column: str) -> str | None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return None

    result = bind.exec_driver_sql(
        """
        SELECT udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """,
        (table, column),
    ).first()
    return result[0] if result else None


def _get_enum_labels(enum_name: str) -> list[str]:
    bind = op.get_bind()
    if not is_postgres(bind):
        return []

    rows = bind.exec_driver_sql(
        """
        SELECT e.enumlabel
        FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        WHERE t.typname = %s
        ORDER BY e.enumsortorder
        """,
        (enum_name,),
    ).fetchall()
    return [row[0] for row in rows]


def _ensure_window_column_type(window_enum) -> None:
    bind = op.get_bind()
    if not is_postgres(bind):  # pragma: no cover - sqlite fallback
        return
    if not column_exists(bind, "limit_configs", "window"):
        return

    current_type = _get_column_udt_name("limit_configs", "window")
    existing_labels = _get_enum_labels(LIMIT_WINDOW_ENUM_NAME)
    recreate_type = bool(existing_labels and set(existing_labels) != set(LIMIT_WINDOW_VALUES))
    target_enum_name = LIMIT_WINDOW_ENUM_NAME if not recreate_type else f"{LIMIT_WINDOW_ENUM_NAME}_new"

    if recreate_type:
        _ensure_enum_exists(target_enum_name, LIMIT_WINDOW_VALUES)

    enum_to_use = (
        window_enum
        if target_enum_name == LIMIT_WINDOW_ENUM_NAME
        else safe_enum(bind, target_enum_name, LIMIT_WINDOW_VALUES)
    )

    normalized_case = """
        CASE
            WHEN "window" IS NULL THEN 'PER_TX'::{target}
            WHEN "window"::text = 'DAY' THEN 'DAILY'::{target}
            WHEN "window"::text = 'MONTH' THEN 'MONTHLY'::{target}
            WHEN "window"::text IN ('PER_TX', 'DAILY', 'MONTHLY') THEN "window"::text::{target}
            ELSE 'PER_TX'::{target}
        END
    """.format(target=target_enum_name)

    if current_type != target_enum_name:
        op.alter_column(
            "limit_configs",
            "window",
            type_=enum_to_use,
            postgresql_using=normalized_case,
        )
    else:
        op.execute(sa.text(f"UPDATE limit_configs SET \"window\" = {normalized_case}"))

    if recreate_type:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {LIMIT_WINDOW_ENUM_NAME}"))
        op.execute(sa.text(f"ALTER TYPE {target_enum_name} RENAME TO {LIMIT_WINDOW_ENUM_NAME}"))
        enum_to_use = safe_enum(bind, LIMIT_WINDOW_ENUM_NAME, LIMIT_WINDOW_VALUES)

    op.alter_column(
        "limit_configs",
        "window",
        existing_type=enum_to_use,
        server_default=sa.text("'PER_TX'::limitwindow") if is_postgres(bind) else "PER_TX",
        nullable=False,
    )


def _shift_scope_values_into_window() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):  # pragma: no cover - defensive for sqlite
        return

    op.execute(
        sa.text(
            """
            UPDATE limit_configs
            SET "window" = CASE
                WHEN scope::text IN ('PER_TX', 'DAILY', 'MONTHLY') THEN scope::text::limitwindow
                ELSE "window"
            END
            """
        )
    )


def _convert_scope_column(scope_enum) -> None:
    bind = op.get_bind()
    if not is_postgres(bind):  # pragma: no cover - sqlite fallback
        return
    if not column_exists(bind, "limit_configs", "scope"):
        return

    current_type = _get_column_udt_name("limit_configs", "scope")
    if current_type != LIMIT_CONFIG_SCOPE_ENUM_NAME:
        op.alter_column(
            "limit_configs",
            "scope",
            type_=scope_enum,
            postgresql_using="""
                CASE
                    WHEN scope::text IN ('CLIENT', 'CARD', 'TARIFF', 'GLOBAL')
                        THEN scope::text::limitconfigscope
                    WHEN scope::text IN ('PER_TX', 'DAILY', 'MONTHLY')
                        THEN 'GLOBAL'::limitconfigscope
                    ELSE 'GLOBAL'::limitconfigscope
                END
            """,
        )

    op.execute(sa.text("UPDATE limit_configs SET scope = COALESCE(scope, 'GLOBAL'::limitconfigscope)"))
    op.alter_column(
        "limit_configs",
        "scope",
        existing_type=scope_enum,
        server_default=sa.text("'GLOBAL'::limitconfigscope") if is_postgres(bind) else "GLOBAL",
        nullable=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_enum_exists(LIMIT_CONFIG_SCOPE_ENUM_NAME, LIMIT_CONFIG_SCOPE_VALUES)
    _ensure_enum_exists(LIMIT_WINDOW_ENUM_NAME, LIMIT_WINDOW_VALUES)
    _ensure_enum_labels(LIMIT_CONFIG_SCOPE_ENUM_NAME, LIMIT_CONFIG_SCOPE_VALUES)
    _ensure_enum_labels(LIMIT_WINDOW_ENUM_NAME, LIMIT_WINDOW_VALUES)

    if not table_exists(bind, "limit_configs"):
        return

    window_enum = safe_enum(bind, LIMIT_WINDOW_ENUM_NAME, LIMIT_WINDOW_VALUES)
    scope_enum = safe_enum(bind, LIMIT_CONFIG_SCOPE_ENUM_NAME, LIMIT_CONFIG_SCOPE_VALUES)

    _ensure_window_column_type(window_enum)
    _shift_scope_values_into_window()
    _convert_scope_column(scope_enum)


def downgrade() -> None:
    # No destructive downgrade to avoid breaking existing data; enums are left intact.
    pass
