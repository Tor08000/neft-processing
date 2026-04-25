"""Create card access table for client portal card sharing.

Revision ID: 20300300_0223_card_access_runtime_repair
Revises: 20300290_0222_subscription_plan_demo_seed_runtime_repair
Create Date: 2030-01-20 04:10:00.000000
"""

from __future__ import annotations

from alembic import op

from db.schema import resolve_db_schema


revision = "20300300_0223_card_access_runtime_repair"
down_revision = "20300290_0222_subscription_plan_demo_seed_runtime_repair"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _table(name: str) -> str:
    return f"{_q(SCHEMA)}.{_q(name)}" if SCHEMA else _q(name)


def _type(name: str) -> str:
    return f"{_q(SCHEMA)}.{_q(name)}" if SCHEMA else _q(name)


def upgrade() -> None:
    bind = op.get_bind()

    bind.exec_driver_sql(
        f"""
        DO $$
        BEGIN
            BEGIN
                CREATE TYPE {_type('card_access_scope')} AS ENUM ('VIEW', 'USE', 'MANAGE');
            EXCEPTION
                WHEN duplicate_object OR unique_violation THEN
                    NULL;
            END;
        END $$;
        """
    )
    bind.exec_driver_sql(
        f"""
        CREATE TABLE IF NOT EXISTS {_table('card_access')} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id UUID NOT NULL REFERENCES {_table('clients')}(id),
            user_id VARCHAR(64) NOT NULL,
            card_id VARCHAR NOT NULL,
            scope {_type('card_access_scope')} NOT NULL,
            effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
            effective_to TIMESTAMPTZ NULL,
            created_by VARCHAR(64) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_card_access_user_card UNIQUE (card_id, user_id)
        );
        """
    )
    bind.exec_driver_sql(f"CREATE INDEX IF NOT EXISTS ix_card_access_client_id ON {_table('card_access')} (client_id);")
    bind.exec_driver_sql(f"CREATE INDEX IF NOT EXISTS ix_card_access_user_id ON {_table('card_access')} (user_id);")
    bind.exec_driver_sql(f"CREATE INDEX IF NOT EXISTS ix_card_access_card_id ON {_table('card_access')} (card_id);")


def downgrade() -> None:
    pass
