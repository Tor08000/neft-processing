from __future__ import annotations

from datetime import datetime, timezone

from app.services.decision_memory.cooldown import CooldownStatus
from app.services.fleet_decision_choice import build_decision_choice_from_stats
from app.services.fleet_decision_choice.evaluator import ActionEffectStats
from app.services.fleet_decision_choice.defaults import DEFAULT_WINDOW_DAYS


def test_decision_choice_penalizes_cooldown_action() -> None:
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    stats = [
        ActionEffectStats(
            action_code="SUGGEST_RESTRICT_NIGHT_FUELING",
            insight_type="DRIVER",
            window_days=DEFAULT_WINDOW_DAYS,
            applied_count=50,
            improved_count=35,
            no_change_count=10,
            worsened_count=5,
            avg_effect_delta=0.2,
            last_computed_at=now,
        ),
        ActionEffectStats(
            action_code="SUGGEST_EXCLUDE_STATION_FROM_ROUTES",
            insight_type="DRIVER",
            window_days=DEFAULT_WINDOW_DAYS,
            applied_count=40,
            improved_count=20,
            no_change_count=10,
            worsened_count=10,
            avg_effect_delta=0.05,
            last_computed_at=now,
        ),
    ]
    cooldowns = {
        "SUGGEST_RESTRICT_NIGHT_FUELING": CooldownStatus(
            cooldown=True,
            reason="Action tried 2 times in 14 days with no improvement",
            recent_count=2,
            failed_streak=2,
        )
    }

    result = build_decision_choice_from_stats(
        stats,
        window_days=DEFAULT_WINDOW_DAYS,
        now=now,
        cooldowns=cooldowns,
    )

    assert result["recommended_action"]["action_code"] == "SUGGEST_EXCLUDE_STATION_FROM_ROUTES"
