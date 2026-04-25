from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.models.audit_log import ActorType, AuditLog
from app.models.cases import Case, CaseEvent
from app.models.decision_memory import DecisionMemoryRecord
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerAccountType,
    InternalLedgerTransaction,
    InternalLedgerTransactionType,
)
from app.models.reconciliation import (
    ExternalStatement,
    ReconciliationDiscrepancy,
    ReconciliationLink,
    ReconciliationLinkStatus,
    ReconciliationRun,
)
from app.models.settlement_v1 import (
    SettlementAccount,
    SettlementItem,
    SettlementPeriod,
    SettlementPeriodStatus,
    SettlementPayout,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.case_events_service import verify_case_event_chain, verify_case_event_signatures
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService
from app.services.reconciliation_service import run_external_reconciliation, upload_external_statement
from app.services.settlement_service import approve_settlement, calculate_settlement_period, execute_payout

from ._scoped_router_harness import scoped_session_context


SETTLEMENT_V1_TEST_TABLES = (
    AuditLog.__table__,
    Case.__table__,
    CaseEvent.__table__,
    DecisionMemoryRecord.__table__,
    InternalLedgerAccount.__table__,
    InternalLedgerTransaction.__table__,
    InternalLedgerEntry.__table__,
    ReconciliationRun.__table__,
    ReconciliationDiscrepancy.__table__,
    ReconciliationLink.__table__,
    ExternalStatement.__table__,
    SettlementAccount.__table__,
    SettlementPeriod.__table__,
    SettlementItem.__table__,
    SettlementPayout.__table__,
)



@pytest.fixture()
def signing_key() -> bytes:
    private_key = Ed25519PrivateKey.generate()
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture(autouse=True)
def audit_signing_env(monkeypatch: pytest.MonkeyPatch, signing_key: bytes) -> None:
    monkeypatch.setenv("AUDIT_SIGNING_MODE", "local")
    monkeypatch.setenv("AUDIT_SIGNING_REQUIRED", "true")
    monkeypatch.setenv("AUDIT_SIGNING_ALG", "ed25519")
    monkeypatch.setenv("AUDIT_SIGNING_KEY_ID", "local-test-key")
    monkeypatch.setenv("AUDIT_SIGNING_PRIVATE_KEY_B64", base64.b64encode(signing_key).decode("utf-8"))


@pytest.fixture
def db_session():
    with scoped_session_context(tables=SETTLEMENT_V1_TEST_TABLES) as session:
        yield session


def _post_partner_entry(
    db_session,
    *,
    partner_id: str,
    currency: str,
    amount: Decimal,
    direction: InternalLedgerEntryDirection,
    source_type: str,
    source_id: str,
    adjustment_kind: str | None = None,
) -> None:
    ledger_service = InternalLedgerService(db_session)
    amount_minor = int(amount * Decimal("100"))
    partner_direction = direction
    clearing_direction = (
        InternalLedgerEntryDirection.DEBIT
        if partner_direction == InternalLedgerEntryDirection.CREDIT
        else InternalLedgerEntryDirection.CREDIT
    )
    meta = {"source_type": source_type, "source_id": source_id}
    if adjustment_kind:
        meta["adjustment_kind"] = adjustment_kind
    ledger_service.post_transaction(
        tenant_id=1,
        transaction_type=InternalLedgerTransactionType.SETTLEMENT_ALLOCATION_CREATED,
        external_ref_type="SETTLEMENT_ITEM",
        external_ref_id=source_id,
        idempotency_key=f"settlement:item:{source_id}",
        posted_at=datetime.now(timezone.utc),
        meta={"source_type": source_type, "source_id": source_id},
        entries=[
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PARTNER_SETTLEMENT,
                client_id=partner_id,
                direction=partner_direction,
                amount=amount_minor,
                currency=currency,
                meta=meta,
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.SETTLEMENT_CLEARING,
                client_id=None,
                direction=clearing_direction,
                amount=amount_minor,
                currency=currency,
                meta=meta,
            ),
        ],
    )


def _ledger_balanced(db_session, tx_id: str) -> bool:
    entries = db_session.query(InternalLedgerEntry).filter(InternalLedgerEntry.ledger_transaction_id == tx_id).all()
    debit_sum = sum(entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.DEBIT)
    credit_sum = sum(entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.CREDIT)
    return debit_sum == credit_sum


def test_settlement_flow_end_to_end(db_session):
    partner_id = "1f1d6d6e-2c9e-4b4f-9f2e-4fabc3344556"
    currency = "RUB"
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=2)
    period_end = now + timedelta(days=2)

    _post_partner_entry(
        db_session,
        partner_id=partner_id,
        currency=currency,
        amount=Decimal("100"),
        direction=InternalLedgerEntryDirection.CREDIT,
        source_type="invoice",
        source_id="d0d4c9c9-7d5c-4a48-8f76-821243dcfe2b",
    )
    _post_partner_entry(
        db_session,
        partner_id=partner_id,
        currency=currency,
        amount=Decimal("10"),
        direction=InternalLedgerEntryDirection.DEBIT,
        source_type="adjustment",
        source_id="6fbdbe89-8cb5-4a53-aad3-3047f3f3a1c5",
        adjustment_kind="fee",
    )
    _post_partner_entry(
        db_session,
        partner_id=partner_id,
        currency=currency,
        amount=Decimal("5"),
        direction=InternalLedgerEntryDirection.DEBIT,
        source_type="refund",
        source_id="7e1d9fda-0c2f-4ec7-9b7d-147edb8a4313",
    )
    _post_partner_entry(
        db_session,
        partner_id=partner_id,
        currency=currency,
        amount=Decimal("2"),
        direction=InternalLedgerEntryDirection.CREDIT,
        source_type="adjustment",
        source_id="7f6a85db-ef1b-4b42-a9dc-91c73b86f47e",
    )

    ctx = RequestContext(
        actor_type=ActorType.USER,
        actor_id="user-1",
        actor_email="user@example.com",
        tenant_id=1,
    )
    period = calculate_settlement_period(
        db_session,
        partner_id=partner_id,
        currency=currency,
        period_start=period_start,
        period_end=period_end,
        actor=ctx,
        idempotency_key="period-1",
    )
    db_session.commit()

    saved_period = db_session.query(SettlementPeriod).filter(SettlementPeriod.id == period.id).one()
    assert saved_period.status == SettlementPeriodStatus.CALCULATED
    assert saved_period.total_gross == Decimal("100")
    assert saved_period.total_fees == Decimal("10")
    assert saved_period.total_refunds == Decimal("5")
    assert saved_period.net_amount == Decimal("87")

    items = db_session.query(SettlementItem).filter(SettlementItem.settlement_period_id == period.id).all()
    assert len(items) == 4

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "SETTLEMENT_CALCULATED")
        .filter(AuditLog.entity_id == str(period.id))
        .one()
    )
    assert audit.id is not None

    approved = approve_settlement(db_session, period_id=str(period.id), actor=ctx)
    db_session.commit()
    assert approved.status == SettlementPeriodStatus.APPROVED

    payout = execute_payout(
        db_session,
        period_id=str(period.id),
        provider="bank_stub",
        idempotency_key="payout-1",
        actor=ctx,
    )
    db_session.commit()

    saved_payout = db_session.query(SettlementPayout).filter(SettlementPayout.id == payout.id).one()
    assert saved_payout.status.value == "SENT"
    assert saved_payout.ledger_tx_id is not None

    ledger_tx = (
        db_session.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.id == saved_payout.ledger_tx_id)
        .one()
    )
    assert ledger_tx.transaction_type == InternalLedgerTransactionType.PARTNER_PAYOUT
    assert _ledger_balanced(db_session, str(ledger_tx.id))

    link = (
        db_session.query(ReconciliationLink)
        .filter(ReconciliationLink.entity_type == "payout", ReconciliationLink.entity_id == payout.id)
        .one()
    )
    assert link.status == ReconciliationLinkStatus.PENDING

    replay = execute_payout(
        db_session,
        period_id=str(period.id),
        provider="bank_stub",
        idempotency_key="payout-1",
        actor=ctx,
    )
    assert replay.id == payout.id
    assert db_session.query(SettlementPayout).count() == 1

    statement = upload_external_statement(
        db_session,
        provider="bank_stub",
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
        currency=currency,
        total_in=None,
        total_out=None,
        closing_balance=None,
        lines=[{"id": "stmt-payout-1", "amount": "87", "direction": "OUT"}],
    )
    run_external_reconciliation(db_session, statement_id=str(statement.id))
    db_session.commit()

    link = (
        db_session.query(ReconciliationLink)
        .filter(ReconciliationLink.entity_type == "payout", ReconciliationLink.entity_id == payout.id)
        .one()
    )
    assert link.status == ReconciliationLinkStatus.MATCHED

    case = db_session.query(Case).filter(Case.entity_id == str(period.id)).one()
    chain = verify_case_event_chain(db_session, case_id=str(case.id))
    signatures = verify_case_event_signatures(db_session, case_id=str(case.id))
    assert chain.verified is True
    assert signatures.verified is True

    audit_verify = AuditService(db_session).verify_chain(
        date_from=now - timedelta(days=5),
        date_to=now + timedelta(days=5),
        tenant_id=1,
    )
    assert audit_verify["status"] == "OK"
