from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services import risk_adapter
from app.services.risk_adapter import OperationContext, RiskDecisionLevel, RiskResult, evaluate_risk


@pytest.fixture(autouse=True)
def _reset_risk_metrics():
    risk_adapter.metrics.reset()
    yield
    risk_adapter.metrics.reset()


def _context(*, amount: int = 1_000) -> OperationContext:
    return OperationContext(
        client_id=uuid4(),
        card_id=uuid4(),
        terminal_id="terminal-1",
        merchant_id="merchant-1",
        product_type="DIESEL",
        amount=amount,
        currency="RUB",
        created_at=datetime.now(timezone.utc),
    )


def test_call_risk_engine_timeout_is_explicitly_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _slow_post(payload):
        await asyncio.sleep(risk_adapter.AI_SCORE_TIMEOUT_SECONDS + 0.2)
        return {"risk_score": 0.1, "decision": "LOW"}

    monkeypatch.setattr(risk_adapter, "_post_score", _slow_post)

    result = asyncio.run(risk_adapter.call_risk_engine(_context()))

    assert result.source == "FALLBACK"
    assert result.degraded is True
    assert result.flags["error_type"] == "timeout"
    assert result.flags["degraded"] is True
    assert result.decision.reason_codes == ["ai_timeout"]
    assert result.pipeline["status"] == "degraded"


def test_evaluate_risk_marks_malformed_ai_payload_as_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _rules(context, db=None, rules=None):
        return RiskResult(
            risk_score=0.8,
            risk_result="HIGH",
            reasons=["amount_above_threshold"],
            flags={},
            source="RULES",
        )

    async def _bad_post(payload):
        return {"decision": "LOW", "model_version": "broken"}

    monkeypatch.setattr("app.services.risk_rules.evaluate_rules", _rules)
    monkeypatch.setattr(risk_adapter, "_post_score", _bad_post)

    result = asyncio.run(evaluate_risk(_context(amount=150_000)))

    assert result.source == "RULES_FALLBACK"
    assert result.degraded is True
    assert result.flags["ai_error_type"] == "malformed_response"
    assert result.flags["decision_trace"]["ai"]["degraded"] is True
    assert len(result.flags["decision_trace_hash"]) == 64
    assert "amount_above_threshold" in result.decision.reason_codes


def test_evaluate_risk_records_ai_success_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _rules(context, db=None, rules=None):
        return RiskResult(
            risk_score=0.1,
            risk_result="LOW",
            reasons=[],
            flags={},
            source="RULES",
        )

    async def _post(payload):
        return {
            "risk_score": 0.76,
            "decision": "HIGH",
            "reason_codes": ["ai_high"],
            "model_version": "v1.2.3",
        }

    monkeypatch.setattr("app.services.risk_rules.evaluate_rules", _rules)
    monkeypatch.setattr(risk_adapter, "_post_score", _post)

    result = asyncio.run(evaluate_risk(_context()))
    same_result = asyncio.run(evaluate_risk(_context()))

    assert result.source == "AI"
    assert result.degraded is False
    assert result.decision.level == RiskDecisionLevel.HIGH
    assert result.decision.reason_codes == ["ai_high"]
    assert result.flags["decision_trace"]["ai"]["pipeline"]["status"] == "ok"
    assert result.flags["decision_trace"]["result"]["source"] == "AI"
    assert len(result.flags["decision_trace_hash"]) == 64
    assert result.flags["decision_trace_hash"] == same_result.flags["decision_trace_hash"]
