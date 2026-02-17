"""Ensure users.email has a unique constraint compatible with bootstrap upsert.

Revision ID: 20251026_0001_users_email_unique_for_bootstrap
Revises: 20251025_0001_enterprise_security_sessions
Create Date: 2025-10-26 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251026_0001_users_email_unique_for_bootstrap"
down_revision = "20251025_0001_enterprise_security_sessions"
branch_labels = None
depends_on = None

AUTH_SCHEMA = "public"
USERS_TABLE = "users"
UNIQUE_NAME = "uq_users_email"


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names(schema=AUTH_SCHEMA)


def _has_unique_on_email() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for constraint in inspector.get_unique_constraints(USERS_TABLE, schema=AUTH_SCHEMA):
        columns = tuple(constraint.get("column_names") or ())
        if columns == ("email",):
            return True

    for index in inspector.get_indexes(USERS_TABLE, schema=AUTH_SCHEMA):
        if not index.get("unique"):
            continue
        columns = tuple(index.get("column_names") or ())
        if columns == ("email",):
            return True

    return False


def upgrade() -> None:
    if not _table_exists(USERS_TABLE):
        return

    op.execute(
        sa.text(
            f'''
            UPDATE "{AUTH_SCHEMA}".{USERS_TABLE}
            SET email = lower(email)
            WHERE email <> lower(email)
            '''
        )
    )

    op.execute(
        sa.text(
            f'''
            WITH ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY email
                        ORDER BY created_at NULLS LAST, id
                    ) AS rn
                FROM "{AUTH_SCHEMA}".{USERS_TABLE}
            )
            DELETE FROM "{AUTH_SCHEMA}".{USERS_TABLE} u
            USING ranked r
            WHERE u.id = r.id
              AND r.rn > 1
            '''
        )
    )

    if not _has_unique_on_email():
        op.create_unique_constraint(UNIQUE_NAME, USERS_TABLE, ["email"], schema=AUTH_SCHEMA)


def downgrade() -> None:
    if not _table_exists(USERS_TABLE):
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_names = {constraint.get("name") for constraint in inspector.get_unique_constraints(USERS_TABLE, schema=AUTH_SCHEMA)}
    if UNIQUE_NAME in unique_names:
        op.drop_constraint(UNIQUE_NAME, USERS_TABLE, schema=AUTH_SCHEMA, type_="unique")
