from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskDecisionType, RiskSubjectType
from app.models.risk_score import RiskLevel
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine
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


def _threshold(
    *,
    threshold_set_id: str,
    min_score: int,
    max_score: int,
    risk_level: RiskLevel,
    decision: RiskDecisionType,
    requires_manual_review: bool = False,
    active: bool = True,
) -> RiskThreshold:
    return RiskThreshold(
        threshold_set_id=threshold_set_id,
        subject_type=RiskSubjectType.PAYMENT,
        min_score=min_score,
        max_score=max_score,
        risk_level=risk_level,
        outcome=decision,
        requires_manual_review=requires_manual_review,
        active=active,
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def test_threshold_matching_block(session):
    threshold_set = RiskThresholdSet(
        id="payments_v3",
        subject_type=RiskSubjectType.PAYMENT,
        version=1,
        active=True,
    )
    policy = RiskPolicy(
        id="payments_default",
        subject_type=RiskSubjectType.PAYMENT,
        tenant_id=None,
        client_id=None,
        provider=None,
        currency="RUB",
        country=None,
        threshold_set_id="payments_v3",
        model_selector="risk_model_v3",
        priority=10,
        active=True,
    )
    session.add_all([threshold_set, policy])
    session.add_all(
        [
            _threshold(
                threshold_set_id="payments_v3",
                min_score=0,
                max_score=80,
                risk_level=RiskLevel.HIGH,
                decision=RiskDecisionType.ALLOW,
            ),
            _threshold(
                threshold_set_id="payments_v3",
                min_score=81,
                max_score=100,
                risk_level=RiskLevel.VERY_HIGH,
                decision=RiskDecisionType.BLOCK,
            ),
        ]
    )
    session.commit()

    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=85))
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=500,
        currency="RUB",
        history={},
        metadata={"subject_id": "op-1"},
    )

    result = engine_instance.evaluate(ctx)

    assert result.risk_decision == RiskDecisionType.BLOCK
    assert result.outcome == "DECLINE"
    assert result.risk_level == RiskLevel.VERY_HIGH


def test_policy_priority_selects_lowest_number(session):
    session.add_all(
        [
            RiskThresholdSet(
                id="set-low",
                subject_type=RiskSubjectType.PAYMENT,
                version=1,
                active=True,
            ),
            RiskThresholdSet(
                id="set-high",
                subject_type=RiskSubjectType.PAYMENT,
                version=1,
                active=True,
            ),
            RiskPolicy(
                id="policy-low",
                subject_type=RiskSubjectType.PAYMENT,
                tenant_id=None,
                client_id=None,
                provider=None,
                currency="RUB",
                country=None,
                threshold_set_id="set-low",
                model_selector="risk_model_v3",
                priority=200,
                active=True,
            ),
            RiskPolicy(
                id="policy-high",
                subject_type=RiskSubjectType.PAYMENT,
                tenant_id=None,
                client_id=None,
                provider=None,
                currency="RUB",
                country=None,
                threshold_set_id="set-high",
                model_selector="risk_model_v3",
                priority=10,
                active=True,
            ),
        ]
    )
    session.add_all(
        [
            _threshold(
                threshold_set_id="set-low",
                min_score=0,
                max_score=100,
                risk_level=RiskLevel.LOW,
                decision=RiskDecisionType.ALLOW,
            ),
            _threshold(
                threshold_set_id="set-high",
                min_score=0,
                max_score=100,
                risk_level=RiskLevel.HIGH,
                decision=RiskDecisionType.BLOCK,
            ),
        ]
    )
    session.commit()

    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=20))
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=100,
        currency="RUB",
        history={},
        metadata={"subject_id": "op-2"},
    )

    result = engine_instance.evaluate(ctx)

    assert result.policy_id == "policy-high"
    assert result.risk_decision == RiskDecisionType.BLOCK


def test_allow_with_review_keeps_outcome_allow(session):
    threshold_set = RiskThresholdSet(
        id="set-review",
        subject_type=RiskSubjectType.PAYMENT,
        version=1,
        active=True,
    )
    policy = RiskPolicy(
        id="policy-review",
        subject_type=RiskSubjectType.PAYMENT,
        tenant_id=None,
        client_id=None,
        provider=None,
        currency="RUB",
        country=None,
        threshold_set_id="set-review",
        model_selector="risk_model_v3",
        priority=5,
        active=True,
    )
    session.add_all([threshold_set, policy])
    session.add(
        _threshold(
            threshold_set_id="set-review",
            min_score=0,
            max_score=100,
            risk_level=RiskLevel.LOW,
            decision=RiskDecisionType.ALLOW,
            requires_manual_review=True,
        )
    )
    session.commit()

    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=10))
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=100,
        currency="RUB",
        history={},
        metadata={"subject_id": "op-3"},
    )

    result = engine_instance.evaluate(ctx)

    assert result.risk_decision == RiskDecisionType.ALLOW_WITH_REVIEW
    assert result.outcome == "ALLOW"


def test_hard_rule_blocks_before_thresholds(session):
    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=10))
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="CLIENT",
        action=DecisionAction.DOCUMENT_FINALIZE,
        history={},
        metadata={
            "document_acknowledged": False,
            "subject_id": "doc-1",
        },
    )

    result = engine_instance.evaluate(ctx)

    assert result.outcome == "DECLINE"
    assert result.risk_decision == RiskDecisionType.BLOCK
