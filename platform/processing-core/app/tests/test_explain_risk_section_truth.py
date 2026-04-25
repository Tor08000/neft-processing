from __future__ import annotations

from types import SimpleNamespace

from app.models.risk_decision import RiskDecision
from app.models.risk_score import RiskLevel
from app.models.risk_types import RiskDecisionActor, RiskDecisionType, RiskSubjectType
from app.services.explain.sources import build_risk_section


class _DummyDB:
    def __init__(self, decision: RiskDecision) -> None:
        self._decision = decision

    def get(self, model, identifier):
        return self._decision


def test_build_risk_section_uses_persisted_decision_trace() -> None:
    decision = RiskDecision(
        id="risk-row-1",
        decision_id="decision-1",
        subject_type=RiskSubjectType.PAYMENT,
        subject_id="tx-1",
        score=87,
        risk_level=RiskLevel.VERY_HIGH,
        threshold_set_id="threshold-v1",
        policy_id="policy-v1",
        outcome=RiskDecisionType.BLOCK,
        model_version="risk-v4-2025.01",
        reasons=[{"feature": "amount_exceeds_single_limit", "impact": None}],
        features_snapshot={
            "decision_hash": "decision-hash-1",
            "context_hash": "context-hash-1",
            "scoring_trace_hash": "scoring-trace-hash-1",
            "scoring_source": "stub_default",
        },
        audit_id="audit-1",
        decided_by=RiskDecisionActor.SYSTEM,
    )
    tx = SimpleNamespace(
        meta={"fraud_signals": [{"code": "velocity_spike"}]},
        risk_decision_id=decision.id,
    )

    payload = build_risk_section(_DummyDB(decision), tx=tx)

    assert payload["decision"] == "BLOCK"
    assert payload["score"] == 87
    assert payload["policy_id"] == "policy-v1"
    assert payload["decision_id"] == "decision-1"
    assert payload["decision_hash"] == "decision-hash-1"
    assert payload["context_hash"] == "context-hash-1"
    assert payload["scoring_trace_hash"] == "scoring-trace-hash-1"
    assert payload["scoring_source"] == "stub_default"
    assert payload["fraud_signals"] == [{"code": "velocity_spike"}]
