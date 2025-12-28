from __future__ import annotations

from .model_registry import model_registry
from .providers.local_llm import local_tx_score
from .schemas import (
    ExplainFeature,
    ExplainPayload,
    ModelType,
    RiskCategory,
    RiskScoreRequest,
    RiskScoreResponse,
    ScoreRequest,
    ScoreResponse,
)


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


class RiskScoreModelProvider:
    def score(self, payload: RiskScoreRequest) -> RiskScoreResponse:
        model_info = model_registry.get(ModelType.RISK_SCORE) or model_registry.train(ModelType.RISK_SCORE)
        contributions = self._score_contributions(payload)
        risk_score = int(min(100, max(0, round(sum(contributions.values()), 0))))
        risk_category = self._category_from_score(risk_score)
        decision = self._decision_from_score(risk_score)
        explain = self._build_explain(payload, contributions, decision)
        return RiskScoreResponse(
            risk_score=risk_score,
            risk_category=risk_category,
            decision=decision,
            model_version=model_info.version,
            explain=explain,
        )

    def _score_contributions(self, payload: RiskScoreRequest) -> dict[str, float]:
        contributions: dict[str, float] = {}
        amount = payload.amount
        if amount >= 100_000:
            contributions["transaction_amount"] = 35.0
        elif amount >= 50_000:
            contributions["transaction_amount"] = 25.0
        elif amount >= 10_000:
            contributions["transaction_amount"] = 15.0
        else:
            contributions["transaction_amount"] = 5.0

        if payload.client_score is not None:
            contributions["client_score"] = (1 - payload.client_score) * 30
        else:
            contributions["client_score"] = 15.0

        doc_weight = {"invoice": 5.0, "payout": 15.0, "credit_note": 10.0}[payload.document_type]
        contributions["document_type"] = doc_weight

        status = (payload.client_status or "").lower()
        if status in {"blocked", "suspended"}:
            contributions["client_status"] = 25.0
        elif status in {"new", "trial"}:
            contributions["client_status"] = 10.0
        elif status:
            contributions["client_status"] = 2.0
        else:
            contributions["client_status"] = 6.0

        history = payload.history
        if history:
            if history.chargebacks:
                contributions["chargebacks"] = min(20.0, history.chargebacks * 5.0)
            else:
                contributions["chargebacks"] = 0.0
            if history.operations_count_30d and history.operations_count_30d > 20:
                contributions["operations_count_30d"] = 10.0
            else:
                contributions["operations_count_30d"] = 3.0
            if history.avg_amount_30d and history.avg_amount_30d > 50_000:
                contributions["avg_amount_30d"] = 10.0
            else:
                contributions["avg_amount_30d"] = 2.0
        else:
            contributions["chargebacks"] = 4.0
            contributions["operations_count_30d"] = 4.0
            contributions["avg_amount_30d"] = 4.0

        return contributions

    @staticmethod
    def _category_from_score(score: int) -> RiskCategory:
        if score < 40:
            return RiskCategory.LOW
        if score < 70:
            return RiskCategory.MEDIUM
        return RiskCategory.HIGH

    @staticmethod
    def _decision_from_score(score: int) -> str:
        if score >= 75:
            return "DECLINE"
        if score >= 50:
            return "MANUAL_REVIEW"
        return "ALLOW"

    def _build_explain(
        self,
        payload: RiskScoreRequest,
        contributions: dict[str, float],
        decision: str,
    ) -> ExplainPayload:
        features = [
            ExplainFeature(feature="transaction_amount", value=payload.amount, shap_value=self._shap(contributions)),
            ExplainFeature(
                feature="client_score",
                value=payload.client_score if payload.client_score is not None else "unknown",
                shap_value=self._shap(contributions, key="client_score"),
            ),
            ExplainFeature(
                feature="document_type",
                value=payload.document_type,
                shap_value=self._shap(contributions, key="document_type"),
            ),
            ExplainFeature(
                feature="client_status",
                value=payload.client_status or "unknown",
                shap_value=self._shap(contributions, key="client_status"),
            ),
        ]
        history = payload.history
        features.extend(
            [
                ExplainFeature(
                    feature="chargebacks",
                    value=history.chargebacks if history else None,
                    shap_value=self._shap(contributions, key="chargebacks"),
                ),
                ExplainFeature(
                    feature="operations_count_30d",
                    value=history.operations_count_30d if history else None,
                    shap_value=self._shap(contributions, key="operations_count_30d"),
                ),
                ExplainFeature(
                    feature="avg_amount_30d",
                    value=history.avg_amount_30d if history else None,
                    shap_value=self._shap(contributions, key="avg_amount_30d"),
                ),
            ]
        )

        reason = "Risk score exceeds threshold" if decision == "DECLINE" else "Risk score within policy thresholds"
        return ExplainPayload(features=features, reason=reason)

    @staticmethod
    def _shap(contributions: dict[str, float], key: str = "transaction_amount") -> float:
        value = contributions.get(key, 0.0)
        return round(-value / 100, 2)
