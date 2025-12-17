"""Fix limit config scope enum and add window period

Revision ID: 20270710_0028_limit_config_scope_enum_fix
Revises: 20270626_0027_add_posting_result_to_operations
Create Date: 2027-07-10 00:00:00
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import (
    column_exists,
    ensure_pg_enum,
    is_postgres,
    safe_enum,
    table_exists,
)

# revision identifiers, used by Alembic.
revision = "20270710_0028_limit_config_scope_enum_fix"
down_revision = "20270626_0027_add_posting_result_to_operations"
branch_labels = None
depends_on: Sequence[str] | None = None


LIMIT_CONFIG_SCOPE_VALUES = ["GLOBAL", "CLIENT", "CARD", "TARIFF"]
LIMIT_WINDOW_VALUES = ["PER_TX", "DAILY", "MONTHLY"]


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


def _ensure_window_column_type(window_enum) -> None:
    bind = op.get_bind()
    if not column_exists(bind, "limit_configs", "window"):
        return

    current_type = _get_column_udt_name("limit_configs", "window")
    if current_type != "limitscope":
        op.alter_column(
            "limit_configs",
            "window",
            type_=window_enum,
            postgresql_using="""
                CASE
                    WHEN window::text = 'DAY' THEN 'DAILY'::limitscope
                    WHEN window::text = 'MONTH' THEN 'MONTHLY'::limitscope
                    WHEN window::text IN ('PER_TX', 'DAILY', 'MONTHLY') THEN window::text::limitscope
                    ELSE 'DAILY'::limitscope
                END
            """,
        )

    op.execute(sa.text("UPDATE limit_configs SET window = COALESCE(window, 'DAILY'::limitscope)"))
    op.alter_column(
        "limit_configs",
        "window",
        existing_type=window_enum,
        server_default=sa.text("'DAILY'::limitscope") if is_postgres(bind) else "DAILY",
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
            SET window = CASE
                WHEN scope::text IN ('PER_TX', 'DAILY', 'MONTHLY') THEN scope::text::limitscope
                ELSE window
            END
            """
        )
    )


def _convert_scope_column(scope_enum) -> None:
    bind = op.get_bind()
    if not column_exists(bind, "limit_configs", "scope"):
        return

    current_type = _get_column_udt_name("limit_configs", "scope")
    if current_type != "limitconfigscope":
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
    ensure_pg_enum(bind, "limitconfigscope", values=LIMIT_CONFIG_SCOPE_VALUES)
    ensure_pg_enum(bind, "limitscope", values=LIMIT_WINDOW_VALUES)

    if not table_exists(bind, "limit_configs"):
        return

    window_enum = safe_enum(bind, "limitscope", LIMIT_WINDOW_VALUES)
    scope_enum = safe_enum(bind, "limitconfigscope", LIMIT_CONFIG_SCOPE_VALUES)

    _ensure_window_column_type(window_enum)
    _shift_scope_values_into_window()
    _convert_scope_column(scope_enum)


def downgrade() -> None:
    # No destructive downgrade to avoid breaking existing data; enums are left intact.
    pass
