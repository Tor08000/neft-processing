from uuid import uuid4

from app.db import Base, SessionLocal, engine
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.operation import OperationStatus
from app.models.terminal import Terminal
from app.services import transactions_service
from app.services.risk_adapter import RiskDecision, RiskDecisionLevel, RiskEvaluation


class _ApprovedLimits:
    approved = True
    daily_limit = None
    limit_per_tx = None
    used_today = None
    new_used_today = None
    applied_rule_id = "rule-1"

    def model_dump(self):
        return {"approved": True, "applied_rule_id": self.applied_rule_id}


def test_authorize_sets_valid_status_and_response(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    decision = RiskDecision(level=RiskDecisionLevel.MEDIUM, rules_fired=[], reason_codes=[])
    evaluation = RiskEvaluation(decision=decision, score=0.1, source="TEST", flags={})

    monkeypatch.setattr(transactions_service, "evaluate_limits_locally", lambda *_, **__: _ApprovedLimits())
    monkeypatch.setattr(transactions_service, "_evaluate_risk", lambda *_, **__: evaluation)

    client_id = uuid4()
    with SessionLocal() as session:
        session.add(Client(id=client_id, name="Client", status="ACTIVE"))
        session.add(Card(id="card-1", client_id=str(client_id), status="ACTIVE"))
        session.add(Merchant(id="merchant-1", name="M", status="ACTIVE"))
        session.add(Terminal(id="terminal-1", merchant_id="merchant-1", status="ACTIVE"))
        session.commit()

        op = transactions_service.authorize_operation(
            session,
            client_id=str(client_id),
            card_id="card-1",
            terminal_id="terminal-1",
            merchant_id="merchant-1",
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
