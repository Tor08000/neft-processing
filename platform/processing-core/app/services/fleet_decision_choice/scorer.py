from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.services.fleet_decision_choice import benchmark, evaluator


@dataclass(frozen=True)
class ActionScore:
    action_code: str
    applied_count: int
    improved_count: int
    success_rate: float
    confidence_weight: float
    effect_strength: float
    benchmark_modifier: float
    adjusted_score: float
    benchmark_comparison: str | None
    rank: int = 0


def score_actions(
    stats: list[evaluator.ActionEffectStats],
    *,
    peer_percentiles: dict[str, float] | None = None,
    now: datetime | None = None,
) -> list[ActionScore]:
    scored: list[ActionScore] = []
    for item in stats:
        evaluation = evaluator.evaluate_action(item, now=now)
        bench = benchmark.resolve_benchmark(item.action_code, peer_percentiles=peer_percentiles)
        adjusted = evaluation.success_rate * evaluation.confidence_weight * bench.modifier
        scored.append(
            ActionScore(
                action_code=item.action_code,
                applied_count=item.applied_count,
                improved_count=item.improved_count,
                success_rate=evaluation.success_rate,
                confidence_weight=evaluation.confidence_weight,
                effect_strength=evaluation.effect_strength,
                benchmark_modifier=bench.modifier,
                adjusted_score=adjusted,
                benchmark_comparison=bench.comparison,
            )
        )

    ranked = sorted(scored, key=lambda score: (-score.adjusted_score, score.action_code))
    return [
        ActionScore(
            **{
                **score.__dict__,
                "rank": index + 1,
            }
        )
        for index, score in enumerate(ranked)
    ]


__all__ = ["ActionScore", "score_actions"]
