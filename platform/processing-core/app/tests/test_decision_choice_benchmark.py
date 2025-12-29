from __future__ import annotations

from datetime import datetime, timezone

from app.services.fleet_decision_choice import build_decision_choice_from_stats
from app.services.fleet_decision_choice.evaluator import ActionEffectStats
from app.services.fleet_decision_choice.defaults import DEFAULT_WINDOW_DAYS


def test_decision_choice_benchmark_modifier_influences_ranking() -> None:
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    stats = [
        ActionEffectStats(
            action_code="SUGGEST_RESTRICT_NIGHT_FUELING",
            insight_type="DRIVER",
            window_days=DEFAULT_WINDOW_DAYS,
            applied_count=50,
            improved_count=30,
            no_change_count=15,
            worsened_count=5,
            avg_effect_delta=0.15,
            last_computed_at=now,
        ),
        ActionEffectStats(
            action_code="SUGGEST_EXCLUDE_STATION_FROM_ROUTES",
            insight_type="DRIVER",
            window_days=DEFAULT_WINDOW_DAYS,
            applied_count=50,
            improved_count=30,
            no_change_count=15,
            worsened_count=5,
            avg_effect_delta=0.1,
            last_computed_at=now,
        ),
    ]
    peer_percentiles = {
        "SUGGEST_RESTRICT_NIGHT_FUELING": 0.82,
        "SUGGEST_EXCLUDE_STATION_FROM_ROUTES": 0.22,
    }

    result = build_decision_choice_from_stats(
        stats,
        window_days=DEFAULT_WINDOW_DAYS,
        now=now,
        peer_percentiles=peer_percentiles,
    )

    assert result["recommended_action"]["action"] == "RESTRICT_NIGHT_FUELING"
    assert "Эффективнее" in result["reasoning"]["benchmark"]
