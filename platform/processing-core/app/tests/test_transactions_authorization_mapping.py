from uuid import uuid4

import pytest
from sqlalchemy import Column, MetaData, String, Table

from app.models.account import Account, AccountBalance
from app.models.audit_log import AuditLog
from app.models.card import Card
from app.models.client import Client
from app.models.ledger_entry import LedgerEntry
from app.models.merchant import Merchant
from app.models.operation import OperationStatus, Operation
from app.models.risk_score import RiskLevel
from app.models.terminal import Terminal
from app.services import transactions_service
from app.services.decision import DecisionEngine, DecisionOutcome, DecisionResult
from app.services.risk_adapter import RiskDecision, RiskDecisionLevel, RiskEvaluation
from app.models.unified_rule import UnifiedRulePolicy
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

TRANSACTIONS_MAPPING_TEST_TABLES = (
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


class _ApprovedLimits:
    approved = True
    daily_limit = None
    limit_per_tx = None
    used_today = None
    new_used_today = None
    applied_rule_id = "rule-1"

    def model_dump(self):
        return {"approved": True, "applied_rule_id": self.applied_rule_id}


@pytest.fixture(autouse=True)
def _allow_transaction_dependencies(monkeypatch: pytest.MonkeyPatch):
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


@pytest.fixture
def session():
    with scoped_session_context(tables=TRANSACTIONS_MAPPING_TEST_TABLES) as db:
        yield db


def test_authorize_sets_valid_status_and_response(monkeypatch: pytest.MonkeyPatch, session):

    decision = RiskDecision(level=RiskDecisionLevel.MEDIUM, rules_fired=[], reason_codes=[])
    evaluation = RiskEvaluation(decision=decision, score=0.1, source="TEST", flags={})

    monkeypatch.setattr(transactions_service, "evaluate_limits_locally", lambda *_, **__: _ApprovedLimits())
    monkeypatch.setattr(transactions_service, "_evaluate_risk", lambda *_, **__: evaluation)

    client_id = uuid4()
    session.add(Client(id=client_id, name="Client", status="ACTIVE"))
    session.add(Card(id="card-1", client_id=str(client_id), status="ACTIVE"))
    session.add(Merchant(id=MERCHANT_ID, name="M", status="ACTIVE"))
    session.add(Terminal(id="terminal-1", merchant_id=MERCHANT_ID, status="ACTIVE"))
    session.commit()

    op = transactions_service.authorize_operation(
        session,
        client_id=str(client_id),
        card_id="card-1",
        terminal_id="terminal-1",
        merchant_id=MERCHANT_ID,
        tariff_id=None,
        product_id=None,
        product_type=None,
        amount=5000,
        currency="RUB",
        ext_operation_id="ext-mapping-1",
        quantity=None,
        unit_price=None,
        mcc=None,
        product_category=None,
        tx_type=None,
        client_group_id=None,
        card_group_id=None,
        risk_evaluation=evaluation,
    )

    assert op.status == OperationStatus.AUTHORIZED
    assert op.response_code == "00"
    assert op.response_message == "APPROVED"
