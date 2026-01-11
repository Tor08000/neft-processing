import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.audit_log import AuditLog
from app.models.cases import Case, CaseEvent
from app.models.decision_memory import DecisionMemoryRecord
from app.models.finance import CreditNote
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerEntry,
    InternalLedgerTransaction,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.marketplace_catalog import (
    MarketplaceProduct,
    MarketplaceProductModerationStatus,
    MarketplaceProductStatus,
    MarketplaceProductType,
)
from app.models.marketplace_commissions import (
    MarketplaceCommissionRule,
    MarketplaceCommissionScope,
    MarketplaceCommissionStatus,
    MarketplaceCommissionType,
)
from app.models.marketplace_contracts import Contract, ContractObligation, ContractStatus, ContractVersion
from app.models.marketplace_order_sla import (
    MarketplaceOrderContractLink,
    MarketplaceOrderEvent,
    OrderSlaConsequence,
    OrderSlaEvaluation,
)
from app.models.marketplace_orders import MarketplaceOrder, MarketplaceOrderActorType, MarketplaceOrderEventType
from app.models.marketplace_settlement import MarketplaceAdjustment, MarketplaceSettlementItem
from app.models.payout_batch import PayoutBatch, PayoutItem
from app.services.marketplace_order_service import MarketplaceOrderService
from app.services.marketplace_settlement_service import MarketplaceSettlementService
from app.services.order_sla_consequence_service import apply_sla_consequences
from app.services.order_sla_service import evaluate_order_event


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


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    tables = [
        AuditLog.__table__,
        DecisionMemoryRecord.__table__,
        Case.__table__,
        CaseEvent.__table__,
        Contract.__table__,
        ContractVersion.__table__,
        ContractObligation.__table__,
        MarketplaceOrderContractLink.__table__,
        MarketplaceOrderEvent.__table__,
        OrderSlaEvaluation.__table__,
        OrderSlaConsequence.__table__,
        InternalLedgerAccount.__table__,
        InternalLedgerTransaction.__table__,
        InternalLedgerEntry.__table__,
        MarketplaceProduct.__table__,
        MarketplaceOrder.__table__,
        MarketplaceCommissionRule.__table__,
        MarketplaceSettlementItem.__table__,
        MarketplaceAdjustment.__table__,
        PayoutBatch.__table__,
        PayoutItem.__table__,
        Invoice.__table__,
        CreditNote.__table__,
    ]
    for table in tables:
        table.create(bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        for table in reversed(tables):
            table.drop(bind=engine)
        engine.dispose()


def test_order_sla_billing_consequence_flow(db_session: Session) -> None:
    contract = Contract(
        contract_number="C-ORDER-002",
        contract_type="service",
        party_a_type="client",
        party_a_id="22222222-2222-2222-2222-222222222222",
        party_b_type="partner",
        party_b_id="33333333-3333-3333-3333-333333333333",
        currency="RUB",
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
        penalty_value="500",
    )
    db_session.add(contract)
    db_session.flush()
    obligation.contract_id = contract.id
    db_session.add(obligation)

    product = MarketplaceProduct(
        id=str(uuid4()),
        partner_id=str(contract.party_b_id),
        type=MarketplaceProductType.SERVICE.value,
        title="Oil change",
        description="Service",
        category="maintenance",
        price_model="FIXED",
        price_config={"amount": "1000", "currency": "RUB"},
        status=MarketplaceProductStatus.PUBLISHED.value,
        moderation_status=MarketplaceProductModerationStatus.APPROVED.value,
    )
    db_session.add(product)
    db_session.flush()

    commission_rule = MarketplaceCommissionRule(
        id=str(uuid4()),
        scope=MarketplaceCommissionScope.MARKETPLACE.value,
        partner_id=str(contract.party_b_id),
        product_category="maintenance",
        commission_type=MarketplaceCommissionType.PERCENT.value,
        rate=Decimal("0.1"),
        min_commission=Decimal("50"),
        max_commission=Decimal("150"),
        priority=100,
        status=MarketplaceCommissionStatus.ACTIVE.value,
    )
    db_session.add(commission_rule)
    db_session.commit()

    order_service = MarketplaceOrderService(db_session)
    order = order_service.create_order(
        client_id=str(contract.party_a_id),
        product_id=str(product.id),
        quantity=Decimal("1"),
        actor=MarketplaceOrderActorType.SYSTEM,
    )
    order_service.accept_order(
        partner_id=str(contract.party_b_id),
        order_id=str(order.id),
        note=None,
        actor=MarketplaceOrderActorType.SYSTEM,
    )
    order_service.start_order(
        partner_id=str(contract.party_b_id),
        order_id=str(order.id),
        note=None,
        actor=MarketplaceOrderActorType.SYSTEM,
    )
    order_service.complete_order(
        partner_id=str(contract.party_b_id),
        order_id=str(order.id),
        summary="done",
        actor=MarketplaceOrderActorType.SYSTEM,
    )
    db_session.commit()

    assert order.commission_snapshot is not None

    invoice = Invoice(
        id=str(uuid4()),
        client_id=str(contract.party_a_id),
        period_from=datetime.now(timezone.utc).date() - timedelta(days=30),
        period_to=datetime.now(timezone.utc).date(),
        currency="RUB",
        total_amount=1000,
        total_with_tax=1000,
        amount_due=1000,
        status=InvoiceStatus.SENT.value,
    )
    db_session.add(invoice)
    db_session.commit()

    order_id = str(order.id)
    created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    accepted_at = datetime.now(timezone.utc) - timedelta(hours=1)
    created_event = MarketplaceOrderEvent(
        order_id=order_id,
        client_id=str(contract.party_a_id),
        partner_id=str(contract.party_b_id),
        event_type=MarketplaceOrderEventType.MARKETPLACE_ORDER_CREATED,
        occurred_at=created_at,
        payload_redacted={},
        actor_type=MarketplaceOrderActorType.SYSTEM,
        audit_event_id=str(uuid4()),
    )
    accepted_event = MarketplaceOrderEvent(
        order_id=order_id,
        client_id=str(contract.party_a_id),
        partner_id=str(contract.party_b_id),
        event_type=MarketplaceOrderEventType.MARKETPLACE_ORDER_CONFIRMED_BY_PARTNER,
        occurred_at=accepted_at,
        payload_redacted={},
        actor_type=MarketplaceOrderActorType.SYSTEM,
        audit_event_id=str(uuid4()),
    )
    db_session.add_all([created_event, accepted_event])
    db_session.commit()

    summary = evaluate_order_event(db_session, order_event_id=str(accepted_event.id))
    assert summary.violations
    evaluation = summary.violations[0]
    db_session.commit()

    result = apply_sla_consequences(db_session, evaluation_id=str(evaluation.id))
    assert result is not None
    db_session.commit()

    adjustment = db_session.query(MarketplaceAdjustment).one()
    assert adjustment.amount == Decimal("500")
    settlement_item = db_session.query(MarketplaceSettlementItem).filter_by(order_id=order.id).one()
    assert settlement_item.penalty_amount == Decimal("500")
    assert db_session.query(CreditNote).count() == 1

    period = order.completed_at.strftime("%Y-%m")
    payout = MarketplaceSettlementService(db_session).build_payout_batch(
        tenant_id=1,
        partner_id=str(order.partner_id),
        period=period,
    )
    assert payout.batch.total_amount == Decimal("400")

    event_types = {event.event_type for event in db_session.query(AuditLog).all()}
    assert "SLA_BREACH_DETECTED" in event_types
    assert "MARKETPLACE_SLA_PENALTY_APPLIED" in event_types
    assert "BILLING_CREDIT_NOTE_CREATED" in event_types
