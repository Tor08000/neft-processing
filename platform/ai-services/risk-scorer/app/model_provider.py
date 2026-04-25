from __future__ import annotations

import hashlib
import json
from typing import Any

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


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_stable_value(item) for item in value]
    if isinstance(value, tuple):
        return [_stable_value(item) for item in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def _stable_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(
        _stable_value(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ScoreModelProvider:
    """Простейший провайдер скоринга с возможностью замены."""

    def score(self, payload: ScoreRequest) -> ScoreResponse:
        features = payload.model_dump(mode="json")
        result = local_tx_score(features)
        if "score" not in result:
            raise ValueError("heuristic_score_missing")
        score = float(result["score"])
        reasons = result.get("reasons") or []
        decision = self._decision_from_score(score)
        reason_text = ",".join(reasons) if reasons else decision.upper()
        assumptions = ["heuristic_local_rules", "provider_not_ml"]
        trace_payload = {
            "provider": "local_heuristic",
            "score_source": "heuristic",
            "model_version": "local-heuristic-v1",
            "formula_version": "heuristic_local_rules_v1",
            "input_hash": _stable_hash(features),
            "feature_keys": sorted(features.keys()),
            "result": {
                "score": score,
                "decision": decision,
                "reasons": reasons,
            },
            "assumptions": assumptions,
        }
        trace = {**trace_payload, "trace_hash": _stable_hash(trace_payload)}
        return ScoreResponse(
            score=score,
            decision=decision,
            reason=reason_text,
            reasons=reasons,
            provider="local_heuristic",
            score_source="heuristic",
            degraded=False,
            assumptions=assumptions,
            trace=trace,
        )

    @staticmethod
    def _decision_from_score(score: float) -> str:
        if score < 0.5:
            return "allow"
        if score < 0.75:
            return "review"
        return "deny"


class RiskScoreModelProvider:
    def score(self, payload: RiskScoreRequest) -> RiskScoreResponse:
        model_info = model_registry.get(ModelType.RISK_SCORE)
        model_version = model_info.version if model_info else "heuristic-risk-score-v1"
        contributions, assumptions = self._score_contributions(payload)
        risk_score = int(min(100, max(0, round(sum(contributions.values()), 0))))
        risk_category = self._category_from_score(risk_score)
        decision = self._decision_from_score(risk_score)
        explain = self._build_explain(
            payload,
            contributions,
            decision,
            assumptions,
            risk_score=risk_score,
            risk_category=risk_category,
            model_version=model_version,
        )
        return RiskScoreResponse(
            risk_score=risk_score,
            risk_category=risk_category,
            decision=decision,
            model_version=model_version,
            model_source="heuristic_rules",
            degraded=False,
            assumptions=assumptions,
            explain=explain,
        )

    def _score_contributions(self, payload: RiskScoreRequest) -> tuple[dict[str, float], list[str]]:
        contributions: dict[str, float] = {}
        assumptions: list[str] = ["heuristic_ruleset_v1"]
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
            assumptions.append("client_score_missing_assumed_neutral")

        doc_weight = {
            "invoice": 5.0,
            "payout": 15.0,
            "credit_note": 10.0,
            "payment": 8.0,
            "document": 6.0,
            "export": 12.0,
            "fuel_transaction": 9.0,
        }[payload.document_type]
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
            assumptions.append("client_status_missing_assumed_unknown")

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
            assumptions.append("history_missing_assumed_sparse")

        return contributions, assumptions

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
        assumptions: list[str],
        *,
        risk_score: int,
        risk_category: RiskCategory,
        model_version: str,
    ) -> ExplainPayload:
        features = [
            ExplainFeature(
                feature="transaction_amount",
                value=payload.amount,
                shap_value=self._shap(contributions),
                contribution=contributions.get("transaction_amount"),
            ),
            ExplainFeature(
                feature="client_score",
                value=payload.client_score if payload.client_score is not None else "unknown",
                shap_value=self._shap(contributions, key="client_score"),
                contribution=contributions.get("client_score"),
            ),
            ExplainFeature(
                feature="document_type",
                value=payload.document_type,
                shap_value=self._shap(contributions, key="document_type"),
                contribution=contributions.get("document_type"),
            ),
            ExplainFeature(
                feature="client_status",
                value=payload.client_status or "unknown",
                shap_value=self._shap(contributions, key="client_status"),
                contribution=contributions.get("client_status"),
            ),
        ]
        history = payload.history
        features.extend(
            [
                ExplainFeature(
                    feature="chargebacks",
                    value=history.chargebacks if history else None,
                    shap_value=self._shap(contributions, key="chargebacks"),
                    contribution=contributions.get("chargebacks"),
                ),
                ExplainFeature(
                    feature="operations_count_30d",
                    value=history.operations_count_30d if history else None,
                    shap_value=self._shap(contributions, key="operations_count_30d"),
                    contribution=contributions.get("operations_count_30d"),
                ),
                ExplainFeature(
                    feature="avg_amount_30d",
                    value=history.avg_amount_30d if history else None,
                    shap_value=self._shap(contributions, key="avg_amount_30d"),
                    contribution=contributions.get("avg_amount_30d"),
                ),
            ]
        )

        reason = "Risk score exceeds threshold" if decision == "DECLINE" else "Risk score within policy thresholds"
        trace_payload = self._decision_trace(
            payload=payload,
            contributions=contributions,
            assumptions=assumptions,
            risk_score=risk_score,
            risk_category=risk_category,
            decision=decision,
            model_version=model_version,
        )
        return ExplainPayload(
            features=features,
            reason=reason,
            source="heuristic_rules",
            assumptions=assumptions,
            score_breakdown=contributions,
            trace=trace_payload,
            trace_hash=_stable_hash(trace_payload),
        )

    @staticmethod
    def _shap(contributions: dict[str, float], key: str = "transaction_amount") -> float:
        value = contributions.get(key, 0.0)
        return round(-value / 100, 2)

    def _decision_trace(
        self,
        *,
        payload: RiskScoreRequest,
        contributions: dict[str, float],
        assumptions: list[str],
        risk_score: int,
        risk_category: RiskCategory,
        decision: str,
        model_version: str,
    ) -> dict[str, Any]:
        history = payload.history
        feature_values = {
            "amount": payload.amount,
            "client_score": payload.client_score,
            "document_type": payload.document_type,
            "client_status": payload.client_status or "unknown",
            "history": history.model_dump(mode="json") if history else None,
        }
        return {
            "provider": "risk-scorer",
            "model_source": "heuristic_rules",
            "model_version": model_version,
            "formula_version": "heuristic_ruleset_v1",
            "input_hash": _stable_hash(payload.model_dump(mode="json")),
            "metadata_keys": sorted((payload.metadata or {}).keys()),
            "feature_values": feature_values,
            "score_breakdown": {key: round(value, 6) for key, value in sorted(contributions.items())},
            "thresholds": {
                "category_low_lt": 40,
                "category_high_gte": 70,
                "manual_review_gte": 50,
                "decline_gte": 75,
            },
            "result": {
                "risk_score": risk_score,
                "risk_category": risk_category.value,
                "decision": decision,
            },
            "assumptions": list(assumptions),
        }
