from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.cases import Case, CaseEventType, CaseKind, CasePriority
from app.models.fleet import FuelCardGroupMember
from app.models.fuel import (
    FleetActionBreachKind,
    FleetActionPolicy,
    FleetActionPolicyAction,
    FleetActionPolicyScopeType,
    FleetActionTriggerType,
    FleetNotificationEventType,
    FleetNotificationSeverity,
    FleetPolicyExecution,
    FleetPolicyExecutionStatus,
    FuelAnomaly,
    FuelCard,
    FuelCardStatus,
    FuelCardGroup,
    FuelLimitBreach,
    FuelLimitBreachScopeType,
    FuelLimitBreachType,
    FuelTransaction,
)
from app.security.rbac.principal import Principal
from app.services import fleet_service
from app.services.case_event_redaction import redact_deep
from app.services.case_events_service import CaseEventActor, emit_case_event
from app.services.cases_service import create_case
from app.services.decision_memory.records import record_decision_memory
from app.services.fleet_metrics import metrics as fleet_metrics
from app.services.fleet_notification_dispatcher import enqueue_notification


@dataclass(frozen=True)
class PolicyExecutionResult:
    policy_id: str
    status: FleetPolicyExecutionStatus
    execution_id: str | None


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


def _severity_rank(severity: FleetNotificationSeverity) -> int:
    return {
        FleetNotificationSeverity.LOW: 1,
        FleetNotificationSeverity.MEDIUM: 2,
        FleetNotificationSeverity.HIGH: 3,
        FleetNotificationSeverity.CRITICAL: 4,
    }[severity]


def _breach_kind(breach: FuelLimitBreach) -> FleetActionBreachKind:
    if breach.breach_type == FuelLimitBreachType.STATION:
        return FleetActionBreachKind.HARD
    if breach.breach_type == FuelLimitBreachType.CATEGORY and breach.delta < 0:
        return FleetActionBreachKind.SOFT
    return FleetActionBreachKind.HARD


def _resolve_group_ids(db: Session, *, card_id: str | None) -> list[str]:
    if not card_id:
        return []
    group_rows = (
        db.query(FuelCardGroupMember.group_id)
        .filter(FuelCardGroupMember.card_id == card_id)
        .filter(FuelCardGroupMember.removed_at.is_(None))
        .all()
    )
    return [str(row[0]) for row in group_rows]


def _select_policies(
    db: Session,
    *,
    client_id: str,
    trigger_type: FleetActionTriggerType,
    severity: FleetNotificationSeverity,
    breach_kind: FleetActionBreachKind | None,
    card_id: str | None,
    group_ids: list[str],
) -> list[FleetActionPolicy]:
    def _filter_policies(policies: Iterable[FleetActionPolicy]) -> list[FleetActionPolicy]:
        matched: list[FleetActionPolicy] = []
        for policy in policies:
            if _severity_rank(severity) < _severity_rank(policy.trigger_severity_min):
                continue
            if policy.breach_kind and breach_kind:
                if policy.breach_kind == FleetActionBreachKind.ANY:
                    pass
                elif policy.breach_kind != breach_kind:
                    continue
            matched.append(policy)
        return matched

    if card_id:
        card_policies = (
            db.query(FleetActionPolicy)
            .filter(FleetActionPolicy.client_id == client_id)
            .filter(FleetActionPolicy.trigger_type == trigger_type)
            .filter(FleetActionPolicy.active.is_(True))
            .filter(FleetActionPolicy.scope_type == FleetActionPolicyScopeType.CARD)
            .filter(FleetActionPolicy.scope_id == card_id)
            .all()
        )
        matched = _filter_policies(card_policies)
        if matched:
            return matched

    if group_ids:
        group_policies = (
            db.query(FleetActionPolicy)
            .filter(FleetActionPolicy.client_id == client_id)
            .filter(FleetActionPolicy.trigger_type == trigger_type)
            .filter(FleetActionPolicy.active.is_(True))
            .filter(FleetActionPolicy.scope_type == FleetActionPolicyScopeType.GROUP)
            .filter(FleetActionPolicy.scope_id.in_(group_ids))
            .all()
        )
        matched = _filter_policies(group_policies)
        if matched:
            return matched

    client_policies = (
        db.query(FleetActionPolicy)
        .filter(FleetActionPolicy.client_id == client_id)
        .filter(FleetActionPolicy.trigger_type == trigger_type)
        .filter(FleetActionPolicy.active.is_(True))
        .filter(FleetActionPolicy.scope_type == FleetActionPolicyScopeType.CLIENT)
        .all()
    )
    return _filter_policies(client_policies)


def _cooldown_active(db: Session, *, policy: FleetActionPolicy, now: datetime) -> bool:
    if not policy.cooldown_seconds:
        return False
    window_start = now - timedelta(seconds=policy.cooldown_seconds)
    recent = (
        db.query(FleetPolicyExecution)
        .filter(FleetPolicyExecution.policy_id == policy.id)
        .filter(FleetPolicyExecution.created_at >= window_start)
        .order_by(FleetPolicyExecution.created_at.desc())
        .first()
    )
    return recent is not None


def _dedupe_key(client_id: str, policy_id: str, event_id: str) -> str:
    return f"client:{client_id}:policy:{policy_id}:event:{event_id}"


def _write_execution(
    db: Session,
    *,
    policy: FleetActionPolicy,
    client_id: str,
    event_type: str,
    event_id: str,
    action: str,
    status: FleetPolicyExecutionStatus,
    reason: str | None,
    audit_event_id: str | None,
) -> FleetPolicyExecution:
    execution = FleetPolicyExecution(
        client_id=client_id,
        policy_id=policy.id,
        event_type=event_type,
        event_id=event_id,
        action=action,
        status=status,
        reason=reason,
        dedupe_key=_dedupe_key(client_id, str(policy.id), event_id),
        audit_event_id=audit_event_id,
    )
    db.add(execution)
    db.flush()
    return execution


def _emit_policy_audit_event(
    db: Session,
    *,
    client_id: str,
    event_type: CaseEventType,
    payload: dict[str, str | None],
) -> str:
    return fleet_service._emit_event(
        db,
        client_id=client_id,
        principal=_system_principal(),
        request_id=None,
        trace_id=None,
        event_type=event_type,
        payload=payload,
    )


def _notify_policy_action(
    db: Session,
    *,
    client_id: str,
    severity: FleetNotificationSeverity,
    event_ref_id: str,
    payload: dict[str, str | None],
) -> None:
    payload.setdefault("route", "/client/fleet/notifications/alerts")
    enqueue_notification(
        db,
        client_id=client_id,
        event_type=FleetNotificationEventType.POLICY_ACTION,
        severity=severity,
        event_ref_type="policy_action",
        event_ref_id=event_ref_id,
        payload=payload,
        principal=_system_principal(),
        request_id=None,
        trace_id=None,
    )


def _augment_policy_payload(
    db: Session,
    *,
    payload: dict[str, str | None],
    card_id: str | None,
    group_ids: list[str],
    breach_kind: FleetActionBreachKind | None,
) -> dict[str, str | None]:
    group_id = group_ids[0] if group_ids else None
    payload.setdefault("card_id", card_id)
    payload.setdefault("group_id", group_id)
    if card_id:
        payload.setdefault("alias", _resolve_card_alias(db, card_id))
        payload.setdefault("link_type", "card")
        payload.setdefault("link_id", card_id)
    if group_id:
        payload.setdefault("group_label", _resolve_group_name(db, group_id))
    if breach_kind:
        payload.setdefault("breach_kind", breach_kind.value)
    return payload


def _create_escalation_case(
    db: Session,
    *,
    client_id: str,
    tenant_id: int,
    title: str,
    description: dict[str, str | None],
    source_type: str,
    source_id: str,
) -> str:
    existing = (
        db.query(Case)
        .filter(Case.case_source_ref_type == source_type)
        .filter(Case.case_source_ref_id == source_id)
        .filter(Case.kind == CaseKind.FLEET)
        .one_or_none()
    )
    if existing:
        return str(existing.id)

    case = create_case(
        db,
        tenant_id=tenant_id,
        kind=CaseKind.FLEET,
        entity_id=client_id,
        kpi_key=None,
        window_days=None,
        title=title,
        priority=CasePriority.HIGH,
        note="Escalation created",
        explain=redact_deep(description, "", include_hash=True),
        diff=None,
        selected_actions=None,
        mastery_snapshot=None,
        created_by="system",
    )
    case.case_source_ref_type = source_type
    case.case_source_ref_id = source_id
    db.flush()

    event = emit_case_event(
        db,
        case_id=str(case.id),
        event_type=CaseEventType.FLEET_ESCALATION_CASE_CREATED,
        actor=CaseEventActor(id="system", email=None),
        request_id=None,
        trace_id=None,
        extra_payload=redact_deep(description, "", include_hash=True),
    )
    db.flush()
    record_decision_memory(
        db,
        case_id=str(case.id),
        decision_type="escalation",
        decision_ref_id=event.id,
        decision_at=_now(),
        decided_by_user_id=None,
        context_snapshot=redact_deep(description, "", include_hash=True),
        rationale="escalation_created",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=event.id,
    )
    return str(case.id)


def _create_failure_case(
    db: Session,
    *,
    client_id: str,
    tenant_id: int,
    title: str,
    description: dict[str, str | None],
    source_id: str,
) -> str:
    existing = (
        db.query(Case)
        .filter(Case.case_source_ref_type == "policy_action_failure")
        .filter(Case.case_source_ref_id == source_id)
        .filter(Case.kind == CaseKind.FLEET)
        .one_or_none()
    )
    if existing:
        return str(existing.id)
    case = create_case(
        db,
        tenant_id=tenant_id,
        kind=CaseKind.FLEET,
        entity_id=client_id,
        kpi_key=None,
        window_days=None,
        title=title,
        priority=CasePriority.HIGH,
        note="Policy action failed",
        explain=redact_deep(description, "", include_hash=True),
        diff=None,
        selected_actions=None,
        mastery_snapshot=None,
        created_by="system",
    )
    case.case_source_ref_type = "policy_action_failure"
    case.case_source_ref_id = source_id
    db.flush()
    return str(case.id)


def _auto_block_card(
    db: Session,
    *,
    card_id: str,
    client_id: str,
    breach_id: str,
) -> str:
    card = db.query(FuelCard).filter(FuelCard.id == card_id).one()
    if card.status == FuelCardStatus.BLOCKED:
        return str(card.id)
    fleet_service.set_card_status(
        db,
        card_id=card_id,
        status=FuelCardStatus.BLOCKED,
        principal=_system_principal(),
        request_id=None,
        trace_id=None,
        reason="auto_block_due_to_hard_limit_breach",
    )
    audit_event_id = fleet_service._emit_event(
        db,
        client_id=client_id,
        principal=_system_principal(),
        request_id=None,
        trace_id=None,
        event_type=CaseEventType.FUEL_CARD_AUTO_BLOCKED,
        payload={
            "breach_id": breach_id,
            "card_id": card_id,
        },
    )
    record_decision_memory(
        db,
        case_id=None,
        decision_type="auto_action",
        decision_ref_id=breach_id,
        decision_at=_now(),
        decided_by_user_id=None,
        context_snapshot={"action": "AUTO_BLOCK_CARD", "breach_id": breach_id, "card_id": card_id},
        rationale="Auto-block due to HARD limit breach",
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=audit_event_id,
    )
    return str(card.id)


def _resolve_group_name(db: Session, group_id: str | None) -> str | None:
    if not group_id:
        return None
    group = db.query(FuelCardGroup).filter(FuelCardGroup.id == group_id).one_or_none()
    return group.name if group else None


def _resolve_card_alias(db: Session, card_id: str | None) -> str | None:
    if not card_id:
        return None
    card = db.query(FuelCard.card_alias).filter(FuelCard.id == card_id).scalar()
    return str(card) if card else None


def _resolve_tenant_id(
    db: Session, *, client_id: str, card_id: str | None, group_ids: list[str]
) -> int:
    if card_id:
        tenant_id = db.query(FuelCard.tenant_id).filter(FuelCard.id == card_id).scalar()
        if tenant_id is not None:
            return int(tenant_id)
    if group_ids:
        tenant_id = db.query(FuelCardGroup.tenant_id).filter(FuelCardGroup.id == group_ids[0]).scalar()
        if tenant_id is not None:
            return int(tenant_id)
    fallback = db.query(FuelCard.tenant_id).filter(FuelCard.client_id == client_id).scalar()
    return int(fallback) if fallback is not None else 1


def _apply_policy_action(
    db: Session,
    *,
    policy: FleetActionPolicy,
    client_id: str,
    event_type: str,
    event_id: str,
    severity: FleetNotificationSeverity,
    breach_kind: FleetActionBreachKind | None,
    card_id: str | None,
    group_ids: list[str],
) -> FleetPolicyExecution:
    if policy.action == FleetActionPolicyAction.NONE:
        audit_event_id = _emit_policy_audit_event(
            db,
            client_id=client_id,
            event_type=CaseEventType.FLEET_POLICY_ACTION_APPLIED,
            payload={"policy_id": str(policy.id), "action": policy.action.value, "event_id": event_id},
        )
        return _write_execution(
            db,
            policy=policy,
            client_id=client_id,
            event_type=event_type,
            event_id=event_id,
            action=policy.action.value,
            status=FleetPolicyExecutionStatus.SKIPPED,
            reason="action_none",
            audit_event_id=audit_event_id,
        )

    if policy.action == FleetActionPolicyAction.NOTIFY_ONLY:
        payload = {
            "event_type": event_type,
            "event_id": event_id,
            "policy_id": str(policy.id),
            "action": policy.action.value,
            "severity": severity.value,
        }
        _notify_policy_action(
            db,
            client_id=client_id,
            severity=severity,
            event_ref_id=event_id,
            payload=_augment_policy_payload(
                db,
                payload=payload,
                card_id=card_id,
                group_ids=group_ids,
                breach_kind=breach_kind,
            ),
        )
        audit_event_id = _emit_policy_audit_event(
            db,
            client_id=client_id,
            event_type=CaseEventType.FLEET_POLICY_ACTION_APPLIED,
            payload=payload,
        )
        fleet_metrics.mark_policy_action(policy.action.value, "APPLIED")
        return _write_execution(
            db,
            policy=policy,
            client_id=client_id,
            event_type=event_type,
            event_id=event_id,
            action=policy.action.value,
            status=FleetPolicyExecutionStatus.APPLIED,
            reason=None,
            audit_event_id=audit_event_id,
        )

    if policy.action == FleetActionPolicyAction.AUTO_BLOCK_CARD:
        if breach_kind != FleetActionBreachKind.HARD:
            audit_event_id = _emit_policy_audit_event(
                db,
                client_id=client_id,
                event_type=CaseEventType.FLEET_POLICY_ACTION_APPLIED,
                payload={"policy_id": str(policy.id), "action": policy.action.value, "event_id": event_id},
            )
            return _write_execution(
                db,
                policy=policy,
                client_id=client_id,
                event_type=event_type,
                event_id=event_id,
                action=policy.action.value,
                status=FleetPolicyExecutionStatus.SKIPPED,
                reason="hard_breach_required",
                audit_event_id=audit_event_id,
            )
        if not card_id:
            audit_event_id = _emit_policy_audit_event(
                db,
                client_id=client_id,
                event_type=CaseEventType.FLEET_POLICY_ACTION_FAILED,
                payload={"policy_id": str(policy.id), "action": policy.action.value, "event_id": event_id},
            )
            tenant_id = _resolve_tenant_id(db, client_id=client_id, card_id=None, group_ids=group_ids)
            _create_failure_case(
                db,
                client_id=client_id,
                tenant_id=tenant_id,
                title="Fleet policy action failed: missing card",
                description={
                    "event_type": event_type,
                    "event_id": event_id,
                    "policy_id": str(policy.id),
                    "reason": "missing_card_id",
                },
                source_id=event_id,
            )
            _notify_policy_action(
                db,
                client_id=client_id,
                severity=severity,
                event_ref_id=event_id,
                payload=_augment_policy_payload(
                    db,
                    payload={
                        "event_type": event_type,
                        "event_id": event_id,
                        "policy_id": str(policy.id),
                        "action": policy.action.value,
                        "status": "FAILED",
                        "reason": "missing_card_id",
                    },
                    card_id=card_id,
                    group_ids=group_ids,
                    breach_kind=breach_kind,
                ),
            )
            fleet_metrics.mark_policy_action(policy.action.value, "FAILED")
            return _write_execution(
                db,
                policy=policy,
                client_id=client_id,
                event_type=event_type,
                event_id=event_id,
                action=policy.action.value,
                status=FleetPolicyExecutionStatus.FAILED,
                reason="missing_card_id",
                audit_event_id=audit_event_id,
            )
        card = db.query(FuelCard).filter(FuelCard.id == card_id).one()
        if card.status == FuelCardStatus.BLOCKED:
            audit_event_id = _emit_policy_audit_event(
                db,
                client_id=client_id,
                event_type=CaseEventType.FLEET_POLICY_ACTION_APPLIED,
                payload={"policy_id": str(policy.id), "action": policy.action.value, "event_id": event_id},
            )
            return _write_execution(
                db,
                policy=policy,
                client_id=client_id,
                event_type=event_type,
                event_id=event_id,
                action=policy.action.value,
                status=FleetPolicyExecutionStatus.SKIPPED,
                reason="card_already_blocked",
                audit_event_id=audit_event_id,
            )
        try:
            _auto_block_card(db, card_id=card_id, client_id=client_id, breach_id=event_id)
            audit_event_id = _emit_policy_audit_event(
                db,
                client_id=client_id,
                event_type=CaseEventType.FLEET_POLICY_ACTION_APPLIED,
                payload={"policy_id": str(policy.id), "action": policy.action.value, "event_id": event_id},
            )
            _notify_policy_action(
                db,
                client_id=client_id,
                severity=severity,
                event_ref_id=event_id,
                payload=_augment_policy_payload(
                    db,
                    payload={
                        "event_type": event_type,
                        "event_id": event_id,
                        "policy_id": str(policy.id),
                        "action": policy.action.value,
                        "status": "APPLIED",
                        "status_after": FuelCardStatus.BLOCKED.value,
                    },
                    card_id=card_id,
                    group_ids=group_ids,
                    breach_kind=breach_kind,
                ),
            )
            fleet_metrics.mark_auto_block("APPLIED")
            fleet_metrics.mark_policy_action(policy.action.value, "APPLIED")
            return _write_execution(
                db,
                policy=policy,
                client_id=client_id,
                event_type=event_type,
                event_id=event_id,
                action=policy.action.value,
                status=FleetPolicyExecutionStatus.APPLIED,
                reason=None,
                audit_event_id=audit_event_id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            audit_event_id = _emit_policy_audit_event(
                db,
                client_id=client_id,
                event_type=CaseEventType.FLEET_POLICY_ACTION_FAILED,
                payload={
                    "policy_id": str(policy.id),
                    "action": policy.action.value,
                    "event_id": event_id,
                    "error": str(exc)[:200],
                },
            )
            tenant_id = _resolve_tenant_id(db, client_id=client_id, card_id=card_id, group_ids=group_ids)
            _create_failure_case(
                db,
                client_id=client_id,
                tenant_id=tenant_id,
                title="Fleet policy action failed: auto-block",
                description={
                    "event_type": event_type,
                    "event_id": event_id,
                    "policy_id": str(policy.id),
                    "reason": str(exc)[:200],
                },
                source_id=event_id,
            )
            _notify_policy_action(
                db,
                client_id=client_id,
                severity=severity,
                event_ref_id=event_id,
                payload=_augment_policy_payload(
                    db,
                    payload={
                        "event_type": event_type,
                        "event_id": event_id,
                        "policy_id": str(policy.id),
                        "action": policy.action.value,
                        "status": "FAILED",
                        "reason": str(exc)[:200],
                    },
                    card_id=card_id,
                    group_ids=group_ids,
                    breach_kind=breach_kind,
                ),
            )
            fleet_metrics.mark_auto_block("FAILED")
            fleet_metrics.mark_policy_action(policy.action.value, "FAILED")
            return _write_execution(
                db,
                policy=policy,
                client_id=client_id,
                event_type=event_type,
                event_id=event_id,
                action=policy.action.value,
                status=FleetPolicyExecutionStatus.FAILED,
                reason=str(exc)[:200],
                audit_event_id=audit_event_id,
            )

    if policy.action == FleetActionPolicyAction.ESCALATE_CASE:
        group_id = group_ids[0] if group_ids else None
        card_alias = _resolve_card_alias(db, card_id)
        group_name = _resolve_group_name(db, group_id)
        title = "Fleet escalation"
        if card_alias:
            title = f"Fleet escalation: {event_type} on card {card_alias}"
        description = {
            "event_type": event_type,
            "event_id": event_id,
            "card_id": card_id,
            "card_alias": card_alias,
            "group_id": group_id,
            "group_name": group_name,
            "policy_id": str(policy.id),
        }
        try:
            resolved_tenant_id = _resolve_tenant_id(db, client_id=client_id, card_id=card_id, group_ids=group_ids)
            _create_escalation_case(
                db,
                client_id=client_id,
                tenant_id=resolved_tenant_id,
                title=title,
                description=description,
                source_type=event_type,
                source_id=event_id,
            )
            audit_event_id = _emit_policy_audit_event(
                db,
                client_id=client_id,
                event_type=CaseEventType.FLEET_POLICY_ACTION_APPLIED,
                payload={"policy_id": str(policy.id), "action": policy.action.value, "event_id": event_id},
            )
            _notify_policy_action(
                db,
                client_id=client_id,
                severity=severity,
                event_ref_id=event_id,
                payload=_augment_policy_payload(
                    db,
                    payload={
                        "event_type": event_type,
                        "event_id": event_id,
                        "policy_id": str(policy.id),
                        "action": policy.action.value,
                        "status": "APPLIED",
                    },
                    card_id=card_id,
                    group_ids=group_ids,
                    breach_kind=breach_kind,
                ),
            )
            fleet_metrics.mark_escalation("APPLIED")
            fleet_metrics.mark_policy_action(policy.action.value, "APPLIED")
            return _write_execution(
                db,
                policy=policy,
                client_id=client_id,
                event_type=event_type,
                event_id=event_id,
                action=policy.action.value,
                status=FleetPolicyExecutionStatus.APPLIED,
                reason=None,
                audit_event_id=audit_event_id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            audit_event_id = _emit_policy_audit_event(
                db,
                client_id=client_id,
                event_type=CaseEventType.FLEET_POLICY_ACTION_FAILED,
                payload={
                    "policy_id": str(policy.id),
                    "action": policy.action.value,
                    "event_id": event_id,
                    "error": str(exc)[:200],
                },
            )
            resolved_tenant_id = _resolve_tenant_id(db, client_id=client_id, card_id=card_id, group_ids=group_ids)
            _create_failure_case(
                db,
                client_id=client_id,
                tenant_id=resolved_tenant_id,
                title="Fleet policy action failed: escalation",
                description={
                    "event_type": event_type,
                    "event_id": event_id,
                    "policy_id": str(policy.id),
                    "reason": str(exc)[:200],
                },
                source_id=event_id,
            )
            _notify_policy_action(
                db,
                client_id=client_id,
                severity=severity,
                event_ref_id=event_id,
                payload=_augment_policy_payload(
                    db,
                    payload={
                        "event_type": event_type,
                        "event_id": event_id,
                        "policy_id": str(policy.id),
                        "action": policy.action.value,
                        "status": "FAILED",
                        "reason": str(exc)[:200],
                    },
                    card_id=card_id,
                    group_ids=group_ids,
                    breach_kind=breach_kind,
                ),
            )
            fleet_metrics.mark_escalation("FAILED")
            fleet_metrics.mark_policy_action(policy.action.value, "FAILED")
            return _write_execution(
                db,
                policy=policy,
                client_id=client_id,
                event_type=event_type,
                event_id=event_id,
                action=policy.action.value,
                status=FleetPolicyExecutionStatus.FAILED,
                reason=str(exc)[:200],
                audit_event_id=audit_event_id,
            )

    audit_event_id = _emit_policy_audit_event(
        db,
        client_id=client_id,
        event_type=CaseEventType.FLEET_POLICY_ACTION_FAILED,
        payload={"policy_id": str(policy.id), "action": policy.action.value, "event_id": event_id},
    )
    resolved_tenant_id = _resolve_tenant_id(db, client_id=client_id, card_id=card_id, group_ids=group_ids)
    _create_failure_case(
        db,
        client_id=client_id,
        tenant_id=resolved_tenant_id,
        title="Fleet policy action failed",
        description={
            "event_type": event_type,
            "event_id": event_id,
            "policy_id": str(policy.id),
            "reason": "unsupported_action",
        },
        source_id=event_id,
    )
    _notify_policy_action(
        db,
        client_id=client_id,
        severity=severity,
        event_ref_id=event_id,
        payload=_augment_policy_payload(
            db,
            payload={
                "event_type": event_type,
                "event_id": event_id,
                "policy_id": str(policy.id),
                "action": policy.action.value,
                "status": "FAILED",
                "reason": "unsupported_action",
            },
            card_id=card_id,
            group_ids=group_ids,
            breach_kind=breach_kind,
        ),
    )
    fleet_metrics.mark_policy_action(policy.action.value, "FAILED")
    return _write_execution(
        db,
        policy=policy,
        client_id=client_id,
        event_type=event_type,
        event_id=event_id,
        action=policy.action.value,
        status=FleetPolicyExecutionStatus.FAILED,
        reason="unsupported_action",
        audit_event_id=audit_event_id,
    )


def evaluate_policies_for_breach(db: Session, breach_id: str) -> list[PolicyExecutionResult]:
    breach = db.query(FuelLimitBreach).filter(FuelLimitBreach.id == breach_id).one_or_none()
    if not breach:
        return []
    severity = fleet_service._breach_severity(breach)
    breach_kind = _breach_kind(breach)
    card_id: str | None = None
    group_ids: list[str] = []
    if breach.scope_type == FuelLimitBreachScopeType.CARD:
        card_id = str(breach.scope_id)
    elif breach.scope_type == FuelLimitBreachScopeType.GROUP:
        group_ids.append(str(breach.scope_id))
    if breach.tx_id:
        tx = db.query(FuelTransaction).filter(FuelTransaction.id == breach.tx_id).one_or_none()
        if tx and tx.card_id:
            card_id = card_id or str(tx.card_id)
    if card_id:
        group_ids = group_ids or _resolve_group_ids(db, card_id=card_id)

    policies = _select_policies(
        db,
        client_id=breach.client_id,
        trigger_type=FleetActionTriggerType.LIMIT_BREACH,
        severity=severity,
        breach_kind=breach_kind,
        card_id=card_id,
        group_ids=group_ids,
    )
    results: list[PolicyExecutionResult] = []
    for policy in policies:
        dedupe_key = _dedupe_key(breach.client_id, str(policy.id), str(breach.id))
        existing = (
            db.query(FleetPolicyExecution)
            .filter(FleetPolicyExecution.dedupe_key == dedupe_key)
            .one_or_none()
        )
        if existing:
            results.append(
                PolicyExecutionResult(
                    policy_id=str(policy.id),
                    status=existing.status,
                    execution_id=str(existing.id),
                )
            )
            continue
        now = _now()
        if _cooldown_active(db, policy=policy, now=now):
            audit_event_id = _emit_policy_audit_event(
                db,
                client_id=breach.client_id,
                event_type=CaseEventType.FLEET_POLICY_ACTION_APPLIED,
                payload={"policy_id": str(policy.id), "action": policy.action.value, "event_id": str(breach.id)},
            )
            execution = _write_execution(
                db,
                policy=policy,
                client_id=breach.client_id,
                event_type="limit_breach",
                event_id=str(breach.id),
                action=policy.action.value,
                status=FleetPolicyExecutionStatus.SKIPPED,
                reason="cooldown_active",
                audit_event_id=audit_event_id,
            )
            results.append(
                PolicyExecutionResult(
                    policy_id=str(policy.id),
                    status=execution.status,
                    execution_id=str(execution.id),
                )
            )
            continue
        started_at = _now()
        execution = _apply_policy_action(
            db,
            policy=policy,
            client_id=breach.client_id,
            event_type="limit_breach",
            event_id=str(breach.id),
            severity=severity,
            breach_kind=breach_kind,
            card_id=card_id,
            group_ids=group_ids,
        )
        fleet_metrics.observe_policy_execution_latency((_now() - started_at).total_seconds())
        results.append(
            PolicyExecutionResult(
                policy_id=str(policy.id),
                status=execution.status,
                execution_id=str(execution.id),
            )
        )
    return results


def evaluate_policies_for_anomaly(db: Session, anomaly_id: str) -> list[PolicyExecutionResult]:
    anomaly = db.query(FuelAnomaly).filter(FuelAnomaly.id == anomaly_id).one_or_none()
    if not anomaly:
        return []
    card_id = str(anomaly.card_id) if anomaly.card_id else None
    group_ids: list[str] = []
    if anomaly.group_id:
        group_ids.append(str(anomaly.group_id))
    if card_id and not group_ids:
        group_ids = _resolve_group_ids(db, card_id=card_id)

    policies = _select_policies(
        db,
        client_id=anomaly.client_id,
        trigger_type=FleetActionTriggerType.ANOMALY,
        severity=anomaly.severity,
        breach_kind=None,
        card_id=card_id,
        group_ids=group_ids,
    )
    results: list[PolicyExecutionResult] = []
    for policy in policies:
        dedupe_key = _dedupe_key(anomaly.client_id, str(policy.id), str(anomaly.id))
        existing = (
            db.query(FleetPolicyExecution)
            .filter(FleetPolicyExecution.dedupe_key == dedupe_key)
            .one_or_none()
        )
        if existing:
            results.append(
                PolicyExecutionResult(
                    policy_id=str(policy.id),
                    status=existing.status,
                    execution_id=str(existing.id),
                )
            )
            continue
        now = _now()
        if _cooldown_active(db, policy=policy, now=now):
            audit_event_id = _emit_policy_audit_event(
                db,
                client_id=anomaly.client_id,
                event_type=CaseEventType.FLEET_POLICY_ACTION_APPLIED,
                payload={"policy_id": str(policy.id), "action": policy.action.value, "event_id": str(anomaly.id)},
            )
            execution = _write_execution(
                db,
                policy=policy,
                client_id=anomaly.client_id,
                event_type="anomaly",
                event_id=str(anomaly.id),
                action=policy.action.value,
                status=FleetPolicyExecutionStatus.SKIPPED,
                reason="cooldown_active",
                audit_event_id=audit_event_id,
            )
            results.append(
                PolicyExecutionResult(
                    policy_id=str(policy.id),
                    status=execution.status,
                    execution_id=str(execution.id),
                )
            )
            continue
        started_at = _now()
        execution = _apply_policy_action(
            db,
            policy=policy,
            client_id=anomaly.client_id,
            event_type="anomaly",
            event_id=str(anomaly.id),
            severity=anomaly.severity,
            breach_kind=None,
            card_id=card_id,
            group_ids=group_ids,
        )
        fleet_metrics.observe_policy_execution_latency((_now() - started_at).total_seconds())
        results.append(
            PolicyExecutionResult(
                policy_id=str(policy.id),
                status=execution.status,
                execution_id=str(execution.id),
            )
        )
    return results


__all__ = ["evaluate_policies_for_anomaly", "evaluate_policies_for_breach", "PolicyExecutionResult"]
