from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.cases import CaseEventType
from app.models.fuel import (
    FleetNotificationEventType,
    FleetNotificationPolicy,
    FuelLimitBreach,
    FuelLimitBreachScopeType,
    FuelLimitEscalation,
    FuelLimitEscalationAction,
    FuelLimitEscalationStatus,
    FuelCardStatus,
)
from app.security.rbac.principal import Principal
from app.services import fleet_service
from app.services.decision_memory.records import record_decision_memory
from app.services.fleet_metrics import metrics as fleet_metrics


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _system_principal() -> Principal:
    return Principal(
        user_id=None,
        roles={"admin"},
        scopes=set(),
        client_id=None,
        partner_id=None,
        is_admin=True,
        raw_claims={"subject_type": "system"},
    )


def _policy_matches_scope(policy: FleetNotificationPolicy, breach: FuelLimitBreach) -> bool:
    if policy.scope_type.value == "client":
        return True
    if policy.scope_type.value == "group" and breach.scope_type == FuelLimitBreachScopeType.GROUP:
        return str(policy.scope_id) == str(breach.scope_id)
    if policy.scope_type.value == "card" and breach.scope_type == FuelLimitBreachScopeType.CARD:
        return str(policy.scope_id) == str(breach.scope_id)
    return False


def _is_hard_breach(breach: FuelLimitBreach) -> bool:
    return breach.delta >= 0


def handle_limit_breaches(
    db: Session,
    *,
    breaches: Iterable[FuelLimitBreach],
    principal: Principal | None,
    request_id: str | None,
    trace_id: str | None,
) -> list[FuelLimitEscalation]:
    escalations: list[FuelLimitEscalation] = []
    db.flush()
    for breach in breaches:
        policies = (
            db.query(FleetNotificationPolicy)
            .filter(FleetNotificationPolicy.client_id == breach.client_id)
            .filter(FleetNotificationPolicy.event_type == FleetNotificationEventType.LIMIT_BREACH)
            .filter(FleetNotificationPolicy.active.is_(True))
            .all()
        )
        for policy in policies:
            if not _policy_matches_scope(policy, breach):
                continue
            action = policy.action_on_critical
            if not action or action == FuelLimitEscalationAction.NOTIFY_ONLY:
                continue
            if policy.hard_breach_only and not _is_hard_breach(breach):
                continue
            existing = (
                db.query(FuelLimitEscalation)
                .filter(FuelLimitEscalation.breach_id == breach.id)
                .filter(FuelLimitEscalation.action == action)
                .one_or_none()
            )
            if existing:
                escalations.append(existing)
                continue
            escalation = FuelLimitEscalation(
                client_id=breach.client_id,
                breach_id=breach.id,
                action=action,
                status=FuelLimitEscalationStatus.TRIGGERED,
            )
            db.add(escalation)
            db.flush()
            try:
                if action == FuelLimitEscalationAction.AUTO_BLOCK_CARD and breach.scope_type == FuelLimitBreachScopeType.CARD:
                    fleet_service.set_card_status(
                        db,
                        card_id=str(breach.scope_id),
                        status=FuelCardStatus.BLOCKED,
                        principal=_system_principal(),
                        request_id=request_id,
                        trace_id=trace_id,
                        reason="auto_block_due_to_limit_breach",
                    )
                    audit_event_id = fleet_service._emit_event(
                        db,
                        client_id=breach.client_id,
                        principal=principal,
                        request_id=request_id,
                        trace_id=trace_id,
                        event_type=CaseEventType.FUEL_CARD_AUTO_BLOCKED,
                        payload={
                            "breach_id": str(breach.id),
                            "card_id": str(breach.scope_id),
                        },
                    )
                    escalation.status = FuelLimitEscalationStatus.APPLIED
                    escalation.applied_at = _now()
                    escalation.audit_event_id = audit_event_id
                    record_decision_memory(
                        db,
                        case_id=None,
                        decision_type="auto_action",
                        decision_ref_id=str(breach.id),
                        decision_at=_now(),
                        decided_by_user_id=str(principal.user_id) if principal and principal.user_id else None,
                        context_snapshot={"action": action.value, "breach_id": str(breach.id)},
                        rationale="auto_block_due_to_limit_breach",
                        score_snapshot=None,
                        mastery_snapshot=None,
                        audit_event_id=audit_event_id,
                    )
                    fleet_metrics.mark_auto_action(action.value, "APPLIED")
                else:
                    escalation.status = FuelLimitEscalationStatus.FAILED
                    escalation.error = "unsupported_action"
                    fleet_metrics.mark_auto_action(action.value, "FAILED")
            except Exception as exc:  # pragma: no cover - defensive
                escalation.status = FuelLimitEscalationStatus.FAILED
                escalation.error = str(exc)[:500]
                fleet_metrics.mark_auto_action(action.value, "FAILED")
            escalations.append(escalation)
    return escalations


__all__ = ["handle_limit_breaches"]
