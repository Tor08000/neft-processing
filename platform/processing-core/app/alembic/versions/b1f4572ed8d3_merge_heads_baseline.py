"""merge heads (baseline).

Revision ID: b1f4572ed8d3
Revises: 20261201_0017_unified_rules, 20297170_0125_crm_onboarding_v1, 20297200_0125_add_legal_gate_tables, 20297200_0126_notifications_v1, 20297230_0128_integrations_hub_v1, 20297240_0129_bi_runtime_marts_v1, 20298010_0129_security_service_identities_abac
Create Date: 2026-01-12 09:33:54.064694
"""

from __future__ import annotations


revision = "b1f4572ed8d3"
down_revision = (
    "20261201_0017_unified_rules",
    "20297170_0125_crm_onboarding_v1",
    "20297200_0125_add_legal_gate_tables",
    "20297200_0126_notifications_v1",
    "20297230_0128_integrations_hub_v1",
    "20297240_0129_bi_runtime_marts_v1",
    "20298010_0129_security_service_identities_abac",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
