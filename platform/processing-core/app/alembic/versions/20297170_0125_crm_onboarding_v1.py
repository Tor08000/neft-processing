"""crm onboarding v1 tables.

Revision ID: 20297170_0125_crm_onboarding_v1
Revises: 20297160_0124_fix_operations_client_id_type
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    table_exists,
)
from db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20297170_0125_crm_onboarding_v1"
down_revision = "20297160_0124_fix_operations_client_id_type"
branch_labels = None
depends_on = None

CRM_LEAD_STATUS = ["NEW", "QUALIFIED", "DISQUALIFIED", "CONVERTED"]
CRM_DEAL_STAGE = ["DISCOVERY", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]
CRM_DEAL_EVENT_TYPE = ["STAGE_CHANGED", "NOTE", "CALL", "EMAIL", "TASK_CREATED", "CONTRACT_LINKED"]
CRM_TASK_SUBJECT_TYPE = ["LEAD", "DEAL", "CLIENT", "CONTRACT", "TICKET"]
CRM_TASK_STATUS = ["OPEN", "DONE", "CANCELLED"]
CRM_TASK_PRIORITY = ["LOW", "MEDIUM", "HIGH"]
CRM_CLIENT_PROFILE_STATUS = ["PROSPECT", "ACTIVE", "SUSPENDED", "TERMINATED"]
CRM_CLIENT_RISK_LEVEL = ["LOW", "MEDIUM", "HIGH"]
CLIENT_ONBOARDING_STATE = [
    "LEAD_CREATED",
    "QUALIFIED_CLIENT_CREATED",
    "LEGAL_ACCEPTANCE_PENDING",
    "LEGAL_ACCEPTED",
    "CONTRACT_PENDING",
    "CONTRACT_SIGNED",
    "SUBSCRIPTION_ASSIGNED",
    "LIMITS_APPLIED",
    "CARDS_ISSUED",
    "CLIENT_ACTIVATED",
    "FIRST_OPERATION_ALLOWED",
    "FAILED",
]
CLIENT_ONBOARDING_EVENT_TYPE = ["STATE_CHANGED", "ACTION_APPLIED", "BLOCKED"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "crm_lead_status", CRM_LEAD_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_deal_stage", CRM_DEAL_STAGE, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_deal_event_type", CRM_DEAL_EVENT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_task_subject_type", CRM_TASK_SUBJECT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_task_status", CRM_TASK_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_task_priority", CRM_TASK_PRIORITY, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_client_profile_status", CRM_CLIENT_PROFILE_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "crm_client_risk_level", CRM_CLIENT_RISK_LEVEL, schema=SCHEMA)
    ensure_pg_enum(bind, "client_onboarding_state", CLIENT_ONBOARDING_STATE, schema=SCHEMA)
    ensure_pg_enum(bind, "client_onboarding_event_type", CLIENT_ONBOARDING_EVENT_TYPE, schema=SCHEMA)

    if not table_exists(bind, "crm_leads", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "crm_leads",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.Integer(), nullable=False),
                sa.Column("source", sa.String(length=64)),
                sa.Column(
                    "status",
                    sa.Enum(*CRM_LEAD_STATUS, name="crm_lead_status", native_enum=False),
                    nullable=False,
                ),
                sa.Column("company_name", sa.String(length=256)),
                sa.Column("contact_name", sa.String(length=256)),
                sa.Column("phone", sa.String(length=64)),
                sa.Column("email", sa.String(length=256)),
                sa.Column("comment", sa.Text()),
                sa.Column("utm", sa.JSON()),
                sa.Column("assigned_to", sa.String(length=64)),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_crm_leads_tenant", "crm_leads", ["tenant_id"], schema=SCHEMA)

    if not table_exists(bind, "crm_deals", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "crm_deals",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.Integer(), nullable=False),
                sa.Column("lead_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.crm_leads.id")),
                sa.Column("client_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.crm_clients.id")),
                sa.Column(
                    "stage",
                    sa.Enum(*CRM_DEAL_STAGE, name="crm_deal_stage", native_enum=False),
                    nullable=False,
                ),
                sa.Column("value_amount", sa.BigInteger()),
                sa.Column("currency", sa.String(length=3)),
                sa.Column("probability", sa.Integer()),
                sa.Column("next_step", sa.Text()),
                sa.Column("owner_id", sa.String(length=64)),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_crm_deals_tenant", "crm_deals", ["tenant_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_crm_deals_client", "crm_deals", ["client_id"], schema=SCHEMA)

    if not table_exists(bind, "crm_deal_events", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "crm_deal_events",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("deal_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.crm_deals.id")),
                sa.Column(
                    "event_type",
                    sa.Enum(*CRM_DEAL_EVENT_TYPE, name="crm_deal_event_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column("payload", sa.JSON()),
                sa.Column("actor_id", sa.String(length=64)),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_crm_deal_events_deal", "crm_deal_events", ["deal_id"], schema=SCHEMA)

    if not table_exists(bind, "crm_tasks", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "crm_tasks",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.Integer(), nullable=False),
                sa.Column(
                    "subject_type",
                    sa.Enum(*CRM_TASK_SUBJECT_TYPE, name="crm_task_subject_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column("subject_id", sa.String(length=64), nullable=False),
                sa.Column("title", sa.String(length=256), nullable=False),
                sa.Column("description", sa.Text()),
                sa.Column(
                    "status",
                    sa.Enum(*CRM_TASK_STATUS, name="crm_task_status", native_enum=False),
                    nullable=False,
                ),
                sa.Column(
                    "priority",
                    sa.Enum(*CRM_TASK_PRIORITY, name="crm_task_priority", native_enum=False),
                    nullable=False,
                ),
                sa.Column("due_at", sa.DateTime(timezone=True)),
                sa.Column("assigned_to", sa.String(length=64)),
                sa.Column("created_by", sa.String(length=64)),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_crm_tasks_tenant", "crm_tasks", ["tenant_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_crm_tasks_due", "crm_tasks", ["due_at"], schema=SCHEMA)

    if not table_exists(bind, "crm_ticket_links", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "crm_ticket_links",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("client_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.crm_clients.id")),
                sa.Column("ticket_id", sa.String(length=64), nullable=False),
                sa.Column("linked_by", sa.String(length=64)),
                sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_crm_ticket_links_scope",
            "crm_ticket_links",
            ["client_id", "ticket_id"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "crm_client_profiles", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "crm_client_profiles",
            schema=SCHEMA,
            columns=(
                sa.Column("client_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.crm_clients.id"), primary_key=True),
                sa.Column("legal_name", sa.String(length=256)),
                sa.Column("inn", sa.String(length=32)),
                sa.Column("kpp", sa.String(length=32)),
                sa.Column("ogrn", sa.String(length=32)),
                sa.Column("legal_address", sa.Text()),
                sa.Column("actual_address", sa.Text()),
                sa.Column("bank_details", sa.JSON()),
                sa.Column("contacts", sa.JSON()),
                sa.Column("roles", sa.JSON()),
                sa.Column(
                    "status",
                    sa.Enum(*CRM_CLIENT_PROFILE_STATUS, name="crm_client_profile_status", native_enum=False),
                    nullable=False,
                ),
                sa.Column(
                    "risk_level",
                    sa.Enum(*CRM_CLIENT_RISK_LEVEL, name="crm_client_risk_level", native_enum=False),
                ),
                sa.Column("tags", sa.JSON()),
                sa.Column("notes", sa.Text()),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )

    if not table_exists(bind, "client_onboarding_state", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "client_onboarding_state",
            schema=SCHEMA,
            columns=(
                sa.Column("client_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.crm_clients.id"), primary_key=True),
                sa.Column(
                    "state",
                    sa.Enum(*CLIENT_ONBOARDING_STATE, name="client_onboarding_state", native_enum=False),
                    nullable=False,
                ),
                sa.Column("state_entered_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
                sa.Column("block_reason", sa.Text()),
                sa.Column("meta", sa.JSON()),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )

    if not table_exists(bind, "client_onboarding_events", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "client_onboarding_events",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("client_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.crm_clients.id")),
                sa.Column(
                    "event_type",
                    sa.Enum(*CLIENT_ONBOARDING_EVENT_TYPE, name="client_onboarding_event_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column(
                    "from_state",
                    sa.Enum(*CLIENT_ONBOARDING_STATE, name="client_onboarding_state", native_enum=False),
                ),
                sa.Column(
                    "to_state",
                    sa.Enum(*CLIENT_ONBOARDING_STATE, name="client_onboarding_state", native_enum=False),
                ),
                sa.Column("actor_id", sa.String(length=64)),
                sa.Column("payload", sa.JSON()),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(
            bind,
            "ix_client_onboarding_events_client",
            "client_onboarding_events",
            ["client_id"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    raise RuntimeError("crm onboarding v1 cannot be downgraded")
