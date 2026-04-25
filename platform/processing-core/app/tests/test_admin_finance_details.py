from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import ActorType
from app.models.partner_finance import (
    PartnerLedgerDirection,
    PartnerLedgerEntry,
    PartnerLedgerEntryType,
    PartnerPayoutPolicy,
    PartnerPayoutRequest,
    PartnerPayoutRequestStatus,
    PartnerPayoutSchedule,
)
from app.models.partner_legal import (
    PartnerLegalDetails,
    PartnerLegalProfile,
    PartnerLegalStatus,
    PartnerLegalType,
)
from app.models.settlement_v1 import SettlementPeriod, SettlementPeriodStatus
from app.routers.admin.finance import _ensure_settlement_snapshot, _settlement_snapshot_for_partner
from app.services.audit_service import AuditService, RequestContext

from ._money_router_harness import (
    ADMIN_FINANCE_TEST_TABLES,
    BILLING_INVOICES_REFLECTED,
    BILLING_PAYMENT_INTAKES_REFLECTED,
    admin_finance_client_context,
    money_session_context,
)


@pytest.fixture
def session() -> Session:
    with money_session_context(tables=ADMIN_FINANCE_TEST_TABLES) as db:
        yield db


@pytest.fixture
def finance_client(session: Session) -> TestClient:
    with admin_finance_client_context(db_session=session) as api_client:
        yield api_client


def _audit_ctx() -> RequestContext:
    return RequestContext(actor_type=ActorType.SYSTEM, actor_id="test-suite")


def _seed_reflected_invoice(session: Session, *, invoice_id: str, status: str = "ISSUED") -> None:
    now = datetime.now(timezone.utc)
    session.execute(
        BILLING_INVOICES_REFLECTED.insert().values(
            id=invoice_id,
            org_id="org-100",
            client_id="client-100",
            subscription_id="sub-100",
            status=status,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            issued_at=now - timedelta(days=8),
            due_at=now - timedelta(days=2),
            paid_at=None,
            total_amount=Decimal("12500.00"),
            currency="RUB",
            pdf_url="https://example.test/invoice.pdf",
            pdf_status="READY",
            reconciliation_request_id="recon-1",
            created_at=now - timedelta(days=9),
        )
    )


def _seed_payment_intake(session: Session, *, intake_id: int, invoice_id: str, status: str = "UNDER_REVIEW") -> None:
    session.execute(
        BILLING_PAYMENT_INTAKES_REFLECTED.insert().values(
            id=intake_id,
            org_id=100,
            invoice_id=invoice_id,
            status=status,
            amount=Decimal("12500.00"),
            currency="RUB",
            payer_name="ООО Клиент",
            payer_inn="7701001001",
            bank_reference="PAY-2026-03",
            paid_at_claimed=date(2026, 4, 1),
            comment="manual upload",
            created_by_user_id="client-user-1",
            reviewed_by_admin=None,
            reviewed_at=None,
            review_note=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )


def test_admin_finance_invoice_detail_returns_state_explain_and_timeline(
    finance_client: TestClient,
    session: Session,
) -> None:
    invoice_id = str(uuid4())
    _seed_reflected_invoice(session, invoice_id=invoice_id, status="OVERDUE")
    _seed_payment_intake(session, intake_id=101, invoice_id=invoice_id, status="UNDER_REVIEW")
    _seed_payment_intake(session, intake_id=102, invoice_id=invoice_id, status="APPROVED")

    audit = AuditService(session)
    audit.audit(
        event_type="SUBSCRIPTION_INVOICE_ISSUED",
        entity_type="billing_invoice",
        entity_id=invoice_id,
        action="ISSUED",
        after={"status": "ISSUED"},
        request_ctx=_audit_ctx(),
    )
    audit.audit(
        event_type="SUBSCRIPTION_INVOICE_OVERDUE",
        entity_type="billing_invoice",
        entity_id=invoice_id,
        action="OVERDUE",
        reason="due_date_elapsed",
        before={"status": "ISSUED"},
        after={"status": "OVERDUE"},
        request_ctx=_audit_ctx(),
    )
    session.commit()

    response = finance_client.get(f"/api/core/v1/admin/finance/invoices/{invoice_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == invoice_id
    assert payload["state_explain"]["current_status"] == "OVERDUE"
    assert payload["state_explain"]["has_pdf"] is True
    assert payload["state_explain"]["is_overdue"] is True
    assert payload["state_explain"]["payment_intakes_total"] == 2
    assert payload["state_explain"]["payment_intakes_pending"] == 1
    assert payload["state_explain"]["latest_payment_intake_status"] == "APPROVED"
    assert payload["timeline"][0]["event_type"] == "SUBSCRIPTION_INVOICE_OVERDUE"
    assert payload["timeline"][0]["reason"] == "due_date_elapsed"


def test_admin_finance_payment_intake_detail_returns_invoice_status_and_timeline(
    finance_client: TestClient,
    session: Session,
) -> None:
    invoice_id = str(uuid4())
    _seed_reflected_invoice(session, invoice_id=invoice_id, status="PAID")
    _seed_payment_intake(session, intake_id=201, invoice_id=invoice_id, status="APPROVED")

    audit = AuditService(session)
    audit.audit(
        event_type="PAYMENT_INTAKE_SUBMITTED",
        entity_type="billing_payment_intake",
        entity_id="201",
        action="SUBMIT",
        after={"invoice_id": invoice_id, "status": "SUBMITTED"},
        request_ctx=_audit_ctx(),
    )
    audit.audit(
        event_type="PAYMENT_INTAKE_APPROVED",
        entity_type="billing_payment_intake",
        entity_id="201",
        action="APPROVE",
        reason="bank statement matched",
        after={"invoice_id": invoice_id, "status": "APPROVED"},
        request_ctx=_audit_ctx(),
    )
    session.commit()

    response = finance_client.get("/api/core/v1/admin/finance/payment-intakes/201")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 201
    assert payload["invoice_id"] == invoice_id
    assert payload["invoice_status"] == "PAID"
    assert payload["invoice_link"] == f"/finance/invoices/{invoice_id}"
    assert [item["event_type"] for item in payload["timeline"]] == [
        "PAYMENT_INTAKE_APPROVED",
        "PAYMENT_INTAKE_SUBMITTED",
    ]


def test_admin_finance_payout_detail_returns_blockers_trace_and_audit_explain(
    finance_client: TestClient,
    session: Session,
) -> None:
    partner_id = str(uuid4())
    payout_id = str(uuid4())
    correlation_id = "corr-payout-1"
    now = datetime.now(timezone.utc)

    session.add(
        PartnerPayoutRequest(
            id=payout_id,
            partner_org_id=partner_id,
            amount=Decimal("1500.00"),
            currency="RUB",
            status=PartnerPayoutRequestStatus.REQUESTED,
            requested_by="partner-user-1",
            correlation_id=correlation_id,
            created_at=now - timedelta(hours=2),
        )
    )
    session.add(
        PartnerPayoutPolicy(
            partner_org_id=partner_id,
            currency="RUB",
            min_payout_amount=Decimal("2000.00"),
            payout_hold_days=0,
            payout_schedule=PartnerPayoutSchedule.WEEKLY,
        )
    )
    session.add(
        PartnerLegalProfile(
            partner_id=partner_id,
            legal_type=PartnerLegalType.LEGAL_ENTITY,
            legal_status=PartnerLegalStatus.VERIFIED,
            country="RU",
        )
    )
    session.add(
        PartnerLegalDetails(
            partner_id=partner_id,
            legal_name="ООО Партнер",
            inn="7702002002",
            kpp="770201001",
            ogrn="1027700000001",
            bank_account="40817810000000000001",
            bank_bic="044525225",
            bank_name="АО Банк",
        )
    )
    session.add(
        SettlementPeriod(
            partner_id=partner_id,
            currency="RUB",
            period_start=now - timedelta(days=7),
            period_end=now - timedelta(days=1),
            status=SettlementPeriodStatus.APPROVED,
            total_gross=Decimal("5000.00"),
            total_fees=Decimal("250.00"),
            total_refunds=Decimal("0"),
            net_amount=Decimal("4750.00"),
        )
    )
    session.add(
        PartnerLedgerEntry(
            partner_org_id=partner_id,
            order_id=None,
            entry_type=PartnerLedgerEntryType.PAYOUT_REQUESTED,
            amount=Decimal("1500.00"),
            currency="RUB",
            direction=PartnerLedgerDirection.DEBIT,
            meta_json={"source_type": "payout_request", "source_id": payout_id, "correlation_id": correlation_id},
            created_at=now - timedelta(hours=2),
        )
    )
    session.add(
        PartnerLedgerEntry(
            partner_org_id=partner_id,
            order_id=None,
            entry_type=PartnerLedgerEntryType.PAYOUT_REQUESTED,
            amount=Decimal("1500.00"),
            currency="RUB",
            direction=PartnerLedgerDirection.CREDIT,
            meta_json={
                "source_type": "payout_request",
                "source_id": payout_id,
                "correlation_id": correlation_id,
                "bucket": "blocked",
            },
            created_at=now - timedelta(hours=2),
        )
    )
    audit = AuditService(session)
    audit.audit(
        event_type="partner_payout_requested",
        entity_type="partner_payout_request",
        entity_id=payout_id,
        action="partner_payout_requested",
        after={"partner_org_id": partner_id, "status": "REQUESTED"},
        external_refs={"correlation_id": correlation_id},
        request_ctx=_audit_ctx(),
    )
    session.commit()

    response = finance_client.get(f"/api/core/v1/admin/finance/payouts/{payout_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["payout_id"] == payout_id
    assert payload["blockers"] == ["MIN_THRESHOLD"]
    assert payload["block_reason"] == "MIN_THRESHOLD"
    assert payload["legal_status"] == "VERIFIED"
    assert payload["settlement_state"] == "APPROVED"
    assert payload["correlation_chain"] == [correlation_id]
    assert payload["settlement_snapshot"]["breakdown"]["net"] == "4750.0000"
    assert payload["block_reason_tree"]["policy"]["min_payout_amount"] == "2000.0000"
    assert len(payload["trace"]) == 2
    assert payload["trace"][0]["entity_type"].startswith("partner_ledger_entry:")
    assert payload["audit_events"][0]["event_type"] == "partner_payout_requested"


def test_admin_finance_settlement_snapshot_accepts_legacy_partner_alias(session: Session) -> None:
    canonical_partner_id = str(uuid4())
    competing_partner_id = str(uuid4())
    session.add(
        PartnerLegalProfile(
            partner_id=canonical_partner_id,
            legal_type=PartnerLegalType.LEGAL_ENTITY,
            legal_status=PartnerLegalStatus.VERIFIED,
            country="RU",
        )
    )
    session.add(
        PartnerLegalDetails(
            partner_id=canonical_partner_id,
            legal_name="Partner LLC",
            inn="7702002002",
            kpp="770201001",
            ogrn="1027700000001",
            bank_account="40817810000000000001",
            bank_bic="044525225",
            bank_name="AO Bank",
        )
    )
    session.add(
        PartnerLegalProfile(
            partner_id=competing_partner_id,
            legal_type=PartnerLegalType.LEGAL_ENTITY,
            legal_status=PartnerLegalStatus.VERIFIED,
            country="RU",
        )
    )
    session.add(
        PartnerLegalDetails(
            partner_id=competing_partner_id,
            legal_name="Partner LLC",
            inn="7702002002",
            kpp="770201001",
            ogrn="1027700000001",
            bank_account="40817810000000000002",
            bank_bic="044525225",
            bank_name="AO Bank",
        )
    )
    session.add(
        PartnerLegalProfile(
            partner_id="1",
            legal_type=PartnerLegalType.LEGAL_ENTITY,
            legal_status=PartnerLegalStatus.VERIFIED,
            country="RU",
        )
    )
    session.add(
        PartnerLegalDetails(
            partner_id="1",
            legal_name="Partner LLC",
            inn="7702002002",
            kpp="770201001",
            ogrn="1027700000001",
            bank_account="40817810000000000001",
            bank_bic="044525225",
            bank_name="AO Bank",
        )
    )
    session.add(
        SettlementPeriod(
            partner_id=canonical_partner_id,
            currency="RUB",
            period_start=datetime.now(timezone.utc) - timedelta(days=7),
            period_end=datetime.now(timezone.utc) - timedelta(days=1),
            status=SettlementPeriodStatus.APPROVED,
            total_gross=Decimal("5000.00"),
            total_fees=Decimal("0"),
            total_refunds=Decimal("0"),
            net_amount=Decimal("5000.00"),
        )
    )
    session.commit()

    _ensure_settlement_snapshot(session, partner_id="1", currency="RUB")
    snapshot = _settlement_snapshot_for_partner(session, partner_id="1", currency="RUB")
    assert snapshot is not None
    assert snapshot["partner_org_id"] == canonical_partner_id
