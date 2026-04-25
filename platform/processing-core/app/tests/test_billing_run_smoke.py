from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.admin import require_admin_user
from app.models.audit_log import AuditLog
from app.models.billing_job_run import BillingJobRun
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.clearing_batch import ClearingBatch
from app.models.client_actions import ReconciliationRequest
from app.models.decision_result import DecisionResult as DecisionResultRecord
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, InvoiceTransitionLog
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.models.risk_decision import RiskDecision
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_training_snapshot import RiskTrainingSnapshot
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.routers.admin.billing import router as admin_billing_router
from app.security.rbac.principal import Principal, get_principal
from app.services.billing_run import BillingRunService
from app.tests._money_router_harness import FUEL_STATIONS_REFLECTED, money_session_context
from app.tests._scoped_router_harness import router_client_context


BILLING_RUN_TEST_TABLES = (
    FUEL_STATIONS_REFLECTED,
    BillingPeriod.__table__,
    BillingJobRun.__table__,
    Operation.__table__,
    ClearingBatch.__table__,
    ReconciliationRequest.__table__,
    Invoice.__table__,
    InvoiceLine.__table__,
    InvoiceTransitionLog.__table__,
    AuditLog.__table__,
    DecisionResultRecord.__table__,
    RiskDecision.__table__,
    RiskPolicy.__table__,
    RiskThresholdSet.__table__,
    RiskThreshold.__table__,
    RiskTrainingSnapshot.__table__,
)


def _make_token(*roles: str) -> dict[str, object]:
    return {
        "sub": "00000000-0000-0000-0000-000000000201",
        "user_id": "00000000-0000-0000-0000-000000000201",
        "tenant_id": "1",
        "roles": list(roles),
    }


def _make_principal(*roles: str) -> Principal:
    return Principal(
        user_id=UUID("00000000-0000-0000-0000-000000000201"),
        roles={"admin"},
        scopes=set(),
        client_id=None,
        partner_id=None,
        is_admin=True,
        raw_claims=_make_token(*roles),
    )


def _seed_global_thresholds(session) -> None:
    if session.query(RiskThresholdSet).count():
        return
    session.add_all(
        [
            RiskThresholdSet(
                id="global-payment-thresholds",
                subject_type=RiskSubjectType.PAYMENT,
                version=1,
                active=True,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.PAYMENT,
                block_threshold=90,
                review_threshold=70,
                allow_threshold=0,
            ),
            RiskThresholdSet(
                id="global-invoice-thresholds",
                subject_type=RiskSubjectType.INVOICE,
                version=1,
                active=True,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.INVOICE,
                block_threshold=90,
                review_threshold=70,
                allow_threshold=0,
            ),
        ]
    )
    session.flush()


@pytest.fixture()
def session():
    with money_session_context(tables=BILLING_RUN_TEST_TABLES) as db:
        _seed_global_thresholds(db)
        db.commit()
        yield db


@contextmanager
def admin_client_context(session, *, roles: tuple[str, ...] = ("ADMIN", "ADMIN_FINANCE")):
    token = _make_token(*roles)
    principal = _make_principal(*roles)

    def token_override() -> dict[str, object]:
        return dict(token)

    def principal_override() -> Principal:
        return principal

    with router_client_context(
        router=admin_billing_router,
        prefix="/api/v1/admin",
        db_session=session,
        dependency_overrides={
            get_principal: principal_override,
            require_admin_user: token_override,
        },
    ) as client:
        yield client


def _make_operation(
    *,
    client_id: str,
    created_at: datetime,
    captured_amount: int,
    refunded_amount: int = 0,
) -> Operation:
    operation_id = str(uuid4())
    return Operation(
        ext_operation_id=operation_id,
        operation_type=OperationType.COMMIT,
        status=OperationStatus.CAPTURED,
        created_at=created_at,
        updated_at=created_at,
        merchant_id="m-1",
        terminal_id="t-1",
        client_id=client_id,
        card_id="card-1",
        product_id="prod-1",
        product_type=ProductType.AI92,
        amount=captured_amount,
        amount_settled=captured_amount,
        currency="RUB",
        quantity=Decimal("10.000"),
        unit_price=Decimal("5.500"),
        captured_amount=captured_amount,
        refunded_amount=refunded_amount,
        response_code="00",
        response_message="OK",
        authorized=True,
    )


def test_billing_run_smoke(session) -> None:
    client_id = str(uuid4())
    start_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)

    operations = [
        _make_operation(client_id=client_id, created_at=start_at + timedelta(hours=1), captured_amount=2_000),
        _make_operation(client_id=client_id, created_at=start_at + timedelta(hours=2), captured_amount=3_000),
    ]
    session.add_all(operations)
    session.commit()

    payload = {
        "period_type": BillingPeriodType.ADHOC.value,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "tz": "UTC",
        "client_id": None,
    }

    with admin_client_context(session) as admin_client:
        first_response = admin_client.post("/api/v1/admin/billing/run", json=payload)
        assert first_response.status_code == 200
        first_body = first_response.json()
        assert first_body["invoices_created"] == 1
        assert first_body["invoice_lines_created"] == len(operations)
        assert first_body["total_amount"] == 5_000
        assert first_body["period_from"] == str(start_at.date())
        assert first_body["period_to"] == str(end_at.date())

        invoice = session.query(Invoice).one()
        assert invoice.period_from == start_at.date()
        assert invoice.period_to == end_at.date()
        assert invoice.status == InvoiceStatus.DRAFT
        lines = session.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).all()
        assert len(lines) == len(operations)
        assert sum(int(line.line_amount) for line in lines) == invoice.total_amount

        second_response = admin_client.post("/api/v1/admin/billing/run", json=payload)
        assert second_response.status_code == 200
        second_body = second_response.json()
        assert second_body["invoices_created"] == 1
        assert second_body["invoices_rebuilt"] == 0
        assert session.query(Invoice).count() == 1

        session.refresh(invoice)
        lines_after = session.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).all()
        assert len(lines_after) == len(operations)
        assert sum(int(line.line_amount) for line in lines_after) == invoice.total_amount


def test_finalize_period_requires_finance_role(session) -> None:
    start_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    payload = {
        "period_type": BillingPeriodType.ADHOC.value,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "tz": "UTC",
    }

    with admin_client_context(session, roles=("ADMIN",)) as admin_client:
        response = admin_client.post("/api/v1/admin/billing/periods/finalize", json=payload)
        assert response.status_code == 403


def test_billing_run_respects_existing_transaction(session) -> None:
    service = BillingRunService(session)
    start_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    client_id = str(uuid4())
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}

    with session.begin():
        operation = _make_operation(
            client_id=client_id,
            created_at=start_at + timedelta(hours=1),
            captured_amount=1_000,
        )
        session.add(operation)
        session.flush()
        service.run(
            period_type=BillingPeriodType.ADHOC,
            start_at=start_at,
            end_at=end_at,
            tz="UTC",
            client_id=None,
            token=token,
        )

    invoice = session.query(Invoice).filter(Invoice.client_id == client_id).one()
    lines = session.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).all()
    assert len(lines) == 1
    assert lines[0].operation_id == operation.operation_id


def test_billing_run_fails_on_locked_period(session) -> None:
    start_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    period = BillingPeriod(
        period_type=BillingPeriodType.ADHOC,
        start_at=start_at,
        end_at=end_at,
        tz="UTC",
        status=BillingPeriodStatus.LOCKED,
    )
    session.add(period)
    session.commit()

    payload = {
        "period_type": BillingPeriodType.ADHOC.value,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "tz": "UTC",
        "client_id": None,
    }

    with admin_client_context(session) as admin_client:
        response = admin_client.post("/api/v1/admin/billing/run", json=payload)
        assert response.status_code == 409
