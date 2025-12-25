from app.models.risk_score import RiskLevel, RiskScoreAction
from app.services.decision import DecisionContext, DecisionEngine, DecisionOutcome
from app.services.decision.rules.scoring_rules import default_scoring_rules


def test_scoring_rules_large_payment():
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        amount=10_000_001,
        action=RiskScoreAction.PAYMENT,
        scoring_rules=default_scoring_rules(),
    )
    result = DecisionEngine().evaluate(ctx)

    assert result.risk_level == RiskLevel.HIGH
    assert result.outcome == DecisionOutcome.DECLINE
    assert "amount_exceeds_single_limit" in result.explain["reason_codes"]


def test_scoring_rules_blocked_client():
    ctx = DecisionContext(
        tenant_id=1,
        client_id="blocked-1",
        amount=500,
        action=RiskScoreAction.PAYMENT,
        scoring_rules=default_scoring_rules(blocked_clients={"blocked-1"}),
    )
    result = DecisionEngine().evaluate(ctx)

    assert result.risk_level == RiskLevel.VERY_HIGH
    assert result.outcome == DecisionOutcome.DECLINE
    assert "client_is_blocked" in result.explain["reason_codes"]


def test_scoring_rules_underage_client():
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        amount=500,
        action=RiskScoreAction.PAYMENT,
        scoring_rules=default_scoring_rules(),
        age=16,
    )
    result = DecisionEngine().evaluate(ctx)

    assert result.risk_level == RiskLevel.HIGH
    assert result.outcome == DecisionOutcome.DECLINE
    assert "client_underage" in result.explain["reason_codes"]


def test_decision_engine_determinism():
    ctx = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        amount=500,
        action=RiskScoreAction.PAYMENT,
        scoring_rules=default_scoring_rules(),
    )
    engine = DecisionEngine()
    first = engine.evaluate(ctx)
    second = engine.evaluate(ctx)

    assert first.outcome == second.outcome
    assert first.risk_level == second.risk_level
    assert first.risk_score == second.risk_score
    assert first.explain == second.explain
