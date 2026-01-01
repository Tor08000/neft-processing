from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.operation import Operation, OperationStatus, RiskResult
from app.schemas.explain_v2 import (
    ExplainActionCatalogItem,
    ExplainDecision,
    ExplainDocument,
    ExplainEvidence,
    ExplainReasonNode,
    ExplainRecommendedAction,
    ExplainScoreBand,
    ExplainV2Response,
)


def build_explain_for_operation(
    db: Session,
    *,
    operation_id: str,
    tenant_id: int,
) -> ExplainV2Response:
    operation = db.query(Operation).filter(Operation.operation_id == operation_id).first()
    if not operation:
        raise ValueError("operation_not_found")
    risk_payload = operation.risk_payload if isinstance(operation.risk_payload, dict) else {}
    decision_payload = _extract_risk_explain(risk_payload)
    decision = _resolve_decision(operation, decision_payload)
    score = operation.risk_score if operation.risk_score is not None else decision_payload.get("score")
    score_band = _resolve_score_band(operation.risk_result, decision_payload)
    factors = _extract_factors(decision_payload, operation.reason)
    reason_tree, evidence = _build_reason_tree_with_evidence(decision, factors)
    return ExplainV2Response(
        kind="operation",
        id=str(operation.operation_id),
        decision=decision,
        score=int(score) if score is not None else None,
        score_band=score_band,
        policy_snapshot=_extract_policy_snapshot(decision_payload),
        generated_at=datetime.now(timezone.utc),
        reason_tree=reason_tree,
        evidence=evidence,
        documents=[],
        recommended_actions=_recommend_actions(decision),
    )


def build_explain_for_invoice(
    db: Session,
    *,
    invoice_id: str,
    tenant_id: int,
) -> ExplainV2Response:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("invoice_not_found")
    reason_tree, evidence = _build_reason_tree_with_evidence(
        "REVIEW",
        [
            "Проверить статус оплаты и документы",
            "Сравнить сумму с ожидаемым уровнем",
        ],
    )
    return ExplainV2Response(
        kind="invoice",
        id=str(invoice.id),
        decision="REVIEW",
        score=None,
        score_band="review",
        policy_snapshot=None,
        generated_at=datetime.now(timezone.utc),
        reason_tree=reason_tree,
        evidence=evidence,
        documents=[],
        recommended_actions=_recommend_actions("REVIEW"),
    )


def build_explain_for_marketplace_order(
    *,
    order_id: str,
    tenant_id: int,
) -> ExplainV2Response:
    reason_tree, evidence = _build_reason_tree_with_evidence(
        "REVIEW",
        [
            "Подтвердить статус заказа у партнера",
            "Сверить историю статусов и документов",
        ],
    )
    return ExplainV2Response(
        kind="marketplace_order",
        id=str(order_id),
        decision="REVIEW",
        score=None,
        score_band="review",
        policy_snapshot=None,
        generated_at=datetime.now(timezone.utc),
        reason_tree=reason_tree,
        evidence=evidence,
        documents=[],
        recommended_actions=_recommend_actions("REVIEW"),
    )


def build_explain_for_kpi(
    *,
    kpi_key: str,
    window_days: int,
    tenant_id: int,
) -> ExplainV2Response:
    title = f"Показатель {kpi_key} за {window_days} дней"
    reason_tree = ExplainReasonNode(
        id="root",
        title=title,
        weight=1.0,
        children=[
            ExplainReasonNode(
                id="metric_variance",
                title="Изменение относительно предыдущего периода",
                weight=0.4,
                evidence_refs=["ev_kpi_delta"],
            ),
            ExplainReasonNode(
                id="metric_level",
                title="Текущее значение и целевой уровень",
                weight=0.25,
                evidence_refs=["ev_kpi_value"],
            ),
        ],
    )
    evidence = [
        ExplainEvidence(
            id="ev_kpi_delta",
            type="metric",
            label="Сравнение с предыдущим периодом",
            value={"window_days": window_days},
            source="kpi_summary",
            confidence=0.6,
        ),
        ExplainEvidence(
            id="ev_kpi_value",
            type="metric",
            label="Значение KPI",
            value={"kpi_key": kpi_key},
            source="kpi_summary",
            confidence=0.6,
        ),
    ]
    return ExplainV2Response(
        kind="kpi",
        id=kpi_key,
        decision="REVIEW",
        score=None,
        score_band="review",
        policy_snapshot=None,
        generated_at=datetime.now(timezone.utc),
        reason_tree=reason_tree,
        evidence=evidence,
        documents=[],
        recommended_actions=_recommend_actions("REVIEW"),
    )


def list_actions_catalog(kind: str) -> list[ExplainActionCatalogItem]:
    if kind == "kpi":
        return []
    return [
        ExplainActionCatalogItem(
            action_code="REQUEST_DOCS",
            label="Запросить документы",
            description="Помогает подтвердить контекст и снизить неопределенность.",
            risk_hint="Снижает риск ложного отказа",
            side_effects="Увеличивает время обработки",
        ),
        ExplainActionCatalogItem(
            action_code="MANUAL_REVIEW",
            label="Передать на ручную проверку",
            description="Ручная проверка снижает риск ошибок модели.",
            risk_hint="Снижает риск за счет ручной проверки",
            side_effects="Увеличивает затраты на обработку",
        ),
        ExplainActionCatalogItem(
            action_code="ADJUST_LIMITS",
            label="Скорректировать лимиты",
            description="Подходит если лимиты слишком строгие.",
            risk_hint="Риск может снизиться при корректных лимитах",
            side_effects="Требует согласования лимитов",
        ),
    ]


def _extract_risk_explain(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}
    decision_engine = payload.get("decision_engine")
    if isinstance(decision_engine, dict):
        explain_payload = decision_engine.get("explain")
        if isinstance(explain_payload, dict):
            return explain_payload
    decision_payload = payload.get("decision")
    if isinstance(decision_payload, dict):
        return decision_payload
    return {}


def _resolve_decision(operation: Operation, decision_payload: dict) -> ExplainDecision:
    decision = decision_payload.get("decision") or decision_payload.get("outcome")
    if isinstance(decision, str):
        normalized = decision.upper()
        if normalized in {"ALLOW", "APPROVE", "AUTHORIZED"}:
            return "APPROVE"
        if normalized in {"DECLINE", "BLOCK"}:
            return "DECLINE"
        if normalized in {"MANUAL_REVIEW", "REVIEW"}:
            return "REVIEW"
    if operation.status == OperationStatus.DECLINED:
        return "DECLINE"
    if operation.status == OperationStatus.AUTHORIZED:
        return "APPROVE"
    return "REVIEW"


def _resolve_score_band(risk_result: RiskResult | None, decision_payload: dict) -> ExplainScoreBand | None:
    if risk_result:
        mapping = {
            RiskResult.LOW: "low",
            RiskResult.MEDIUM: "medium",
            RiskResult.HIGH: "high",
            RiskResult.BLOCK: "block",
            RiskResult.MANUAL_REVIEW: "review",
        }
        return mapping.get(risk_result)
    band = decision_payload.get("risk_level") or decision_payload.get("score_band")
    if isinstance(band, str):
        normalized = band.lower()
        if normalized in {"low", "medium", "high", "block", "review"}:
            return normalized
    return None


def _extract_factors(decision_payload: dict, fallback_reason: str | None) -> list[str]:
    factors = decision_payload.get("factors")
    if isinstance(factors, list):
        resolved = [str(item) for item in factors if item]
        if resolved:
            return resolved[:3]
    reason_codes = decision_payload.get("reason_codes")
    if isinstance(reason_codes, list):
        resolved = [str(item) for item in reason_codes if item]
        if resolved:
            return resolved[:3]
    if fallback_reason:
        return [fallback_reason]
    return ["Недостаточно данных для детального объяснения"]


def _build_reason_tree_with_evidence(
    decision: ExplainDecision,
    factors: Iterable[str],
) -> tuple[ExplainReasonNode, list[ExplainEvidence]]:
    children: list[ExplainReasonNode] = []
    evidence: list[ExplainEvidence] = []
    weights = _build_weights(list(factors))
    for index, (factor, weight) in enumerate(zip(factors, weights)):
        evidence_id = f"ev_factor_{index + 1}"
        children.append(
            ExplainReasonNode(
                id=f"reason_{index + 1}",
                title=factor,
                weight=weight,
                evidence_refs=[evidence_id],
            )
        )
        evidence.append(
            ExplainEvidence(
                id=evidence_id,
                type="rule",
                label=factor,
                value=None,
                source="risk_engine",
                confidence=0.7,
            )
        )
    root = ExplainReasonNode(
        id="root",
        title=decision.title(),
        weight=1.0,
        children=children,
    )
    return root, evidence


def _build_weights(factors: list[str]) -> list[float]:
    if not factors:
        return []
    base = 0.5
    step = 0.15
    weights = []
    for idx in range(len(factors)):
        weight = max(0.05, base - (idx * step))
        weights.append(round(weight, 2))
    return weights


def _extract_policy_snapshot(decision_payload: dict) -> str | None:
    policy = decision_payload.get("policy_id") or decision_payload.get("policy")
    return str(policy) if policy else None


def _recommend_actions(decision: ExplainDecision) -> list[ExplainRecommendedAction]:
    if decision == "DECLINE":
        return [
            ExplainRecommendedAction(
                action_code="REQUEST_DOCS",
                title="Запросить документы",
                description="Снизит неопределенность и риск ложного отказа.",
                expected_effect="risk_down",
                priority="high",
            )
        ]
    if decision == "APPROVE":
        return [
            ExplainRecommendedAction(
                action_code="MONITOR",
                title="Продолжить мониторинг",
                description="Следить за дальнейшими сигналами без изменений.",
                expected_effect="risk_neutral",
                priority="low",
            )
        ]
    return [
        ExplainRecommendedAction(
            action_code="MANUAL_REVIEW",
            title="Передать на ручную проверку",
            description="Уточнить детали и принять решение.",
            expected_effect="risk_down",
            priority="medium",
        )
    ]
