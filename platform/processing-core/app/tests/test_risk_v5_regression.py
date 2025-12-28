from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskDecisionType, RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
from app.services.decision.scoring import StubRiskScorer
from app.services.risk_v5.hook import register_shadow_hook
from app.services.risk_v5.scorer_client import ScorerResponse


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


def _threshold_set(*, threshold_set_id: str) -> RiskThresholdSet:
    return RiskThresholdSet(
        id=threshold_set_id,
        subject_type=RiskSubjectType.PAYMENT,
        scope=RiskThresholdScope.GLOBAL,
        action=RiskThresholdAction.PAYMENT,
        block_threshold=80,
        review_threshold=60,
        allow_threshold=10,
        currency="RUB",
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _make_engine(session):
    fixed_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return DecisionEngine(
        session,
        scorer=StubRiskScorer(default_score=65),
        now_provider=lambda: fixed_now,
    )


def _make_context():
    return DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=500,
        currency="RUB",
        history={},
        metadata={"subject_id": "op-1"},
    )


def test_v4_output_unchanged_with_v5_shadow(session, monkeypatch: pytest.MonkeyPatch):
    session.add(_threshold_set(threshold_set_id="payments_v4"))
    session.add(
        RiskPolicy(
            id="policy-v4",
            subject_type=RiskSubjectType.PAYMENT,
            tenant_id=None,
            client_id=None,
            provider=None,
            currency="RUB",
            country=None,
            threshold_set_id="payments_v4",
            model_selector="risk_v4",
            priority=10,
            active=True,
        )
    )
    session.commit()

    register_shadow_hook()
    monkeypatch.setenv("RISK_V5_SHADOW_ENABLED", "true")
    monkeypatch.setenv("RISK_V5_AB_WEIGHT", "100")

    def _score(*, payload: dict) -> ScorerResponse:
        return ScorerResponse(score=90, model_version="risk-v5-1", explain={"predicted_outcome": "BLOCK"})

    monkeypatch.setattr("app.services.risk_v5.scorer_client.score", _score)

    engine_instance = _make_engine(session)
    result_with_shadow = engine_instance.evaluate(_make_context())

    monkeypatch.setenv("RISK_V5_SHADOW_ENABLED", "false")
    engine_instance = _make_engine(session)
    result_without_shadow = engine_instance.evaluate(_make_context())

    assert result_with_shadow.outcome == result_without_shadow.outcome
    assert result_with_shadow.risk_decision == result_without_shadow.risk_decision
    assert result_with_shadow.outcome == DecisionOutcome.MANUAL_REVIEW
    assert result_with_shadow.risk_decision == RiskDecisionType.ALLOW_WITH_REVIEW
