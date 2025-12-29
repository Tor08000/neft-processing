from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.what_if import defaults


class RiskOutlook(str, Enum):
    IMPROVE = "IMPROVE"
    NO_CHANGE = "NO_CHANGE"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class ScoreInput:
    action_code: str
    probability_improved_pct: int
    memory_penalty_pct: int
    risk_outlook: RiskOutlook


@dataclass(frozen=True)
class ScoreResult:
    action_code: str
    what_if_score: float
    rank: int


def compute_memory_penalty_pct(*, cooldown_active: bool, failed_streak: int, recency_weight: float = 1.0) -> int:
    if cooldown_active:
        return 100
    base_penalty = 0.0
    if failed_streak >= 2:
        base_penalty = 0.6
    elif failed_streak == 1:
        base_penalty = 0.3
    weight = max(0.0, min(1.0, recency_weight))
    return round(base_penalty * weight * 100)


def resolve_risk_outlook(action_category: str | None, memory_penalty_pct: int) -> tuple[RiskOutlook, list[str]]:
    if memory_penalty_pct >= defaults.HIGH_PENALTY_PCT:
        return (
            RiskOutlook.UNCERTAIN,
            [
                "Memory penalty высокий: действие недавно не дало эффекта.",
                "Risk improvement uncertain из-за повторяемости без улучшений.",
            ],
        )
    if action_category in {"DRIVER_BEHAVIOR", "STATION_TRUST", "ROUTE_ADHERENCE"}:
        return (
            RiskOutlook.IMPROVE,
            [
                "Действие влияет на поведенческий или маршрутный риск.",
                "Risk posture expected to improve.",
            ],
        )
    return (
        RiskOutlook.NO_CHANGE,
        [
            "Нет прямых факторов, меняющих risk posture.",
            "Risk posture ожидается без изменений.",
        ],
    )


def compute_score(score_input: ScoreInput) -> float:
    prob_component = (score_input.probability_improved_pct / 100) * defaults.WEIGHT_PROBABILITY
    outlook_bonus = defaults.OUTLOOK_BONUS.get(score_input.risk_outlook.value, 0.0)
    risk_component = outlook_bonus * defaults.WEIGHT_RISK
    penalty_component = (score_input.memory_penalty_pct / 100) * defaults.WEIGHT_PENALTY
    return prob_component + risk_component - penalty_component


def rank_candidates(score_inputs: list[ScoreInput]) -> list[ScoreResult]:
    scored = [
        (item.action_code, compute_score(item))
        for item in score_inputs
    ]
    ranked = sorted(scored, key=lambda item: (-item[1], item[0]))
    return [
        ScoreResult(action_code=action_code, what_if_score=score, rank=index + 1)
        for index, (action_code, score) in enumerate(ranked)
    ]


__all__ = [
    "RiskOutlook",
    "ScoreInput",
    "ScoreResult",
    "compute_memory_penalty_pct",
    "compute_score",
    "rank_candidates",
    "resolve_risk_outlook",
]
