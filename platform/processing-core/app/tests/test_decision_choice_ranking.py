from __future__ import annotations

from datetime import datetime, timezone

from app.services.fleet_decision_choice import build_decision_choice_from_stats
from app.services.fleet_decision_choice.evaluator import ActionEffectStats
from app.services.fleet_decision_choice.defaults import DEFAULT_WINDOW_DAYS


def test_decision_choice_ranking_prefers_higher_adjusted_score() -> None:
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    stats = [
        ActionEffectStats(
            action_code="SUGGEST_RESTRICT_NIGHT_FUELING",
            insight_type="DRIVER",
            window_days=DEFAULT_WINDOW_DAYS,
            applied_count=100,
            improved_count=70,
            no_change_count=20,
            worsened_count=10,
            avg_effect_delta=0.12,
            last_computed_at=now,
        ),
        ActionEffectStats(
            action_code="SUGGEST_EXCLUDE_STATION_FROM_ROUTES",
            insight_type="DRIVER",
            window_days=DEFAULT_WINDOW_DAYS,
            applied_count=20,
            improved_count=18,
            no_change_count=1,
            worsened_count=1,
            avg_effect_delta=0.2,
            last_computed_at=now,
        ),
    ]

    result = build_decision_choice_from_stats(stats, window_days=DEFAULT_WINDOW_DAYS, now=now)

    assert result["recommended_action"]["action"] == "RESTRICT_NIGHT_FUELING"
    assert result["recommended_action"]["rank"] == 1
