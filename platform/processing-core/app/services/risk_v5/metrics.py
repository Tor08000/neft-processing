from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class RiskV5Metrics:
    score_distribution: Counter[str] = field(default_factory=Counter)
    predicted_outcomes: Counter[str] = field(default_factory=Counter)
    disagreement_total: int = 0
    total: int = 0
    scored_total: int = 0
    label_total: int = 0
    label_available: int = 0

    def observe_score(self, score: int | None) -> None:
        if score is None:
            return
        self.scored_total += 1
        bucket = _score_bucket(score)
        self.score_distribution[bucket] += 1

    def observe_predicted(self, predicted: str | None) -> None:
        if predicted is None:
            return
        self.predicted_outcomes[predicted] += 1

    def observe_decision(self, *, v4_outcome: str, v5_outcome: str | None) -> None:
        self.total += 1
        if v5_outcome and v5_outcome != v4_outcome:
            self.disagreement_total += 1

    def observe_label(self, available: bool) -> None:
        self.label_total += 1
        if available:
            self.label_available += 1

    def reset(self) -> None:
        self.score_distribution.clear()
        self.predicted_outcomes.clear()
        self.disagreement_total = 0
        self.total = 0
        self.scored_total = 0
        self.label_total = 0
        self.label_available = 0


def _score_bucket(score: int) -> str:
    if score < 20:
        return "0-19"
    if score < 50:
        return "20-49"
    if score < 80:
        return "50-79"
    return "80-100"


metrics = RiskV5Metrics()

__all__ = ["RiskV5Metrics", "metrics"]
