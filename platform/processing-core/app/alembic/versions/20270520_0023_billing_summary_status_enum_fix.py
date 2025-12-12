"""Ensure billing_summary_status enum exists for downgrade safety

Revision ID: 20270520_0023_billing_summary_status_enum_fix
Revises: 20270301_0022_extend_alembic_version_len
Create Date: 2027-05-20 00:00:00
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20270520_0023_billing_summary_status_enum_fix"
down_revision = "20270301_0022_extend_alembic_version_len"
branch_labels = None
depends_on = None


ENUM_NAME = "billing_summary_status"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = '{ENUM_NAME}'
            ) THEN
                CREATE TYPE {ENUM_NAME} AS ENUM (
                    'PENDING',
                    'FINALIZED'
                );
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            type_oid oid;
            is_used boolean;
        BEGIN
            SELECT oid INTO type_oid FROM pg_type WHERE typname = '{ENUM_NAME}' LIMIT 1;

            IF type_oid IS NOT NULL THEN
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_attribute a
                    JOIN pg_class c ON a.attrelid = c.oid
                    WHERE a.atttypid = type_oid
                        AND c.relkind = 'r'
                        AND a.attnum > 0
                ) INTO is_used;

                IF NOT is_used THEN
                    EXECUTE 'DROP TYPE ' || quote_ident('{ENUM_NAME}');
                END IF;
            END IF;
        END $$;
        """
    )
