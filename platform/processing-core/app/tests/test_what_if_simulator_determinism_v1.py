from __future__ import annotations

from app.services.what_if import scoring
from app.services.what_if.inputs import WhatIfSubject
from app.services.what_if.simulator import CandidatePayload, simulate_candidates


def test_what_if_simulator_deterministic_output() -> None:
    subject = WhatIfSubject(type="INSIGHT", id="insight-123")
    candidates = [
        CandidatePayload(
            action_code="SUGGEST_RESTRICT_NIGHT_FUELING",
            action_title="Ограничить ночные заправки",
            normalized_code="RESTRICT_NIGHT_FUELING",
            probability_improved_pct=60,
            expected_effect_label="IMPROVED",
            projection_window_days=7,
            confidence=0.6,
            sample_size=12,
            memory_penalty_pct=0,
            memory_window_days=90,
            cooldown_active=False,
            cooldown_reason=None,
            risk_outlook=scoring.RiskOutlook.IMPROVE,
            risk_notes=["note1", "note2"],
            deeplink="/crm/limit-profiles",
        ),
        CandidatePayload(
            action_code="SUGGEST_EXCLUDE_STATION_FROM_ROUTES",
            action_title="Исключить станцию из маршрутов",
            normalized_code="EXCLUDE_STATION_FROM_ROUTES",
            probability_improved_pct=55,
            expected_effect_label="IMPROVED",
            projection_window_days=7,
            confidence=0.55,
            sample_size=10,
            memory_penalty_pct=30,
            memory_window_days=90,
            cooldown_active=False,
            cooldown_reason=None,
            risk_outlook=scoring.RiskOutlook.NO_CHANGE,
            risk_notes=["note1", "note2"],
            deeplink="/logistics/route-constraints",
        ),
    ]

    first = simulate_candidates(subject, candidates)
    second = simulate_candidates(subject, candidates)

    assert first == second
