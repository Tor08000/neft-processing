from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone

import pytest

from app.models.risk_types import RiskDecisionType, RiskSubjectType
from app.models.risk_v5_shadow_decision import RiskV5ShadowDecision
from app.services.decision.context import DecisionContext
from app.services.risk_v5.ab import determine_bucket
from app.services.risk_v5.feature_store import build_feature_snapshot
from app.services.risk_v5.registry_client import model_selector
from app.services.risk_v5.scorer_client import ScorerResponse
from app.services.risk_v5.shadow import enqueue_shadow_decision


class DummyQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return None


class DummySession:
    def __init__(self) -> None:
        self.added: list = []
        self.flushed = False

    def begin_nested(self):
        return nullcontext()

    def add(self, item):
        self.added.append(item)

    def flush(self):
        self.flushed = True

    def query(self, *args, **kwargs):
        return DummyQuery()


class DummyRiskDecision:
    def __init__(self) -> None:
        self.decision_id = "decision-1"
        self.subject_type = RiskSubjectType.PAYMENT
        self.subject_id = "op-1"
        self.score = 42
        self.outcome = RiskDecisionType.ALLOW
        self.policy_id = "policy-v4"
        self.threshold_set_id = "threshold-v4"
        self.decided_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.features_snapshot = {
            "tenant_id": 1,
            "client_id": "client-1",
            "actor_type": "SYSTEM",
            "action": "PAYMENT_AUTHORIZE",
            "amount": 1000,
            "currency": "USD",
            "history": {"txn_count_24h": 3},
            "metadata": {"subject_id": "op-1", "provider_risk_level": "LOW"},
        }


@pytest.mark.parametrize("client_id", ["client-1", "client-2"])
def test_deterministic_bucket(client_id: str) -> None:
    bucket = determine_bucket(
        client_id=client_id,
        subject_type=RiskSubjectType.PAYMENT,
        salt="test-salt",
        weight_b=50,
    )
    repeat = determine_bucket(
        client_id=client_id,
        subject_type=RiskSubjectType.PAYMENT,
        salt="test-salt",
        weight_b=50,
    )
    assert bucket == repeat


def test_feature_hash_deterministic() -> None:
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        action="PAYMENT_AUTHORIZE",
        amount=1000,
        currency="USD",
        history={"txn_count_24h": 3},
        metadata={"provider_risk_level": "LOW"},
    )
    snapshot_a = build_feature_snapshot(ctx)
    snapshot_b = build_feature_snapshot(ctx)
    assert snapshot_a.features_hash == snapshot_b.features_hash


def test_model_selector() -> None:
    selector = model_selector(RiskSubjectType.PAYMENT)
    assert selector == "risk_v5_payment"


def test_shadow_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISK_V5_AB_WEIGHT", "100")

    def _score(*, payload: dict) -> ScorerResponse:
        return ScorerResponse(score=87, model_version="risk-v5-1", explain={"top_features": []})

    monkeypatch.setattr("app.services.risk_v5.scorer_client.score", _score)
    session = DummySession()
    record = enqueue_shadow_decision(session, DummyRiskDecision())
    assert isinstance(record, RiskV5ShadowDecision)
    assert session.added
    assert session.flushed
    assert record.v5_score == 87
