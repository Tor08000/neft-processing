import os
from uuid import uuid4

import pytest

from app.db import Base, SessionLocal, engine
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.ledger_entry import LedgerEntry
from app.models.operation import Operation, OperationStatus, RiskResult
from app.models.terminal import Terminal
from app.services.transactions_service import (
    AmountExceeded,
    PostingFailed,
    authorize_operation,
    commit_operation,
    refund_operation,
    reverse_operation,
)


@pytest.fixture(autouse=True)
def _mock_risk_engine(monkeypatch):
    from app.services import transactions_service

    def risk_override(context):
        threshold = int(os.getenv("RISK_HIGH_THRESHOLD", "100000"))
        if context.amount >= threshold:
            return RiskResult.HIGH, 0.8, {"risk_result": "HIGH", "reasons": ["threshold"]}
        return RiskResult.LOW, 0.1, {"risk_result": "LOW", "reasons": ["ok"]}

    monkeypatch.setattr(transactions_service, "call_risk_engine_sync", risk_override)
    yield


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_refs(db):
    client_pk = uuid4()
    db.add(Client(id=client_pk, name="Test", status="ACTIVE"))
    db.add(Card(id="card-1", client_id=str(client_pk), status="ACTIVE"))
    db.add(Merchant(id="m-1", name="M1", status="ACTIVE"))
    db.add(Terminal(id="t-1", merchant_id="m-1", status="ACTIVE"))
    db.commit()
    return str(client_pk)


def test_authorize_happy_path(session):
    client_id = _seed_refs(session)
    op = authorize_operation(
        session,
        client_id=client_id,
        card_id="card-1",
        terminal_id="t-1",
        merchant_id="m-1",
        product_id=None,
        product_type=None,
        amount=10_000,
        currency="RUB",
        ext_operation_id="ext-1",
        mcc="5541",
        product_category="FUEL",
    )

    assert op.status == OperationStatus.POSTED
    assert op.auth_code is not None
    assert op.limit_check_result["approved"] is True
    assert op.risk_result in {RiskResult.LOW, RiskResult.MEDIUM}
    assert op.accounts
    assert op.posting_result
    assert session.query(LedgerEntry).count() == 2


def test_authorize_limit_failure(session):
    client_id = _seed_refs(session)
    op = authorize_operation(
        session,
        client_id=client_id,
        card_id="card-1",
        terminal_id="t-1",
        merchant_id="m-1",
        product_id=None,
        product_type=None,
        amount=200_000,  # above default per-tx limit
        currency="RUB",
        ext_operation_id="ext-2",
    )

    assert op.status == OperationStatus.DECLINED
    assert op.response_code == "LIMIT_EXCEEDED"


def test_risk_high_flag(session, monkeypatch):
    client_id = _seed_refs(session)
    # force night time
    monkeypatch.setenv("RISK_HIGH_THRESHOLD", "1000")
    op = authorize_operation(
        session,
        client_id=client_id,
        card_id="card-1",
        terminal_id="t-1",
        merchant_id="m-1",
        product_id=None,
        product_type=None,
        amount=5000,
        currency="RUB",
        ext_operation_id="ext-3",
    )

    assert op.risk_result in {RiskResult.HIGH, RiskResult.MEDIUM}


def test_commit_reverse_and_refund(session):
    client_id = _seed_refs(session)
    auth = authorize_operation(
        session,
        client_id=client_id,
        card_id="card-1",
        terminal_id="t-1",
        merchant_id="m-1",
        product_id=None,
        product_type=None,
        amount=10_000,
        currency="RUB",
        ext_operation_id="ext-4",
    )

    committed = commit_operation(session, operation_id=auth.operation_id, amount=5_000)
    assert committed.status == OperationStatus.COMPLETED
    assert committed.amount_settled == 5_000

    with pytest.raises(AmountExceeded):
        refund_operation(session, original_operation_id=auth.operation_id, amount=10_000)

    refund = refund_operation(session, original_operation_id=auth.operation_id, amount=2_000)
    assert refund.amount == 2_000

    # create new auth to test reversal flow
    fresh_auth = authorize_operation(
        session,
        client_id=client_id,
        card_id="card-1",
        terminal_id="t-1",
        merchant_id="m-1",
        product_id=None,
        product_type=None,
        amount=1_000,
        currency="RUB",
        ext_operation_id="ext-5",
    )

    reversed_op = reverse_operation(session, operation_id=fresh_auth.operation_id, reason="manual")
    assert reversed_op.status == OperationStatus.REVERSED


def test_hard_decline_stops_posting(session, monkeypatch):
    client_id = _seed_refs(session)
    from app.services import transactions_service
    from app.services import risk_adapter

    def hard_decline(context, db=None):
        return risk_adapter.RiskEvaluation(
            decision=risk_adapter.RiskDecision(
                level=risk_adapter.RiskDecisionLevel.HARD_DECLINE,
                rules_fired=["hard"],
                reason_codes=["block"],
            ),
            score=1.0,
            source="test",
            flags={},
        )

    monkeypatch.setattr(transactions_service, "call_risk_engine_sync", hard_decline)
    monkeypatch.setattr(transactions_service, "RISK_ENGINE_OVERRIDE", hard_decline)

    risk_eval = hard_decline(None)
    op = authorize_operation(
        session,
        client_id=client_id,
        card_id="card-1",
        terminal_id="t-1",
        merchant_id="m-1",
        product_id=None,
        product_type=None,
        amount=1_000,
        currency="RUB",
        ext_operation_id="ext-hard",
        risk_evaluation=risk_eval,
    )

    assert op.status == OperationStatus.DECLINED
    assert session.query(LedgerEntry).count() == 0


def test_posting_failure_rolls_back(session, monkeypatch):
    client_id = _seed_refs(session)
    from app.services import transactions_service

    def allow_risk(context, db=None):
        return transactions_service.risk_adapter.RiskEvaluation(
            decision=transactions_service.risk_adapter.RiskDecision(
                level=transactions_service.risk_adapter.RiskDecisionLevel.LOW,
                rules_fired=[],
                reason_codes=[],
            ),
            score=0.1,
            source="test",
            flags={},
        )

    monkeypatch.setattr(transactions_service, "RISK_ENGINE_OVERRIDE", allow_risk)

    risk_eval = allow_risk(None)

    with pytest.raises(PostingFailed):
        authorize_operation(
            session,
            client_id=client_id,
            card_id="card-1",
            terminal_id="t-1",
            merchant_id="m-1",
            product_id=None,
            product_type=None,
            amount=1_000,
            currency="RUB",
            ext_operation_id="ext-fail",
            risk_evaluation=risk_eval,
            simulate_posting_error=True,
        )

    op = session.query(Operation).filter(Operation.operation_id == "ext-fail").first()
    assert op is not None
    assert op.status == OperationStatus.ERROR
    assert op.response_code == "POSTING_ERROR"
    assert session.query(LedgerEntry).count() == 0

