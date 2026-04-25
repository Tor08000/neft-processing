from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.endpoints.fuel_transactions import router as fuel_transactions_router
from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.billing_job_run import BillingJobRun
from app.models.billing_period import BillingPeriod
from app.models.card import Card
from app.models.clearing_batch import ClearingBatch
from app.models.client_actions import DocumentAcknowledgement, ReconciliationRequest
from app.models.crm import (
    ClientOnboardingEvent,
    ClientOnboardingState,
    CRMClient,
    CRMClientProfile,
    CRMContract,
    CRMDeal,
    CRMDealEvent,
    CRMFeatureFlag,
    CRMLead,
    CRMLimitProfile,
    CRMRiskProfile,
    CRMSubscription,
    CRMSubscriptionCharge,
    CRMSubscriptionPeriodSegment,
    CRMTask,
    CRMTariffPlan,
    CRMTicketLink,
    CRMUsageCounter,
)
from app.models.decision_result import DecisionResult
from app.models.documents import Document
from app.models.fleet import FleetDriver, FleetVehicle
from app.models.fuel import (
    FleetOfflineProfile,
    FuelCard,
    FuelCardGroup,
    FuelLimit,
    FuelNetwork,
    FuelRiskProfile,
    FuelRiskShadowEvent,
    FuelStation,
    FuelStationNetwork,
    FuelTransaction,
)
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.invoice import Invoice, InvoiceLine, InvoiceTransitionLog
from app.models.legal_graph import LegalEdge, LegalNode
from app.models.logistics import LogisticsOrder
from app.models.money_flow import MoneyFlowEvent
from app.models.money_flow_v3 import MoneyFlowLink, MoneyInvariantSnapshot
from app.models.pricing import PriceSchedule, PriceVersion
from app.models.risk_decision import RiskDecision
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_training_snapshot import RiskTrainingSnapshot
from app.models.rule import Rule
from app.models.subscriptions_v1 import ClientSubscription, SubscriptionEvent, SubscriptionPlan
from app.routers.admin.crm import router as admin_crm_router
from app.security.rbac.principal import Principal, get_principal

from ._scoped_router_harness import router_client_context, scoped_session_context

CRM_TEST_HEADERS = {"X-CRM-Version": "1"}


def _dedupe_tables(*tables):
    seen: set[str] = set()
    ordered = []
    for table in tables:
        key = str(table.key)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(table)
    return tuple(ordered)


CRM_TEST_TABLES = _dedupe_tables(
    AuditLog.__table__,
    CRMClient.__table__,
    CRMClientProfile.__table__,
    CRMLimitProfile.__table__,
    CRMRiskProfile.__table__,
    CRMTariffPlan.__table__,
    CRMLead.__table__,
    CRMDeal.__table__,
    CRMDealEvent.__table__,
    CRMTask.__table__,
    CRMTicketLink.__table__,
    CRMContract.__table__,
    CRMSubscription.__table__,
    CRMFeatureFlag.__table__,
)

CRM_ONBOARDING_TEST_TABLES = _dedupe_tables(
    *CRM_TEST_TABLES,
    Card.__table__,
    DocumentAcknowledgement.__table__,
    ClientOnboardingState.__table__,
    ClientOnboardingEvent.__table__,
)

CRM_CONTRACT_INTEGRATION_TEST_TABLES = _dedupe_tables(
    *CRM_TEST_TABLES,
    FleetVehicle.__table__,
    FleetDriver.__table__,
    FuelCardGroup.__table__,
    FleetOfflineProfile.__table__,
    FuelCard.__table__,
    FuelNetwork.__table__,
    FuelStationNetwork.__table__,
    FuelStation.__table__,
    FuelLimit.__table__,
    FuelRiskProfile.__table__,
)

CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES = _dedupe_tables(
    *CRM_TEST_TABLES,
    CRMSubscriptionCharge.__table__,
    CRMSubscriptionPeriodSegment.__table__,
    CRMUsageCounter.__table__,
    SubscriptionPlan.__table__,
    ClientSubscription.__table__,
    SubscriptionEvent.__table__,
    PriceVersion.__table__,
    PriceSchedule.__table__,
    BillingPeriod.__table__,
    BillingJobRun.__table__,
    ClearingBatch.__table__,
    ReconciliationRequest.__table__,
    Invoice.__table__,
    InvoiceLine.__table__,
    InvoiceTransitionLog.__table__,
    Document.__table__,
    LegalNode.__table__,
    LegalEdge.__table__,
    InternalLedgerAccount.__table__,
    InternalLedgerTransaction.__table__,
    InternalLedgerEntry.__table__,
    MoneyFlowEvent.__table__,
    MoneyFlowLink.__table__,
    MoneyInvariantSnapshot.__table__,
    DecisionResult.__table__,
    RiskDecision.__table__,
    RiskTrainingSnapshot.__table__,
    RiskThresholdSet.__table__,
    RiskThreshold.__table__,
    RiskPolicy.__table__,
    FleetVehicle.__table__,
    FleetDriver.__table__,
    FuelCardGroup.__table__,
    FleetOfflineProfile.__table__,
    FuelCard.__table__,
    FuelNetwork.__table__,
    FuelStationNetwork.__table__,
    FuelStation.__table__,
    FuelTransaction.__table__,
    LogisticsOrder.__table__,
)

CRM_FUEL_INTEGRATION_TEST_TABLES = _dedupe_tables(
    *CRM_CONTRACT_INTEGRATION_TEST_TABLES,
    Rule.__table__,
    DecisionResult.__table__,
    RiskDecision.__table__,
    RiskTrainingSnapshot.__table__,
    RiskThresholdSet.__table__,
    RiskThreshold.__table__,
    RiskPolicy.__table__,
    FuelTransaction.__table__,
    FuelRiskShadowEvent.__table__,
    InternalLedgerTransaction.__table__,
    LegalNode.__table__,
    LegalEdge.__table__,
)

_ADMIN_PRINCIPAL = Principal(
    user_id=UUID("00000000-0000-0000-0000-000000000001"),
    roles={"admin"},
    scopes=set(),
    client_id=None,
    partner_id=None,
    is_admin=True,
    raw_claims={"roles": ["admin"]},
)


def admin_principal_override() -> Principal:
    return _ADMIN_PRINCIPAL


@contextmanager
def crm_session_context(*, tables=CRM_TEST_TABLES) -> Iterator[Session]:
    with scoped_session_context(tables=tables) as session:
        if any(getattr(table, "key", None) == "documents" for table in tables):
            # `document_files` currently has overlapping ORM definitions in two document contours.
            # For scoped CRM tests we only need the physical table to exist so `Document.files`
            # doesn't trip mapper sync during subscription billing flush.
            session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS document_files (
                        id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        file_type TEXT NULL,
                        bucket TEXT NULL,
                        object_key TEXT NULL,
                        sha256 TEXT NULL,
                        size_bytes BIGINT NULL,
                        content_type TEXT NULL,
                        meta TEXT NULL,
                        storage_key TEXT NULL,
                        filename TEXT NULL,
                        mime TEXT NULL,
                        size BIGINT NULL,
                        created_at DATETIME NULL
                    )
                    """
                )
            )
            session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_document_files_document_id ON document_files (document_id)"
                )
            )
            session.commit()
        yield session


@contextmanager
def crm_admin_client_context(*, db_session: Session) -> Iterator[TestClient]:
    with router_client_context(
        router=admin_crm_router,
        prefix="/api/core/v1/admin",
        db_session=db_session,
        dependency_overrides={get_principal: admin_principal_override},
    ) as client:
        yield client


@contextmanager
def crm_admin_fuel_client_context(*, db_session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(admin_crm_router, prefix="/api/core/v1/admin")
    app.include_router(fuel_transactions_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_principal] = admin_principal_override

    with TestClient(app) as client:
        yield client


__all__ = [
    "CRM_CONTRACT_INTEGRATION_TEST_TABLES",
    "CRM_FUEL_INTEGRATION_TEST_TABLES",
    "CRM_ONBOARDING_TEST_TABLES",
    "CRM_SUBSCRIPTION_INTEGRATION_TEST_TABLES",
    "CRM_TEST_HEADERS",
    "CRM_TEST_TABLES",
    "crm_admin_client_context",
    "crm_admin_fuel_client_context",
    "crm_session_context",
]
