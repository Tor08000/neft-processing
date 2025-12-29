from __future__ import annotations

from app.services.what_if import scoring


def test_what_if_ranking_prefers_best_score() -> None:
    inputs = [
        scoring.ScoreInput(
            action_code="SUGGEST_RESTRICT_NIGHT_FUELING",
            probability_improved_pct=65,
            memory_penalty_pct=0,
            risk_outlook=scoring.RiskOutlook.IMPROVE,
        ),
        scoring.ScoreInput(
            action_code="SUGGEST_EXCLUDE_STATION_FROM_ROUTES",
            probability_improved_pct=50,
            memory_penalty_pct=30,
            risk_outlook=scoring.RiskOutlook.NO_CHANGE,
        ),
        scoring.ScoreInput(
            action_code="SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL",
            probability_improved_pct=55,
            memory_penalty_pct=0,
            risk_outlook=scoring.RiskOutlook.NO_CHANGE,
        ),
    ]

    ranked = scoring.rank_candidates(inputs)

    assert ranked[0].action_code == "SUGGEST_RESTRICT_NIGHT_FUELING"
    assert ranked[0].rank == 1


def test_what_if_cooldown_penalty_drops_rank() -> None:
    baseline = scoring.ScoreInput(
        action_code="SUGGEST_RESTRICT_NIGHT_FUELING",
        probability_improved_pct=70,
        memory_penalty_pct=0,
        risk_outlook=scoring.RiskOutlook.IMPROVE,
    )
    cooldown = scoring.ScoreInput(
        action_code="SUGGEST_EXCLUDE_STATION_FROM_ROUTES",
        probability_improved_pct=70,
        memory_penalty_pct=100,
        risk_outlook=scoring.RiskOutlook.IMPROVE,
    )

    ranked = scoring.rank_candidates([cooldown, baseline])

    assert ranked[0].action_code == "SUGGEST_RESTRICT_NIGHT_FUELING"
    assert ranked[1].action_code == "SUGGEST_EXCLUDE_STATION_FROM_ROUTES"
