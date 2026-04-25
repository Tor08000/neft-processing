import os
from uuid import uuid4

import pytest
from sqlalchemy import Column, MetaData, String, Table

from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.account import Account, AccountBalance
from app.models.audit_log import AuditLog
from app.models.ledger_entry import LedgerEntry
from app.models.operation import Operation, OperationStatus, RiskResult
from app.models.terminal import Terminal
from app.models.risk_score import RiskLevel
from app.models.unified_rule import UnifiedRulePolicy
from app.services.decision import DecisionEngine, DecisionOutcome, DecisionResult
from app.services.transactions_service import (
    AmountExceeded,
    PostingFailed,
    authorize_operation,
    commit_operation,
    refund_operation,
    reverse_operation,
)
from app.tests._scoped_router_harness import scoped_session_context


_TRANSACTIONS_TEST_METADATA = MetaData()

FLEET_OFFLINE_PROFILES_REFLECTED = Table(
    "fleet_offline_profiles",
    _TRANSACTIONS_TEST_METADATA,
    Column("id", String(36), primary_key=True),
)

FUEL_STATIONS_REFLECTED = Table(
    "fuel_stations",
    _TRANSACTIONS_TEST_METADATA,
    Column("id", String(64), primary_key=True),
)

TRANSACTIONS_PIPELINE_TEST_TABLES = (
    FLEET_OFFLINE_PROFILES_REFLECTED,
    FUEL_STATIONS_REFLECTED,
    Client.__table__,
    Card.__table__,
    Merchant.__table__,
    Terminal.__table__,
    Operation.__table__,
    Account.__table__,
    AccountBalance.__table__,
    LedgerEntry.__table__,
    AuditLog.__table__,
)

MERCHANT_ID = "11111111-1111-1111-1111-111111111111"
TERMINAL_ID = "t-1"
CARD_ID = "card-1"


class _LimitsResult:
    def __init__(self, *, approved: bool, applied_rule_id: str = "rule-1"):
        self.approved = approved
        self.daily_limit = 500_000
        self.limit_per_tx = 100_000
        self.used_today = 0
        self.new_used_today = 0
        self.applied_rule_id = applied_rule_id

    def model_dump(self):
        return {
            "approved": self.approved,
            "applied_rule_id": self.applied_rule_id,
            "daily_limit": self.daily_limit,
            "limit_per_tx": self.limit_per_tx,
            "used_today": self.used_today,
            "new_used_today": self.new_used_today,
        }


class _ApprovedContractLimits:
    approved = True
    violations: list[object] = []


def _allow_decision() -> DecisionResult:
    return DecisionResult(
        decision_id=str(uuid4()),
        decision_version="test",
        outcome=DecisionOutcome.ALLOW,
        risk_score=0,
        risk_level=RiskLevel.LOW,
        explain={},
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
def _allow_transaction_dependencies(monkeypatch: pytest.MonkeyPatch):
    from app.services import transactions_service

    monkeypatch.setattr(DecisionEngine, "evaluate", lambda *_args, **_kwargs: _allow_decision())
    monkeypatch.setattr(
        transactions_service,
        "evaluate_with_db",
        lambda *_args, **_kwargs: (UnifiedRulePolicy.ALLOW, [], None),
    )
    monkeypatch.setattr(
        transactions_service,
        "check_contractual_limits",
        lambda *_args, **_kwargs: _ApprovedContractLimits(),
    )

    def _evaluate_limits(request, db=None):
        return _LimitsResult(approved=request.amount <= 100_000)

    monkeypatch.setattr(transactions_service, "evaluate_limits_locally", _evaluate_limits)


@pytest.fixture
def session():
    with scoped_session_context(tables=TRANSACTIONS_PIPELINE_TEST_TABLES) as db:
        yield db


def _seed_refs(db):
    client_pk = uuid4()
    db.add(Client(id=client_pk, name="Test", status="ACTIVE"))
    db.add(Card(id=CARD_ID, client_id=str(client_pk), status="ACTIVE"))
    db.add(Merchant(id=MERCHANT_ID, name="M1", status="ACTIVE"))
    db.add(Terminal(id=TERMINAL_ID, merchant_id=MERCHANT_ID, status="ACTIVE"))
    db.commit()
    return str(client_pk)


def test_authorize_happy_path(session):
    client_id = _seed_refs(session)
    op = authorize_operation(
        session,
        client_id=client_id,
        card_id=CARD_ID,
        terminal_id=TERMINAL_ID,
        merchant_id=MERCHANT_ID,
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
        card_id=CARD_ID,
        terminal_id=TERMINAL_ID,
        merchant_id=MERCHANT_ID,
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
        card_id=CARD_ID,
        terminal_id=TERMINAL_ID,
        merchant_id=MERCHANT_ID,
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
        card_id=CARD_ID,
        terminal_id=TERMINAL_ID,
        merchant_id=MERCHANT_ID,
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
        card_id=CARD_ID,
        terminal_id=TERMINAL_ID,
        merchant_id=MERCHANT_ID,
        product_id=None,
        product_type=None,
        amount=1_000,
        currency="RUB",
        ext_operation_id="ext-5",
    )

    reversed_op = reverse_operation(session, operation_id=fresh_auth.operation_id, reason="manual")
    assert reversed_op.status == OperationStatus.REVERSED


def test_refund_creates_postings(session):
    client_id = _seed_refs(session)
    auth = authorize_operation(
        session,
        client_id=client_id,
        card_id=CARD_ID,
        terminal_id=TERMINAL_ID,
        merchant_id=MERCHANT_ID,
        product_id=None,
        product_type=None,
        amount=1_000,
        currency="RUB",
        ext_operation_id="ext-refund-postings",
        mcc="5541",
        product_category="FUEL",
    )

    commit_operation(session, operation_id=auth.operation_id)
    ledger_before = session.query(LedgerEntry).count()

    refund = refund_operation(
        session,
        original_operation_id=auth.operation_id,
        amount=500,
    )

    ledger_after = session.query(LedgerEntry).count()
    balances = {b.account_id: b.current_balance for b in session.query(AccountBalance).all()}

    assert ledger_after == ledger_before + 2
    assert refund.accounts
    assert refund.posting_result
    assert refund.posting_result.get("entries")
    client_account_id, merchant_account_id = auth.accounts[0], auth.accounts[1]
    assert balances[client_account_id] == -500
    assert balances[merchant_account_id] == 500


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
        card_id=CARD_ID,
        terminal_id=TERMINAL_ID,
        merchant_id=MERCHANT_ID,
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
        card_id=CARD_ID,
        terminal_id=TERMINAL_ID,
        merchant_id=MERCHANT_ID,
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
