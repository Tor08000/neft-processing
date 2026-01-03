from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.db import Base, engine, get_sessionmaker
from app.models.audit_log import ActorType, AuditLog
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.cases import Case, CaseEvent
from app.models.finance import CreditNote, InvoicePayment, InvoiceSettlementAllocation, SettlementSourceType
from app.models.internal_ledger import (
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransaction,
)
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus, InvoiceTransitionLog
from app.models.marketplace_contracts import Contract, ContractObligation, ContractStatus
from app.models.marketplace_order_sla import (
    MarketplaceOrderContractLink,
    MarketplaceOrderEvent,
    MarketplaceSlaNotificationOutbox,
    OrderSlaConsequence,
    OrderSlaEvaluation,
)
from app.models.marketplace_orders import MarketplaceOrderActorType, MarketplaceOrderEventType
from app.services.audit_service import RequestContext
from app.services.finance import FinanceService
from app.services.invoice_state_machine import InvalidTransitionError, InvoiceStateMachine
from app.services.order_sla_consequence_service import apply_sla_consequences
from app.services.order_sla_service import evaluate_order_event


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _disable_decision_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    def _noop(*_args, **_kwargs):
        return None

    import app.services.marketplace_contract_binding_service as binding_service
    import app.services.order_sla_consequence_service as sla_consequence_service
    import app.services.order_sla_service as sla_service

    monkeypatch.setattr(binding_service, "record_decision_memory", _noop)
    monkeypatch.setattr(sla_consequence_service, "record_decision_memory", _noop)
    monkeypatch.setattr(sla_service, "record_decision_memory", _noop)


@pytest.fixture()
def db_session():
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def _ledger_balanced(db_session, tx_id: str) -> bool:
    entries = (
        db_session.query(InternalLedgerEntry)
        .filter(InternalLedgerEntry.ledger_transaction_id == tx_id)
        .all()
    )
    debit_sum = sum(entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.DEBIT)
    credit_sum = sum(entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.CREDIT)
    return debit_sum == credit_sum


def _request_ctx() -> RequestContext:
    return RequestContext(
        actor_type=ActorType.USER,
        actor_id="tester",
        actor_roles=["ADMIN", "ADMIN_FINANCE"],
        tenant_id=1,
    )


def _create_invoice(
    db_session,
    *,
    total: int,
    status: InvoiceStatus = InvoiceStatus.SENT,
    amount_paid: int = 0,
    amount_refunded: int = 0,
    credited_amount: int = 0,
    due_date: date | None = None,
    currency: str = "RUB",
) -> Invoice:
    period = BillingPeriod(
        period_type=BillingPeriodType.ADHOC,
        start_at=datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc),
        end_at=datetime.combine(date.today(), datetime.max.time(), tzinfo=timezone.utc),
        tz="UTC",
        status=BillingPeriodStatus.FINALIZED,
    )
    db_session.add(period)
    db_session.flush()
    amount_due = total - amount_paid - credited_amount + amount_refunded
    now = datetime.now(timezone.utc)
    invoice = Invoice(
        client_id="client-1",
        period_from=date.today(),
        period_to=date.today(),
        currency=currency,
        billing_period_id=period.id,
        total_amount=total,
        tax_amount=0,
        total_with_tax=total,
        amount_paid=amount_paid,
        amount_due=amount_due,
        amount_refunded=amount_refunded,
        credited_amount=credited_amount,
        status=status,
        issued_at=now,
        sent_at=now if status in {InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID} else None,
        paid_at=now if status == InvoiceStatus.PAID else None,
        pdf_status=InvoicePdfStatus.READY,
        due_date=due_date,
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def _assert_audit_status(db_session, invoice_id: str, expected_status: InvoiceStatus) -> None:
    events = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_type == "invoice")
        .filter(AuditLog.entity_id == invoice_id)
        .filter(AuditLog.event_type == "INVOICE_STATUS_CHANGED")
        .all()
    )
    assert any(event.after and event.after.get("status") == expected_status.value for event in events)


def test_scn1_partial_payment_idempotent(db_session) -> None:
    invoice = _create_invoice(db_session, total=10_000, currency="USD")
    service = FinanceService(db_session)

    first = service.apply_payment(
        invoice_id=invoice.id,
        amount=4_000,
        currency="RUB",
        idempotency_key="scn1-pay-1",
        external_ref="SCN1-EXT-1",
        provider="bank_stub",
        request_ctx=_request_ctx(),
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": 1},
    )
    db_session.commit()

    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.PARTIALLY_PAID
    assert invoice.amount_paid == 4_000
    assert invoice.amount_due == 6_000

    ledger_tx = (
        db_session.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.external_ref_type == "PAYMENT")
        .filter(InternalLedgerTransaction.external_ref_id == str(first.payment.id))
        .one()
    )
    assert _ledger_balanced(db_session, str(ledger_tx.id))

    _assert_audit_status(db_session, invoice.id, InvoiceStatus.PARTIALLY_PAID)
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == invoice.id)
        .filter(AuditLog.event_type == "INVOICE_PAYMENT_ALLOCATED")
        .count()
        == 1
    )

    replay = service.apply_payment(
        invoice_id=invoice.id,
        amount=4_000,
        currency="RUB",
        idempotency_key="scn1-pay-1",
        external_ref="SCN1-EXT-1",
        provider="bank_stub",
        request_ctx=_request_ctx(),
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": 1},
    )
    db_session.commit()
    assert replay.is_replay is True
    assert replay.payment.id == first.payment.id
    assert db_session.query(InvoicePayment).filter_by(invoice_id=invoice.id).count() == 1

    second = service.apply_payment(
        invoice_id=invoice.id,
        amount=6_000,
        currency="RUB",
        idempotency_key="scn1-pay-2",
        external_ref="SCN1-EXT-2",
        provider="bank_stub",
        request_ctx=_request_ctx(),
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": 1},
    )
    db_session.commit()
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.PAID
    assert invoice.amount_due == 0

    ledger_tx = (
        db_session.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.external_ref_type == "PAYMENT")
        .filter(InternalLedgerTransaction.external_ref_id == str(second.payment.id))
        .one()
    )
    assert _ledger_balanced(db_session, str(ledger_tx.id))

    replay_final = service.apply_payment(
        invoice_id=invoice.id,
        amount=6_000,
        currency="RUB",
        idempotency_key="scn1-pay-2",
        external_ref="SCN1-EXT-2",
        provider="bank_stub",
        request_ctx=_request_ctx(),
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": 1},
    )
    db_session.commit()
    assert replay_final.is_replay is True
    assert db_session.query(InvoicePayment).filter_by(invoice_id=invoice.id).count() == 2
    _assert_audit_status(db_session, invoice.id, InvoiceStatus.PAID)


def test_scn2_overdue_then_paid(db_session) -> None:
    invoice = _create_invoice(db_session, total=7_500, due_date=date.today() - timedelta(days=1))
    machine = InvoiceStateMachine(invoice, db=db_session)

    machine.transition(to=InvoiceStatus.OVERDUE, actor="scheduler", reason="overdue_check")
    db_session.commit()

    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.OVERDUE
    _assert_audit_status(db_session, invoice.id, InvoiceStatus.OVERDUE)

    service = FinanceService(db_session)
    paid = service.apply_payment(
        invoice_id=invoice.id,
        amount=7_500,
        currency="RUB",
        idempotency_key="scn2-pay-1",
        external_ref="SCN2-EXT-1",
        provider="bank_stub",
        request_ctx=_request_ctx(),
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": 1},
    )
    db_session.commit()

    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.PAID
    assert invoice.amount_due == 0

    ledger_tx = (
        db_session.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.external_ref_type == "PAYMENT")
        .filter(InternalLedgerTransaction.external_ref_id == str(paid.payment.id))
        .one()
    )
    assert _ledger_balanced(db_session, str(ledger_tx.id))

    paid_invoice = _create_invoice(db_session, total=5_000, status=InvoiceStatus.PAID, amount_paid=5_000)
    machine = InvoiceStateMachine(paid_invoice, db=db_session)
    with pytest.raises(InvalidTransitionError):
        machine.transition(to=InvoiceStatus.OVERDUE, actor="scheduler", reason="bad_transition")


def test_scn3_cancel_void_idempotent(db_session) -> None:
    invoice = _create_invoice(db_session, total=3_000)
    machine = InvoiceStateMachine(invoice, db=db_session)

    machine.transition(to=InvoiceStatus.CANCELLED, actor="ops", reason="void")
    db_session.commit()
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.CANCELLED
    _assert_audit_status(db_session, invoice.id, InvoiceStatus.CANCELLED)

    machine.transition(to=InvoiceStatus.CANCELLED, actor="ops", reason="void")
    db_session.commit()
    assert (
        db_session.query(InvoiceTransitionLog)
        .filter(InvoiceTransitionLog.invoice_id == invoice.id)
        .filter(InvoiceTransitionLog.to_status == InvoiceStatus.CANCELLED)
        .count()
        == 1
    )
    assert db_session.query(InvoiceSettlementAllocation).filter_by(invoice_id=invoice.id).count() == 0

    paid_invoice = _create_invoice(db_session, total=2_000, status=InvoiceStatus.PAID, amount_paid=2_000)
    machine = InvoiceStateMachine(paid_invoice, db=db_session)
    with pytest.raises(InvalidTransitionError):
        machine.transition(to=InvoiceStatus.CANCELLED, actor="ops", reason="cannot_void_paid")


def test_scn4_refund_after_sla_penalty(db_session) -> None:
    client_id = "22222222-2222-2222-2222-222222222222"
    partner_id = "33333333-3333-3333-3333-333333333333"
    contract = Contract(
        contract_number="C-SLA-001",
        contract_type="service",
        party_a_type="client",
        party_a_id=client_id,
        party_b_type="partner",
        party_b_id=partner_id,
        currency="USD",
        effective_from=datetime.now(timezone.utc) - timedelta(days=1),
        effective_to=None,
        status=ContractStatus.ACTIVE.value,
        audit_event_id="11111111-1111-1111-1111-111111111111",
    )
    obligation = ContractObligation(
        contract_id=contract.id,
        obligation_type="response",
        metric="response_time",
        threshold="30",
        comparison="<=",
        window="order",
        penalty_type="credit",
        penalty_value="1500",
    )
    db_session.add(contract)
    db_session.flush()
    obligation.contract_id = contract.id
    db_session.add(obligation)
    db_session.commit()

    order_id = str(uuid4())
    created_at = datetime.now(timezone.utc) - timedelta(minutes=33)
    accepted_at = datetime.now(timezone.utc)
    created_event = MarketplaceOrderEvent(
        order_id=order_id,
        client_id=client_id,
        partner_id=partner_id,
        event_type=MarketplaceOrderEventType.MARKETPLACE_ORDER_CREATED,
        occurred_at=created_at,
        payload_redacted={},
        actor_type=MarketplaceOrderActorType.SYSTEM,
        audit_event_id=str(uuid4()),
    )
    accepted_event = MarketplaceOrderEvent(
        order_id=order_id,
        client_id=client_id,
        partner_id=partner_id,
        event_type=MarketplaceOrderEventType.MARKETPLACE_ORDER_CONFIRMED_BY_PARTNER,
        occurred_at=accepted_at,
        payload_redacted={},
        actor_type=MarketplaceOrderActorType.SYSTEM,
        audit_event_id=str(uuid4()),
    )
    db_session.add_all([created_event, accepted_event])
    db_session.commit()

    summary = evaluate_order_event(db_session, order_event_id=str(accepted_event.id), request_ctx=_request_ctx())
    assert summary.violations
    evaluation = summary.violations[0]
    db_session.commit()

    consequence_result = apply_sla_consequences(db_session, evaluation_id=str(evaluation.id), request_ctx=_request_ctx())
    db_session.commit()
    assert consequence_result is not None

    sla_audit_types = {
        entry.event_type
        for entry in db_session.query(AuditLog)
        .filter(AuditLog.entity_type.in_(["order_sla_evaluation", "order_sla_consequence"]))
        .all()
    }
    assert "SLA_BREACH_DETECTED" in sla_audit_types
    assert "SLA_CONSEQUENCE_APPLIED" in sla_audit_types

    consequence = db_session.query(OrderSlaConsequence).one()
    sla_tx = (
        db_session.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.external_ref_type == "ORDER_SLA_CONSEQUENCE")
        .filter(InternalLedgerTransaction.external_ref_id == str(consequence.id))
        .one()
    )
    assert _ledger_balanced(db_session, str(sla_tx.id))

    invoice = _create_invoice(db_session, total=10_000)
    invoice.client_id = client_id
    db_session.add(invoice)
    db_session.commit()

    service = FinanceService(db_session)
    credit = service.create_credit_note(
        invoice_id=invoice.id,
        amount=1_500,
        currency="USD",
        reason="sla_penalty",
        idempotency_key="scn4-credit-1",
        request_ctx=_request_ctx(),
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": 1},
    )
    db_session.commit()

    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.PARTIALLY_PAID
    assert invoice.amount_due == 8_500

    payment = service.apply_payment(
        invoice_id=invoice.id,
        amount=8_500,
        currency="USD",
        idempotency_key="scn4-pay-1",
        external_ref="SCN4-PAY-1",
        provider="bank_stub",
        request_ctx=_request_ctx(),
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": 1},
    )
    db_session.commit()

    refund = service.create_refund(
        invoice_id=invoice.id,
        amount=2_000,
        currency="USD",
        reason="order_refund",
        external_ref="SCN4-REF-1",
        provider="bank_stub",
        request_ctx=_request_ctx(),
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": 1},
    )
    db_session.commit()

    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.PARTIALLY_PAID
    assert invoice.amount_due == 2_000

    for ledger_ref, ref_id in (
        ("CREDIT_NOTE", str(credit.credit_note.id)),
        ("PAYMENT", str(payment.payment.id)),
        ("REFUND", str(refund.credit_note.id)),
    ):
        ledger_tx = (
            db_session.query(InternalLedgerTransaction)
            .filter(InternalLedgerTransaction.external_ref_type == ledger_ref)
            .filter(InternalLedgerTransaction.external_ref_id == ref_id)
            .one()
        )
        assert _ledger_balanced(db_session, str(ledger_tx.id))

    allocations = (
        db_session.query(InvoiceSettlementAllocation)
        .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
        .all()
    )
    total_payments = sum(a.amount for a in allocations if a.source_type == SettlementSourceType.PAYMENT)
    total_credits = sum(a.amount for a in allocations if a.source_type == SettlementSourceType.CREDIT_NOTE)
    total_refunds = sum(a.amount for a in allocations if a.source_type == SettlementSourceType.REFUND)
    assert total_payments - total_credits - total_refunds >= 0
    assert {a.source_type for a in allocations} == {
        SettlementSourceType.PAYMENT,
        SettlementSourceType.CREDIT_NOTE,
        SettlementSourceType.REFUND,
    }

    refund_replay = service.create_refund(
        invoice_id=invoice.id,
        amount=2_000,
        currency="USD",
        reason="order_refund",
        external_ref="SCN4-REF-1",
        provider="bank_stub",
        request_ctx=_request_ctx(),
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": 1},
    )
    db_session.commit()
    assert refund_replay.is_replay is True
    assert db_session.query(CreditNote).filter_by(invoice_id=invoice.id).count() == 2
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == invoice.id)
        .filter(AuditLog.event_type.in_(["CREDIT_NOTE_ALLOCATED", "REFUND_ALLOCATED"]))
        .count()
        == 2
    )

    assert db_session.query(OrderSlaEvaluation).count() == 1
    assert db_session.query(MarketplaceOrderContractLink).count() == 1
    assert db_session.query(MarketplaceSlaNotificationOutbox).count() >= 1
