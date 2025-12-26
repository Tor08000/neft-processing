from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskDecisionType, RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
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


def test_risk_engine_v4_determinism(session):
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

    fixed_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    engine_instance = DecisionEngine(
        session,
        scorer=StubRiskScorer(default_score=65),
        now_provider=lambda: fixed_now,
    )
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

    first = engine_instance.evaluate(ctx)
    second = engine_instance.evaluate(ctx)

    assert first.outcome == second.outcome
    assert first.risk_decision == second.risk_decision
    assert first.explain == second.explain


def test_risk_engine_v4_determinism_different_timestamps(session):
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

    engine_instance = DecisionEngine(
        session,
        scorer=StubRiskScorer(default_score=65),
        now_provider=lambda: datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    later_engine = DecisionEngine(
        session,
        scorer=StubRiskScorer(default_score=65),
        now_provider=lambda: datetime(2025, 2, 1, tzinfo=timezone.utc),
    )
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

    first = engine_instance.evaluate(ctx)
    second = later_engine.evaluate(ctx)

    assert first.outcome == second.outcome
    assert first.risk_decision == second.risk_decision
    assert first.explain["decision_hash"] == second.explain["decision_hash"]


@pytest.mark.parametrize(
    ("score", "expected_decision", "expected_outcome"),
    [
        (80, RiskDecisionType.BLOCK, DecisionOutcome.DECLINE),
        (60, RiskDecisionType.ALLOW_WITH_REVIEW, DecisionOutcome.MANUAL_REVIEW),
        (10, RiskDecisionType.ALLOW, DecisionOutcome.ALLOW),
        (70, RiskDecisionType.ALLOW_WITH_REVIEW, DecisionOutcome.MANUAL_REVIEW),
        (30, RiskDecisionType.ALLOW, DecisionOutcome.ALLOW),
    ],
)
def test_threshold_boundaries(session, score, expected_decision, expected_outcome):
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

    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=score))
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=500,
        currency="RUB",
        history={},
        metadata={"subject_id": f"op-{score}"},
    )

    result = engine_instance.evaluate(ctx)

    assert result.risk_decision == expected_decision
    assert result.outcome == expected_outcome


def test_missing_thresholds_uses_global(session):
    session.add(_threshold_set(threshold_set_id="global_v4"))
    session.commit()

    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=10))
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=500,
        currency="RUB",
        history={},
        metadata={"subject_id": "op-global"},
    )

    result = engine_instance.evaluate(ctx)

    assert result.threshold_set_id == "global_v4"
    assert result.outcome == DecisionOutcome.ALLOW


def test_missing_global_thresholds_fail_closed(session):
    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=10))
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=500,
        currency="RUB",
        history={},
        metadata={"subject_id": "op-missing"},
    )

    result = engine_instance.evaluate(ctx)

    assert result.risk_decision == RiskDecisionType.BLOCK
    assert result.outcome == DecisionOutcome.DECLINE
    assert "missing_threshold_set" in result.explain["factors"]


@pytest.mark.parametrize(
    ("ctx_kwargs", "expected_reason"),
    [
        ({"amount": None, "client_id": "client-1", "action": DecisionAction.PAYMENT_AUTHORIZE}, "missing_amount"),
        ({"amount": 500, "client_id": None, "action": DecisionAction.PAYMENT_AUTHORIZE}, "missing_client_id"),
        ({"amount": 500, "client_id": "client-1", "action": "UNKNOWN_ACTION"}, "unknown_action"),
    ],
)
def test_incomplete_context_blocks(session, ctx_kwargs, expected_reason):
    session.add(_threshold_set(threshold_set_id="payments_v4"))
    session.commit()

    ctx = DecisionContext(
        tenant_id=1,
        actor_type="SYSTEM",
        currency="RUB",
        history={},
        metadata={"subject_id": "op-incomplete"},
        **ctx_kwargs,
    )
    result = DecisionEngine(session, scorer=StubRiskScorer(default_score=10)).evaluate(ctx)

    assert result.risk_decision == RiskDecisionType.BLOCK
    assert result.outcome == DecisionOutcome.DECLINE
    assert expected_reason in result.explain["factors"]


def test_conflicting_policies_resolve_by_priority_and_specificity(session):
    session.add_all(
        [
            RiskThresholdSet(
                id="policy-low",
                subject_type=RiskSubjectType.PAYMENT,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.PAYMENT,
                block_threshold=80,
                review_threshold=60,
                allow_threshold=10,
                valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            RiskThresholdSet(
                id="policy-high",
                subject_type=RiskSubjectType.PAYMENT,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.PAYMENT,
                block_threshold=80,
                review_threshold=60,
                allow_threshold=10,
                valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            RiskPolicy(
                id="policy-priority-low",
                subject_type=RiskSubjectType.PAYMENT,
                tenant_id=None,
                client_id=None,
                provider=None,
                currency="RUB",
                country=None,
                threshold_set_id="policy-high",
                model_selector="risk_v4",
                priority=5,
                active=True,
            ),
            RiskPolicy(
                id="policy-priority-high",
                subject_type=RiskSubjectType.PAYMENT,
                tenant_id=None,
                client_id="client-1",
                provider=None,
                currency="RUB",
                country=None,
                threshold_set_id="policy-low",
                model_selector="risk_v4",
                priority=10,
                active=True,
            ),
        ]
    )
    session.commit()

    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=65))
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

    assert result.policy_id == "policy-priority-low"


def test_conflicting_policies_resolve_by_specificity(session):
    session.add_all(
        [
            RiskThresholdSet(
                id="set-generic",
                subject_type=RiskSubjectType.PAYMENT,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.PAYMENT,
                block_threshold=80,
                review_threshold=60,
                allow_threshold=10,
                valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            RiskThresholdSet(
                id="set-specific",
                subject_type=RiskSubjectType.PAYMENT,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.PAYMENT,
                block_threshold=80,
                review_threshold=60,
                allow_threshold=10,
                valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            RiskPolicy(
                id="policy-generic",
                subject_type=RiskSubjectType.PAYMENT,
                tenant_id=None,
                client_id=None,
                provider=None,
                currency="RUB",
                country=None,
                threshold_set_id="set-generic",
                model_selector="risk_v4",
                priority=5,
                active=True,
            ),
            RiskPolicy(
                id="policy-specific",
                subject_type=RiskSubjectType.PAYMENT,
                tenant_id=None,
                client_id="client-1",
                provider=None,
                currency="RUB",
                country=None,
                threshold_set_id="set-specific",
                model_selector="risk_v4",
                priority=5,
                active=True,
            ),
        ]
    )
    session.commit()

    engine_instance = DecisionEngine(session, scorer=StubRiskScorer(default_score=65))
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="SYSTEM",
        action=DecisionAction.PAYMENT_AUTHORIZE,
        amount=500,
        currency="RUB",
        history={},
        metadata={"subject_id": "op-2"},
    )

    result = engine_instance.evaluate(ctx)

    assert result.policy_id == "policy-specific"
