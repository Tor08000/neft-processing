from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.decision_memory import cooldown as memory_cooldown
from app.services.decision_memory import decay as memory_decay
from app.services.decision_memory import repository as memory_repository
from app.services.decision_memory import stats as memory_stats
from app.services.fleet_assistant.projections import build_outcome_projection
from app.services.what_if import actions, defaults, explain, inputs, scoring


@dataclass(frozen=True)
class CandidatePayload:
    action_code: str
    action_title: str
    normalized_code: str
    probability_improved_pct: int
    expected_effect_label: str
    projection_window_days: int
    confidence: float
    sample_size: int
    memory_penalty_pct: int
    memory_window_days: int
    cooldown_active: bool
    cooldown_reason: str | None
    risk_outlook: scoring.RiskOutlook
    risk_notes: list[str]
    deeplink: str | None


@dataclass(frozen=True)
class SimulationResponse:
    subject: dict
    candidates: list[dict]
    recommendation: dict | None


def evaluate_what_if(
    db: Session,
    *,
    subject: inputs.WhatIfSubject,
    max_candidates: int | None = None,
) -> dict:
    resolved_max = max_candidates or defaults.MAX_CANDIDATES
    context = inputs.build_context(db, subject=subject)
    decision_choice_info = actions.extract_decision_choice_info(context.decision_choice)
    suggested_actions = context.suggested_actions if context.subject.type == "INSIGHT" else None
    candidate_actions = actions.list_candidate_actions(
        suggested_actions=suggested_actions,
        decision_choice=context.decision_choice,
        max_candidates=resolved_max,
    )
    if not candidate_actions:
        return _empty_response(context)

    memory_stats_map = _load_memory_stats(db, context=context, action_codes=candidate_actions)
    cooldown_map = _load_cooldowns(db, context=context, action_codes=candidate_actions)

    candidates = [
        _build_candidate(
            db=db,
            action_code=action_code,
            context=context,
            decision_choice_info=decision_choice_info,
            memory_stats_map=memory_stats_map,
            cooldown_map=cooldown_map,
        )
        for action_code in candidate_actions
    ]
    return _build_response(context=context, candidates=candidates)


def simulate_candidates(subject: inputs.WhatIfSubject, candidates: list[CandidatePayload]) -> SimulationResponse:
    ranked = _rank_candidates(candidates)
    return _assemble_response(subject=subject, ranked=ranked)


def _load_memory_stats(
    db: Session,
    *,
    context: inputs.WhatIfContext,
    action_codes: list[str],
) -> dict[str, memory_stats.DecisionActionStats]:
    memory_entity_type = context.memory_entity_type
    if not memory_entity_type or context.tenant_id is None:
        return {}
    return memory_stats.build_action_stats_map(
        db,
        tenant_id=context.tenant_id,
        client_id=context.client_id,
        action_codes=action_codes,
        entity_type=memory_entity_type,
        window_days=context.window_days or defaults.MEMORY_WINDOW_DAYS,
    )


def _load_cooldowns(
    db: Session,
    *,
    context: inputs.WhatIfContext,
    action_codes: list[str],
) -> dict[str, memory_cooldown.CooldownStatus]:
    memory_entity_type = context.memory_entity_type
    if not memory_entity_type or not context.entity_id:
        return {}
    return {
        action_code: memory_cooldown.evaluate_cooldown(
            db,
            entity_type=memory_entity_type,
            entity_id=context.entity_id,
            action_code=action_code,
        )
        for action_code in action_codes
    }


def _build_candidate(
    db: Session,
    *,
    action_code: str,
    context: inputs.WhatIfContext,
    decision_choice_info: dict[str, actions.DecisionChoiceActionInfo],
    memory_stats_map: dict[str, memory_stats.DecisionActionStats],
    cooldown_map: dict[str, memory_cooldown.CooldownStatus],
) -> CandidatePayload:
    decision_meta = decision_choice_info.get(action_code)
    confidence = 0.0
    cooldown_active = False
    cooldown_reason = None
    memory_window_days = defaults.MEMORY_WINDOW_DAYS
    if decision_meta and decision_meta.confidence is not None:
        confidence = decision_meta.confidence
    elif action_code in context.confidence_map:
        confidence = context.confidence_map[action_code]
    if decision_meta:
        cooldown_active = decision_meta.cooldown
        cooldown_reason = decision_meta.cooldown_reason
        if decision_meta.memory_window_days:
            memory_window_days = decision_meta.memory_window_days

    memory_stats_item = memory_stats_map.get(action_code)
    sample_size = 0
    if memory_stats_item:
        sample_size = memory_stats_item.applied_count
        memory_window_days = memory_stats_item.window_days
    elif decision_meta and decision_meta.memory_sample_size is not None:
        sample_size = decision_meta.memory_sample_size

    cooldown_status = cooldown_map.get(action_code)
    if cooldown_status:
        cooldown_active = cooldown_status.cooldown
        cooldown_reason = cooldown_status.reason
    failed_streak = cooldown_status.failed_streak if cooldown_status else 0
    recency_weight = 1.0
    if not cooldown_active and failed_streak > 0 and context.memory_entity_type and context.entity_id:
        outcomes = memory_repository.list_recent_outcomes(
            db,
            entity_type=context.memory_entity_type,
            entity_id=context.entity_id,
            action_code=action_code,
        )
        if outcomes:
            now = datetime.now(timezone.utc)
            age_days = memory_decay.outcome_age_days(outcomes[0], now=now)
            recency_weight = memory_decay.decay_weight(
                age_days=age_days,
                half_life_days=defaults.MEMORY_HALF_LIFE_DAYS,
            )
    memory_penalty_pct = scoring.compute_memory_penalty_pct(
        cooldown_active=cooldown_active,
        failed_streak=failed_streak,
        recency_weight=recency_weight,
    )

    projection = build_outcome_projection(
        confidence=confidence,
        sample_size=sample_size,
        trend_label=None,
        entity_type=context.entity_type,
        sla_remaining_minutes=None,
        aging_days=None,
        insight_status=None,
        time_window_days=defaults.PROJECTION_WINDOW_DAYS,
        cooldown=cooldown_active,
        cooldown_reason=cooldown_reason,
    )
    applied = projection.if_applied

    normalized_code = actions.normalize_action_code(action_code)
    category = actions.action_category(action_code)
    risk_outlook, risk_notes = scoring.resolve_risk_outlook(category, memory_penalty_pct)

    return CandidatePayload(
        action_code=action_code,
        action_title=actions.action_title(action_code),
        normalized_code=normalized_code,
        probability_improved_pct=applied.probability_improved_pct,
        expected_effect_label=applied.expected_effect_label,
        projection_window_days=applied.expected_time_window_days,
        confidence=round(confidence, 2),
        sample_size=sample_size,
        memory_penalty_pct=memory_penalty_pct,
        memory_window_days=memory_window_days,
        cooldown_active=cooldown_active,
        cooldown_reason=cooldown_reason,
        risk_outlook=risk_outlook,
        risk_notes=risk_notes,
        deeplink=actions.action_deeplink(action_code),
    )


def _build_response(*, context: inputs.WhatIfContext, candidates: list[CandidatePayload]) -> dict:
    ranked = _rank_candidates(candidates)
    response = _assemble_response(subject=context.subject, ranked=ranked)
    return {
        "subject": response.subject,
        "candidates": response.candidates,
        "recommendation": response.recommendation,
    }


def _assemble_response(subject: inputs.WhatIfSubject, ranked: list[tuple[CandidatePayload, scoring.ScoreResult]]) -> SimulationResponse:
    candidates_payload: list[dict] = []
    recommendation = None
    for candidate, score_result in ranked:
        candidates_payload.append(
            _candidate_payload(candidate=candidate, rank=score_result.rank, what_if_score=score_result.what_if_score)
        )
    if ranked:
        best = ranked[0][0]
        recommendation = {
            "best_action_code": best.normalized_code,
            "reason_short": "Лучшее сочетание вероятности эффекта и низкого penalty",
        }
    return SimulationResponse(
        subject={"type": subject.type, "id": subject.id},
        candidates=candidates_payload,
        recommendation=recommendation,
    )


def _rank_candidates(candidates: list[CandidatePayload]) -> list[tuple[CandidatePayload, scoring.ScoreResult]]:
    score_inputs = [
        scoring.ScoreInput(
            action_code=candidate.action_code,
            probability_improved_pct=candidate.probability_improved_pct,
            memory_penalty_pct=candidate.memory_penalty_pct,
            risk_outlook=candidate.risk_outlook,
        )
        for candidate in candidates
    ]
    ranked_scores = scoring.rank_candidates(score_inputs)
    score_map = {score.action_code: score for score in ranked_scores}
    ranked = sorted(
        candidates,
        key=lambda item: (score_map[item.action_code].rank, item.action_code),
    )
    return [(item, score_map[item.action_code]) for item in ranked]


def _candidate_payload(*, candidate: CandidatePayload, rank: int, what_if_score: float) -> dict:
    score_value = round(what_if_score, 2)
    return {
        "rank": rank,
        "action": {
            "code": candidate.normalized_code,
            "title": candidate.action_title,
        },
        "projection": {
            "probability_improved_pct": candidate.probability_improved_pct,
            "expected_effect_label": candidate.expected_effect_label,
            "window_days": candidate.projection_window_days,
        },
        "memory": {
            "cooldown": candidate.cooldown_active,
            "memory_penalty_pct": candidate.memory_penalty_pct,
            "basis": {
                "sample_size": candidate.sample_size,
                "confidence": candidate.confidence,
                "window_days": candidate.memory_window_days,
                "half_life_days": defaults.MEMORY_HALF_LIFE_DAYS,
                "cooldown_reason": candidate.cooldown_reason,
            },
        },
        "risk": {
            "outlook": candidate.risk_outlook.value,
            "notes": candidate.risk_notes,
        },
        "what_if_score": score_value,
        "explain": explain.build_explain_lines(
            probability_improved_pct=candidate.probability_improved_pct,
            sample_size=candidate.sample_size,
            memory_penalty_pct=candidate.memory_penalty_pct,
            risk_outlook=candidate.risk_outlook,
        ),
        "deeplink": candidate.deeplink,
    }


def _empty_response(context: inputs.WhatIfContext) -> dict:
    return {
        "subject": {"type": context.subject.type, "id": context.subject.id},
        "candidates": [],
        "recommendation": None,
    }


__all__ = [
    "CandidatePayload",
    "SimulationResponse",
    "evaluate_what_if",
    "simulate_candidates",
]
