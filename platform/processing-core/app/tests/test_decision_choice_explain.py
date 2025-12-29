from __future__ import annotations

from datetime import datetime, timezone

from app.services.fleet_decision_choice import build_decision_choice_from_stats
from app.services.fleet_decision_choice.evaluator import ActionEffectStats
from app.services.fleet_decision_choice.defaults import DEFAULT_WINDOW_DAYS


def test_decision_choice_explain_contains_rates() -> None:
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    stats = [
        ActionEffectStats(
            action_code="SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL",
            insight_type="STATION",
            window_days=DEFAULT_WINDOW_DAYS,
            applied_count=30,
            improved_count=20,
            no_change_count=7,
            worsened_count=3,
            avg_effect_delta=0.08,
            last_computed_at=now,
        ),
        ActionEffectStats(
            action_code="SUGGEST_EXCLUDE_STATION_FROM_ROUTES",
            insight_type="STATION",
            window_days=DEFAULT_WINDOW_DAYS,
            applied_count=30,
            improved_count=10,
            no_change_count=12,
            worsened_count=8,
            avg_effect_delta=0.02,
            last_computed_at=now,
        ),
    ]

    result = build_decision_choice_from_stats(stats, window_days=DEFAULT_WINDOW_DAYS, now=now)
    reasoning = result["reasoning"]

    assert "67%" in reasoning["why"]
    assert "33%" in reasoning["comparison"]
    assert reasoning["data_window"] == f"последние {DEFAULT_WINDOW_DAYS} дней"
