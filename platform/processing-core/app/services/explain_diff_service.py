from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.schemas.explain_diff import (
    ExplainDiffDecision,
    ExplainDiffEvidence,
    ExplainDiffPayload,
    ExplainDiffReason,
    ExplainDiffReasonDelta,
    ExplainDiffResponse,
    ExplainDiffRisk,
    ExplainDiffRiskLabel,
    ExplainDiffSnapshot,
)
from app.schemas.explain_v2 import ExplainV2Response
from app.services.explain_v2_service import (
    build_explain_for_invoice,
    build_explain_for_kpi,
    build_explain_for_marketplace_order,
    build_explain_for_operation,
)


def build_explain_diff(
    db: Session,
    *,
    kind: str,
    context_id: str,
    actions: list[str],
    tenant_id: int,
    is_admin: bool,
) -> ExplainDiffResponse:
    before_explain = _load_before(db, context=_ExplainDiffContext(kind=kind, id=context_id), tenant_id=tenant_id)
    before_snapshot = _snapshot_from_explain(before_explain)
    after_snapshot = _apply_actions(before_snapshot, actions)
    diff = _build_diff(before_snapshot, after_snapshot)
    meta = {
        "simulation": True,
        "confidence": 0.78 if is_admin else None,
        "memory_penalty": "LOW" if is_admin else None,
    }
    return ExplainDiffResponse(before=before_snapshot, after=after_snapshot, diff=diff, meta=meta)


@dataclass
class _ExplainDiffContext:
    kind: str
    id: str


def _load_before(db: Session, *, context: _ExplainDiffContext, tenant_id: int) -> ExplainV2Response:
    if context.kind == "operation":
        return build_explain_for_operation(db, operation_id=context.id, tenant_id=tenant_id)
    if context.kind == "invoice":
        return build_explain_for_invoice(db, invoice_id=context.id, tenant_id=tenant_id)
    if context.kind == "order":
        return build_explain_for_marketplace_order(order_id=context.id, tenant_id=tenant_id)
    if context.kind == "kpi":
        return build_explain_for_kpi(kpi_key=context.id, window_days=7, tenant_id=tenant_id)
    raise ValueError("unsupported_kind")


def _snapshot_from_explain(explain: ExplainV2Response) -> ExplainDiffSnapshot:
    reasons = _flatten_reasons(explain)
    evidence = [
        ExplainDiffEvidence(
            id=item.id,
            label=item.label,
            type=item.type,
            source=item.source,
            confidence=item.confidence,
        )
        for item in explain.evidence
    ]
    risk_score = _normalize_score(explain.score)
    if risk_score is None:
        risk_score = 0.5
    return ExplainDiffSnapshot(
        risk_score=risk_score,
        decision=explain.decision,
        reasons=reasons,
        evidence=evidence,
    )


def _flatten_reasons(explain: ExplainV2Response) -> list[ExplainDiffReason]:
    if not explain.reason_tree:
        return []
    reasons: list[ExplainDiffReason] = []
    stack = list(explain.reason_tree.children)
    while stack:
        node = stack.pop(0)
        reasons.append(ExplainDiffReason(code=node.id, title=node.title, weight=node.weight))
        stack.extend(node.children or [])
    return reasons


def _normalize_score(score: int | None) -> float | None:
    if score is None:
        return None
    if score > 1:
        return min(max(score / 100, 0), 1)
    return min(max(float(score), 0), 1)


def _apply_actions(snapshot: ExplainDiffSnapshot, actions: list[str]) -> ExplainDiffSnapshot:
    reasons = [ExplainDiffReason(**reason.model_dump()) for reason in snapshot.reasons]
    evidence = [ExplainDiffEvidence(**item.model_dump()) for item in snapshot.evidence]
    risk_score = snapshot.risk_score if snapshot.risk_score is not None else 0.5

    for action in actions:
        code = action.upper()
        if "REQUEST_DOCS" in code:
            if reasons:
                removed = reasons.pop(0)
                evidence = [item for item in evidence if item.label != removed.title]
            risk_score = max(0.0, risk_score - 0.15)
        elif "MANUAL_REVIEW" in code:
            if reasons:
                reasons[0].weight = max(0.0, (reasons[0].weight or 0) - 0.1)
            risk_score = max(0.0, risk_score - 0.05)
        elif "ADJUST_LIMITS" in code:
            reasons.append(ExplainDiffReason(code="LIMITS_ADJUSTED", title="Скорректированы лимиты", weight=0.2))
            evidence.append(
                ExplainDiffEvidence(id="ev_limits_adjusted", label="Limits adjusted", type="rule", source="risk")
            )
            risk_score = min(1.0, risk_score + 0.08)
        elif "BLOCK" in code:
            reasons.append(ExplainDiffReason(code="MANUAL_BLOCK", title="Ручная блокировка", weight=0.3))
            evidence.append(
                ExplainDiffEvidence(id="ev_manual_block", label="Manual block", type="event", source="audit")
            )
            risk_score = min(1.0, risk_score + 0.12)

    decision = _decision_from_score(risk_score)
    return ExplainDiffSnapshot(
        risk_score=risk_score,
        decision=decision,
        reasons=reasons,
        evidence=evidence,
    )


def _decision_from_score(score: float) -> ExplainDiffDecision:
    if score >= 0.7:
        return "DECLINE"
    if score >= 0.5:
        return "REVIEW"
    return "APPROVE"


def _build_diff(before: ExplainDiffSnapshot, after: ExplainDiffSnapshot) -> ExplainDiffPayload:
    before_map = {reason.code: reason for reason in before.reasons}
    after_map = {reason.code: reason for reason in after.reasons}
    removed = [code for code in before_map.keys() if code not in after_map]
    added = [code for code in after_map.keys() if code not in before_map]
    weakened: list[ExplainDiffReasonDelta] = []
    strengthened: list[ExplainDiffReasonDelta] = []
    for code in before_map.keys() & after_map.keys():
        before_weight = before_map[code].weight or 0
        after_weight = after_map[code].weight or 0
        delta = round(after_weight - before_weight, 3)
        if delta <= -0.05:
            weakened.append(ExplainDiffReasonDelta(code=code, delta=delta))
        elif delta >= 0.05:
            strengthened.append(ExplainDiffReasonDelta(code=code, delta=delta))

    before_evidence_ids = {item.id for item in before.evidence}
    after_evidence_ids = {item.id for item in after.evidence}
    evidence_removed = sorted(before_evidence_ids - after_evidence_ids)
    evidence_added = sorted(after_evidence_ids - before_evidence_ids)

    before_score = before.risk_score if before.risk_score is not None else 0.5
    after_score = after.risk_score if after.risk_score is not None else 0.5
    risk_delta = round(after_score - before_score, 3)
    if risk_delta < 0:
        label: ExplainDiffRiskLabel = "IMPROVED"
    elif risk_delta > 0:
        label = "WORSENED"
    else:
        label = "NO_CHANGE"

    return ExplainDiffPayload(
        risk=ExplainDiffRisk(delta=risk_delta, label=label),
        reasons={
            "removed": removed,
            "weakened": weakened,
            "strengthened": strengthened,
            "added": added,
        },
        evidence={"removed": evidence_removed, "added": evidence_added},
    )


__all__ = ["build_explain_diff"]
