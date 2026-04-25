from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.admin import require_admin_user
from app.api.v1.endpoints.payouts import router as payouts_router
from app.db.schema import DB_SCHEMA
from app.models.account import Account, AccountBalance
from app.models.audit_log import AuditLog
from app.models.billing_period import BillingPeriod
from app.models.billing_job_run import BillingJobRun
from app.models.billing_summary import BillingSummary
from app.models.clearing import Clearing
from app.models.clearing_batch import ClearingBatch
from app.models.clearing_batch_operation import ClearingBatchOperation
from app.models.client_actions import ReconciliationRequest
from app.models.contract_limits import TariffPlan, TariffPrice
from app.models.dispute import Dispute, DisputeEvent
from app.models.financial_adjustment import FinancialAdjustment
from app.models.invoice import Invoice, InvoiceLine, InvoiceTransitionLog
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.ledger_entry import LedgerEntry
from app.models.operation import Operation
from app.models.partner_finance import PartnerLedgerEntry, PartnerPayoutPolicy, PartnerPayoutRequest
from app.models.partner_legal import PartnerLegalDetails, PartnerLegalProfile, PartnerTaxPolicy
from app.models.payout_batch import PayoutBatch, PayoutItem
from app.models.payout_export_file import PayoutExportFile
from app.models.posting_batch import PostingBatch
from app.models.reconciliation import ExternalStatement, ReconciliationDiscrepancy, ReconciliationLink, ReconciliationRun
from app.models.refund_request import RefundRequest
from app.models.settlement_v1 import SettlementPeriod
from app.routers.admin.billing import router as admin_billing_router
from app.routers.admin.clearing import router as admin_clearing_router
from app.routers.admin.finance import router as admin_finance_router
from app.routers.admin.accounts import router as admin_accounts_router
from app.routers.admin.reconciliation import router as admin_reconciliation_router
from app.security.rbac.principal import Principal, get_principal
from app.services.abac.dependency import get_abac_principal
from app.services.abac.engine import AbacPrincipal

from ._scoped_router_harness import router_client_context

ADMIN_BILLING_INVOICE_TEST_TABLES = (
    TariffPlan.__table__,
    TariffPrice.__table__,
    BillingPeriod.__table__,
    ClearingBatch.__table__,
    ReconciliationRequest.__table__,
    Invoice.__table__,
    InvoiceLine.__table__,
    InvoiceTransitionLog.__table__,
    AuditLog.__table__,
)

_REFLECTED_MONEY_METADATA = MetaData()

FUEL_STATIONS_REFLECTED = Table(
    "fuel_stations",
    _REFLECTED_MONEY_METADATA,
    Column("id", String(64), primary_key=True),
)

CARDS_REFLECTED = Table(
    "cards",
    _REFLECTED_MONEY_METADATA,
    Column("id", String(64), primary_key=True),
)

OPERATIONS_REFLECTED = Table(
    "operations",
    _REFLECTED_MONEY_METADATA,
    Column("operation_id", String(64), primary_key=True),
)

BILLING_INVOICES_REFLECTED = Table(
    "billing_invoices",
    _REFLECTED_MONEY_METADATA,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(64), nullable=True),
    Column("client_id", String(64), nullable=True),
    Column("subscription_id", String(64), nullable=True),
    Column("status", String(32), nullable=False),
    Column("period_start", Date, nullable=True),
    Column("period_end", Date, nullable=True),
    Column("issued_at", DateTime(timezone=True), nullable=True),
    Column("due_at", DateTime(timezone=True), nullable=True),
    Column("paid_at", DateTime(timezone=True), nullable=True),
    Column("total_amount", Numeric(18, 4), nullable=True),
    Column("currency", String(8), nullable=True),
    Column("pdf_url", Text, nullable=True),
    Column("pdf_object_key", Text, nullable=True),
    Column("pdf_status", String(32), nullable=True),
    Column("reconciliation_request_id", String(64), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=True),
    schema=DB_SCHEMA,
)

BILLING_PAYMENT_INTAKES_REFLECTED = Table(
    "billing_payment_intakes",
    _REFLECTED_MONEY_METADATA,
    Column("id", Integer, primary_key=True),
    Column("org_id", BigInteger, nullable=False),
    Column("invoice_id", String(36), nullable=False),
    Column("status", String(32), nullable=False),
    Column("amount", Numeric(18, 2), nullable=False),
    Column("currency", String(8), nullable=False),
    Column("payer_name", String(255), nullable=True),
    Column("payer_inn", String(32), nullable=True),
    Column("bank_reference", String(128), nullable=True),
    Column("paid_at_claimed", Date, nullable=True),
    Column("comment", Text, nullable=True),
    Column("proof_object_key", Text, nullable=True),
    Column("proof_file_name", String(255), nullable=True),
    Column("proof_content_type", String(128), nullable=True),
    Column("proof_size", Integer, nullable=True),
    Column("created_by_user_id", String(128), nullable=False),
    Column("reviewed_by_admin", String(128), nullable=True),
    Column("reviewed_at", DateTime(timezone=True), nullable=True),
    Column("review_note", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=True),
    schema=DB_SCHEMA,
)

ADMIN_BILLING_SUMMARY_TEST_TABLES = (
    BillingPeriod.__table__,
    BillingSummary.__table__,
)

ADMIN_CLEARING_TEST_TABLES = (
    BillingPeriod.__table__,
    BillingSummary.__table__,
    Clearing.__table__,
    BillingJobRun.__table__,
    ClearingBatch.__table__,
    OPERATIONS_REFLECTED,
    ClearingBatchOperation.__table__,
)

ADMIN_FINANCE_TEST_TABLES = (
    BILLING_INVOICES_REFLECTED,
    BILLING_PAYMENT_INTAKES_REFLECTED,
    AuditLog.__table__,
    PartnerPayoutRequest.__table__,
    PartnerPayoutPolicy.__table__,
    PartnerLedgerEntry.__table__,
    SettlementPeriod.__table__,
    PartnerLegalProfile.__table__,
    PartnerLegalDetails.__table__,
    PartnerTaxPolicy.__table__,
    FUEL_STATIONS_REFLECTED,
    Operation.__table__,
    Dispute.__table__,
)

ADMIN_RECONCILIATION_TEST_TABLES = (
    InternalLedgerAccount.__table__,
    InternalLedgerTransaction.__table__,
    InternalLedgerEntry.__table__,
    ReconciliationRun.__table__,
    ReconciliationDiscrepancy.__table__,
    ReconciliationLink.__table__,
    ExternalStatement.__table__,
    AuditLog.__table__,
)

PAYOUT_TEST_TABLES = (
    BillingPeriod.__table__,
    FUEL_STATIONS_REFLECTED,
    Operation.__table__,
    PayoutBatch.__table__,
    PayoutItem.__table__,
    PayoutExportFile.__table__,
    AuditLog.__table__,
)

RECONCILIATION_SERVICE_TEST_TABLES = (
    InternalLedgerAccount.__table__,
    InternalLedgerTransaction.__table__,
    InternalLedgerEntry.__table__,
    ReconciliationRun.__table__,
    ExternalStatement.__table__,
    ReconciliationDiscrepancy.__table__,
    ReconciliationLink.__table__,
    AuditLog.__table__,
)

OPERATIONAL_DISPUTE_REFUND_TEST_TABLES = (
    CARDS_REFLECTED,
    Operation.__table__,
    Account.__table__,
    AccountBalance.__table__,
    PostingBatch.__table__,
    LedgerEntry.__table__,
    Dispute.__table__,
    DisputeEvent.__table__,
    RefundRequest.__table__,
    FinancialAdjustment.__table__,
)

ACCOUNT_LEDGER_TEST_TABLES = (
    CARDS_REFLECTED,
    Operation.__table__,
    Account.__table__,
    AccountBalance.__table__,
    PostingBatch.__table__,
    LedgerEntry.__table__,
    AuditLog.__table__,
)

_ADMIN_PRINCIPAL = Principal(
    user_id=UUID("00000000-0000-0000-0000-000000000201"),
    roles={"admin"},
    scopes=set(),
    client_id=None,
    partner_id=None,
    is_admin=True,
    raw_claims={
        "sub": "00000000-0000-0000-0000-000000000201",
        "user_id": "00000000-0000-0000-0000-000000000201",
        "roles": ["ADMIN"],
        "tenant_id": "1",
    },
)


def admin_principal_override() -> Principal:
    return _ADMIN_PRINCIPAL


def admin_token_override() -> dict[str, object]:
    return dict(_ADMIN_PRINCIPAL.raw_claims)


_DEFAULT_PAYOUT_TOKEN = {
    "sub": "00000000-0000-0000-0000-000000000301",
    "user_id": "00000000-0000-0000-0000-000000000301",
    "roles": ["ADMIN", "ADMIN_FINANCE"],
    "tenant_id": "1",
}


def payout_token_override_factory(token_claims: dict[str, object] | None = None):
    claims = dict(_DEFAULT_PAYOUT_TOKEN if token_claims is None else token_claims)

    def _override() -> dict[str, object]:
        return dict(claims)

    return _override


def payout_abac_principal_override_factory(token_claims: dict[str, object] | None = None):
    claims = dict(_DEFAULT_PAYOUT_TOKEN if token_claims is None else token_claims)
    raw_roles = claims.get("roles") or []
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    roles = {str(role) for role in raw_roles if str(role)}
    role = claims.get("role")
    if role:
        roles.add(str(role))
    principal = AbacPrincipal(
        type="USER",
        user_id=str(claims.get("user_id") or claims.get("sub") or ""),
        client_id=str(claims.get("client_id")) if claims.get("client_id") else None,
        partner_id=str(claims.get("partner_id")) if claims.get("partner_id") else None,
        service_name=None,
        roles=roles,
        scopes=set(),
        region=None,
        raw=claims,
    )

    def _override() -> AbacPrincipal:
        return principal

    return _override


@contextmanager
def money_session_context(*, tables=ADMIN_BILLING_SUMMARY_TEST_TABLES) -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_processing_core(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"ATTACH DATABASE ':memory:' AS {DB_SCHEMA}")
        cursor.close()

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )

    for table in tables:
        table.create(bind=engine, checkfirst=True)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(tuple(tables)):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()


@contextmanager
def admin_billing_client_context(*, db_session: Session) -> Iterator[TestClient]:
    # Narrow compatibility-harness for `/api/v1/admin/billing/*` without full app bootstrap.
    with router_client_context(
        router=admin_billing_router,
        prefix="/api/v1/admin",
        db_session=db_session,
        dependency_overrides={
            get_principal: admin_principal_override,
            require_admin_user: admin_token_override,
        },
    ) as client:
        yield client


@contextmanager
def admin_clearing_client_context(*, db_session: Session) -> Iterator[TestClient]:
    # Narrow compatibility-harness for the live `/api/v1/admin/clearing/*` family without full app bootstrap.
    with router_client_context(
        router=admin_clearing_router,
        prefix="/api/v1/admin",
        db_session=db_session,
        dependency_overrides={
            require_admin_user: admin_token_override,
        },
    ) as client:
        yield client


@contextmanager
def admin_finance_client_context(*, db_session: Session) -> Iterator[TestClient]:
    # Canonical admin finance harness for `/api/core/v1/admin/finance/*` without full app bootstrap.
    with router_client_context(
        router=admin_finance_router,
        prefix="/api/core/v1/admin",
        db_session=db_session,
        dependency_overrides={
            get_principal: admin_principal_override,
            require_admin_user: admin_token_override,
        },
    ) as client:
        yield client


@contextmanager
def admin_accounts_client_context(*, db_session: Session) -> Iterator[TestClient]:
    # Narrow admin accounts harness for `/api/v1/admin/accounts*` without full app bootstrap.
    with router_client_context(
        router=admin_accounts_router,
        prefix="/api/v1/admin",
        db_session=db_session,
        dependency_overrides={
            get_principal: admin_principal_override,
            require_admin_user: admin_token_override,
        },
    ) as client:
        yield client


@contextmanager
def admin_reconciliation_client_context(*, db_session: Session) -> Iterator[TestClient]:
    # Canonical admin reconciliation harness for `/api/core/v1/admin/reconciliation/*` without full app bootstrap.
    with router_client_context(
        router=admin_reconciliation_router,
        prefix="/api/core/v1/admin",
        db_session=db_session,
        dependency_overrides={
            get_principal: admin_principal_override,
            require_admin_user: admin_token_override,
        },
    ) as client:
        yield client


@contextmanager
def payout_client_context(
    *,
    db_session: Session,
    token_claims: dict[str, object] | None = None,
) -> Iterator[TestClient]:
    # Narrow payout harness for `/api/v1/payouts/*` with live router/service code and local auth/ABAC overrides.
    with router_client_context(
        router=payouts_router,
        db_session=db_session,
        dependency_overrides={
            require_admin_user: payout_token_override_factory(token_claims),
            get_abac_principal: payout_abac_principal_override_factory(token_claims),
        },
    ) as client:
        client.headers.update({"Authorization": "Bearer smoke-admin"})
        yield client
