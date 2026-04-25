from datetime import datetime, timezone

import pytest

from app.models.audit_log import AuditLog
from app.models.decision_result import DecisionResult as DecisionResultRecord
from app.models.legal_graph import LegalEdge, LegalNode
from app.models.risk_decision import RiskDecision
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_training_snapshot import RiskTrainingSnapshot
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
from app.services.decision.rules import Rule
from app.services.decision.scoring import StubRiskScorer
from app.tests._scoped_router_harness import scoped_session_context


RISK_EXPLAIN_TEST_TABLES = (
    RiskThresholdSet.__table__,
    RiskPolicy.__table__,
    RiskThreshold.__table__,
    DecisionResultRecord.__table__,
    RiskDecision.__table__,
    RiskTrainingSnapshot.__table__,
    AuditLog.__table__,
)

RISK_EXPLAIN_GRAPH_TEST_TABLES = (
    *RISK_EXPLAIN_TEST_TABLES,
    LegalNode.__table__,
    LegalEdge.__table__,
)


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.services.decision.engine.LegalGraphBuilder.ensure_risk_decision_graph",
        lambda self, risk_decision: None,
    )
    with scoped_session_context(tables=RISK_EXPLAIN_TEST_TABLES) as db:
        yield db


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
    assert result.explain["thresholds"]["allow"] == 10
    assert result.explain["thresholds"]["block"] == 80
    assert result.explain["thresholds"]["review"] == 60
    assert result.explain["policy_id"] == "HIGH_RISK_PAYOUT"
    assert "velocity spike" in result.explain["factors"]
    assert result.explain["context_hash"]
    assert result.explain["assumptions"] == ["stub_score_default", "scorer_not_configured"]
    assert len(result.explain["scoring"]["trace_hash"]) == 64
    assert result.explain["scoring_trace_hash"] == result.explain["scoring"]["trace_hash"]
    assert result.explain["pipeline"]["scoring_trace_hash"] == result.explain["scoring"]["trace_hash"]
    assert result.explain["pipeline"]["score_source"] == "stub_default"
    assert result.explain["scoring"]["source"] == "stub_default"
    assert result.explain["scoring"]["evidence"]["compatibility_tail"] == "decision_engine_default_scorer"
    assert result.explain["scoring"]["evidence"]["default_score"] == 87
    assert result.explain["scoring"]["evidence"]["not_ml"] is True
    assert result.explain["model"]["name"] == "risk_v4"
    assert result.explain["model"]["version"] == "2025.01"
    assert result.explain["decision_hash"]
    decision_result_record = (
        session.query(DecisionResultRecord)
        .filter(DecisionResultRecord.decision_id == result.decision_id)
        .one()
    )
    assert decision_result_record.context_hash == result.explain["context_hash"]
    assert decision_result_record.explain["decision_hash"] == result.explain["decision_hash"]
    assert decision_result_record.explain["scoring"]["trace_hash"] == result.explain["scoring"]["trace_hash"]
    decision_record = session.query(RiskDecision).filter(RiskDecision.decision_id == result.decision_id).one()
    assert decision_record.features_snapshot["decision_id"] == result.decision_id
    assert decision_record.features_snapshot["decision_hash"] == result.explain["decision_hash"]
    assert decision_record.features_snapshot["context_hash"] == result.explain["context_hash"]
    assert decision_record.features_snapshot["scoring_trace_hash"] == result.explain["scoring"]["trace_hash"]
    assert decision_record.features_snapshot["scoring_source"] == "stub_default"
    training_snapshot = (
        session.query(RiskTrainingSnapshot)
        .filter(RiskTrainingSnapshot.decision_id == result.decision_id)
        .one()
    )
    assert training_snapshot.features_hash
    assert training_snapshot.context["metadata"]["subject_id"] == "payout-1"


def test_persisted_decision_trace_links_audit_and_graph_without_hash_drift():
    with scoped_session_context(tables=RISK_EXPLAIN_GRAPH_TEST_TABLES) as db:
        threshold_set = RiskThresholdSet(
            id="payments_v4",
            subject_type=RiskSubjectType.PAYMENT,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.PAYMENT,
            block_threshold=80,
            review_threshold=60,
            allow_threshold=10,
            currency="RUB",
            valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        policy = RiskPolicy(
            id="PAYMENT_RISK",
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
        db.add_all([threshold_set, policy])
        db.commit()

        result = DecisionEngine(
            db,
            scorer=StubRiskScorer(default_score=65),
            now_provider=lambda: datetime(2025, 1, 1, tzinfo=timezone.utc),
        ).evaluate(
            DecisionContext(
                tenant_id=1,
                client_id="client-1",
                actor_type="SYSTEM",
                action=DecisionAction.PAYMENT_AUTHORIZE,
                amount=500,
                currency="RUB",
                history={},
                metadata={"subject_id": "payment-op-1"},
            )
        )

        decision_record = db.query(DecisionResultRecord).filter_by(decision_id=result.decision_id).one()
        risk_record = db.query(RiskDecision).filter_by(decision_id=result.decision_id).one()

        assert decision_record.explain["decision_hash"] == result.explain["decision_hash"]
        assert decision_record.explain["scoring_trace_hash"] == result.explain["scoring_trace_hash"]
        assert decision_record.explain["record_refs"]["decision_result_id"] == str(decision_record.id)
        assert decision_record.explain["record_refs"]["risk_decision_id"] == str(risk_record.id)
        assert decision_record.explain["audit"]["decision_audit_id"]
        assert decision_record.explain["audit"]["risk_decision_audit_id"]
        assert decision_record.explain["graph"]["status"] == "written"
        assert decision_record.explain["graph"]["target_type"] == "PAYMENT"
        assert decision_record.explain["graph"]["edge_type"] == "GATED_BY_RISK"

        snapshot = risk_record.features_snapshot
        assert snapshot["record_refs"] == decision_record.explain["record_refs"]
        assert snapshot["audit"] == decision_record.explain["audit"]
        assert snapshot["graph"]["edge_id"] == decision_record.explain["graph"]["edge_id"]
        assert db.query(LegalNode).count() == 2
        assert db.query(LegalEdge).count() == 1
