from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
from app.services.decision.rules import Rule
from app.services.decision.scoring import StubRiskScorer


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


def test_explain_payload_contains_required_fields(session):
    threshold_set = RiskThresholdSet(
        id="payouts_v4",
        subject_type=RiskSubjectType.PAYOUT,
        scope=RiskThresholdScope.GLOBAL,
        action=RiskThresholdAction.PAYOUT,
        block_threshold=80,
        review_threshold=60,
        allow_threshold=10,
        currency="RUB",
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    policy = RiskPolicy(
        id="HIGH_RISK_PAYOUT",
        subject_type=RiskSubjectType.PAYOUT,
        tenant_id=None,
        client_id=None,
        provider=None,
        currency="RUB",
        country=None,
        threshold_set_id="payouts_v4",
        model_selector="risk_v4",
        priority=10,
        active=True,
    )
    session.add_all([threshold_set, policy])
    session.commit()

    rules = [
        Rule(
            id="VELOCITY_SPIKE",
            when=lambda ctx: True,
            outcome=DecisionOutcome.ALLOW,
            explain="velocity spike",
        )
    ]
    engine_instance = DecisionEngine(session, rules=rules, scorer=StubRiskScorer(default_score=87))
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYOUT_EXPORT,
        amount=500,
        currency="RUB",
        history={},
        metadata={"subject_id": "payout-1", "model_version": "2025.01"},
    )

    result = engine_instance.evaluate(ctx)

    assert result.outcome == DecisionOutcome.DECLINE
    assert result.explain["decision"] == "BLOCK"
    assert result.explain["score"] == 87
    assert result.explain["thresholds"]["block"] == 80
    assert result.explain["thresholds"]["review"] == 60
    assert result.explain["policy"] == "HIGH_RISK_PAYOUT"
    assert "velocity spike" in result.explain["factors"]
    assert result.explain["model"]["name"] == "risk_v4"
    assert result.explain["model"]["version"] == "2025.01"
