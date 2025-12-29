from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.services.decision_memory import defaults as memory_defaults
from app.services.decision_memory.cooldown import CooldownStatus
from app.services.decision_memory.stats import DecisionActionStats
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
    cooldown: bool = False
    cooldown_reason: str | None = None
    memory_success_rate: float | None = None
    memory_sample_size: int | None = None
    memory_window_days: int | None = None
    low_confidence: bool = False
    rank: int = 0


def score_actions(
    stats: list[evaluator.ActionEffectStats],
    *,
    peer_percentiles: dict[str, float] | None = None,
    now: datetime | None = None,
    cooldowns: dict[str, CooldownStatus] | None = None,
    memory_stats: dict[str, DecisionActionStats] | None = None,
) -> list[ActionScore]:
    scored: list[ActionScore] = []
    for item in stats:
        evaluation = evaluator.evaluate_action(item, now=now)
        bench = benchmark.resolve_benchmark(item.action_code, peer_percentiles=peer_percentiles)
        cooldown_status = cooldowns.get(item.action_code) if cooldowns else None
        cooldown_active = bool(cooldown_status and cooldown_status.cooldown)
        memory = memory_stats.get(item.action_code) if memory_stats else None
        sample_size = memory.applied_count if memory else item.applied_count
        low_confidence = sample_size < memory_defaults.MIN_SAMPLE_SIZE
        adjusted = evaluation.success_rate * evaluation.confidence_weight * bench.modifier
        if cooldown_active:
            adjusted += memory_defaults.COOLDOWN_PENALTY
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
                cooldown=cooldown_active,
                cooldown_reason=cooldown_status.reason if cooldown_status else None,
                memory_success_rate=memory.success_rate if memory else None,
                memory_sample_size=memory.applied_count if memory else None,
                memory_window_days=memory.window_days if memory else None,
                low_confidence=low_confidence,
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
