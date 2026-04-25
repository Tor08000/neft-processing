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
from app.services.risk_v5 import scorer_client
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
    captured: dict[str, dict] = {}

    def _score(*, payload: dict) -> ScorerResponse:
        captured["payload"] = payload
        return ScorerResponse(score=87, model_version="risk-v5-1", explain={"top_features": []})

    monkeypatch.setattr("app.services.risk_v5.shadow.score", _score)
    session = DummySession()
    record = enqueue_shadow_decision(session, DummyRiskDecision())
    assert isinstance(record, RiskV5ShadowDecision)
    assert session.added
    assert session.flushed
    assert record.v5_score == 87
    assert record.explain["degraded"] is False
    assert record.explain["assumptions"] == ["shadow_only"]
    assert captured["payload"]["amount"] == 1000
    assert captured["payload"]["document_type"] == "payment"
    assert captured["payload"]["metadata"]["subject_type"] == "PAYMENT"
    assert record.explain["provider_payload"]["schema"] == "ai_service_risk_score_v1"


def test_shadow_persistence_records_degraded_explain_on_score_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISK_V5_AB_WEIGHT", "100")

    def _score(*, payload: dict) -> ScorerResponse:
        raise ValueError("score_missing")

    monkeypatch.setattr("app.services.risk_v5.shadow.score", _score)
    session = DummySession()

    record = enqueue_shadow_decision(session, DummyRiskDecision())

    assert isinstance(record, RiskV5ShadowDecision)
    assert record.v5_score is None
    assert record.error == "score_missing"
    assert record.explain["degraded"] is True
    assert record.explain["error"] == "score_missing"


def test_scorer_client_accepts_canonical_risk_score_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, dict] = {}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "risk_score": 83,
                "decision": "MANUAL_REVIEW",
                "model_version": "risk-v5-provider",
                "explain": {"trace_hash": "a" * 64},
            }

    class _Client:
        def __init__(self, *, timeout: float, follow_redirects: bool) -> None:
            captured["client"] = {"timeout": timeout, "follow_redirects": follow_redirects}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, json: dict):
            captured["request"] = {"url": url, "json": json}
            return _Response()

    monkeypatch.setattr(scorer_client.httpx, "Client", _Client)

    result = scorer_client.score(payload={"amount": 1000, "document_type": "payment"})

    assert result.score == 83
    assert result.decision == "MANUAL_REVIEW"
    assert result.model_version == "risk-v5-provider"
    assert captured["request"]["json"]["document_type"] == "payment"


def test_scorer_client_normalizes_legacy_fraction_score(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"score": 0.87, "decision": "review", "trace": {"trace_hash": "b" * 64}}

    class _Client:
        def __init__(self, *, timeout: float, follow_redirects: bool) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, json: dict):
            return _Response()

    monkeypatch.setattr(scorer_client.httpx, "Client", _Client)

    result = scorer_client.score(payload={"amount": 1000})

    assert result.score == 87
    assert result.decision == "review"
