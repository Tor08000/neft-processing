from __future__ import annotations

from app.services.fleet_decision_choice import defaults, scorer


def build_decision_choice_output(
    scores: list[scorer.ActionScore],
    *,
    window_days: int,
) -> dict:
    if not scores:
        return {
            "recommended_action": None,
            "alternatives": [],
            "reasoning": {
                "why": "Недостаточно данных для выбора действия.",
                "comparison": None,
                "benchmark": "Данные для сравнения недоступны.",
                "data_window": f"последние {window_days} дней",
            },
        }
    primary = scores[0]
    alternatives = scores[1:]
    recommended = _build_action_payload(primary)
    return {
        "recommended_action": recommended,
        "alternatives": [_build_action_payload(score) for score in alternatives],
        "reasoning": _build_reasoning(primary, alternatives, window_days=window_days),
    }


def _build_action_payload(score: scorer.ActionScore) -> dict:
    confidence = round(score.success_rate * score.confidence_weight, 2)
    return {
        "action": _label_for_action(score.action_code),
        "confidence": confidence,
        "rank": score.rank,
    }


def _build_reasoning(
    primary: scorer.ActionScore,
    alternatives: list[scorer.ActionScore],
    *,
    window_days: int,
) -> dict:
    success_pct = round(primary.success_rate * 100)
    confidence_pct = round(primary.confidence_weight * 100)
    why = (
        f"{_label_for_action(primary.action_code).replace('_', ' ').title()} "
        f"исторически улучшало ситуацию в {success_pct}% случаев. "
        f"Доверие к оценке: {confidence_pct}% на {primary.applied_count} применениях."
    )
    comparison = _comparison_text(primary, alternatives)
    benchmark = primary.benchmark_comparison or "Данные для сравнения недоступны."
    return {
        "why": why,
        "comparison": comparison,
        "benchmark": benchmark,
        "data_window": f"последние {window_days} дней",
    }


def _comparison_text(primary: scorer.ActionScore, alternatives: list[scorer.ActionScore]) -> str | None:
    if not alternatives:
        return None
    best_alt = alternatives[0]
    alt_pct = round(best_alt.success_rate * 100)
    return (
        f"Это выше, чем {_label_for_action(best_alt.action_code).replace('_', ' ').lower()} "
        f"({alt_pct}%)."
    )


def _label_for_action(action_code: str) -> str:
    return defaults.ACTION_LABELS.get(action_code, action_code)


__all__ = ["build_decision_choice_output"]
