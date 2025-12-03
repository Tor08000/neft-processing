from __future__ import annotations

from .providers.local_llm import local_tx_score
from .schemas import ScoreRequest, ScoreResponse


class ScoreModelProvider:
    """Простейший провайдер скоринга с возможностью замены."""

    def score(self, payload: ScoreRequest) -> ScoreResponse:
        features = payload.model_dump()
        result = local_tx_score(features)
        score = float(result.get("score", 0.0))
        reasons = result.get("reasons") or []
        decision = self._decision_from_score(score)
        reason_text = ",".join(reasons) if reasons else decision.upper()
        return ScoreResponse(score=score, decision=decision, reason=reason_text, reasons=reasons)

    @staticmethod
    def _decision_from_score(score: float) -> str:
        if score < 0.5:
            return "allow"
        if score < 0.75:
            return "review"
        return "deny"
