from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.decision_memory import DecisionMemoryEffectLabel, DecisionMemoryEntityType, DecisionOutcome
from app.services.decision_memory import decay


def test_weighted_stats_prefers_recent_outcomes() -> None:
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    recent = DecisionOutcome(
        tenant_id=1,
        client_id="client-1",
        entity_type=DecisionMemoryEntityType.DRIVER,
        entity_id="driver-1",
        action_code="SUGGEST_RESTRICT_NIGHT_FUELING",
        applied_at=now - timedelta(days=1),
        measured_at=now - timedelta(days=1),
        window_days=7,
        effect_label=DecisionMemoryEffectLabel.IMPROVED,
    )
    older = DecisionOutcome(
        tenant_id=1,
        client_id="client-1",
        entity_type=DecisionMemoryEntityType.DRIVER,
        entity_id="driver-1",
        action_code="SUGGEST_RESTRICT_NIGHT_FUELING",
        applied_at=now - timedelta(days=31),
        measured_at=now - timedelta(days=31),
        window_days=7,
        effect_label=DecisionMemoryEffectLabel.IMPROVED,
    )

    stats = decay.compute_weighted_stats([recent, older], now=now, half_life_days=30)

    recent_weight = decay.decay_weight(age_days=1, half_life_days=30)
    older_weight = decay.decay_weight(age_days=31, half_life_days=30)
    assert stats.weighted_success == pytest.approx(recent_weight + older_weight)
    assert stats.weighted_success > older_weight
