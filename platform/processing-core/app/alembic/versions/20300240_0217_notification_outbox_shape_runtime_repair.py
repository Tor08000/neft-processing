"""Repair legacy notification_outbox shape drift for shared runtime.

Revision ID: 20300240_0217_notification_outbox_shape_runtime_repair
Revises: 20300230_0216_notification_outbox_tenant_client_runtime_repair
Create Date: 2030-01-19 02:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, create_index_if_not_exists, table_exists


revision = "20300240_0217_notification_outbox_shape_runtime_repair"
down_revision = "20300230_0216_notification_outbox_tenant_client_runtime_repair"
branch_labels = None
depends_on = None


def _schema_prefix() -> str:
    return f"{DB_SCHEMA}." if DB_SCHEMA else ""


def _json_empty_sql(bind) -> str:
    if bind.dialect.name == "postgresql":
        return "'{}'::jsonb"
    return "'{}'"


def upgrade() -> None:
    bind = op.get_bind()
    schema_prefix = _schema_prefix()

    if not table_exists(bind, "notification_outbox", schema=DB_SCHEMA):
        return

    if not column_exists(bind, "notification_outbox", "aggregate_type", schema=DB_SCHEMA):
        op.add_column(
            "notification_outbox",
            sa.Column("aggregate_type", sa.Text(), nullable=True),
            schema=DB_SCHEMA,
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {schema_prefix}notification_outbox
                SET aggregate_type = COALESCE(aggregate_type, subject_type::text, 'notification')
                WHERE aggregate_type IS NULL
                """
            )
        )
        op.alter_column("notification_outbox", "aggregate_type", nullable=False, schema=DB_SCHEMA)

    if not column_exists(bind, "notification_outbox", "aggregate_id", schema=DB_SCHEMA):
        op.add_column(
            "notification_outbox",
            sa.Column("aggregate_id", sa.Text(), nullable=True),
            schema=DB_SCHEMA,
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {schema_prefix}notification_outbox
                SET aggregate_id = COALESCE(aggregate_id, subject_id, id::text)
                WHERE aggregate_id IS NULL
                """
            )
        )
        op.alter_column("notification_outbox", "aggregate_id", nullable=False, schema=DB_SCHEMA)

    if not column_exists(bind, "notification_outbox", "payload", schema=DB_SCHEMA):
        op.add_column(
            "notification_outbox",
            sa.Column("payload", sa.JSON(), nullable=True, server_default=sa.text(_json_empty_sql(bind))),
            schema=DB_SCHEMA,
        )

    create_index_if_not_exists(
        bind,
        "ix_notification_outbox_aggregate",
        "notification_outbox",
        ["aggregate_type", "aggregate_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    # Keep runtime repair additive-only to avoid breaking legacy shared outbox readers.
    pass
