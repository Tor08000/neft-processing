from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DecisionOutcome = Literal["ALLOW", "DECLINE", "MANUAL_REVIEW"]


@dataclass(frozen=True)
class DecisionResult:
    decision_id: str
    decision_version: str
    outcome: DecisionOutcome
    risk_score: int | None
    rule_hits: list[str]
    model_version: str | None
    explain: dict
