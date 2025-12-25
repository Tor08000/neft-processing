from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence, TYPE_CHECKING

from app.models.risk_score import RiskScore, RiskScoreAction

if TYPE_CHECKING:
    from app.services.decision.rules.scoring_rules import Rule


@dataclass
class DecisionContext:
    tenant_id: int
    client_id: str
    amount: float | int | None
    action: RiskScoreAction
    scoring_rules: Sequence["Rule"] = field(default_factory=list)
    risk_score: RiskScore | None = None
    age: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
