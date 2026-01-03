import base64
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.audit_log import AuditLog
from app.models.cases import Case, CaseEvent
from app.models.decision_memory import DecisionMemoryRecord
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerEntry,
    InternalLedgerTransaction,
)
from app.models.marketplace_contracts import Contract, ContractObligation, ContractStatus, ContractVersion
from app.models.marketplace_order_sla import (
    MarketplaceOrderContractLink,
    MarketplaceOrderEvent,
    MarketplaceSlaNotificationOutbox,
    OrderSlaConsequence,
    OrderSlaEvaluation,
)
from app.services.marketplace_contract_binding_service import bind_contract_for_order
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
        MarketplaceSlaNotificationOutbox.__table__,
        InternalLedgerAccount.__table__,
        InternalLedgerTransaction.__table__,
        InternalLedgerEntry.__table__,
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


def test_marketplace_order_sla_breach_creates_consequence(db_session: Session) -> None:
    contract = Contract(
        contract_number="C-ORDER-001",
        contract_type="service",
        party_a_type="client",
        party_a_id="22222222-2222-2222-2222-222222222222",
        party_b_type="partner",
        party_b_id="33333333-3333-3333-3333-333333333333",
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
        penalty_value="1000",
    )
    db_session.add(contract)
    db_session.flush()
    obligation.contract_id = contract.id
    db_session.add(obligation)
    db_session.commit()

    order_id = "order-1"
    created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    accepted_at = datetime.now(timezone.utc) - timedelta(hours=1)
    created_event = MarketplaceOrderEvent(
        order_id=order_id,
        client_id=str(contract.party_a_id),
        partner_id=str(contract.party_b_id),
        event_type="MARKETPLACE_ORDER_CREATED",
        occurred_at=created_at,
    )
    accepted_event = MarketplaceOrderEvent(
        order_id=order_id,
        client_id=str(contract.party_a_id),
        partner_id=str(contract.party_b_id),
        event_type="MARKETPLACE_ORDER_CONFIRMED_BY_PARTNER",
        occurred_at=accepted_at,
    )
    db_session.add_all([created_event, accepted_event])
    db_session.commit()

    bound_contract_id = bind_contract_for_order(
        db_session,
        order_id=order_id,
        client_id=str(contract.party_a_id),
        partner_id=str(contract.party_b_id),
    )
    assert bound_contract_id == str(contract.id)

    summary = evaluate_order_event(db_session, order_event_id=str(accepted_event.id))
    assert summary.violations
    evaluation = summary.violations[0]
    db_session.commit()

    result = apply_sla_consequences(db_session, evaluation_id=str(evaluation.id))
    assert result is not None
    db_session.commit()

    assert db_session.query(OrderSlaConsequence).count() == 1
    assert db_session.query(InternalLedgerTransaction).count() == 1
    assert db_session.query(InternalLedgerEntry).count() == 2
    assert db_session.query(MarketplaceSlaNotificationOutbox).count() == 2
    assert db_session.query(Case).count() == 1

    replay = apply_sla_consequences(db_session, evaluation_id=str(evaluation.id))
    assert replay is not None
    assert replay.consequence.id == result.consequence.id
    assert db_session.query(OrderSlaConsequence).count() == 1
