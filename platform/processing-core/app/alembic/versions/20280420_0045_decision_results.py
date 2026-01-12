"""Add decision results table.

Revision ID: 20280420_0045_decision_results
Revises: 20280415_0044_accounting_export_batches
Create Date: 2028-04-20 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists
from db.types import GUID
from db.schema import resolve_db_schema

revision = "20280420_0045_decision_results"
down_revision = "20280415_0044_accounting_export_batches"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    bind = op.get_bind()
    json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")

    create_table_if_not_exists(
        bind,
        "decision_results",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("decision_version", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("rule_hits", json_type, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("explain", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "uq_decision_results_decision_id",
        "decision_results",
        ["decision_id"],
        unique=True,
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_decision_results_action",
        "decision_results",
        ["action"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_decision_results_outcome",
        "decision_results",
        ["outcome"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_decision_results_context_hash",
        "decision_results",
        ["context_hash"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass
