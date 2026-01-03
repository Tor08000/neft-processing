from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_contracts import Contract, ContractObligation
from app.models.marketplace_order_sla import (
    MarketplaceOrderContractLink,
    MarketplaceOrderEvent,
    OrderSlaEvaluation,
    OrderSlaSeverity,
    OrderSlaStatus,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.decision_memory.records import record_decision_memory
from app.services.marketplace_contract_binding_service import bind_contract_for_order


ORDER_EVENT_TYPES = {
    "MARKETPLACE_ORDER_CREATED",
    "MARKETPLACE_ORDER_CONFIRMED_BY_PARTNER",
    "MARKETPLACE_ORDER_STARTED",
    "MARKETPLACE_ORDER_COMPLETED",
    "MARKETPLACE_ORDER_FAILED",
}


@dataclass(frozen=True)
class OrderSlaEvaluationSummary:
    evaluations: list[OrderSlaEvaluation]
    violations: list[OrderSlaEvaluation]


def _normalize_metric(metric: str) -> str:
    return (metric or "").strip().lower()


def _first_event_time(events: list[MarketplaceOrderEvent], event_types: set[str]) -> datetime | None:
    for event in events:
        if event.event_type in event_types:
            return event.occurred_at
    return None


def _minutes_delta(start: datetime, end: datetime) -> Decimal:
    return Decimal(str((end - start).total_seconds() / 60))


def _compare(value: Decimal, threshold: Decimal, comparison: str) -> bool:
    if comparison == "<=":
        return value <= threshold
    if comparison == ">=":
        return value >= threshold
    raise ValueError("unsupported_comparison")


def _severity_for_violation(value: Decimal, threshold: Decimal) -> OrderSlaSeverity:
    if threshold <= 0:
        return OrderSlaSeverity.HIGH
    delta_ratio = (value - threshold) / threshold
    if delta_ratio >= Decimal("0.5"):
        return OrderSlaSeverity.CRITICAL
    if delta_ratio >= Decimal("0.2"):
        return OrderSlaSeverity.HIGH
    if delta_ratio >= Decimal("0.1"):
        return OrderSlaSeverity.MEDIUM
    return OrderSlaSeverity.LOW


def _resolve_contract_id(
    db: Session,
    *,
    order_id: str,
    client_id: str | None,
    partner_id: str | None,
    request_ctx: RequestContext | None,
) -> str | None:
    link = (
        db.query(MarketplaceOrderContractLink)
        .filter(MarketplaceOrderContractLink.order_id == order_id)
        .one_or_none()
    )
    if link:
        return str(link.contract_id)
    return bind_contract_for_order(
        db,
        order_id=order_id,
        client_id=client_id,
        partner_id=partner_id,
        request_ctx=request_ctx,
    )


def _evaluate_response_time(events: list[MarketplaceOrderEvent]) -> tuple[Decimal, datetime, datetime] | None:
    created_at = _first_event_time(events, {"MARKETPLACE_ORDER_CREATED"})
    accepted_at = _first_event_time(events, {"MARKETPLACE_ORDER_CONFIRMED_BY_PARTNER"})
    started_at = _first_event_time(events, {"MARKETPLACE_ORDER_STARTED"})
    end_at = accepted_at or started_at
    if not created_at or not end_at:
        return None
    return _minutes_delta(created_at, end_at), created_at, end_at


def _evaluate_completion_time(events: list[MarketplaceOrderEvent]) -> tuple[Decimal, datetime, datetime] | None:
    started_at = _first_event_time(events, {"MARKETPLACE_ORDER_STARTED"})
    completed_at = _first_event_time(events, {"MARKETPLACE_ORDER_COMPLETED"})
    if not started_at or not completed_at:
        return None
    return _minutes_delta(started_at, completed_at), started_at, completed_at


def evaluate_order_event(
    db: Session,
    *,
    order_event_id: str,
    request_ctx: RequestContext | None = None,
) -> OrderSlaEvaluationSummary:
    event = db.query(MarketplaceOrderEvent).filter(MarketplaceOrderEvent.id == order_event_id).one_or_none()
    if not event or event.event_type not in ORDER_EVENT_TYPES:
        return OrderSlaEvaluationSummary(evaluations=[], violations=[])

    order_id = event.order_id
    contract_id = _resolve_contract_id(
        db,
        order_id=order_id,
        client_id=event.client_id,
        partner_id=event.partner_id,
        request_ctx=request_ctx,
    )
    if not contract_id:
        return OrderSlaEvaluationSummary(evaluations=[], violations=[])

    contract = db.query(Contract).filter(Contract.id == contract_id).one()
    obligations = (
        db.query(ContractObligation)
        .filter(ContractObligation.contract_id == contract_id)
        .all()
    )
    events = (
        db.query(MarketplaceOrderEvent)
        .filter(MarketplaceOrderEvent.order_id == order_id)
        .order_by(MarketplaceOrderEvent.occurred_at.asc())
        .all()
    )

    evaluations: list[OrderSlaEvaluation] = []
    violations: list[OrderSlaEvaluation] = []
    for obligation in obligations:
        metric = _normalize_metric(obligation.metric)
        if metric == "response_time":
            result = _evaluate_response_time(events)
        elif metric in {"completion_time", "delivery_time"}:
            result = _evaluate_completion_time(events)
        else:
            continue

        if not result:
            continue
        measured_value, period_start, period_end = result
        threshold = Decimal(str(obligation.threshold))
        try:
            ok = _compare(measured_value, threshold, obligation.comparison)
        except ValueError:
            ok = False
        status = OrderSlaStatus.OK if ok else OrderSlaStatus.VIOLATION
        breach_reason = None
        breach_severity = None
        if status == OrderSlaStatus.VIOLATION:
            breach_reason = f"{metric}_exceeded"
            breach_severity = _severity_for_violation(measured_value, threshold)

        audit = AuditService(db).audit(
            event_type="ORDER_SLA_EVALUATED",
            entity_type="order_sla_evaluation",
            entity_id=str(order_id),
            action="ORDER_SLA_EVALUATED",
            after={
                "order_id": order_id,
                "contract_id": contract_id,
                "obligation_id": str(obligation.id),
                "metric": metric,
                "measured_value": str(measured_value),
                "status": status.value,
            },
            request_ctx=request_ctx,
        )

        created_at = datetime.now(timezone.utc)
        evaluation = OrderSlaEvaluation(
            id=new_uuid_str(),
            order_id=order_id,
            contract_id=contract_id,
            obligation_id=obligation.id,
            period_start=period_start,
            period_end=period_end,
            measured_value=measured_value,
            status=status,
            breach_reason=breach_reason,
            breach_severity=breach_severity,
            created_at=created_at,
            audit_event_id=audit.id,
        )
        db.add(evaluation)
        evaluations.append(evaluation)

        record_decision_memory(
            db,
            case_id=None,
            decision_type="order_sla_evaluation",
            decision_ref_id=evaluation.id,
            decision_at=created_at,
            decided_by_user_id=request_ctx.actor_id if request_ctx else None,
            context_snapshot={
                "order_id": order_id,
                "contract_id": contract_id,
                "obligation_id": str(obligation.id),
                "metric": metric,
                "status": status.value,
                "measured_value": str(measured_value),
            },
            rationale=None if status == OrderSlaStatus.OK else f"SLA breach for order {order_id}",
            score_snapshot=None,
            mastery_snapshot=None,
            audit_event_id=str(audit.id),
        )

        if status == OrderSlaStatus.VIOLATION:
            breach_audit = AuditService(db).audit(
                event_type="SLA_BREACH_DETECTED",
                entity_type="order_sla_evaluation",
                entity_id=str(evaluation.id),
                action="SLA_BREACH_DETECTED",
                after={
                    "order_id": order_id,
                    "contract_id": contract_id,
                    "obligation_id": str(obligation.id),
                    "measured_value": str(measured_value),
                    "threshold": str(threshold),
                    "severity": breach_severity.value if breach_severity else None,
                },
                request_ctx=request_ctx,
            )
            record_decision_memory(
                db,
                case_id=None,
                decision_type="order_sla_violation",
                decision_ref_id=evaluation.id,
                decision_at=created_at,
                decided_by_user_id=request_ctx.actor_id if request_ctx else None,
                context_snapshot={
                    "order_id": order_id,
                    "contract_id": contract_id,
                    "obligation_id": str(obligation.id),
                    "metric": metric,
                    "measured_value": str(measured_value),
                    "threshold": str(threshold),
                },
                rationale=f"SLA breach: {metric} exceeded by order {order_id}",
                score_snapshot=None,
                mastery_snapshot=None,
                audit_event_id=str(breach_audit.id),
            )
            violations.append(evaluation)

    return OrderSlaEvaluationSummary(evaluations=evaluations, violations=violations)


__all__ = ["OrderSlaEvaluationSummary", "evaluate_order_event"]
