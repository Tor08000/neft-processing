from __future__ import annotations

from dataclasses import dataclass

from app.services.fleet_decision_choice import defaults


@dataclass(frozen=True)
class BenchmarkResult:
    modifier: float
    comparison: str | None
    percentile: float | None


def resolve_benchmark(
    action_code: str,
    *,
    peer_percentiles: dict[str, float] | None,
) -> BenchmarkResult:
    if not peer_percentiles or action_code not in peer_percentiles:
        return BenchmarkResult(modifier=1.0, comparison=None, percentile=None)
    percentile = peer_percentiles[action_code]
    modifier = _modifier_for_percentile(percentile)
    comparison = _comparison_text(percentile)
    return BenchmarkResult(modifier=modifier, comparison=comparison, percentile=percentile)


def _modifier_for_percentile(percentile: float) -> float:
    if percentile >= defaults.BENCHMARK_BONUS_THRESHOLD:
        return defaults.BENCHMARK_BONUS_MULTIPLIER
    if percentile <= defaults.BENCHMARK_PENALTY_THRESHOLD:
        return defaults.BENCHMARK_PENALTY_MULTIPLIER
    return 1.0


def _comparison_text(percentile: float) -> str:
    percentile_pct = round(percentile * 100)
    return f"Эффективнее, чем у {percentile_pct}% сопоставимых парков"


__all__ = ["BenchmarkResult", "resolve_benchmark"]
