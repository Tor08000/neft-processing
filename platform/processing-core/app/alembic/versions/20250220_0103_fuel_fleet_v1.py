"""fuel fleet v1 tables

Revision ID: 20250220_0103_fuel_fleet_v1
Revises: 20291940_0102_marketplace_contracts_v1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.utils import (
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_expr_index_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    is_postgres,
    table_exists,
)
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20250220_0103_fuel_fleet_v1"
down_revision = "20291940_0102_marketplace_contracts_v1"
branch_labels = None
depends_on = None

FUEL_GROUP_ROLE = ["viewer", "manager", "admin"]
EMPLOYEE_STATUS = ["ACTIVE", "INVITED", "DISABLED"]

CASE_EVENT_TYPES = [
    "CARD_CREATED",
    "CARD_STATUS_CHANGED",
    "GROUP_CREATED",
    "GROUP_MEMBER_ADDED",
    "GROUP_MEMBER_REMOVED",
    "GROUP_ACCESS_GRANTED",
    "GROUP_ACCESS_REVOKED",
    "LIMIT_SET",
    "LIMIT_REVOKED",
    "TRANSACTION_INGESTED",
    "TRANSACTION_IMPORTED",
]


def _schema_prefix() -> str:
    return f"{SCHEMA}." if SCHEMA else ""


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "fuel_group_role", FUEL_GROUP_ROLE, schema=SCHEMA)
    ensure_pg_enum(bind, "employee_status", EMPLOYEE_STATUS, schema=SCHEMA)
    ensure_pg_enum_value(bind, "fuel_card_status", "CLOSED", schema=SCHEMA)
    ensure_pg_enum_value(bind, "case_kind", "FLEET", schema=SCHEMA)
    for value in CASE_EVENT_TYPES:
        ensure_pg_enum_value(bind, "case_event_type", value, schema=SCHEMA)

    if table_exists(bind, "fuel_cards", schema=SCHEMA):
        if not column_exists(bind, "fuel_cards", "card_alias", schema=SCHEMA):
            op.add_column("fuel_cards", sa.Column("card_alias", sa.String(length=128), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_cards", "masked_pan", schema=SCHEMA):
            op.add_column("fuel_cards", sa.Column("masked_pan", sa.String(length=32), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_cards", "token_ref", schema=SCHEMA):
            op.add_column("fuel_cards", sa.Column("token_ref", sa.String(length=128), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_cards", "currency", schema=SCHEMA):
            op.add_column("fuel_cards", sa.Column("currency", sa.String(length=3), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_cards", "audit_event_id", schema=SCHEMA):
            op.add_column("fuel_cards", sa.Column("audit_event_id", sa.String(length=36), nullable=True), schema=SCHEMA)
        create_unique_index_if_not_exists(
            bind,
            "uq_fuel_cards_card_alias",
            "fuel_cards",
            ["card_alias"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_cards_client_status",
            "fuel_cards",
            ["client_id", "status"],
            schema=SCHEMA,
        )

    if table_exists(bind, "fuel_card_groups", schema=SCHEMA):
        if not column_exists(bind, "fuel_card_groups", "description", schema=SCHEMA):
            op.add_column(
                "fuel_card_groups",
                sa.Column("description", sa.String(length=256), nullable=True),
                schema=SCHEMA,
            )
        if not column_exists(bind, "fuel_card_groups", "audit_event_id", schema=SCHEMA):
            op.add_column(
                "fuel_card_groups",
                sa.Column("audit_event_id", sa.String(length=36), nullable=True),
                schema=SCHEMA,
            )
        create_unique_index_if_not_exists(
            bind,
            "uq_fuel_card_groups_client_name",
            "fuel_card_groups",
            ["client_id", "name"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fuel_card_group_members", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fuel_card_group_members",
            schema=SCHEMA,
            columns=(
                sa.Column("group_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.fuel_card_groups.id")),
                sa.Column("card_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.fuel_cards.id")),
                sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("audit_event_id", sa.String(length=36), nullable=True),
                sa.PrimaryKeyConstraint("group_id", "card_id", name="pk_fuel_card_group_members"),
            ),
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_card_group_members_group",
            "fuel_card_group_members",
            ["group_id"],
            schema=SCHEMA,
        )
        if is_postgres(bind):
            bind.exec_driver_sql(
                f"""
                CREATE INDEX IF NOT EXISTS ix_fuel_card_group_members_active
                ON {_schema_prefix()}fuel_card_group_members (group_id, card_id)
                WHERE removed_at IS NULL
                """
            )

    if not table_exists(bind, "client_employees", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "client_employees",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("client_id", sa.String(length=64), nullable=False),
                sa.Column("email", sa.String(length=256), nullable=False),
                sa.Column(
                    "status",
                    sa.Enum(*EMPLOYEE_STATUS, name="employee_status", native_enum=False),
                    nullable=False,
                ),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("audit_event_id", sa.String(length=36), nullable=True),
            ),
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_client_employees_client_email",
            "client_employees",
            ["client_id", "email"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fuel_group_access", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fuel_group_access",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("client_id", sa.String(length=64), nullable=False),
                sa.Column("group_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.fuel_card_groups.id")),
                sa.Column("employee_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.client_employees.id")),
                sa.Column(
                    "role",
                    sa.Enum(*FUEL_GROUP_ROLE, name="fuel_group_role", native_enum=False),
                    nullable=False,
                ),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("audit_event_id", sa.String(length=36), nullable=True),
                sa.UniqueConstraint("group_id", "employee_id", name="uq_fuel_group_access_group_employee"),
            ),
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_group_access_group",
            "fuel_group_access",
            ["group_id"],
            schema=SCHEMA,
        )
        if is_postgres(bind):
            bind.exec_driver_sql(
                f"""
                CREATE INDEX IF NOT EXISTS ix_fuel_group_access_active
                ON {_schema_prefix()}fuel_group_access (group_id, employee_id)
                WHERE revoked_at IS NULL
                """
            )

    if table_exists(bind, "fuel_limits", schema=SCHEMA):
        if not column_exists(bind, "fuel_limits", "amount_limit", schema=SCHEMA):
            op.add_column("fuel_limits", sa.Column("amount_limit", sa.Numeric(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_limits", "volume_limit_liters", schema=SCHEMA):
            op.add_column("fuel_limits", sa.Column("volume_limit_liters", sa.Numeric(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_limits", "categories", schema=SCHEMA):
            op.add_column("fuel_limits", sa.Column("categories", sa.JSON(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_limits", "stations_allowlist", schema=SCHEMA):
            op.add_column("fuel_limits", sa.Column("stations_allowlist", sa.JSON(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_limits", "effective_from", schema=SCHEMA):
            op.add_column(
                "fuel_limits", sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA
            )
        if not column_exists(bind, "fuel_limits", "audit_event_id", schema=SCHEMA):
            op.add_column("fuel_limits", sa.Column("audit_event_id", sa.String(length=36), nullable=True), schema=SCHEMA)
        create_index_if_not_exists(
            bind,
            "ix_fuel_limits_scope",
            "fuel_limits",
            ["client_id", "scope_type", "scope_id"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_limits_scope_active",
            "fuel_limits",
            ["scope_type", "scope_id", "active"],
            schema=SCHEMA,
        )

    if table_exists(bind, "fuel_transactions", schema=SCHEMA):
        if not column_exists(bind, "fuel_transactions", "amount", schema=SCHEMA):
            op.add_column("fuel_transactions", sa.Column("amount", sa.Numeric(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_transactions", "volume_liters", schema=SCHEMA):
            op.add_column("fuel_transactions", sa.Column("volume_liters", sa.Numeric(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_transactions", "category", schema=SCHEMA):
            op.add_column("fuel_transactions", sa.Column("category", sa.String(length=128), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_transactions", "merchant_name", schema=SCHEMA):
            op.add_column("fuel_transactions", sa.Column("merchant_name", sa.String(length=256), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_transactions", "location", schema=SCHEMA):
            op.add_column("fuel_transactions", sa.Column("location", sa.String(length=256), nullable=True), schema=SCHEMA)
        if not column_exists(bind, "fuel_transactions", "station_external_id", schema=SCHEMA):
            op.add_column(
                "fuel_transactions", sa.Column("station_external_id", sa.String(length=128), nullable=True), schema=SCHEMA
            )
        if not column_exists(bind, "fuel_transactions", "raw_payload_redacted", schema=SCHEMA):
            op.add_column(
                "fuel_transactions", sa.Column("raw_payload_redacted", sa.JSON(), nullable=True), schema=SCHEMA
            )
        if not column_exists(bind, "fuel_transactions", "audit_event_id", schema=SCHEMA):
            op.add_column(
                "fuel_transactions", sa.Column("audit_event_id", sa.String(length=36), nullable=True), schema=SCHEMA
            )
        create_unique_expr_index_if_not_exists(
            bind,
            "uq_fuel_transactions_external_ref",
            "fuel_transactions",
            "(external_ref) WHERE external_ref IS NOT NULL",
            schema=SCHEMA,
        )

    if is_postgres(bind) and table_exists(bind, "fuel_transactions", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}fuel_transactions_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'fuel_transactions is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS fuel_transactions_worm_update
                ON {_schema_prefix()}fuel_transactions
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER fuel_transactions_worm_update
                BEFORE UPDATE ON {_schema_prefix()}fuel_transactions
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}fuel_transactions_worm_guard()
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS fuel_transactions_worm_delete
                ON {_schema_prefix()}fuel_transactions
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER fuel_transactions_worm_delete
                BEFORE DELETE ON {_schema_prefix()}fuel_transactions
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}fuel_transactions_worm_guard()
                """
            )
        )

    if is_postgres(bind) and table_exists(bind, "fuel_cards", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}fuel_cards_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.status IS DISTINCT FROM OLD.status
                       OR NEW.token_ref IS DISTINCT FROM OLD.token_ref
                       OR NEW.audit_event_id IS DISTINCT FROM OLD.audit_event_id
                    THEN
                        IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                           OR NEW.client_id IS DISTINCT FROM OLD.client_id
                           OR NEW.card_token IS DISTINCT FROM OLD.card_token
                           OR NEW.card_alias IS DISTINCT FROM OLD.card_alias
                           OR NEW.masked_pan IS DISTINCT FROM OLD.masked_pan
                           OR NEW.currency IS DISTINCT FROM OLD.currency
                           OR NEW.card_group_id IS DISTINCT FROM OLD.card_group_id
                           OR NEW.vehicle_id IS DISTINCT FROM OLD.vehicle_id
                           OR NEW.driver_id IS DISTINCT FROM OLD.driver_id
                           OR NEW.issued_at IS DISTINCT FROM OLD.issued_at
                           OR NEW.blocked_at IS DISTINCT FROM OLD.blocked_at
                           OR NEW.meta IS DISTINCT FROM OLD.meta
                           OR NEW.created_at IS DISTINCT FROM OLD.created_at
                        THEN
                            RAISE EXCEPTION 'fuel_cards is WORM';
                        END IF;
                        RETURN NEW;
                    END IF;
                    RAISE EXCEPTION 'fuel_cards is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS fuel_cards_worm_update
                ON {_schema_prefix()}fuel_cards
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER fuel_cards_worm_update
                BEFORE UPDATE ON {_schema_prefix()}fuel_cards
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}fuel_cards_worm_guard()
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS fuel_cards_worm_delete
                ON {_schema_prefix()}fuel_cards
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER fuel_cards_worm_delete
                BEFORE DELETE ON {_schema_prefix()}fuel_cards
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}fuel_cards_worm_guard()
                """
            )
        )

    if is_postgres(bind) and table_exists(bind, "fuel_limits", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}fuel_limits_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.active IS DISTINCT FROM OLD.active
                       OR NEW.audit_event_id IS DISTINCT FROM OLD.audit_event_id
                    THEN
                        IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                           OR NEW.client_id IS DISTINCT FROM OLD.client_id
                           OR NEW.scope_type IS DISTINCT FROM OLD.scope_type
                           OR NEW.scope_id IS DISTINCT FROM OLD.scope_id
                           OR NEW.fuel_type_code IS DISTINCT FROM OLD.fuel_type_code
                           OR NEW.station_id IS DISTINCT FROM OLD.station_id
                           OR NEW.station_network_id IS DISTINCT FROM OLD.station_network_id
                           OR NEW.limit_type IS DISTINCT FROM OLD.limit_type
                           OR NEW.period IS DISTINCT FROM OLD.period
                           OR NEW.value IS DISTINCT FROM OLD.value
                           OR NEW.currency IS DISTINCT FROM OLD.currency
                           OR NEW.amount_limit IS DISTINCT FROM OLD.amount_limit
                           OR NEW.volume_limit_liters IS DISTINCT FROM OLD.volume_limit_liters
                           OR NEW.categories IS DISTINCT FROM OLD.categories
                           OR NEW.stations_allowlist IS DISTINCT FROM OLD.stations_allowlist
                           OR NEW.priority IS DISTINCT FROM OLD.priority
                           OR NEW.meta IS DISTINCT FROM OLD.meta
                           OR NEW.valid_from IS DISTINCT FROM OLD.valid_from
                           OR NEW.valid_to IS DISTINCT FROM OLD.valid_to
                           OR NEW.time_window_start IS DISTINCT FROM OLD.time_window_start
                           OR NEW.time_window_end IS DISTINCT FROM OLD.time_window_end
                           OR NEW.timezone IS DISTINCT FROM OLD.timezone
                           OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
                           OR NEW.created_at IS DISTINCT FROM OLD.created_at
                        THEN
                            RAISE EXCEPTION 'fuel_limits is WORM';
                        END IF;
                        RETURN NEW;
                    END IF;
                    RAISE EXCEPTION 'fuel_limits is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS fuel_limits_worm_update
                ON {_schema_prefix()}fuel_limits
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER fuel_limits_worm_update
                BEFORE UPDATE ON {_schema_prefix()}fuel_limits
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}fuel_limits_worm_guard()
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS fuel_limits_worm_delete
                ON {_schema_prefix()}fuel_limits
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER fuel_limits_worm_delete
                BEFORE DELETE ON {_schema_prefix()}fuel_limits
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}fuel_limits_worm_guard()
                """
            )
        )

    if is_postgres(bind) and table_exists(bind, "fuel_group_access", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}fuel_group_access_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.revoked_at IS DISTINCT FROM OLD.revoked_at
                       OR NEW.role IS DISTINCT FROM OLD.role
                       OR NEW.audit_event_id IS DISTINCT FROM OLD.audit_event_id
                    THEN
                        IF NEW.client_id IS DISTINCT FROM OLD.client_id
                           OR NEW.group_id IS DISTINCT FROM OLD.group_id
                           OR NEW.employee_id IS DISTINCT FROM OLD.employee_id
                           OR NEW.created_at IS DISTINCT FROM OLD.created_at
                        THEN
                            RAISE EXCEPTION 'fuel_group_access is WORM';
                        END IF;
                        RETURN NEW;
                    END IF;
                    RAISE EXCEPTION 'fuel_group_access is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS fuel_group_access_worm_update
                ON {_schema_prefix()}fuel_group_access
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER fuel_group_access_worm_update
                BEFORE UPDATE ON {_schema_prefix()}fuel_group_access
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}fuel_group_access_worm_guard()
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS fuel_group_access_worm_delete
                ON {_schema_prefix()}fuel_group_access
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER fuel_group_access_worm_delete
                BEFORE DELETE ON {_schema_prefix()}fuel_group_access
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}fuel_group_access_worm_guard()
                """
            )
        )

    if is_postgres(bind) and table_exists(bind, "fuel_card_group_members", schema=SCHEMA):
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_schema_prefix()}fuel_card_group_members_worm_guard()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.removed_at IS DISTINCT FROM OLD.removed_at
                       OR NEW.audit_event_id IS DISTINCT FROM OLD.audit_event_id
                    THEN
                        IF NEW.group_id IS DISTINCT FROM OLD.group_id
                           OR NEW.card_id IS DISTINCT FROM OLD.card_id
                           OR NEW.added_at IS DISTINCT FROM OLD.added_at
                        THEN
                            RAISE EXCEPTION 'fuel_card_group_members is WORM';
                        END IF;
                        RETURN NEW;
                    END IF;
                    RAISE EXCEPTION 'fuel_card_group_members is WORM';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS fuel_card_group_members_worm_update
                ON {_schema_prefix()}fuel_card_group_members
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER fuel_card_group_members_worm_update
                BEFORE UPDATE ON {_schema_prefix()}fuel_card_group_members
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}fuel_card_group_members_worm_guard()
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DROP TRIGGER IF EXISTS fuel_card_group_members_worm_delete
                ON {_schema_prefix()}fuel_card_group_members
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER fuel_card_group_members_worm_delete
                BEFORE DELETE ON {_schema_prefix()}fuel_card_group_members
                FOR EACH ROW EXECUTE FUNCTION {_schema_prefix()}fuel_card_group_members_worm_guard()
                """
            )
        )


def downgrade() -> None:
    pass
